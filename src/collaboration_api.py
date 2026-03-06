"""
智能体协作接口（异步版）
========================
本模块用于给"其他智能体"调用本外汇智能体能力，属于 in-process SDK 接口。

典型协作场景：
- 客服智能体：询问"美元兑人民币近期走势如何？"
- 投研智能体：拿结构化预测结果做下游决策
- 报警智能体：定时读取实时汇率并触发阈值告警
"""

from __future__ import annotations
from typing import Any, TypedDict
from src.forex_service import ForexService
from src.graph import build_forex_graph
from src.logging_utils import get_logger

logger = get_logger(__name__)


class ForexRunRequest(TypedDict, total=False):
    """其他智能体调用本智能体时的请求结构。"""

    base_currency: str
    target_currency: str
    history_days: int
    forecast_days: int
    caller_agent: str
    caller_task_id: str


class ForexRunResponse(TypedDict):
    """本智能体返回给其他智能体的标准响应。"""

    ok: bool
    request: dict[str, Any]
    realtime: dict[str, Any]
    history_records: list[dict[str, Any]]
    analysis: dict[str, Any]
    forecast: dict[str, Any]
    report: str
    report_en: str
    node_timings: dict[str, float]
    error: str


class ForexAgentCollaborationAPI:
    """
    对外协作 API（异步版）。
    其他智能体不需要了解 LangGraph 细节，只要调用本类方法即可。
    """

    def __init__(self) -> None:
        self._graph = build_forex_graph()
        self._forex_service = ForexService()

    @staticmethod
    def _is_same_currency(base: str, target: str) -> bool:
        return base.upper() == target.upper()

    async def get_realtime_quote(self, base_currency: str, target_currency: str) -> dict[str, Any]:
        """面向其他智能体的轻量接口：只取实时汇率。"""
        logger.info(
            "collab_call | method=get_realtime_quote | base=%s | target=%s",
            base_currency,
            target_currency,
        )
        if self._is_same_currency(base_currency, target_currency):
            from datetime import date
            logger.info("same_currency_shortcut | pair=%s/%s | rate=1.0", base_currency, target_currency)
            return {
                "base_currency": base_currency,
                "target_currency": target_currency,
                "rate": 1.0,
                "date": date.today().isoformat(),
            }
        quote = await self._forex_service.get_realtime_quote(
            base_currency=base_currency, target_currency=target_currency,
        )
        return {
            "base_currency": base_currency,
            "target_currency": target_currency,
            "rate": quote["rate"],
            "date": quote["date"],
        }

    def _build_same_currency_response(
        self, base: str, target: str,
        history_days: int, forecast_days: int,
        request: ForexRunRequest,
    ) -> ForexRunResponse:
        """base == target 时直接返回恒等结果，跳过 graph / LLM / 外部 API。"""
        from datetime import date, timedelta
        logger.info("same_currency_shortcut | pair=%s/%s | skipping_graph", base, target)
        today = date.today()
        history = [
            {"date": (today - timedelta(days=i)).isoformat(), "rate": 1.0}
            for i in range(history_days - 1, -1, -1)
        ]
        return {
            "ok": True,
            "request": {
                "base_currency": base,
                "target_currency": target,
                "history_days": history_days,
                "forecast_days": forecast_days,
                "caller_agent": request.get("caller_agent", "unknown"),
                "caller_task_id": request.get("caller_task_id", "na"),
            },
            "realtime": {"rate": 1.0, "date": today.isoformat()},
            "history_records": history,
            "analysis": {
                "mean_rate": 1.0, "std_rate": 0.0,
                "latest_rate": 1.0, "return_pct": 0.0,
                "ma_short": 1.0, "ma_long": 1.0,
                "trend_label": "恒等",
            },
            "forecast": {
                "forecast_days": forecast_days,
                "predicted_rates": [1.0] * forecast_days,
                "trend": "identity",
                "confidence": 1.0,
                "reason": f"{base} 与 {target} 为同一货币，汇率恒为 1.0。",
                "method": "identity",
                "model_used": "identity",
                "slope": 0.0,
            },
            "report": (
                f"## {base}/{target} 分析报告\n\n"
                f"基准货币与目标货币相同（{base}），汇率恒定为 **1.0**，"
                f"无波动、无趋势变化。\n\n"
                f"- 当前汇率：1.000000\n"
                f"- 历史波动率：0.000000\n"
                f"- 预测结果：未来 {forecast_days} 天汇率保持 1.0\n\n"
                f"> 提示：如需分析实际汇率走势，请选择两种不同的货币。"
            ),
            "report_en": (
                f"## {base}/{target} Analysis Report\n\n"
                f"Base and target currencies are identical ({base}). "
                f"The exchange rate is constant at **1.0** with zero volatility.\n\n"
                f"- Current rate: 1.000000\n"
                f"- Historical volatility: 0.000000\n"
                f"- Forecast: rate remains 1.0 for the next {forecast_days} days\n\n"
                f"> Note: Select two different currencies for actual trend analysis."
            ),
            "node_timings": {},
            "error": "",
        }

    async def run_full_analysis(self, request: ForexRunRequest) -> ForexRunResponse:
        """面向其他智能体的完整分析接口（实时 + 历史分析 + 趋势预测 + 报告）。"""
        base = request.get("base_currency", "USD").upper()
        target = request.get("target_currency", "CNY").upper()
        history_days = int(request.get("history_days", 90))
        forecast_days = int(request.get("forecast_days", 30))

        logger.info(
            "collab_call | method=run_full_analysis | caller=%s | task_id=%s | pair=%s/%s | history_days=%s | forecast_days=%s",
            request.get("caller_agent", "unknown"),
            request.get("caller_task_id", "na"),
            base,
            target,
            history_days,
            forecast_days,
        )

        if self._is_same_currency(base, target):
            return self._build_same_currency_response(base, target, history_days, forecast_days, request)

        try:
            result = await self._graph.ainvoke(
                {
                    "base_currency": base,
                    "target_currency": target,
                    "history_days": history_days,
                    "forecast_days": forecast_days,
                }
            )
            response: ForexRunResponse = {
                "ok": True,
                "request": {
                    "base_currency": base,
                    "target_currency": target,
                    "history_days": history_days,
                    "forecast_days": forecast_days,
                    "caller_agent": request.get("caller_agent", "unknown"),
                    "caller_task_id": request.get("caller_task_id", "na"),
                },
                "realtime": {
                    "rate": result.get("realtime_rate"),
                    "date": result.get("realtime_date"),
                },
                "history_records": result.get("history_records", []),
                "analysis": result.get("analysis", {}),
                "forecast": result.get("forecast", {}),
                "report": result.get("report", ""),
                "report_en": result.get("report_en", ""),
                "node_timings": result.get("node_timings", {}),
                "error": "",
            }
            logger.info(
                "collab_return | method=run_full_analysis | ok=true | report_len=%s",
                len(response["report"]),
            )
            return response
        except Exception as exc:
            logger.exception("collab_return | method=run_full_analysis | ok=false")
            return {
                "ok": False,
                "request": dict(request),
                "realtime": {},
                "history_records": [],
                "analysis": {},
                "forecast": {},
                "report": "",
                "report_en": "",
                "node_timings": {},
                "error": str(exc),
            }

    async def build_customer_agent_context(self, request: ForexRunRequest) -> dict[str, Any]:
        """给"客服智能体"提供标准上下文。"""
        result = await self.run_full_analysis(request)
        if not result["ok"]:
            return {
                "ok": False,
                "user_facing_summary": f"外汇分析暂时不可用：{result['error']}",
                "structured_payload": result,
            }

        forecast = result["forecast"]
        summary = (
            f"{result['request']['base_currency']}/{result['request']['target_currency']} 当前汇率为 "
            f"{result['realtime'].get('rate')}（{result['realtime'].get('date')}）。"
            f" 未来{forecast.get('forecast_days')}天预测趋势为 {forecast.get('trend', 'sideways')}，"
            f" 置信度约 {forecast.get('confidence', 0.0)}。"
        )
        return {
            "ok": True,
            "user_facing_summary": summary,
            "structured_payload": result,
        }


# 便于其他模块直接 import 使用的默认实例
forex_collab_api = ForexAgentCollaborationAPI()
