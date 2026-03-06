"""
MCP 服务端（异步版，跨工程智能体协作）
=====================================
将外汇智能体能力以 MCP Tools 形式暴露，便于其他智能体通过 MCP 协议调用。
所有 tool 函数均为 async def。
"""

from __future__ import annotations

from src.collaboration_api import forex_collab_api
from src.logging_utils import get_logger

logger = get_logger(__name__)

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover
    FastMCP = None  # type: ignore[assignment]
    _import_error = exc
else:
    _import_error = None


def create_mcp_server():
    if FastMCP is None:
        raise RuntimeError(
            f"MCP SDK 不可用，请先安装 `mcp` 包。import_error={_import_error}"
        )

    mcp = FastMCP("forex-agent-mcp")

    @mcp.tool()
    async def get_realtime_quote(base_currency: str = "USD", target_currency: str = "CNY") -> dict:
        """获取实时汇率。"""
        logger.info("mcp_call | tool=get_realtime_quote | pair=%s/%s", base_currency, target_currency)
        return await forex_collab_api.get_realtime_quote(base_currency=base_currency, target_currency=target_currency)

    @mcp.tool()
    async def run_full_analysis(
        base_currency: str = "USD",
        target_currency: str = "CNY",
        history_days: int = 90,
        forecast_days: int = 30,
        caller_agent: str = "mcp-client",
        caller_task_id: str = "na",
    ) -> dict:
        """执行完整外汇分析（实时、历史分析、预测、报告）。"""
        logger.info(
            "mcp_call | tool=run_full_analysis | caller=%s | task_id=%s | pair=%s/%s",
            caller_agent,
            caller_task_id,
            base_currency,
            target_currency,
        )
        return await forex_collab_api.run_full_analysis(
            {
                "base_currency": base_currency,
                "target_currency": target_currency,
                "history_days": history_days,
                "forecast_days": forecast_days,
                "caller_agent": caller_agent,
                "caller_task_id": caller_task_id,
            }
        )

    @mcp.tool()
    async def build_customer_context(
        base_currency: str = "USD",
        target_currency: str = "CNY",
        history_days: int = 90,
        forecast_days: int = 30,
        caller_agent: str = "customer-service-agent",
        caller_task_id: str = "na",
    ) -> dict:
        """生成客服智能体可直接使用的用户摘要上下文。"""
        logger.info(
            "mcp_call | tool=build_customer_context | caller=%s | task_id=%s",
            caller_agent,
            caller_task_id,
        )
        return await forex_collab_api.build_customer_agent_context(
            {
                "base_currency": base_currency,
                "target_currency": target_currency,
                "history_days": history_days,
                "forecast_days": forecast_days,
                "caller_agent": caller_agent,
                "caller_task_id": caller_task_id,
            }
        )

    return mcp


def run_mcp() -> None:
    mcp = create_mcp_server()
    logger.info("mcp_server_start | name=forex-agent-mcp")
    mcp.run()
