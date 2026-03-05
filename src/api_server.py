"""
跨工程协作服务（FastAPI）
=========================
将本外汇智能体暴露为 HTTP 服务，便于其他项目中的智能体进行远程调用。
"""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src.api_models import A2AMessageRequest, FullAnalysisRequest, RealtimeRequest, StandardResponse
from src.collaboration_api import forex_collab_api
from src.logging_utils import get_logger

logger = get_logger(__name__)
_DEBUG_LOG_PATH = Path(__file__).parent.parent / "debug-150bb6.log"


# #region agent log
def _debug_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "150bb6",
            "runId": f"api-{datetime.now().strftime('%Y%m%d%H%M%S')}",
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

app = FastAPI(
    title="Forex Agent Collaboration API",
    version="1.0.0",
    description="外汇智能体跨工程协作接口（REST + A2A-style message）",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _normalize_analysis_data(result: dict) -> dict:
    """标准化分析返回体：data 只保留业务字段，去掉嵌套状态字段。"""
    return {
        "request": result.get("request", {}),
        "realtime": result.get("realtime", {}),
        "history_records": result.get("history_records", []),
        "analysis": result.get("analysis", {}),
        "forecast": result.get("forecast", {}),
        "report": result.get("report", ""),
        "report_en": result.get("report_en", ""),
        "node_timings": result.get("node_timings", {}),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/forex/realtime", response_model=StandardResponse)
def realtime_quote(req: RealtimeRequest) -> StandardResponse:
    trace_id = req.caller_task_id
    logger.info(
        "api_call | endpoint=/v1/forex/realtime | caller=%s | task_id=%s",
        req.caller_agent,
        trace_id,
    )
    try:
        data = forex_collab_api.get_realtime_quote(
            base_currency=req.base_currency.upper(),
            target_currency=req.target_currency.upper(),
        )
        # #region agent log
        _debug_log(
            hypothesis_id="H1",
            location="src/api_server.py:67",
            message="realtime_response_shape",
            data={"keys": sorted(list(data.keys())), "rate_type": type(data.get("rate")).__name__},
        )
        # #endregion
        return StandardResponse(ok=True, trace_id=trace_id, data=data)
    except Exception as exc:
        logger.exception("api_error | endpoint=/v1/forex/realtime")
        return StandardResponse(ok=False, trace_id=trace_id, error=str(exc))


@app.post("/v1/forex/analyze", response_model=StandardResponse)
def full_analysis(req: FullAnalysisRequest) -> StandardResponse:
    trace_id = req.caller_task_id
    logger.info(
        "api_call | endpoint=/v1/forex/analyze | caller=%s | task_id=%s",
        req.caller_agent,
        trace_id,
    )
    result = forex_collab_api.run_full_analysis(
        {
            "base_currency": req.base_currency,
            "target_currency": req.target_currency,
            "history_days": req.history_days,
            "forecast_days": req.forecast_days,
            "caller_agent": req.caller_agent,
            "caller_task_id": req.caller_task_id,
        }
    )
    # #region agent log
    _debug_log(
        hypothesis_id="H2",
        location="src/api_server.py:95",
        message="analyze_result_shape",
        data={
            "result_keys": sorted(list(result.keys())),
            "ok_value": bool(result.get("ok", False)),
            "report_len": len(str(result.get("report", ""))),
            "history_records_len": len(result.get("history_records", [])) if isinstance(result.get("history_records", []), list) else -1,
        },
    )
    # #endregion
    ok = bool(result.get("ok", False))
    normalized = _normalize_analysis_data(result) if ok else {}
    # #region agent log
    _debug_log(
        hypothesis_id="H3",
        location="src/api_server.py:128",
        message="analyze_normalized_response_shape",
        data={"ok": ok, "data_keys": sorted(list(normalized.keys())) if isinstance(normalized, dict) else []},
    )
    # #endregion
    return StandardResponse(
        ok=ok,
        trace_id=trace_id,
        data=normalized,
        error=result.get("error", "") if not ok else "",
    )


@app.post("/v1/a2a/message", response_model=StandardResponse)
def a2a_message(req: A2AMessageRequest) -> StandardResponse:
    """
    A2A 风格通用入口：
    - action=get_realtime_quote
    - action=run_full_analysis
    - action=build_customer_context
    """
    logger.info(
        "a2a_call | source=%s | target=%s | action=%s | trace_id=%s",
        req.source_agent,
        req.target_agent,
        req.action,
        req.trace_id,
    )
    try:
        if req.action == "get_realtime_quote":
            data = forex_collab_api.get_realtime_quote(
                base_currency=str(req.payload.get("base_currency", "USD")).upper(),
                target_currency=str(req.payload.get("target_currency", "CNY")).upper(),
            )
            return StandardResponse(ok=True, trace_id=req.trace_id, data=data)

        if req.action == "run_full_analysis":
            result = forex_collab_api.run_full_analysis(
                {
                    "base_currency": req.payload.get("base_currency", "USD"),
                    "target_currency": req.payload.get("target_currency", "CNY"),
                    "history_days": req.payload.get("history_days", 90),
                    "forecast_days": req.payload.get("forecast_days", 30),
                    "caller_agent": req.source_agent,
                    "caller_task_id": req.trace_id,
                }
            )
            ok = bool(result.get("ok", False))
            return StandardResponse(
                ok=ok,
                trace_id=req.trace_id,
                data=_normalize_analysis_data(result) if ok else {},
                error=result.get("error", "") if not ok else "",
            )

        result = forex_collab_api.build_customer_agent_context(
            {
                "base_currency": req.payload.get("base_currency", "USD"),
                "target_currency": req.payload.get("target_currency", "CNY"),
                "history_days": req.payload.get("history_days", 90),
                "forecast_days": req.payload.get("forecast_days", 30),
                "caller_agent": req.source_agent,
                "caller_task_id": req.trace_id,
            }
        )
        return StandardResponse(
            ok=result.get("ok", False),
            trace_id=req.trace_id,
            data=result if result.get("ok", False) else {},
            error="" if result.get("ok", False) else str(result),
        )
    except Exception as exc:
        logger.exception("a2a_error | action=%s", req.action)
        return StandardResponse(ok=False, trace_id=req.trace_id, error=str(exc))


# ---------- Vue 前端静态文件（必须在所有路由之后） ----------
_VUE_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _VUE_DIST.is_dir():
    from fastapi.responses import RedirectResponse

    @app.get("/ui")
    def _ui_redirect():
        return RedirectResponse(url="/ui/")

    app.mount("/ui", StaticFiles(directory=str(_VUE_DIST), html=True), name="vue-ui")

