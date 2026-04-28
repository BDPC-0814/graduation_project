import gzip
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .control_service import (
    ControlBusyError,
    NoActiveJobError,
    control_service,
)
from .data_service import (
    acknowledge_alert,
    batch_acknowledge_alerts,
    batch_silence_alerts,
    bootstrap_database,
    create_rule,
    delete_rule,
    export_rules,
    get_compare_history,
    get_alert_summary,
    get_alert_trends,
    get_dashboard_overview,
    get_devices,
    get_events,
    get_experiment_evaluation_report,
    get_history,
    get_recent_logs,
    get_realtime_metrics,
    get_rules,
    ingest_records,
    import_rules,
    query_alerts,
    silence_alert,
    unsilence_alert,
    update_rule,
)
from .schemas import (
    AlertActionRequest,
    AlertBatchActionRequest,
    AlertBatchActionResult,
    AlertBatchSilenceRequest,
    AlertRecord,
    AlertRuleCreateRequest,
    AlertRuleDeleteRequest,
    AlertRuleExportResponse,
    AlertRuleImportRequest,
    AlertRuleImportResult,
    AlertRuleRecord,
    AlertRuleUpdateRequest,
    AlertSilenceRequest,
    AlertSummary,
    CompareHistoryResponse,
    ControlJob,
    ControlStatusResponse,
    DashboardOverview,
    DeviceSummary,
    EventRecord,
    HistoryResponse,
    LiveCollectionRequest,
    LogRecord,
    ReplayCompareRequest,
    ReplayTraceRequest,
    RealtimeMetric,
    SchedulerConfig,
)


app = FastAPI(
    title="Fault Evolution Sampling API",
    version="0.1.0",
    description="Visualization backend for device metrics, history, and events.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"


def _validate_rule_definition(payload: dict):
    operator = payload.get("operator")
    threshold_value = payload.get("threshold_value")
    threshold_text = payload.get("threshold_text")
    if operator in {"ge", "gt"} and threshold_value is None:
        raise HTTPException(status_code=422, detail="threshold_value is required for numeric operators")
    if operator in {"eq", "ne"} and (threshold_text is None or str(threshold_text).strip() == ""):
        raise HTTPException(status_code=422, detail="threshold_text is required for text operators")


def _model_to_dict(model, **kwargs):
    if hasattr(model, "model_dump"):
        return model.model_dump(**kwargs)
    return model.dict(**kwargs)


def _ensure_alert_ids(alert_ids: list[int]):
    if not alert_ids:
        raise HTTPException(status_code=422, detail="alert_ids must not be empty")


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


@app.on_event("startup")
def on_startup():
    bootstrap_database()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/ingest")
async def ingest_batch(request: Request):
    raw_body = await request.body()
    encoding = request.headers.get("content-encoding", "").lower()
    body = gzip.decompress(raw_body) if encoding == "gzip" else raw_body
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid payload: {exc}") from exc

    records = payload.get("records", [])
    parsed_records = []
    for item in records:
        parsed_records.append((item.get("type", "unknown"), item.get("payload", {})))
    summary = ingest_records(parsed_records, source="outbox")
    return {"ok": True, "received": len(parsed_records), **summary}


@app.get("/api/devices", response_model=list[DeviceSummary])
def list_devices():
    return get_devices()


@app.get("/api/metrics/realtime", response_model=list[RealtimeMetric])
def realtime_metrics():
    return get_realtime_metrics()


@app.get("/api/metrics/history", response_model=HistoryResponse)
def metric_history(
    device_id: str = Query(..., description="Device identifier, e.g. cpu0"),
    limit: int = Query(120, ge=10, le=1000),
):
    return {"device_id": device_id, "points": get_history(device_id=device_id, limit=limit)}


@app.get("/api/metrics/compare", response_model=CompareHistoryResponse)
def compare_history(
    device_ids: str = Query("", description="Comma-separated device ids"),
    limit: int = Query(120, ge=10, le=1000),
):
    parsed_ids = [item.strip() for item in device_ids.split(",") if item.strip()]
    return get_compare_history(device_ids=parsed_ids, limit=limit)


@app.get("/api/metrics/logs", response_model=list[LogRecord])
def metric_logs(limit: int = Query(80, ge=10, le=500)):
    return get_recent_logs(limit=limit)


@app.get("/api/events", response_model=list[EventRecord])
def list_events(
    device_id: Optional[str] = Query(None, description="Optional device identifier"),
    severity: Optional[str] = Query(None, description="Optional severity filter"),
    limit: int = Query(100, ge=10, le=500),
):
    return get_events(device_id=device_id, severity=severity, limit=limit)


@app.get("/api/alerts/summary", response_model=AlertSummary)
def alert_summary():
    return get_alert_summary()


@app.get("/api/alerts", response_model=list[AlertRecord])
def list_alerts(
    status: Optional[str] = Query(None, description="Optional status filter, supports comma-separated values"),
    device_id: Optional[str] = Query(None, description="Optional device identifier"),
    severity: Optional[str] = Query(None, description="Optional severity filter"),
    rule_key: Optional[str] = Query(None, description="Optional rule key filter"),
    limit: int = Query(200, ge=10, le=500),
):
    return query_alerts(
        status=status,
        device_id=device_id,
        severity=severity,
        rule_key=rule_key,
        limit=limit,
    )


@app.get("/api/alerts/trends")
def alert_trends(hours: int = Query(24, ge=1, le=168)):
    return get_alert_trends(hours=hours)


@app.post("/api/alerts/{alert_id}/acknowledge", response_model=AlertRecord)
def alert_acknowledge(alert_id: int, payload: AlertActionRequest):
    try:
        alert = acknowledge_alert(alert_id=alert_id, operator=payload.operator)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return alert


@app.post("/api/alerts/batch/acknowledge", response_model=AlertBatchActionResult)
def alert_batch_acknowledge(payload: AlertBatchActionRequest):
    _ensure_alert_ids(payload.alert_ids)
    return batch_acknowledge_alerts(alert_ids=payload.alert_ids, operator=payload.operator)


@app.post("/api/alerts/{alert_id}/silence", response_model=AlertRecord)
def alert_silence(alert_id: int, payload: AlertSilenceRequest):
    try:
        alert = silence_alert(alert_id=alert_id, minutes=payload.minutes, operator=payload.operator)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return alert


@app.post("/api/alerts/batch/silence", response_model=AlertBatchActionResult)
def alert_batch_silence(payload: AlertBatchSilenceRequest):
    _ensure_alert_ids(payload.alert_ids)
    return batch_silence_alerts(
        alert_ids=payload.alert_ids,
        minutes=payload.minutes,
        operator=payload.operator,
    )


@app.post("/api/alerts/{alert_id}/unsilence", response_model=AlertRecord)
def alert_unsilence(alert_id: int, payload: AlertActionRequest):
    try:
        alert = unsilence_alert(alert_id=alert_id, operator=payload.operator)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return alert


@app.get("/api/alert-rules", response_model=list[AlertRuleRecord])
def alert_rules():
    return get_rules()


@app.get("/api/alert-rules/export", response_model=AlertRuleExportResponse)
def alert_rule_export():
    return export_rules()


@app.post("/api/alert-rules", response_model=AlertRuleRecord)
def alert_rule_create(payload: AlertRuleCreateRequest):
    normalized = _model_to_dict(payload)
    _validate_rule_definition(normalized)
    try:
        return create_rule(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.patch("/api/alert-rules/{rule_key}", response_model=AlertRuleRecord)
def alert_rule_update(rule_key: str, payload: AlertRuleUpdateRequest):
    existing = next((item for item in get_rules() if item["rule_key"] == rule_key), None)
    if existing is None:
        raise HTTPException(status_code=404, detail="alert rule not found")
    updates = _model_to_dict(payload, exclude_unset=True)
    merged = {**existing, **updates}
    _validate_rule_definition(merged)
    updated = update_rule(rule_key=rule_key, updates=updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="alert rule not found")
    return updated


@app.delete("/api/alert-rules/{rule_key}", response_model=AlertRuleRecord)
def alert_rule_delete(rule_key: str, payload: AlertRuleDeleteRequest):
    deleted = delete_rule(rule_key=rule_key, operator=payload.operator)
    if deleted is None:
        raise HTTPException(status_code=404, detail="alert rule not found")
    return deleted


@app.post("/api/alert-rules/import", response_model=AlertRuleImportResult)
def alert_rule_import(payload: AlertRuleImportRequest):
    normalized = _model_to_dict(payload)
    rules = normalized.get("rules", [])
    for rule in rules:
        _validate_rule_definition(rule)
    try:
        return import_rules(
            rules=rules,
            mode=normalized["mode"],
            operator=normalized["operator"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/scheduler/config", response_model=SchedulerConfig)
def scheduler_config():
    return {
        "mode": "evolution",
        "t_min": 0.5,
        "t_max": 8.0,
        "control_dimensions": ["urgency", "field_priority", "execution_pressure"],
        "phase_order": ["聚焦采样", "恢复观测", "巡航巡检", "边端降级"],
        "slow_refresh_cycles": 5,
    }


@app.get("/api/dashboard/overview", response_model=DashboardOverview)
def dashboard_overview():
    return get_dashboard_overview()


@app.get("/api/experiments/evaluation")
def experiment_evaluation(report_path: Optional[str] = None):
    report = get_experiment_evaluation_report(report_path=report_path)
    if report is None:
        raise HTTPException(status_code=404, detail="evaluation report not found")
    return report


@app.get("/api/control/status", response_model=ControlStatusResponse)
def control_status():
    return control_service.get_status()


@app.post("/api/control/trace", response_model=ControlJob)
def control_generate_trace(payload: ReplayTraceRequest):
    try:
        return control_service.start_trace_generation(
            duration=payload.duration,
            step=payload.step,
            seed=payload.seed,
        )
    except ControlBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/control/replay-compare", response_model=ControlJob)
def control_replay_compare(payload: ReplayCompareRequest, request: Request):
    try:
        return control_service.start_replay_compare(
            base_url=str(request.base_url).rstrip("/"),
            devices=payload.devices,
            gpu_vendor=payload.gpu_vendor,
            npu_backend=payload.npu_backend,
            duration=payload.duration,
            fixed_interval=payload.fixed_interval,
            t_min=payload.t_min,
            t_max=payload.t_max,
            regenerate_trace=payload.regenerate_trace,
            trace_duration=payload.trace_duration,
            trace_step=payload.trace_step,
            trace_seed=payload.trace_seed,
        )
    except ControlBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/control/live", response_model=ControlJob)
def control_live_collection(payload: LiveCollectionRequest, request: Request):
    try:
        return control_service.start_live_collection(
            base_url=str(request.base_url).rstrip("/"),
            devices=payload.devices,
            gpu_vendor=payload.gpu_vendor,
            npu_backend=payload.npu_backend,
            mode=payload.mode,
            duration=payload.duration,
            fixed_interval=payload.fixed_interval,
            t_min=payload.t_min,
            t_max=payload.t_max,
        )
    except ControlBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/control/cancel", response_model=ControlJob)
def control_cancel():
    try:
        return control_service.cancel_active_job()
    except NoActiveJobError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


if (FRONTEND_DIST_DIR / "index.html").exists():
    app.mount("/", SPAStaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:
    @app.get("/", include_in_schema=False)
    def frontend_placeholder():
        return PlainTextResponse(
            "Frontend build not found. Run `npm run build` in frontend or use `start_system.ps1` first.",
            status_code=503,
        )
