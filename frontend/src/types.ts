export type RealtimeMetric = {
  device_id: string;
  timestamp?: string | null;
  utilization?: number | null;
  chip_temp_c?: number | null;
  power_w?: number | null;
  sample_interval_s?: number | null;
  evolution_score?: number | null;
  phase?: string | null;
  field_policy?: string | null;
  transport_policy?: string | null;
  control_score?: number | null;
  status: string;
};

export type DeviceSummary = RealtimeMetric & {
  device_type: string;
  latest_timestamp?: string | null;
};

export type HistoryPoint = {
  timestamp?: string | null;
  time?: number | null;
  utilization?: number | null;
  chip_temp_c?: number | null;
  power_w?: number | null;
  sample_interval_s?: number | null;
  evolution_score?: number | null;
  field_priority_score?: number | null;
  execution_pressure_score?: number | null;
  control_score?: number | null;
  interval?: number | null;
  phase?: string | null;
  field_policy?: string | null;
  transport_policy?: string | null;
  status: string;
};

export type HistoryResponse = {
  device_id: string;
  points: HistoryPoint[];
};

export type CompareHistoryResponse = {
  device_ids: string[];
  series: Record<string, HistoryPoint[]>;
};

export type LogRecord = {
  line: string;
  device_id: string;
  timestamp?: string | null;
};

export type EventRecord = {
  timestamp?: string | null;
  time?: number | null;
  device_id: string;
  event_type: string;
  severity: string;
  message: string;
  detail?: string | null;
  source?: string | null;
};

export type AlertRecord = {
  id: number;
  device_id: string;
  rule_key: string;
  title: string;
  severity: string;
  status: string;
  message: string;
  first_seen_at: number;
  last_seen_at: number;
  acknowledged_by?: string | null;
  acknowledged_at?: number | null;
  silenced_until?: number | null;
  closed_at?: number | null;
  event_count: number;
  last_value?: number | null;
  silence_remaining_seconds?: number | null;
  silence_expired: boolean;
};

export type AlertSeverityBreakdown = {
  high: number;
  medium: number;
  low: number;
  info: number;
  [key: string]: number;
};

export type AlertSummary = {
  total: number;
  active_total: number;
  open_total: number;
  acknowledged_total: number;
  silenced_total: number;
  resolved_total: number;
  expired_silence_total: number;
  expiring_silence_total: number;
  rule_total: number;
  enabled_rule_total: number;
  disabled_rule_total: number;
  active_by_severity: AlertSeverityBreakdown;
};

export type AlertTrendResponse = {
  buckets: string[];
  opened: number[];
  resolved: number[];
};

export type AlertRuleRecord = {
  rule_key: string;
  title: string;
  rule_source: "metric" | "event";
  field_name: string;
  operator: "ge" | "gt" | "eq" | "ne";
  threshold_value?: number | null;
  threshold_text?: string | null;
  severity: "high" | "medium" | "low" | "info";
  enabled: boolean;
  auto_resolve: boolean;
  message_template?: string | null;
};

export type AlertActionPayload = {
  operator: string;
};

export type AlertSilencePayload = AlertActionPayload & {
  minutes: number;
};

export type AlertBatchActionPayload = AlertActionPayload & {
  alert_ids: number[];
};

export type AlertBatchSilencePayload = AlertBatchActionPayload & {
  minutes: number;
};

export type AlertBatchFailure = {
  alert_id: number;
  reason: string;
};

export type AlertBatchActionResult = {
  action: string;
  requested_count: number;
  updated_count: number;
  alerts: AlertRecord[];
  failed: AlertBatchFailure[];
};

export type AlertRuleCreatePayload = {
  rule_key: string;
  title: string;
  rule_source: "metric" | "event";
  field_name: string;
  operator: "ge" | "gt" | "eq" | "ne";
  threshold_value?: number | null;
  threshold_text?: string | null;
  severity: "high" | "medium" | "low" | "info";
  enabled: boolean;
  auto_resolve: boolean;
  message_template?: string | null;
};

export type AlertRuleUpdatePayload = Partial<Omit<AlertRuleCreatePayload, "rule_key">>;

export type AlertRuleImportPayload = {
  rules: AlertRuleCreatePayload[];
  mode: "merge" | "replace";
  operator: string;
};

export type AlertRuleImportResult = {
  mode: "merge" | "replace";
  requested_count: number;
  created_count: number;
  updated_count: number;
  deleted_count: number;
  rules: AlertRuleRecord[];
};

export type AlertRuleExportResponse = {
  exported_at: string;
  rule_count: number;
  rules: AlertRuleRecord[];
};

export type DashboardOverview = {
  device_total: number;
  online_count: number;
  high_risk_count: number;
  avg_interval: number;
  active_alerts: number;
  event_total: number;
  elevated_event_total: number;
  outbox_pending: number;
  outbox_dead: number;
  latest_realtime: RealtimeMetric[];
};

export type ExperimentChartSeries = {
  name: string;
  data: Array<number | null>;
};

export type ExperimentChart = {
  title: string;
  labels: string[];
  series: ExperimentChartSeries[];
  y_axis_name?: string | null;
};

export type ExperimentModeStats = {
  count?: number | null;
  p50_s?: number | null;
  p95_s?: number | null;
  mean_s?: number | null;
  median_s?: number | null;
  std_s?: number | null;
  min_s?: number | null;
  max_s?: number | null;
  cpu_mean_percent?: number | null;
  cpu_p95_percent?: number | null;
  mem_mean_mb?: number | null;
  mem_p95_mb?: number | null;
  slow_lane_ratio_percent?: number | null;
  buffered_transport_ratio_percent?: number | null;
  focus_phase_ratio_percent?: number | null;
  execution_pressure_mean?: number | null;
};

export type ExperimentEvaluationReport = {
  generated_at: string;
  summary: {
    sample_count: {
      fixed: number;
      evolution: number;
      reduction_percent?: number | null;
    };
    redundancy_rate_percent: {
      fixed?: number | null;
      evolution?: number | null;
    };
    interval_stats_s: {
      fixed: ExperimentModeStats;
      evolution: ExperimentModeStats;
    };
    overhead_stats: {
      fixed: ExperimentModeStats;
      evolution: ExperimentModeStats;
    };
    behavior_stats: {
      fixed: ExperimentModeStats;
      evolution: ExperimentModeStats;
    };
    latency_stats_s: {
      fixed: ExperimentModeStats;
      evolution: ExperimentModeStats;
    };
  };
  charts: {
    utilization_time: ExperimentChart;
    interval_time: ExperimentChart;
    latency_cdf: ExperimentChart;
    redundancy_time: ExperimentChart;
  };
};

export type ReplayTracePayload = {
  duration: number;
  step: number;
  seed: number;
};

export type ReplayComparePayload = {
  devices: string;
  gpu_vendor: "auto" | "nvidia" | "intel";
  npu_backend: "auto" | "ascend" | "openharmony_hdc" | "rockchip_sysfs";
  duration: number;
  fixed_interval: number;
  t_min: number;
  t_max: number;
  regenerate_trace: boolean;
  trace_duration: number;
  trace_step: number;
  trace_seed: number;
};

export type LiveCollectionPayload = {
  devices: string;
  gpu_vendor: "auto" | "nvidia" | "intel";
  npu_backend: "auto" | "ascend" | "openharmony_hdc" | "rockchip_sysfs";
  mode: "fixed" | "evolution";
  duration: number;
  fixed_interval: number;
  t_min: number;
  t_max: number;
};

export type ControlFileState = {
  exists: boolean;
  path: string;
  updated_at?: string | null;
  size_bytes?: number | null;
  secondary_path?: string | null;
  secondary_exists?: boolean | null;
};

export type ControlStep = {
  key: string;
  label: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  exit_code?: number | null;
};

export type ControlJob = {
  id: string;
  kind: string;
  title: string;
  status: string;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  current_step?: string | null;
  cancel_requested: boolean;
  active_pid?: number | null;
  parameters: Record<string, string | number | boolean | null>;
  steps: ControlStep[];
  artifacts: Record<string, string>;
  log_lines: string[];
};

export type ControlStatusResponse = {
  service: {
    started_at: string;
    python_path: string;
    frontend_dist_ready: boolean;
    frontend_dist_path: string;
  };
  trace: ControlFileState;
  latest_report: ControlFileState;
  active_job?: ControlJob | null;
  recent_jobs: ControlJob[];
};
