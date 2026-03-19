from typing import List, Optional

from pydantic import BaseModel


class DeviceSummary(BaseModel):
    device_id: str
    device_type: str
    status: str
    latest_timestamp: Optional[str] = None
    utilization: Optional[float] = None
    chip_temp_c: Optional[float] = None
    power_w: Optional[float] = None
    sample_interval_s: Optional[float] = None
    risk_score: Optional[float] = None
    state: Optional[str] = None


class RealtimeMetric(BaseModel):
    device_id: str
    timestamp: Optional[str] = None
    utilization: Optional[float] = None
    chip_temp_c: Optional[float] = None
    power_w: Optional[float] = None
    sample_interval_s: Optional[float] = None
    risk_score: Optional[float] = None
    state: Optional[str] = None
    status: str


class HistoryPoint(BaseModel):
    timestamp: Optional[str] = None
    time: Optional[float] = None
    utilization: Optional[float] = None
    chip_temp_c: Optional[float] = None
    power_w: Optional[float] = None
    sample_interval_s: Optional[float] = None
    risk_score: Optional[float] = None
    interval: Optional[float] = None
    state: Optional[str] = None
    status: str
    risk_anomaly: Optional[float] = None
    risk_jump: Optional[float] = None
    risk_pressure: Optional[float] = None
    risk_drift: Optional[float] = None


class HistoryResponse(BaseModel):
    device_id: str
    points: List[HistoryPoint]


class CompareHistoryResponse(BaseModel):
    device_ids: List[str]
    series: dict[str, List[HistoryPoint]]

class SchedulerConfig(BaseModel):
    mode: str = "havfs"
    t_min: float
    t_max: float
    enter_high: float
    exit_high: float
    static_limit: float
    risk_dimensions: List[str]


class DashboardOverview(BaseModel):
    device_total: int
    online_count: int
    high_risk_count: int
    avg_interval: float
    active_alerts: int
    outbox_pending: int
    outbox_dead: int
    latest_realtime: List[RealtimeMetric]


class LogRecord(BaseModel):
    line: str
    device_id: str
    timestamp: Optional[str] = None
