"""
LangGraph 状态定义
==================
集中定义图节点共享状态。
面试讲解要点：所有中间数据（汇率、分析、预测、报告）都在此结构中流转，
每个节点只读自己需要的字段、只写自己负责的字段，职责单一。

node_timings 记录每个节点的耗时，便于性能可观测。
"""

from typing import Any, TypedDict


class ForexAgentState(TypedDict, total=False):
    """外汇智能体在图中的共享状态。"""

    # ---- 输入参数（由调用方填入）----
    base_currency: str
    target_currency: str
    history_days: int
    forecast_days: int

    # ---- 节点 fetch_realtime 写入 ----
    realtime_rate: float
    realtime_date: str

    # ---- 节点 fetch_history 写入 ----
    history_records: list[dict[str, Any]]

    # ---- 节点 analyze 写入 ----
    analysis: dict[str, Any]

    # ---- 节点 forecast 写入 ----
    forecast_plan: dict[str, Any]
    forecast: dict[str, Any]
    risk_assessment: dict[str, Any]
    strategy_advice: dict[str, Any]
    coordinator_summary: dict[str, Any]

    # ---- 节点 report 写入 ----
    report: str
    report_en: str

    # ---- 多智能体通信消息 ----
    agent_messages: list[dict[str, Any]]

    # ---- 各节点耗时（每个节点追加自己的计时）----
    node_timings: dict[str, float]
