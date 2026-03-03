"""
Streamlit 展示层（HTTP 调用版）
===============================
前端仅负责展示，所有业务逻辑通过 HTTP 调协作服务（FastAPI）。
"""
from __future__ import annotations
from datetime import datetime, timedelta
import json
from pathlib import Path
import uuid
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from src.config import settings

st.set_page_config(page_title="外汇智能体", layout="wide", initial_sidebar_state="expanded")

# #region agent log
_DEBUG_LOG_PATH = Path(__file__) /"logs"/ "debug-150bb6.log"


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "150bb6",
            "runId": f"streamlit-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now().timestamp() * 1000),
            "id": f"log_{uuid.uuid4().hex[:12]}",
        }
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion


# ========== 图表构建（缓存）==========

@st.cache_data(show_spinner=False)
def build_chart(
    base: str,
    target: str,
    history_json: str,
    forecast_rates: tuple[float, ...],
    muted: bool = False,
) -> go.Figure:
    """缓存构建 Plotly 图表，同参数毫秒级返回。"""
    df = pd.read_json(history_json, orient="records")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["rate"],
        mode="lines", name="历史汇率",
        line=dict(color="#1f77b4", width=2),
        hovertemplate="历史汇率: %{y:.6f}<extra></extra>",
        opacity=0.35 if muted else 1.0,
    ))

    ma_short = settings.MA_SHORT_WINDOW
    ma_long = settings.MA_LONG_WINDOW
    if len(df) >= ma_short:
        df[f"MA{ma_short}"] = df["rate"].rolling(ma_short).mean()
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[f"MA{ma_short}"],
            mode="lines", name=f"MA{ma_short}",
            line=dict(color="#ff7f0e", width=1, dash="dot"),
            opacity=0.35 if muted else 1.0,
        ))
    if len(df) >= ma_long:
        df[f"MA{ma_long}"] = df["rate"].rolling(ma_long).mean()
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[f"MA{ma_long}"],
            mode="lines", name=f"MA{ma_long}",
            line=dict(color="#2ca02c", width=1, dash="dot"),
            opacity=0.35 if muted else 1.0,
        ))

    pred = np.array(forecast_rates, dtype=float)
    future_dates = pd.date_range(
        start=df["date"].iloc[-1] + pd.Timedelta(days=1),
        periods=len(pred), freq="D",
    )
    # 为了可读性，预测曲线从“最后一个真实点”接出，避免视觉上像独立漂浮的曲线
    pred_dates_with_anchor = pd.DatetimeIndex([df["date"].iloc[-1]]).append(future_dates)
    pred_values_with_anchor = np.concatenate(([float(df["rate"].iloc[-1])], pred))
    fig.add_trace(go.Scatter(
        x=pred_dates_with_anchor, y=pred_values_with_anchor,
        mode="lines", name="预测汇率",
        line=dict(color="#d62728", width=2, dash="dash"),
        hovertemplate="预测汇率: %{y:.6f}<extra></extra>",
        opacity=0.35 if muted else 1.0,
    ))

    fig.update_layout(
        title=f"{base}/{target} 汇率走势与预测",
        xaxis_title="日期", yaxis_title="汇率",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        height=520,
    )
    fig.update_xaxes(tickformat="%Y年%m月%d日")
    return fig


def post_json(url: str, payload: dict) -> dict:
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ========== 侧边栏 ==========
with st.sidebar:
    st.header("参数设置")
    base_currency = st.selectbox(
        "基准货币",
        settings.MAJOR_CURRENCIES,
        index=0,
        format_func=lambda code: f"{code} - {settings.CURRENCY_NAME_MAP.get(code, code)}",
    )
    target_currency = st.selectbox(
        "目标货币",
        settings.MAJOR_CURRENCIES,
        index=3,
        format_func=lambda code: f"{code} - {settings.CURRENCY_NAME_MAP.get(code, code)}",
    )
    history_days = st.slider("历史天数", 30, 365, 90, step=5)
    forecast_days = st.slider("预测天数", 7, 90, 30, step=1)
    st.divider()
    run_btn = st.button("重新分析", type="primary", use_container_width=True)

    st.divider()
    st.subheader("实时汇率监控")
    interval = settings.REALTIME_REFRESH_INTERVAL_MS
    st.caption(f"自动刷新间隔：{interval // 1000}秒")

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
            st.caption(f"数据日期: {quote.get('date', '-') }　刷新: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            st.error(f"实时获取失败（API）：{e}")

    # 优先使用 fragment 局部定时刷新，避免整页重跑导致右侧闪烁
    if hasattr(st, "fragment"):
        run_every_str = f"{max(int(interval // 1000), 1)}s"
        # #region agent log
        _debug_log(
            hypothesis_id="H1",
            location="streamlit_app.py:163",
            message="fragment_run_every_computed",
            data={"interval_ms": int(interval), "run_every": run_every_str},
        )
        # #endregion

        @st.fragment(run_every=run_every_str)
        def realtime_fragment() -> None:
            _render_realtime_panel()

        realtime_fragment()
    else:
        # 兼容低版本 Streamlit：仅首次渲染，不做整页自动刷新
        _render_realtime_panel()

    # st.divider()
    # st.caption(f"LLM: **{settings.LLM_PROVIDER}**")

# ========== 主区域 ==========
st.title("外汇智能体")
# st.caption("LangGraph 驱动 · 通过 HTTP 与协作服务通信 · 实时汇率 · 历史分析 · 趋势预测")


def render_result(
    chart_slot,
    report_slot,
    state: dict,
    muted: bool = False,
    force_replace: bool = False,
) -> None:
    """分别渲染图表和报告，避免同容器残留叠加。"""
    if force_replace:
        chart_slot.empty()
        report_slot.empty()

    if "history_records" in state and "forecast" in state:
        history_json = pd.DataFrame(state["history_records"]).to_json(orient="records")
        forecast_tuple = tuple(state["forecast"]["predicted_rates"])
        fig = build_chart(
            base_currency,
            target_currency,
            history_json,
            forecast_tuple,
            muted=muted,
        )
        with chart_slot.container():
            if muted:
                st.caption("正在计算新结果...")
            chart_key = "main_result_chart_muted" if muted else "main_result_chart_live"
            st.plotly_chart(fig, use_container_width=True, key=chart_key)

    if "report" in state and state["report"]:
        with report_slot.container():
            st.subheader("大模型分析与建议")
            if muted:
                st.markdown(f"<div style='opacity:0.45'>{state['report']}</div>", unsafe_allow_html=True)
            else:
                st.write(state["report"])


# ========== 判断是否需要执行 ==========
current_params = (base_currency, target_currency, history_days, forecast_days)

def is_result_expired() -> bool:
    """
    超过 1 天自动失效，需要重新执行分析。
    """
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

if need_run:
    chart_slot = st.empty()
    report_slot = st.empty()
    # 若已有旧结果，先灰态展示，避免页面空白跳动
    if "result" in st.session_state:
        render_result(
            chart_slot,
            report_slot,
            st.session_state["result"],
            muted=True,
            force_replace=True,
        )
    try:
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

        # with st.expander("工作流执行日志", expanded=False):
        #     timings = final_state.get("node_timings", {})
        #     if timings:
        #         total_time = sum(float(v) for v in timings.values())
        #         parts = [f"**{k}**: {v:.3f}s" for k, v in timings.items()]
        #         st.write(" | ".join(parts))
        #         st.info(f"总耗时：{total_time:.2f}s")
        #     else:
        #         st.write("暂无日志计时信息。")

        render_result(
            chart_slot,
            report_slot,
            final_state,
            muted=False,
            force_replace=True,
        )
    except Exception as e:
        print(f"分析失败（API）：{e}")
        st.error(f"分析失败（API) 返回错误，请检查API与日志")
        # 失败时保留旧结果，不清空页面
        if "result" in st.session_state:
            render_result(
                chart_slot,
                report_slot,
                st.session_state["result"],
                muted=False,
                force_replace=True,
            )

else:
    # ---- 已有缓存结果，直接渲染图表和报告 ----
    chart_slot = st.container()
    report_slot = st.container()
    render_result(
        chart_slot,
        report_slot,
        st.session_state["result"],
        muted=False,
        force_replace=False,
    )
