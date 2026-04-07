import type {
  CompareHistoryResponse,
  DashboardOverview,
  DeviceSummary,
  EventRecord,
  ExperimentEvaluationReport,
  HistoryResponse,
  LogRecord,
  RealtimeMetric,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8001";

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
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
  getExperimentEvaluation: () => fetchJson<ExperimentEvaluationReport>("/api/experiments/evaluation"),
};
