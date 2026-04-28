import type {
  AlertActionPayload,
  AlertBatchActionPayload,
  AlertBatchActionResult,
  AlertBatchSilencePayload,
  AlertRecord,
  AlertRuleExportResponse,
  AlertRuleCreatePayload,
  AlertRuleImportPayload,
  AlertRuleImportResult,
  AlertRuleRecord,
  AlertRuleUpdatePayload,
  AlertSilencePayload,
  AlertSummary,
  AlertTrendResponse,
  CompareHistoryResponse,
  ControlJob,
  ControlStatusResponse,
  DashboardOverview,
  DeviceSummary,
  EventRecord,
  ExperimentEvaluationReport,
  HistoryResponse,
  LiveCollectionPayload,
  LogRecord,
  RealtimeMetric,
  ReplayComparePayload,
  ReplayTracePayload,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function resolveApiUrl(path: string) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(resolveApiUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const body = await response.json().catch(() => null);
      if (body && typeof body === "object") {
        message = String((body as { detail?: string }).detail ?? message);
      }
    } else {
      const text = await response.text().catch(() => "");
      if (text) {
        message = text;
      }
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getOverview: () => fetchJson<DashboardOverview>("/api/dashboard/overview"),
  getDevices: () => fetchJson<DeviceSummary[]>("/api/devices"),
  getRealtime: () => fetchJson<RealtimeMetric[]>("/api/metrics/realtime"),
  getHistory: (deviceId: string, limit = 120) =>
    fetchJson<HistoryResponse>(`/api/metrics/history?device_id=${encodeURIComponent(deviceId)}&limit=${limit}`),
  getCompareHistory: (deviceIds: string[], limit = 120) =>
    fetchJson<CompareHistoryResponse>(
      `/api/metrics/compare?device_ids=${encodeURIComponent(deviceIds.join(","))}&limit=${limit}`
    ),
  getLogs: (limit = 80) => fetchJson<LogRecord[]>(`/api/metrics/logs?limit=${limit}`),
  getEvents: (limit = 100, deviceId?: string, severity?: string) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (deviceId) {
      params.set("device_id", deviceId);
    }
    if (severity) {
      params.set("severity", severity);
    }
    return fetchJson<EventRecord[]>(`/api/events?${params.toString()}`);
  },
  getAlertSummary: () => fetchJson<AlertSummary>("/api/alerts/summary"),
  getAlerts: (params?: { status?: string; deviceId?: string; severity?: string; ruleKey?: string; limit?: number }) => {
    const query = new URLSearchParams();
    query.set("limit", String(params?.limit ?? 200));
    if (params?.status) {
      query.set("status", params.status);
    }
    if (params?.deviceId) {
      query.set("device_id", params.deviceId);
    }
    if (params?.severity) {
      query.set("severity", params.severity);
    }
    if (params?.ruleKey) {
      query.set("rule_key", params.ruleKey);
    }
    return fetchJson<AlertRecord[]>(`/api/alerts?${query.toString()}`);
  },
  getAlertTrends: (hours = 24) => fetchJson<AlertTrendResponse>(`/api/alerts/trends?hours=${hours}`),
  acknowledgeAlert: (alertId: number, payload: AlertActionPayload) =>
    fetchJson<AlertRecord>(`/api/alerts/${alertId}/acknowledge`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  batchAcknowledgeAlerts: (payload: AlertBatchActionPayload) =>
    fetchJson<AlertBatchActionResult>("/api/alerts/batch/acknowledge", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  silenceAlert: (alertId: number, payload: AlertSilencePayload) =>
    fetchJson<AlertRecord>(`/api/alerts/${alertId}/silence`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  batchSilenceAlerts: (payload: AlertBatchSilencePayload) =>
    fetchJson<AlertBatchActionResult>("/api/alerts/batch/silence", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  unsilenceAlert: (alertId: number, payload: AlertActionPayload) =>
    fetchJson<AlertRecord>(`/api/alerts/${alertId}/unsilence`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAlertRules: () => fetchJson<AlertRuleRecord[]>("/api/alert-rules"),
  exportAlertRules: () => fetchJson<AlertRuleExportResponse>("/api/alert-rules/export"),
  createAlertRule: (payload: AlertRuleCreatePayload) =>
    fetchJson<AlertRuleRecord>("/api/alert-rules", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAlertRule: (ruleKey: string, payload: AlertRuleUpdatePayload) =>
    fetchJson<AlertRuleRecord>(`/api/alert-rules/${encodeURIComponent(ruleKey)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteAlertRule: (ruleKey: string, payload: AlertActionPayload) =>
    fetchJson<AlertRuleRecord>(`/api/alert-rules/${encodeURIComponent(ruleKey)}`, {
      method: "DELETE",
      body: JSON.stringify(payload),
    }),
  importAlertRules: (payload: AlertRuleImportPayload) =>
    fetchJson<AlertRuleImportResult>("/api/alert-rules/import", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getExperimentEvaluation: () => fetchJson<ExperimentEvaluationReport>("/api/experiments/evaluation"),
  getControlStatus: () => fetchJson<ControlStatusResponse>("/api/control/status"),
  generateReplayTrace: (payload: ReplayTracePayload) =>
    fetchJson<ControlJob>("/api/control/trace", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startReplayCompare: (payload: ReplayComparePayload) =>
    fetchJson<ControlJob>("/api/control/replay-compare", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startLiveCollection: (payload: LiveCollectionPayload) =>
    fetchJson<ControlJob>("/api/control/live", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cancelActiveJob: () =>
    fetchJson<ControlJob>("/api/control/cancel", {
      method: "POST",
      body: JSON.stringify({}),
    }),
};
