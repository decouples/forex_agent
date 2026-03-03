"""
外汇数据服务
============
多数据源自动降级：任一源失败立刻切换下一源，调用方无感知。

实时接口优先级：Fawazahmed0 > ExchangeRate-API > FloatRates > Frankfurter
历史接口优先级：Fawazahmed0 (≤31天) > ECB SDW > Frankfurter
"""
from __future__ import annotations

from datetime import date, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import settings
from src.logging_utils import get_logger

logger = get_logger(__name__)


class ForexService:
    """外汇数据服务类（多供应商自动降级）。"""

    def __init__(self) -> None:
        self.timeout = (settings.FOREX_API_CONNECT_TIMEOUT, settings.FOREX_API_READ_TIMEOUT)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.FOREX_API_USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
            }
        )
        retry = Retry(
            total=settings.FOREX_API_RETRIES,
            read=settings.FOREX_API_RETRIES,
            connect=settings.FOREX_API_RETRIES,
            backoff_factor=settings.FOREX_API_RETRY_BACKOFF,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

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

    def _get_json(self, url: str, params: dict | None = None, extra_headers: dict | None = None) -> dict | list:
        resp = self.session.get(
            url,
            params=params,
            timeout=self.timeout,
            headers=extra_headers or {},
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _norm_pair(base: str, target: str) -> tuple[str, str]:
        return base.upper(), target.upper()

    # ================================================================
    #  实时查询 —— 各 provider 实现
    # ================================================================

    def _realtime_fawazahmed(self, base: str, target: str) -> dict[str, float | str]:
        url = f"{settings.FOREX_FAWAZAHMED_BASE_URL.rstrip('/')}/currencies/{base.lower()}.json"
        data = self._get_json(url)
        rate = data.get(base.lower(), {}).get(target.lower())
        if rate is None:
            raise ValueError(f"fawazahmed: 未找到 {base}->{target}")
        return {"rate": float(rate), "date": str(data.get("date", date.today().isoformat()))}

    def _realtime_exchangerate_api(self, base: str, target: str) -> dict[str, float | str]:
        url = f"{settings.FOREX_EXCHANGERATE_API_BASE_URL.rstrip('/')}/latest/{base}"
        data = self._get_json(url)
        rate = data.get("rates", {}).get(target)
        if rate is None:
            raise ValueError(f"exchangerate_api: 未找到 {base}->{target}")
        ts = str(data.get("time_last_update_utc", ""))
        return {"rate": float(rate), "date": ts[:16] if ts else date.today().isoformat()}

    def _realtime_floatrates(self, base: str, target: str) -> dict[str, float | str]:
        url = f"{settings.FOREX_FLOATRATES_BASE_URL.rstrip('/')}/daily/{base.lower()}.json"
        data = self._get_json(url)
        item = data.get(target.lower())
        if not item:
            raise ValueError(f"floatrates: 未找到 {base}->{target}")
        return {"rate": float(item["rate"]), "date": str(item.get("date", ""))[:16] or date.today().isoformat()}

    def _realtime_frankfurter(self, base: str, target: str) -> dict[str, float | str]:
        url = f"{settings.FOREX_API_BASE_URL.rstrip('/')}/latest"
        data = self._get_json(url, params={"from": base, "to": target})
        rate = data.get("rates", {}).get(target)
        if rate is None:
            raise ValueError(f"frankfurter: 未找到 {base}->{target}")
        return {"rate": float(rate), "date": str(data.get("date", ""))}

    # ================================================================
    #  历史查询 —— 各 provider 实现
    # ================================================================

    def _history_fawazahmed(
        self, base: str, target: str, start_date: date, end_date: date,
    ) -> list[dict[str, float | str]]:
        """Fawazahmed0 按日期版本逐天查询（CDN 缓存，速度快）。"""
        base_l, target_l = base.lower(), target.lower()
        records: list[dict[str, float | str]] = []
        current = start_date
        while current <= end_date:
            version_url = (
                f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api"
                f"@{current.isoformat()}/v1/currencies/{base_l}.json"
            )
            try:
                data = self._get_json(version_url)
                rate = data.get(base_l, {}).get(target_l)
                if rate is not None:
                    records.append({"date": current.isoformat(), "rate": float(rate)})
            except Exception:
                pass
            current += timedelta(days=1)
        if not records:
            raise ValueError(f"fawazahmed: 历史数据为空 {base}->{target}")
        return records

    def _history_ecb(
        self, base: str, target: str, start_date: date, end_date: date,
    ) -> list[dict[str, float | str]]:
        """
        ECB SDW 官方数据 API（欧洲中央银行统计数据仓库）。
        提供 EUR 基准汇率，需做交叉汇率换算。
        """
        def _fetch_ecb_series(currency: str, s: date, e: date) -> dict[str, float]:
            url = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
            params = {
                "startPeriod": s.isoformat(),
                "endPeriod": e.isoformat(),
                "format": "jsondata",
            }
            data = self._get_json(url, params=params)
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
            target_series = _fetch_ecb_series(target, start_date, end_date)
            records = [
                {"date": d, "rate": 1.0 / v}
                for d, v in sorted(target_series.items()) if v != 0
            ]
        elif target == "EUR":
            base_series = _fetch_ecb_series(base, start_date, end_date)
            records = [
                {"date": d, "rate": v}
                for d, v in sorted(base_series.items())
            ]
        else:
            base_series = _fetch_ecb_series(base, start_date, end_date)
            target_series = _fetch_ecb_series(target, start_date, end_date)
            common_dates = sorted(set(base_series.keys()) & set(target_series.keys()))
            records = []
            for d in common_dates:
                bv, tv = base_series[d], target_series[d]
                if bv != 0:
                    records.append({"date": d, "rate": round(tv / bv, 8)})

        if not records:
            raise ValueError(f"ecb: 历史数据为空 {base}->{target}")
        return records

    def _history_frankfurter(
        self, base: str, target: str, start_date: date, end_date: date,
    ) -> list[dict[str, float | str]]:
        """Frankfurter 区间查询（数据同样来自 ECB，但该第三方服务偶尔不稳定）。"""
        url = f"{settings.FOREX_API_BASE_URL.rstrip('/')}/{start_date.isoformat()}..{end_date.isoformat()}"
        data = self._get_json(url, params={"from": base, "to": target})
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

    def get_realtime_quote(self, base_currency: str, target_currency: str) -> dict[str, float | str]:
        """获取实时汇率及日期（自动降级切换数据源）。"""
        base, target = self._norm_pair(base_currency, target_currency)
        errors: list[str] = []
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
            try:
                result = fn(base, target)
                logger.info(
                    "forex_realtime_success | provider=%s | base=%s | target=%s | rate=%.6f | date=%s",
                    provider, base, target, float(result["rate"]), result["date"],
                )
                return result
            except Exception as exc:
                logger.warning(
                    "forex_realtime_failed | provider=%s | base=%s | target=%s | err=%s",
                    provider, base, target, str(exc),
                )
                errors.append(f"{provider}: {exc}")
        raise RuntimeError(
            f"全部实时数据源均失败（{base}->{target}）：{' | '.join(errors)}"
        )

    def get_realtime_rate(self, base_currency: str, target_currency: str) -> float:
        return float(self.get_realtime_quote(base_currency, target_currency)["rate"])

    def get_history_rates(
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

        for provider in self.history_provider_priority:
            fn = history_map.get(provider)
            if fn is None:
                continue
            if provider == "fawazahmed" and days > 31:
                logger.info("forex_history_skip | provider=%s | reason=range_too_large | days=%s", provider, days)
                errors.append(f"{provider}: 区间>{31}天不适合逐天查询")
                continue
            try:
                records = fn(base, target, start_date, end_date)
                logger.info(
                    "forex_history_success | provider=%s | base=%s | target=%s | points=%s | start=%s | end=%s",
                    provider, base, target, len(records), records[0]["date"], records[-1]["date"],
                )
                return records
            except Exception as exc:
                logger.warning(
                    "forex_history_failed | provider=%s | base=%s | target=%s | days=%s | err=%s",
                    provider, base, target, days, str(exc),
                )
                errors.append(f"{provider}: {exc}")

        raise RuntimeError(
            f"全部历史数据源均失败（{base}->{target}, days={days}）：{' | '.join(errors)}"
        )
