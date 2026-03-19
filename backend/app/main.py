import gzip
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .data_service import (
    bootstrap_database,
    get_compare_history,
    get_dashboard_overview,
    get_devices,
    get_experiment_evaluation_report,
    get_history,
    get_recent_logs,
    get_realtime_metrics,
    ingest_records,
)
from .schemas import (
    CompareHistoryResponse,
    DashboardOverview,
    DeviceSummary,
    HistoryResponse,
    LogRecord,
    RealtimeMetric,
    SchedulerConfig,
)


app = FastAPI(
    title="HAVFS Visualization API",
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


@app.get("/api/scheduler/config", response_model=SchedulerConfig)
def scheduler_config():
    return {
        "mode": "havfs",
        "t_min": 0.5,
        "t_max": 5.0,
        "enter_high": 0.4,
        "exit_high": 0.2,
        "static_limit": 80.0,
        "risk_dimensions": ["anomaly", "jump", "pressure", "drift"],
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
