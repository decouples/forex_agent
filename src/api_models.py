"""
跨工程通信模型定义
==================
用于 FastAPI / A2A 风格调用的请求与响应模型。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RealtimeRequest(BaseModel):
    base_currency: str = Field(default="USD")
    target_currency: str = Field(default="CNY")
    caller_agent: str = Field(default="unknown")
    caller_task_id: str = Field(default="na")


class FullAnalysisRequest(BaseModel):
    base_currency: str = Field(default="USD")
    target_currency: str = Field(default="CNY")
    history_days: int = Field(default=90, ge=7, le=3650)
    forecast_days: int = Field(default=30, ge=1, le=365)
    caller_agent: str = Field(default="unknown")
    caller_task_id: str = Field(default="na")


class A2AMessageRequest(BaseModel):
    """
    A2A 风格的通用消息包。
    action 表示对方智能体希望你执行的能力。
    payload 是该能力对应参数。
    """

    protocol: Literal["a2a.v1"] = "a2a.v1"
    source_agent: str = Field(default="unknown")
    target_agent: str = Field(default="forex-agent")
    trace_id: str = Field(default="na")
    action: Literal["get_realtime_quote", "run_full_analysis", "build_customer_context"]
    payload: dict[str, Any] = Field(default_factory=dict)


class StandardResponse(BaseModel):
    ok: bool
    trace_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str = ""

