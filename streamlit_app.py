"""
Streamlit 展示层（HTTP 调用版）
===============================
前端仅负责展示，所有业务逻辑通过 HTTP 调协作服务（FastAPI）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from src.config import settings

st.set_page_config(page_title="外汇智能体", layout="wide", initial_sidebar_state="expanded")


# ========== 图表构建（缓存）==========

@st.cache_data(show_spinner=False)
def build_chart(
    base: str,
    target: str,
    history_json: str,
    forecast_rates: tuple[float, ...],
    opacity: float = 1.0,
    loading_hint: str = "",
) -> go.Figure:
    df = pd.read_json(history_json, orient="records")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["rate"],
        mode="lines", name="历史汇率",
        line=dict(color="#1f77b4", width=2),
        hovertemplate="历史汇率: %{y:.6f}<extra></extra>",
        opacity=opacity,
    ))

    ma_short = settings.MA_SHORT_WINDOW
    ma_long = settings.MA_LONG_WINDOW
    if len(df) >= ma_short:
        df[f"MA{ma_short}"] = df["rate"].rolling(ma_short).mean()
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[f"MA{ma_short}"],
            mode="lines", name=f"MA{ma_short}",
            line=dict(color="#ff7f0e", width=1, dash="dot"),
            opacity=opacity,
        ))
    if len(df) >= ma_long:
        df[f"MA{ma_long}"] = df["rate"].rolling(ma_long).mean()
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[f"MA{ma_long}"],
            mode="lines", name=f"MA{ma_long}",
            line=dict(color="#2ca02c", width=1, dash="dot"),
            opacity=opacity,
        ))

    pred = np.array(forecast_rates, dtype=float)
    future_dates = pd.date_range(
        start=df["date"].iloc[-1] + pd.Timedelta(days=1),
        periods=len(pred), freq="D",
    )
    pred_dates_with_anchor = pd.DatetimeIndex([df["date"].iloc[-1]]).append(future_dates)
    pred_values_with_anchor = np.concatenate(([float(df["rate"].iloc[-1])], pred))
    fig.add_trace(go.Scatter(
        x=pred_dates_with_anchor, y=pred_values_with_anchor,
        mode="lines", name="预测汇率",
        line=dict(color="#d62728", width=2, dash="dash"),
        hovertemplate="预测汇率: %{y:.6f}<extra></extra>",
        opacity=opacity,
    ))

    title_text = f"{base}/{target} 汇率走势与预测"
    if loading_hint:
        title_text += f"<br><span style='font-size:12px;color:#888'>{loading_hint}</span>"

    fig.update_layout(
        title=title_text,
        xaxis_title="日期", yaxis_title="汇率",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        height=520,
    )
    fig.update_xaxes(tickformat="%Y年%m月%d日")
    return fig


def post_json(url: str, payload: dict) -> dict:
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


# ========== URL 参数持久化 ==========
_qp = st.query_params
_currencies = settings.MAJOR_CURRENCIES


def _safe_currency_index(key: str, default_idx: int) -> int:
    val = _qp.get(key, "")
    if val in _currencies:
        return _currencies.index(val)
    return default_idx


def _safe_int(key: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int(_qp.get(key, default))
        return max(lo, min(hi, v))
    except (ValueError, TypeError):
        return default


# ========== 侧边栏 ==========
with st.sidebar:
    st.header("参数设置")
    base_currency = st.selectbox(
        "基准货币",
        _currencies,
        index=_safe_currency_index("base", 0),
        format_func=lambda code: f"{code} - {settings.CURRENCY_NAME_MAP.get(code, code)}",
        key="sel_base",
    )
    target_currency = st.selectbox(
        "目标货币",
        _currencies,
        index=_safe_currency_index("target", 3),
        format_func=lambda code: f"{code} - {settings.CURRENCY_NAME_MAP.get(code, code)}",
        key="sel_target",
    )
    history_days = st.slider("历史天数", 30, 365, _safe_int("hdays", 90, 30, 365), step=5, key="sl_hdays")
    forecast_days = st.slider("预测天数", 7, 90, _safe_int("fdays", 30, 7, 90), step=1, key="sl_fdays")

    _qp["base"] = base_currency
    _qp["target"] = target_currency
    _qp["hdays"] = str(history_days)
    _qp["fdays"] = str(forecast_days)

    st.divider()
    run_btn = st.button("重新分析", type="primary", use_container_width=True)

    st.divider()
    interval = settings.REALTIME_REFRESH_INTERVAL_MS

    def _render_realtime_panel() -> None:
        try:
            realtime_resp = post_json(
                f"{settings.COLLAB_API_BASE_URL}/v1/forex/realtime",
                {
                    "base_currency": base_currency,
                    "target_currency": target_currency,
                    "caller_agent": "streamlit-ui",
                    "caller_task_id": f"rt-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                },
            )
            quote = realtime_resp.get("data", {})
            st.metric(f"{base_currency}/{target_currency}", f"{float(quote.get('rate', 0.0)):.6f}")
            st.caption(f"数据时间: {quote.get('date', '-')} {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            st.error(f"实时获取失败（API）：{e}")

    if hasattr(st, "fragment"):
        run_every_str = f"{max(int(interval // 1000), 1)}s"

        @st.fragment(run_every=run_every_str)
        def realtime_fragment() -> None:
            _render_realtime_panel()

        realtime_fragment()
    else:
        _render_realtime_panel()


# ========== 主区域 ==========
st.title("外汇智能体")

# 占位符：每个 st.empty() 只通过直接方法调用写入单个元素，
# 这样同一次 run 中再次调用时会替换（而非叠加）。
chart_slot = st.empty()
report_slot = st.empty()

# ========== 判断是否需要执行 ==========
current_params = (base_currency, target_currency, history_days, forecast_days)


def is_result_expired() -> bool:
    last_run_at = st.session_state.get("last_run_at")
    if not last_run_at:
        return True
    try:
        last_dt = datetime.fromisoformat(last_run_at)
    except Exception:
        return True
    return datetime.now() - last_dt >= timedelta(days=1)


need_run = False
if "result" not in st.session_state:
    need_run = True
elif run_btn:
    need_run = True
elif st.session_state.get("last_params") != current_params:
    need_run = True
elif is_result_expired():
    need_run = True


def _write_chart(slot, state: dict, base: str, target: str,
                 muted: bool = False) -> None:
    """向 chart_slot 写入单个 plotly_chart 元素（可替换）。"""
    if "history_records" not in state or "forecast" not in state:
        return
    req = state.get("request", {})
    chart_base = req.get("base_currency", base) if muted else base
    chart_target = req.get("target_currency", target) if muted else target
    history_json = pd.DataFrame(state["history_records"]).to_json(orient="records")
    forecast_tuple = tuple(state["forecast"]["predicted_rates"])
    fig = build_chart(
        chart_base, chart_target, history_json, forecast_tuple,
        opacity=0.3 if muted else 1.0,
        loading_hint="⏳ 正在计算新结果，以下为上一次结果..." if muted else "",
    )
    slot.plotly_chart(fig, use_container_width=True)


def _write_report(slot, state: dict, muted: bool = False) -> None:
    """向 report_slot 写入单个 markdown 元素（可替换）。"""
    report_text = state.get("report", "")
    if not report_text:
        return
    if muted:
        slot.markdown(
            f"### 大模型分析与建议\n\n<div style='opacity:0.35'>{report_text}</div>",
            unsafe_allow_html=True,
        )
    else:
        slot.markdown(f"### 大模型分析与建议\n\n{report_text}")


# ==========================================================================
# 渲染策略
# --------------------------------------------------------------------------
# 关键：对 st.empty() 只使用直接方法调用（如 slot.plotly_chart / slot.markdown），
# 不使用 slot.container()。直接方法调用在同一次 run 中再次调用时会替换前一次内容。
#
# need_run=True 且有旧数据 → 先灰态渲染旧图（旧标题），再 API 调用，
#   API 成功后再次调用 slot.plotly_chart 替换为新图。
# need_run=True 且无旧数据 → spinner + API 调用。
# need_run=False → 直接渲染缓存结果。
# ==========================================================================

if need_run:
    has_old = "result" in st.session_state

    if has_old:
        _write_chart(chart_slot, st.session_state["result"],
                     base_currency, target_currency, muted=True)
        _write_report(report_slot, st.session_state["result"], muted=True)

    try:
        with st.spinner("正在分析，请稍候..."):
            api_resp = post_json(
                f"{settings.COLLAB_API_BASE_URL}/v1/forex/analyze",
                {
                    "base_currency": base_currency,
                    "target_currency": target_currency,
                    "history_days": history_days,
                    "forecast_days": forecast_days,
                    "caller_agent": "streamlit-ui",
                    "caller_task_id": f"ui-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                },
            )
        if not api_resp.get("ok", False):
            raise RuntimeError(api_resp.get("error", "分析失败"))

        final_state = api_resp.get("data", {})
        st.session_state["result"] = final_state
        st.session_state["last_params"] = current_params
        st.session_state["last_run_at"] = datetime.now().isoformat()

        _write_chart(chart_slot, final_state, base_currency, target_currency)
        _write_report(report_slot, final_state)

    except Exception as e:
        st.error(f"分析失败（API）返回错误，请检查 API 与日志：{e}")
        if has_old:
            _write_chart(chart_slot, st.session_state["result"],
                         base_currency, target_currency)
            _write_report(report_slot, st.session_state["result"])

else:
    if "result" in st.session_state:
        _write_chart(chart_slot, st.session_state["result"],
                     base_currency, target_currency)
        _write_report(report_slot, st.session_state["result"])
