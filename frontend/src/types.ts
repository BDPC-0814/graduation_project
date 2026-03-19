export type RealtimeMetric = {
  device_id: string;
  timestamp?: string | null;
  utilization?: number | null;
  chip_temp_c?: number | null;
  power_w?: number | null;
  sample_interval_s?: number | null;
  risk_score?: number | null;
  state?: string | null;
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
  risk_score?: number | null;
  interval?: number | null;
  state?: string | null;
  status: string;
  risk_anomaly?: number | null;
  risk_jump?: number | null;
  risk_pressure?: number | null;
  risk_drift?: number | null;
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

export type DashboardOverview = {
  device_total: number;
  online_count: number;
  high_risk_count: number;
  avg_interval: number;
  active_alerts: number;
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
};

export type ExperimentEvaluationReport = {
  generated_at: string;
  summary: {
    sample_count: {
      fixed: number;
      havfs: number;
      reduction_percent?: number | null;
    };
    redundancy_rate_percent: {
      fixed?: number | null;
      havfs?: number | null;
    };
    interval_stats_s: {
      fixed: ExperimentModeStats;
      havfs: ExperimentModeStats;
    };
    overhead_stats: {
      fixed: ExperimentModeStats;
      havfs: ExperimentModeStats;
    };
    latency_stats_s: {
      fixed: ExperimentModeStats;
      havfs: ExperimentModeStats;
    };
  };
  charts: {
    utilization_time: ExperimentChart;
    interval_time: ExperimentChart;
    latency_cdf: ExperimentChart;
    redundancy_time: ExperimentChart;
  };
};
