from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class DeviceSummary(BaseModel):
    device_id: str
    device_type: str
    status: str
    latest_timestamp: Optional[str] = None
    utilization: Optional[float] = None
    chip_temp_c: Optional[float] = None
    power_w: Optional[float] = None
    sample_interval_s: Optional[float] = None
    evolution_score: Optional[float] = None
    phase: Optional[str] = None
    field_policy: Optional[str] = None
    transport_policy: Optional[str] = None
    control_score: Optional[float] = None


class RealtimeMetric(BaseModel):
    device_id: str
    timestamp: Optional[str] = None
    utilization: Optional[float] = None
    chip_temp_c: Optional[float] = None
    power_w: Optional[float] = None
    sample_interval_s: Optional[float] = None
    evolution_score: Optional[float] = None
    phase: Optional[str] = None
    field_policy: Optional[str] = None
    transport_policy: Optional[str] = None
    control_score: Optional[float] = None
    status: str


class HistoryPoint(BaseModel):
    timestamp: Optional[str] = None
    time: Optional[float] = None
    utilization: Optional[float] = None
    chip_temp_c: Optional[float] = None
    power_w: Optional[float] = None
    sample_interval_s: Optional[float] = None
    evolution_score: Optional[float] = None
    field_priority_score: Optional[float] = None
    execution_pressure_score: Optional[float] = None
    control_score: Optional[float] = None
    interval: Optional[float] = None
    phase: Optional[str] = None
    field_policy: Optional[str] = None
    transport_policy: Optional[str] = None
    status: str


class HistoryResponse(BaseModel):
    device_id: str
    points: List[HistoryPoint]


class CompareHistoryResponse(BaseModel):
    device_ids: List[str]
    series: dict[str, List[HistoryPoint]]

class SchedulerConfig(BaseModel):
    mode: str = "evolution"
    t_min: float
    t_max: float
    control_dimensions: List[str]
    phase_order: List[str]
    slow_refresh_cycles: int


class DashboardOverview(BaseModel):
    device_total: int
    online_count: int
    high_risk_count: int
    avg_interval: float
    active_alerts: int
    event_total: int
    elevated_event_total: int
    outbox_pending: int
    outbox_dead: int
    latest_realtime: List[RealtimeMetric]


class LogRecord(BaseModel):
    line: str
    device_id: str
    timestamp: Optional[str] = None


class EventRecord(BaseModel):
    timestamp: Optional[str] = None
    time: Optional[float] = None
    device_id: str
    event_type: str
    severity: str
    message: str
    detail: Optional[str] = None
    source: Optional[str] = None


class AlertRecord(BaseModel):
    id: int
    device_id: str
    rule_key: str
    title: str
    severity: str
    status: str
    message: str
    first_seen_at: float
    last_seen_at: float
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[float] = None
    silenced_until: Optional[float] = None
    closed_at: Optional[float] = None
    event_count: int
    last_value: Optional[float] = None
    silence_remaining_seconds: Optional[int] = None
    silence_expired: bool = False


class AlertSeverityBreakdown(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class AlertSummary(BaseModel):
    total: int
    active_total: int
    open_total: int
    acknowledged_total: int
    silenced_total: int
    resolved_total: int
    expired_silence_total: int
    expiring_silence_total: int
    rule_total: int
    enabled_rule_total: int
    disabled_rule_total: int
    active_by_severity: AlertSeverityBreakdown


class AlertActionRequest(BaseModel):
    operator: str = "console"


class AlertSilenceRequest(AlertActionRequest):
    minutes: int = Field(default=30, ge=1, le=10080)


class AlertBatchActionRequest(AlertActionRequest):
    alert_ids: List[int] = Field(default_factory=list)


class AlertBatchSilenceRequest(AlertBatchActionRequest):
    minutes: int = Field(default=30, ge=1, le=10080)


class AlertBatchFailure(BaseModel):
    alert_id: int
    reason: str


class AlertBatchActionResult(BaseModel):
    action: str
    requested_count: int
    updated_count: int
    alerts: List[AlertRecord]
    failed: List[AlertBatchFailure]


class AlertRuleRecord(BaseModel):
    rule_key: str
    title: str
    rule_source: Literal["metric", "event"]
    field_name: str
    operator: Literal["ge", "gt", "eq", "ne"]
    threshold_value: Optional[float] = None
    threshold_text: Optional[str] = None
    severity: Literal["high", "medium", "low", "info"]
    enabled: bool
    auto_resolve: bool
    message_template: Optional[str] = None


class AlertRuleCreateRequest(BaseModel):
    rule_key: str
    title: str
    rule_source: Literal["metric", "event"]
    field_name: str
    operator: Literal["ge", "gt", "eq", "ne"]
    threshold_value: Optional[float] = None
    threshold_text: Optional[str] = None
    severity: Literal["high", "medium", "low", "info"]
    enabled: bool = True
    auto_resolve: bool = True
    message_template: Optional[str] = None


class AlertRuleUpdateRequest(BaseModel):
    title: Optional[str] = None
    rule_source: Optional[Literal["metric", "event"]] = None
    field_name: Optional[str] = None
    operator: Optional[Literal["ge", "gt", "eq", "ne"]] = None
    threshold_value: Optional[float] = None
    threshold_text: Optional[str] = None
    severity: Optional[Literal["high", "medium", "low", "info"]] = None
    enabled: Optional[bool] = None
    auto_resolve: Optional[bool] = None
    message_template: Optional[str] = None


class AlertRuleDeleteRequest(BaseModel):
    operator: str = "console"


class AlertRuleImportRequest(BaseModel):
    rules: List[AlertRuleCreateRequest]
    mode: Literal["merge", "replace"] = "merge"
    operator: str = "console"


class AlertRuleImportResult(BaseModel):
    mode: Literal["merge", "replace"]
    requested_count: int
    created_count: int
    updated_count: int
    deleted_count: int
    rules: List[AlertRuleRecord]


class AlertRuleExportResponse(BaseModel):
    exported_at: str
    rule_count: int
    rules: List[AlertRuleRecord]


class ReplayTraceRequest(BaseModel):
    duration: float = 120.0
    step: float = 0.5
    seed: int = 20260407


class ReplayCompareRequest(BaseModel):
    devices: str = "all"
    gpu_vendor: Literal["auto", "nvidia", "intel"] = "auto"
    npu_backend: Literal["auto", "ascend", "openharmony_hdc", "rockchip_sysfs"] = "auto"
    duration: float = 85.0
    fixed_interval: float = 5.0
    t_min: float = 0.5
    t_max: float = 8.0
    regenerate_trace: bool = False
    trace_duration: float = 120.0
    trace_step: float = 0.5
    trace_seed: int = 20260407


class LiveCollectionRequest(BaseModel):
    devices: str = "cpu"
    gpu_vendor: Literal["auto", "nvidia", "intel"] = "auto"
    npu_backend: Literal["auto", "ascend", "openharmony_hdc", "rockchip_sysfs"] = "auto"
    mode: Literal["fixed", "evolution"] = "evolution"
    duration: float = 60.0
    fixed_interval: float = 5.0
    t_min: float = 0.5
    t_max: float = 8.0


class ControlFileState(BaseModel):
    exists: bool
    path: str
    updated_at: Optional[str] = None
    size_bytes: Optional[int] = None
    secondary_path: Optional[str] = None
    secondary_exists: Optional[bool] = None


class ControlStep(BaseModel):
    key: str
    label: str
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None


class ControlJob(BaseModel):
    id: str
    kind: str
    title: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    current_step: Optional[str] = None
    cancel_requested: bool = False
    active_pid: Optional[int] = None
    parameters: dict[str, Any]
    steps: List[ControlStep]
    artifacts: dict[str, str]
    log_lines: List[str]


class ControlServiceState(BaseModel):
    started_at: str
    python_path: str
    frontend_dist_ready: bool
    frontend_dist_path: str


class ControlStatusResponse(BaseModel):
    service: ControlServiceState
    trace: ControlFileState
    latest_report: ControlFileState
    active_job: Optional[ControlJob] = None
    recent_jobs: List[ControlJob]
