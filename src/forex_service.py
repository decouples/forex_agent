"""
外汇数据服务（异步版）
=====================
多数据源自动降级：任一源失败立刻切换下一源，调用方无感知。
全部使用 httpx.AsyncClient，配合 asyncio 事件循环运行。

实时接口优先级：Fawazahmed0 > ExchangeRate-API > FloatRates > Frankfurter
历史接口优先级：Fawazahmed0 (≤31天) > ECB SDW > Frankfurter
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta

import httpx

from src.config import settings
from src.logging_utils import get_logger

logger = get_logger(__name__)

_shared_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def _get_shared_client() -> httpx.AsyncClient:
    """进程级单例 AsyncClient，所有 ForexService 实例共享连接池。"""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        return _shared_client
    async with _client_lock:
        if _shared_client is not None and not _shared_client.is_closed:
            return _shared_client
        pool_limits = httpx.Limits(
            max_connections=50,
            max_keepalive_connections=20,
            keepalive_expiry=30,
        )
        transport = httpx.AsyncHTTPTransport(
            retries=0,
            limits=pool_limits,
        )
        _shared_client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(
                connect=min(settings.FOREX_API_CONNECT_TIMEOUT, 5.0),
                read=min(settings.FOREX_API_READ_TIMEOUT, 10.0),
                write=10.0,
                pool=10.0,
            ),
            headers={
                "User-Agent": settings.FOREX_API_USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
            http2=True,
        )
        return _shared_client


_CIRCUIT_BREAKER_THRESHOLD = 3
_CIRCUIT_BREAKER_COOLDOWN = 300.0
_provider_failures: dict[str, int] = {}
_provider_cooldown_until: dict[str, float] = {}


def _circuit_open(provider: str) -> bool:
    """熔断检查：连续失败 N 次后暂停使用该 provider 一段时间。"""
    import time
    until = _provider_cooldown_until.get(provider, 0)
    if until and time.monotonic() < until:
        return True
    if until and time.monotonic() >= until:
        _provider_failures[provider] = 0
        _provider_cooldown_until[provider] = 0
    return False


def _record_failure(provider: str) -> None:
    import time
    _provider_failures[provider] = _provider_failures.get(provider, 0) + 1
    if _provider_failures[provider] >= _CIRCUIT_BREAKER_THRESHOLD:
        _provider_cooldown_until[provider] = time.monotonic() + _CIRCUIT_BREAKER_COOLDOWN
        logger.warning(
            "circuit_breaker_open | provider=%s | failures=%d | cooldown=%.0fs",
            provider, _provider_failures[provider], _CIRCUIT_BREAKER_COOLDOWN,
        )


def _record_success(provider: str) -> None:
    _provider_failures[provider] = 0
    _provider_cooldown_until[provider] = 0


class ForexService:
    """外汇数据服务类（异步 httpx，多供应商自动降级 + 熔断）。"""

    def __init__(self) -> None:
        self.provider_priority = [
            p.strip().lower()
            for p in settings.FOREX_PROVIDER_PRIORITY.split(",")
            if p.strip()
        ] or ["fawazahmed", "exchangerate_api", "floatrates", "frankfurter"]

        self.history_provider_priority = [
            p.strip().lower()
            for p in settings.FOREX_HISTORY_PROVIDER_PRIORITY.split(",")
            if p.strip()
        ] or ["fawazahmed", "ecb", "frankfurter"]

    async def _get_json(self, url: str, params: dict | None = None, extra_headers: dict | None = None) -> dict | list:
        client = await _get_shared_client()
        resp = await client.get(url, params=params, headers=extra_headers or {})
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _norm_pair(base: str, target: str) -> tuple[str, str]:
        return base.upper(), target.upper()

    # ================================================================
    #  实时查询 —— 各 provider 实现
    # ================================================================

    async def _realtime_fawazahmed(self, base: str, target: str) -> dict[str, float | str]:
        url = f"{settings.FOREX_FAWAZAHMED_BASE_URL.rstrip('/')}/currencies/{base.lower()}.json"
        data = await self._get_json(url)
        rate = data.get(base.lower(), {}).get(target.lower())
        if rate is None:
            raise ValueError(f"fawazahmed: 未找到 {base}->{target}")
        return {"rate": float(rate), "date": str(data.get("date", date.today().isoformat()))}

    async def _realtime_exchangerate_api(self, base: str, target: str) -> dict[str, float | str]:
        url = f"{settings.FOREX_EXCHANGERATE_API_BASE_URL.rstrip('/')}/latest/{base}"
        data = await self._get_json(url)
        rate = data.get("rates", {}).get(target)
        if rate is None:
            raise ValueError(f"exchangerate_api: 未找到 {base}->{target}")
        ts = str(data.get("time_last_update_utc", ""))
        return {"rate": float(rate), "date": ts[:16] if ts else date.today().isoformat()}

    async def _realtime_floatrates(self, base: str, target: str) -> dict[str, float | str]:
        url = f"{settings.FOREX_FLOATRATES_BASE_URL.rstrip('/')}/daily/{base.lower()}.json"
        data = await self._get_json(url)
        item = data.get(target.lower())
        if not item:
            raise ValueError(f"floatrates: 未找到 {base}->{target}")
        return {"rate": float(item["rate"]), "date": str(item.get("date", ""))[:16] or date.today().isoformat()}

    async def _realtime_frankfurter(self, base: str, target: str) -> dict[str, float | str]:
        url = f"{settings.FOREX_API_BASE_URL.rstrip('/')}/latest"
        data = await self._get_json(url, params={"from": base, "to": target})
        rate = data.get("rates", {}).get(target)
        if rate is None:
            raise ValueError(f"frankfurter: 未找到 {base}->{target}")
        return {"rate": float(rate), "date": str(data.get("date", ""))}

    # ================================================================
    #  历史查询 —— 各 provider 实现
    # ================================================================

    async def _history_fawazahmed(
        self, base: str, target: str, start_date: date, end_date: date,
    ) -> list[dict[str, float | str]]:
        """Fawazahmed0 按日期版本逐天查询（CDN 缓存，速度快）。"""
        base_l, target_l = base.lower(), target.lower()

        async def _fetch_one(current: date) -> dict[str, float | str] | None:
            version_url = (
                f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api"
                f"@{current.isoformat()}/v1/currencies/{base_l}.json"
            )
            try:
                data = await self._get_json(version_url)
                rate = data.get(base_l, {}).get(target_l)
                if rate is not None:
                    return {"date": current.isoformat(), "rate": float(rate)}
            except Exception:
                pass
            return None

        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)

        results = await asyncio.gather(*[_fetch_one(d) for d in dates])
        records = [r for r in results if r is not None]
        if not records:
            raise ValueError(f"fawazahmed: 历史数据为空 {base}->{target}")
        return sorted(records, key=lambda x: x["date"])

    async def _history_ecb(
        self, base: str, target: str, start_date: date, end_date: date,
    ) -> list[dict[str, float | str]]:
        """ECB SDW 官方数据 API（欧洲中央银行统计数据仓库）。"""
        async def _fetch_ecb_series(currency: str, s: date, e: date) -> dict[str, float]:
            url = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
            params = {
                "startPeriod": s.isoformat(),
                "endPeriod": e.isoformat(),
                "format": "jsondata",
            }
            data = await self._get_json(url, params=params)
            observations = (
                data.get("dataSets", [{}])[0]
                .get("series", {})
                .get("0:0:0:0:0", {})
                .get("observations", {})
            )
            time_periods = (
                data.get("structure", {})
                .get("dimensions", {})
                .get("observation", [{}])[0]
                .get("values", [])
            )
            result: dict[str, float] = {}
            for idx_str, obs_val in observations.items():
                idx = int(idx_str)
                if idx < len(time_periods) and obs_val:
                    dt = time_periods[idx].get("id", "")
                    val = obs_val[0] if isinstance(obs_val, list) else obs_val
                    if dt and val is not None:
                        result[dt] = float(val)
            return result

        if base == "EUR":
            target_series = await _fetch_ecb_series(target, start_date, end_date)
            records = [
                {"date": d, "rate": 1.0 / v}
                for d, v in sorted(target_series.items()) if v != 0
            ]
        elif target == "EUR":
            base_series = await _fetch_ecb_series(base, start_date, end_date)
            records = [
                {"date": d, "rate": v}
                for d, v in sorted(base_series.items())
            ]
        else:
            base_series, target_series = await asyncio.gather(
                _fetch_ecb_series(base, start_date, end_date),
                _fetch_ecb_series(target, start_date, end_date),
            )
            common_dates = sorted(set(base_series.keys()) & set(target_series.keys()))
            records = []
            for d in common_dates:
                bv, tv = base_series[d], target_series[d]
                if bv != 0:
                    records.append({"date": d, "rate": round(tv / bv, 8)})

        if not records:
            raise ValueError(f"ecb: 历史数据为空 {base}->{target}")
        return records

    async def _history_frankfurter(
        self, base: str, target: str, start_date: date, end_date: date,
    ) -> list[dict[str, float | str]]:
        """Frankfurter 区间查询。"""
        url = f"{settings.FOREX_API_BASE_URL.rstrip('/')}/{start_date.isoformat()}..{end_date.isoformat()}"
        data = await self._get_json(url, params={"from": base, "to": target})
        rates_by_date: dict[str, dict[str, float]] = data.get("rates", {})
        records: list[dict[str, float | str]] = []
        for d in sorted(rates_by_date.keys()):
            target_rate = rates_by_date[d].get(target)
            if target_rate is not None:
                records.append({"date": d, "rate": float(target_rate)})
        if not records:
            raise ValueError(f"frankfurter: 历史数据为空 {base}->{target}")
        return records

    # ================================================================
    #  公共接口
    # ================================================================

    async def get_realtime_quote(self, base_currency: str, target_currency: str) -> dict[str, float | str]:
        """获取实时汇率及日期（自动降级切换数据源，单 provider 超时快速降级）。"""
        base, target = self._norm_pair(base_currency, target_currency)
        errors: list[str] = []
        per_provider_timeout = 8.0
        provider_map = {
            "fawazahmed": self._realtime_fawazahmed,
            "exchangerate_api": self._realtime_exchangerate_api,
            "floatrates": self._realtime_floatrates,
            "frankfurter": self._realtime_frankfurter,
        }
        for provider in self.provider_priority:
            fn = provider_map.get(provider)
            if fn is None:
                continue
            if _circuit_open(provider):
                errors.append(f"{provider}: circuit_breaker_open")
                continue
            try:
                result = await asyncio.wait_for(fn(base, target), timeout=per_provider_timeout)
                _record_success(provider)
                logger.info(
                    "forex_realtime_success | provider=%s | base=%s | target=%s | rate=%.6f | date=%s",
                    provider, base, target, float(result["rate"]), result["date"],
                )
                return result
            except asyncio.TimeoutError:
                _record_failure(provider)
                logger.warning(
                    "forex_realtime_timeout | provider=%s | base=%s | target=%s | limit=%.1fs",
                    provider, base, target, per_provider_timeout,
                )
                errors.append(f"{provider}: timeout>{per_provider_timeout}s")
            except Exception as exc:
                _record_failure(provider)
                logger.warning(
                    "forex_realtime_failed | provider=%s | base=%s | target=%s | err=%s",
                    provider, base, target, str(exc),
                )
                errors.append(f"{provider}: {exc}")
        raise RuntimeError(
            f"全部实时数据源均失败（{base}->{target}）：{' | '.join(errors)}"
        )

    async def get_realtime_rate(self, base_currency: str, target_currency: str) -> float:
        return float((await self.get_realtime_quote(base_currency, target_currency))["rate"])

    async def get_history_rates(
        self,
        base_currency: str,
        target_currency: str,
        days: int,
    ) -> list[dict[str, float | str]]:
        """获取指定天数历史汇率（自动降级切换数据源）。"""
        base, target = self._norm_pair(base_currency, target_currency)
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        errors: list[str] = []

        history_map = {
            "fawazahmed": self._history_fawazahmed,
            "ecb": self._history_ecb,
            "frankfurter": self._history_frankfurter,
        }

        history_timeout = max(settings.FOREX_API_READ_TIMEOUT * 3, 60.0)
        for provider in self.history_provider_priority:
            fn = history_map.get(provider)
            if fn is None:
                continue
            if _circuit_open(provider):
                errors.append(f"{provider}: circuit_breaker_open")
                continue
            if provider == "fawazahmed" and days > 31:
                logger.info("forex_history_skip | provider=%s | reason=range_too_large | days=%s", provider, days)
                errors.append(f"{provider}: 区间>{31}天不适合逐天查询")
                continue
            try:
                records = await asyncio.wait_for(
                    fn(base, target, start_date, end_date),
                    timeout=history_timeout,
                )
                _record_success(provider)
                logger.info(
                    "forex_history_success | provider=%s | base=%s | target=%s | points=%s | start=%s | end=%s",
                    provider, base, target, len(records), records[0]["date"], records[-1]["date"],
                )
                return records
            except asyncio.TimeoutError:
                _record_failure(provider)
                logger.warning(
                    "forex_history_timeout | provider=%s | base=%s | target=%s | days=%s | limit=%.1fs",
                    provider, base, target, days, history_timeout,
                )
                errors.append(f"{provider}: timeout>{history_timeout}s")
            except Exception as exc:
                _record_failure(provider)
                logger.warning(
                    "forex_history_failed | provider=%s | base=%s | target=%s | days=%s | err=%s",
                    provider, base, target, days, str(exc),
                )
                errors.append(f"{provider}: {exc}")

        raise RuntimeError(
            f"全部历史数据源均失败（{base}->{target}, days={days}）：{' | '.join(errors)}"
        )

    async def aclose(self) -> None:
        global _shared_client
        if _shared_client and not _shared_client.is_closed:
            await _shared_client.aclose()
            _shared_client = None
