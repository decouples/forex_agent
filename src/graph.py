"""
LangGraph 工作流定义（异步版）
============================
所有业务逻辑集中在本模块的节点函数中，展示层只消费 graph.astream() 输出。

节点流转（5 步，纯数据管道）：
  START → fetch_realtime → fetch_history → analyze → forecast → report → END

每个节点自带计时，耗时写入 State.node_timings，前端可实时展示瓶颈。
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import asdict
from langgraph.graph import END, START, StateGraph
from src.analysis_service import AnalysisService
from src.forex_service import ForexService
from src.llm_client import get_llm_client
from src.logging_utils import get_logger
from src.state import ForexAgentState

forex_service = ForexService()
analysis_service = AnalysisService()
llm_client = get_llm_client()
logger = get_logger(__name__)

NODE_LABELS: dict[str, str] = {
    "fetch_realtime": "获取实时汇率",
    "fetch_history": "拉取历史数据",
    "analyze": "统计分析",
    "forecast": "趋势预测",
    "report": "大模型生成报告",
}


# ---------- 节点函数（异步，每个都带计时）----------

async def fetch_realtime_node(state: ForexAgentState) -> dict:
    logger.info(
        "node_start | node=fetch_realtime | input={base:%s,target:%s}",
        state["base_currency"],
        state["target_currency"],
    )
    t0 = time.perf_counter()
    quote = await forex_service.get_realtime_quote(
        state["base_currency"], state["target_currency"],
    )
    elapsed = time.perf_counter() - t0
    timings = dict(state.get("node_timings") or {})
    timings["fetch_realtime"] = round(elapsed, 3)
    logger.info(
        "node_end | node=fetch_realtime | output={rate:%.6f,date:%s} | elapsed=%.3fs",
        float(quote["rate"]),
        str(quote["date"]),
        elapsed,
    )
    return {
        "realtime_rate": float(quote["rate"]),
        "realtime_date": str(quote["date"]),
        "node_timings": timings,
    }


async def fetch_history_node(state: ForexAgentState) -> dict:
    logger.info(
        "node_start | node=fetch_history | input={base:%s,target:%s,days:%s}",
        state["base_currency"],
        state["target_currency"],
        state["history_days"],
    )
    t0 = time.perf_counter()
    records = await forex_service.get_history_rates(
        state["base_currency"], state["target_currency"],
        state["history_days"],
    )
    elapsed = time.perf_counter() - t0
    timings = dict(state.get("node_timings") or {})
    timings["fetch_history"] = round(elapsed, 3)
    logger.info(
        "node_end | node=fetch_history | output={points:%s,start:%s,end:%s} | elapsed=%.3fs",
        len(records),
        records[0]["date"] if records else "na",
        records[-1]["date"] if records else "na",
        elapsed,
    )
    return {"history_records": records, "node_timings": timings}


async def analyze_node(state: ForexAgentState) -> dict:
    """统计分析（CPU 密集，放入线程池避免阻塞事件循环）。"""
    logger.info(
        "node_start | node=analyze | input={points:%s}",
        len(state["history_records"]),
    )
    t0 = time.perf_counter()
    result = await asyncio.to_thread(analysis_service.analyze, state["history_records"])
    elapsed = time.perf_counter() - t0
    timings = dict(state.get("node_timings") or {})
    timings["analyze"] = round(elapsed, 3)
    logger.info(
        "node_end | node=analyze | output={trend:%s,mean:%.6f,std:%.6f} | elapsed=%.3fs",
        result.trend_label,
        result.mean_rate,
        result.std_rate,
        elapsed,
    )
    return {"analysis": asdict(result), "node_timings": timings}


async def forecast_node(state: ForexAgentState) -> dict:
    logger.info(
        "node_start | node=forecast | input={points:%s,days:%s,latest:%.6f}",
        len(state["history_records"]),
        state["forecast_days"],
        float(state["history_records"][-1]["rate"]),
    )
    t0 = time.perf_counter()
    history_records = state["history_records"]
    forecast_days = state["forecast_days"]
    latest_rate = float(history_records[-1]["rate"])
    recent_window = history_records[-30:] if len(history_records) > 30 else history_records

    llm_prompt = (
        "你是外汇预测调度智能体。你只做一件事：判断当前走势类型，供下游工具选择预测模型。\n"
        "请严格只输出一个词：up 或 down 或 sideways，不要输出其他内容。\n\n"
        f"货币对: {state['base_currency']}/{state['target_currency']}\n"
        f"最新汇率: {latest_rate}\n"
        f"最近序列: {[float(x['rate']) for x in recent_window]}\n"
    )

    def _extract_trend(text: str) -> str:
        t = (text or "").strip().lower()
        if t in {"up", "down", "sideways"}:
            return t
        if re.search(r"\bup\b|上涨|上升|看涨", t):
            return "up"
        if re.search(r"\bdown\b|下跌|下降|看跌", t):
            return "down"
        return "sideways"

    try:
        decision_raw = await llm_client.agenerate(
            prompt=llm_prompt,
            system_prompt="你是严谨决策器，只返回 up/down/sideways 之一。",
        )
        trend = _extract_trend(decision_raw)
        tool_map = {
            "up": "linear",
            "down": "linear",
            "sideways": "oscillation",
        }
        selected_model = tool_map.get(trend, "linear")
        logger.info(
            "forecast_tool_selected | trend=%s | selected_model=%s | llm_raw=%s",
            trend,
            selected_model,
            decision_raw.strip()[:80],
        )

        tool_result = await asyncio.to_thread(
            analysis_service.forecast,
            history_records=history_records,
            days=forecast_days,
            model_type=selected_model,
        )
        result = {
            "forecast_days": tool_result["forecast_days"],
            "predicted_rates": tool_result["predicted_rates"],
            "trend": trend,
            "confidence": 0.72 if trend in {"up", "down"} else 0.6,
            "reason": f"LLM 判定趋势为 {trend}，路由到 {selected_model} 预测工具。",
            "method": f"llm_decision->{selected_model}",
            "slope": float(tool_result.get("slope", 0.0)),
        }
    except Exception as exc:
        logger.warning("forecast_llm_decision_failed | reason=%s", exc)
        fallback = await asyncio.to_thread(
            analysis_service.forecast,
            history_records=history_records,
            days=forecast_days,
            model_type="linear",
        )
        result = {
            "forecast_days": fallback["forecast_days"],
            "predicted_rates": fallback["predicted_rates"],
            "trend": "sideways",
            "confidence": 0.4,
            "reason": "LLM 决策失败，回退 linear 工具。",
            "method": "fallback_quant->linear",
            "slope": float(fallback.get("slope", 0.0)),
        }

    elapsed = time.perf_counter() - t0
    timings = dict(state.get("node_timings") or {})
    timings["forecast"] = round(elapsed, 3)
    logger.info(
        "node_end | node=forecast | output={method:%s,trend:%s,confidence:%.3f,last:%.6f} | elapsed=%.3fs",
        result.get("method", "na"),
        result.get("trend", "na"),
        float(result.get("confidence", 0.0)),
        float(result["predicted_rates"][-1]) if result.get("predicted_rates") else -1.0,
        elapsed,
    )
    return {"forecast": result, "node_timings": timings}


def _build_data_block(state: ForexAgentState) -> str:
    a = state["analysis"]
    f = state["forecast"]
    return (
        f"- Pair: {state['base_currency']}/{state['target_currency']}\n"
        f"- Live rate: {state['realtime_rate']} (date: {state['realtime_date']})\n"
        f"- Historical mean: {a['mean_rate']:.6f}, volatility: {a['std_rate']:.6f}\n"
        f"- Period return: {a['return_pct']:+.2f}%, trend: {a['trend_label']}\n"
        f"- Forecast method: {f.get('method', 'unknown')}\n"
        f"- Forecast trend: {f.get('trend', 'sideways')}\n"
        f"- Confidence: {f.get('confidence', 0.0)}\n"
        f"- Reason: {f.get('reason', '-')}\n"
        f"- {f['forecast_days']}-day forecast final rate: {f['predicted_rates'][-1]:.6f}"
    )


async def report_node(state: ForexAgentState) -> dict:
    logger.info(
        "node_start | node=report | input={method:%s,trend:%s,last:%.6f}",
        state["forecast"].get("method", "na"),
        state["forecast"].get("trend", "na"),
        float(state["forecast"]["predicted_rates"][-1]),
    )
    t0 = time.perf_counter()
    a = state["analysis"]
    f = state["forecast"]
    data_block = _build_data_block(state)

    prompt_zh = (
        f"请根据以下外汇数据生成一份简洁专业的分析报告（中文，300字以内）：\n"
        f"{data_block}\n\n"
        f"报告须包含：1) 当前走势解读 2) 未来趋势判断 3) 风险提示（非投资建议）"
    )
    prompt_en = (
        f"Generate a concise professional forex analysis report (English, within 200 words) "
        f"based on the following data:\n"
        f"{data_block}\n\n"
        f"Include: 1) Current trend interpretation 2) Future trend forecast 3) Risk disclaimer (not investment advice)"
    )

    async def _gen_zh() -> str:
        try:
            text = await llm_client.agenerate(
                prompt=prompt_zh,
                system_prompt="你是谨慎、专业的外汇分析助手。",
            )
            if not text or not text.strip():
                raise ValueError("LLM 中文报告为空。")
            return text
        except Exception as exc:
            logger.warning("report_llm_zh_failed | reason=%s", exc)
            return (
                "大模型调用失败，已返回规则化摘要：\n\n"
                f"- 当前汇率：{state['realtime_rate']:.6f}（{state['realtime_date']}）\n"
                f"- 区间涨跌幅：{a['return_pct']:+.2f}%\n"
                f"- 趋势判断：{a['trend_label']}\n"
                f"- 预测终值：{f['predicted_rates'][-1]:.6f}\n"
                f"- 错误信息：{exc}"
            )

    async def _gen_en() -> str:
        try:
            text = await llm_client.agenerate(
                prompt=prompt_en,
                system_prompt="You are a cautious, professional forex analysis assistant.",
            )
            if not text or not text.strip():
                raise ValueError("LLM English report is empty.")
            return text
        except Exception as exc:
            logger.warning("report_llm_en_failed | reason=%s", exc)
            return (
                "LLM call failed. Rule-based summary:\n\n"
                f"- Current rate: {state['realtime_rate']:.6f} ({state['realtime_date']})\n"
                f"- Period return: {a['return_pct']:+.2f}%\n"
                f"- Trend: {a['trend_label']}\n"
                f"- Forecast final: {f['predicted_rates'][-1]:.6f}\n"
                f"- Error: {exc}"
            )

    report_zh, report_en = await asyncio.gather(_gen_zh(), _gen_en())

    elapsed = time.perf_counter() - t0
    timings = dict(state.get("node_timings") or {})
    timings["report"] = round(elapsed, 3)
    logger.info(
        "node_end | node=report | output={zh_len:%s,en_len:%s} | elapsed=%.3fs",
        len(report_zh), len(report_en), elapsed,
    )
    return {"report": report_zh, "report_en": report_en, "node_timings": timings}


# ---------- 构建图 ----------

def build_forex_graph():
    graph = StateGraph(ForexAgentState)

    graph.add_node("fetch_realtime", fetch_realtime_node)
    graph.add_node("fetch_history", fetch_history_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("forecast", forecast_node)
    graph.add_node("report", report_node)

    graph.add_edge(START, "fetch_realtime")
    graph.add_edge("fetch_realtime", "fetch_history")
    graph.add_edge("fetch_history", "analyze")
    graph.add_edge("analyze", "forecast")
    graph.add_edge("forecast", "report")
    graph.add_edge("report", END)

    return graph.compile()
