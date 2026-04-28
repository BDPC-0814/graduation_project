import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from "react";

import { api } from "../api";
import { LineChart } from "../charts/LineChart";
import { usePollingData } from "../hooks";
import type {
  AlertBatchActionResult,
  AlertRecord,
  AlertRuleCreatePayload,
  AlertRuleRecord,
  AlertRuleUpdatePayload,
  AlertSummary,
  AlertTrendResponse,
} from "../types";

type FeedbackTone = "info" | "error";
type AlertStatusFilter = "all" | "active" | "open" | "acknowledged" | "silenced" | "resolved";
type AlertSeverity = "high" | "medium" | "low" | "info";
type RuleSource = "metric" | "event";
type RuleOperator = "ge" | "gt" | "eq" | "ne";
type RuleImportMode = "merge" | "replace";

type FeedbackState = {
  tone: FeedbackTone;
  message: string;
};

type AlertRuleDraft = {
  rule_key: string;
  title: string;
  rule_source: RuleSource;
  field_name: string;
  operator: RuleOperator;
  threshold_value: string;
  threshold_text: string;
  severity: AlertSeverity;
  enabled: boolean;
  auto_resolve: boolean;
  message_template: string;
};

const statusOptions: Array<{ value: AlertStatusFilter; label: string }> = [
  { value: "active", label: "活动告警" },
  { value: "open", label: "待处理" },
  { value: "acknowledged", label: "已确认" },
  { value: "silenced", label: "静默中" },
  { value: "resolved", label: "已恢复" },
  { value: "all", label: "全部" },
];

const severityOptions: Array<{ value: "all" | AlertSeverity; label: string }> = [
  { value: "all", label: "全部等级" },
  { value: "high", label: "高" },
  { value: "medium", label: "中" },
  { value: "low", label: "低" },
  { value: "info", label: "提示" },
];

const ruleSourceOptions: Array<{ value: RuleSource; label: string }> = [
  { value: "metric", label: "metric" },
  { value: "event", label: "event" },
];

const operatorOptions: Array<{ value: RuleOperator; label: string }> = [
  { value: "ge", label: "ge (大于等于)" },
  { value: "gt", label: "gt (大于)" },
  { value: "eq", label: "eq (等于)" },
  { value: "ne", label: "ne (不等于)" },
];

const importModeOptions: Array<{ value: RuleImportMode; label: string; hint: string }> = [
  { value: "merge", label: "合并导入", hint: "保留现有规则，对同名规则执行更新" },
  { value: "replace", label: "覆盖导入", hint: "用导入文件替换现有规则集，缺失规则会被删除" },
];

const operatorLabels: Record<RuleOperator, string> = {
  ge: ">=",
  gt: ">",
  eq: "=",
  ne: "!=",
};

const severityLabels: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
  info: "提示",
};

const statusLabels: Record<string, string> = {
  open: "待处理",
  acknowledged: "已确认",
  silenced: "静默中",
  resolved: "已恢复",
};

const emptyRuleDraft: AlertRuleDraft = {
  rule_key: "",
  title: "",
  rule_source: "metric",
  field_name: "",
  operator: "ge",
  threshold_value: "",
  threshold_text: "",
  severity: "medium",
  enabled: true,
  auto_resolve: true,
  message_template: "{field}={value}",
};

function formatDateTime(value?: number | null) {
  if (value === null || value === undefined) {
    return "--";
  }
  return new Date(value * 1000).toLocaleString("zh-CN", { hour12: false });
}

function formatNumber(value?: number | null, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(digits);
}

function formatSilenceCountdown(seconds?: number | null) {
  if (seconds === null || seconds === undefined) {
    return "--";
  }
  if (seconds <= 0) {
    return "已到期";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function toRuleDraft(rule: AlertRuleRecord): AlertRuleDraft {
  return {
    rule_key: rule.rule_key,
    title: rule.title,
    rule_source: rule.rule_source,
    field_name: rule.field_name,
    operator: rule.operator,
    threshold_value: rule.threshold_value === null || rule.threshold_value === undefined ? "" : String(rule.threshold_value),
    threshold_text: rule.threshold_text ?? "",
    severity: rule.severity,
    enabled: rule.enabled,
    auto_resolve: rule.auto_resolve,
    message_template: rule.message_template ?? "",
  };
}

function validateRuleDraft(draft: AlertRuleDraft, isCreate: boolean) {
  if (isCreate && !draft.rule_key.trim()) {
    return "请填写规则键名";
  }
  if (!draft.title.trim()) {
    return "请填写规则标题";
  }
  if (!draft.field_name.trim()) {
    return "请填写字段名";
  }
  if ((draft.operator === "ge" || draft.operator === "gt") && draft.threshold_value.trim() === "") {
    return "数值比较规则需要填写阈值";
  }
  if ((draft.operator === "eq" || draft.operator === "ne") && draft.threshold_text.trim() === "") {
    return "文本比较规则需要填写文本阈值";
  }
  return null;
}

function toCreatePayload(draft: AlertRuleDraft): AlertRuleCreatePayload {
  const normalizedThresholdText = draft.threshold_text.trim();
  const normalizedTemplate = draft.message_template.trim();
  return {
    rule_key: draft.rule_key.trim(),
    title: draft.title.trim(),
    rule_source: draft.rule_source,
    field_name: draft.field_name.trim(),
    operator: draft.operator,
    threshold_value: draft.operator === "ge" || draft.operator === "gt" ? Number(draft.threshold_value) : null,
    threshold_text: draft.operator === "eq" || draft.operator === "ne" ? normalizedThresholdText || null : null,
    severity: draft.severity,
    enabled: draft.enabled,
    auto_resolve: draft.auto_resolve,
    message_template: normalizedTemplate || null,
  };
}

function toUpdatePayload(draft: AlertRuleDraft): AlertRuleUpdatePayload {
  const payload = toCreatePayload(draft);
  return {
    title: payload.title,
    rule_source: payload.rule_source,
    field_name: payload.field_name,
    operator: payload.operator,
    threshold_value: payload.threshold_value,
    threshold_text: payload.threshold_text,
    severity: payload.severity,
    enabled: payload.enabled,
    auto_resolve: payload.auto_resolve,
    message_template: payload.message_template,
  };
}

function describeRuleCondition(
  rule: Pick<AlertRuleDraft, "rule_source" | "field_name" | "operator" | "threshold_value" | "threshold_text">
) {
  const threshold =
    rule.operator === "ge" || rule.operator === "gt" ? rule.threshold_value || "--" : rule.threshold_text || "--";
  return `${rule.rule_source}.${rule.field_name} ${operatorLabels[rule.operator]} ${threshold}`;
}

function normalizeImportedRule(raw: unknown, index: number): AlertRuleCreatePayload {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error(`导入文件中第 ${index + 1} 条规则格式无效`);
  }

  const rule = raw as Record<string, unknown>;
  const ruleKey = String(rule.rule_key ?? "").trim();
  const title = String(rule.title ?? "").trim();
  const fieldName = String(rule.field_name ?? "").trim();
  const ruleSource = String(rule.rule_source ?? "") as RuleSource;
  const operator = String(rule.operator ?? "") as RuleOperator;
  const severity = String(rule.severity ?? "") as AlertSeverity;

  if (!ruleKey || !title || !fieldName) {
    throw new Error(`导入文件中第 ${index + 1} 条规则缺少必填字段`);
  }
  if (!["metric", "event"].includes(ruleSource)) {
    throw new Error(`导入文件中第 ${index + 1} 条规则来源不合法`);
  }
  if (!["ge", "gt", "eq", "ne"].includes(operator)) {
    throw new Error(`导入文件中第 ${index + 1} 条比较运算符不合法`);
  }
  if (!["high", "medium", "low", "info"].includes(severity)) {
    throw new Error(`导入文件中第 ${index + 1} 条严重级别不合法`);
  }

  const thresholdValue =
    rule.threshold_value === null || rule.threshold_value === undefined || rule.threshold_value === ""
      ? null
      : Number(rule.threshold_value);
  if ((operator === "ge" || operator === "gt") && (thresholdValue === null || Number.isNaN(thresholdValue))) {
    throw new Error(`导入文件中第 ${index + 1} 条规则缺少有效的数值阈值`);
  }

  const thresholdText =
    rule.threshold_text === null || rule.threshold_text === undefined ? null : String(rule.threshold_text).trim();
  if ((operator === "eq" || operator === "ne") && !thresholdText) {
    throw new Error(`导入文件中第 ${index + 1} 条规则缺少文本阈值`);
  }

  return {
    rule_key: ruleKey,
    title,
    rule_source: ruleSource,
    field_name: fieldName,
    operator,
    threshold_value: operator === "ge" || operator === "gt" ? thresholdValue : null,
    threshold_text: operator === "eq" || operator === "ne" ? thresholdText : null,
    severity,
    enabled: rule.enabled === undefined ? true : Boolean(rule.enabled),
    auto_resolve: rule.auto_resolve === undefined ? true : Boolean(rule.auto_resolve),
    message_template:
      rule.message_template === null || rule.message_template === undefined
        ? null
        : String(rule.message_template),
  };
}

function normalizeImportedRules(value: unknown): AlertRuleCreatePayload[] {
  const candidate =
    Array.isArray(value)
      ? value
      : value && typeof value === "object" && Array.isArray((value as { rules?: unknown[] }).rules)
        ? (value as { rules: unknown[] }).rules
        : null;

  if (!candidate) {
    throw new Error("导入文件必须是规则数组，或包含 rules 数组的 JSON 对象");
  }

  return candidate.map((item, index) => normalizeImportedRule(item, index));
}

function buildBatchFeedback(actionLabel: string, result: AlertBatchActionResult) {
  if (result.failed.length === 0) {
    return `${actionLabel}完成，共处理 ${result.updated_count} 条告警。`;
  }
  const failedText = result.failed.map((item) => `#${item.alert_id} ${item.reason}`).join("；");
  return `${actionLabel}完成，成功 ${result.updated_count} 条，失败 ${result.failed.length} 条：${failedText}`;
}

function SummaryCard({ title, value, hint }: { title: string; value: string; hint: string }) {
  return (
    <section className="card alert-summary-card">
      <div className="alert-summary-title">{title}</div>
      <div className="alert-summary-value">{value}</div>
      <div className="alert-summary-hint">{hint}</div>
    </section>
  );
}

function AlertCard({
  alert,
  selected,
  operator,
  silenceMinutes,
  actionsDisabled,
  busyKey,
  onToggleSelected,
  onAcknowledge,
  onSilence,
  onUnsilence,
}: {
  alert: AlertRecord;
  selected: boolean;
  operator: string;
  silenceMinutes: number;
  actionsDisabled: boolean;
  busyKey: string | null;
  onToggleSelected: (alertId: number, selected: boolean) => void;
  onAcknowledge: (alertId: number) => Promise<void>;
  onSilence: (alertId: number) => Promise<void>;
  onUnsilence: (alertId: number) => Promise<void>;
}) {
  return (
    <article className={`card alert-card ${selected ? "selected" : ""}`}>
      <div className="alert-card-top">
        <div className="alert-card-heading">
          <label className="alert-select-toggle">
            <input
              type="checkbox"
              checked={selected}
              disabled={actionsDisabled}
              onChange={(event) => onToggleSelected(alert.id, event.target.checked)}
            />
            <span>选择此告警</span>
          </label>
          <div className="alert-card-title-row">
            <span className="alert-device-pill">{alert.device_id}</span>
            <span className={`event-severity ${alert.severity}`}>{severityLabels[alert.severity] ?? alert.severity}</span>
            <span className={`alert-status-pill ${alert.status}`}>{statusLabels[alert.status] ?? alert.status}</span>
          </div>
          <div className="alert-card-title">{alert.title}</div>
          <div className="alert-card-rule">规则键: {alert.rule_key}</div>
        </div>
        <div className="alert-card-side">
          <div>最近触发</div>
          <strong>{formatDateTime(alert.last_seen_at)}</strong>
        </div>
      </div>

      <div className="alert-card-message">{alert.message}</div>

      <div className="alert-meta-grid">
        <div>
          <span>首次出现</span>
          <strong>{formatDateTime(alert.first_seen_at)}</strong>
        </div>
        <div>
          <span>累计事件</span>
          <strong>{alert.event_count}</strong>
        </div>
        <div>
          <span>最近值</span>
          <strong>{formatNumber(alert.last_value)}</strong>
        </div>
        <div>
          <span>确认人</span>
          <strong>{alert.acknowledged_by ?? "--"}</strong>
        </div>
        <div>
          <span>确认时间</span>
          <strong>{formatDateTime(alert.acknowledged_at)}</strong>
        </div>
        <div>
          <span>静默截止</span>
          <strong>
            {alert.status === "silenced"
              ? `${formatDateTime(alert.silenced_until)} / ${formatSilenceCountdown(alert.silence_remaining_seconds)}`
              : "--"}
          </strong>
        </div>
      </div>

      {alert.status === "silenced" && alert.silence_expired ? (
        <div className="alert-inline-tip warning">静默时间已到，但该告警仍未被恢复或解除静默。</div>
      ) : null}

      <div className="alert-action-row">
        <div className="alert-inline-tip">操作人: {operator || "console"}，默认静默时长: {silenceMinutes} 分钟</div>
        <div className="alert-button-row">
          {(alert.status === "open" || alert.status === "silenced") && (
            <button
              type="button"
              className="alert-action-button secondary"
              disabled={actionsDisabled}
              onClick={() => void onAcknowledge(alert.id)}
            >
              {busyKey === `ack-${alert.id}` ? "处理中..." : "确认告警"}
            </button>
          )}
          {alert.status !== "resolved" && (
            <button
              type="button"
              className="alert-action-button primary"
              disabled={actionsDisabled}
              onClick={() => void onSilence(alert.id)}
            >
              {busyKey === `silence-${alert.id}` ? "处理中..." : `静默 ${silenceMinutes} 分钟`}
            </button>
          )}
          {alert.status === "silenced" && (
            <button
              type="button"
              className="alert-action-button ghost"
              disabled={actionsDisabled}
              onClick={() => void onUnsilence(alert.id)}
            >
              {busyKey === `unsilence-${alert.id}` ? "处理中..." : "解除静默"}
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

function SilenceQueue({
  alerts,
  actionsDisabled,
  busyKey,
  onUnsilence,
}: {
  alerts: AlertRecord[];
  actionsDisabled: boolean;
  busyKey: string | null;
  onUnsilence: (alertId: number) => Promise<void>;
}) {
  return (
    <section className="card">
      <div className="section-title">静默队列</div>
      <div className="alert-side-note">这里集中展示当前处于静默状态的告警，便于统一管理和恢复。</div>
      <div className="silence-list">
        {alerts.length === 0 ? (
          <div className="alert-empty">当前没有处于静默中的告警。</div>
        ) : (
          alerts.map((alert) => (
            <div key={alert.id} className="silence-item">
              <div>
                <div className="silence-item-title">
                  {alert.device_id} / {alert.title}
                </div>
                <div className="silence-item-meta">
                  到期时间 {formatDateTime(alert.silenced_until)}，剩余 {formatSilenceCountdown(alert.silence_remaining_seconds)}
                </div>
              </div>
              <button
                type="button"
                className="alert-action-button ghost"
                disabled={actionsDisabled}
                onClick={() => void onUnsilence(alert.id)}
              >
                {busyKey === `unsilence-${alert.id}` ? "处理中..." : "解除"}
              </button>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function RuleEditorCard({
  draft,
  saving,
  deleting,
  actionsDisabled,
  onChange,
  onSave,
  onDelete,
}: {
  draft: AlertRuleDraft;
  saving: boolean;
  deleting: boolean;
  actionsDisabled: boolean;
  onChange: (updates: Partial<AlertRuleDraft>) => void;
  onSave: () => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const numericOperator = draft.operator === "ge" || draft.operator === "gt";

  return (
    <article className="card alert-rule-card">
      <div className="alert-rule-top">
        <div>
          <div className="alert-rule-title">{draft.title || draft.rule_key || "未命名规则"}</div>
          <div className="alert-rule-subtitle">{describeRuleCondition(draft)}</div>
        </div>
        <div className="alert-rule-toggle-row">
          <label className="alert-switch">
            <input
              type="checkbox"
              checked={draft.enabled}
              disabled={actionsDisabled}
              onChange={(event) => onChange({ enabled: event.target.checked })}
            />
            <span>启用</span>
          </label>
          <label className="alert-switch">
            <input
              type="checkbox"
              checked={draft.auto_resolve}
              disabled={actionsDisabled}
              onChange={(event) => onChange({ auto_resolve: event.target.checked })}
            />
            <span>自动恢复</span>
          </label>
        </div>
      </div>

      <div className="alert-rule-grid">
        <label className="control-field">
          <span>规则键名</span>
          <input type="text" value={draft.rule_key} disabled />
        </label>
        <label className="control-field">
          <span>规则标题</span>
          <input
            type="text"
            value={draft.title}
            disabled={actionsDisabled}
            onChange={(event) => onChange({ title: event.target.value })}
          />
        </label>
        <label className="control-field">
          <span>规则来源</span>
          <select
            value={draft.rule_source}
            disabled={actionsDisabled}
            onChange={(event) => onChange({ rule_source: event.target.value as RuleSource })}
          >
            {ruleSourceOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="control-field">
          <span>字段名</span>
          <input
            type="text"
            value={draft.field_name}
            disabled={actionsDisabled}
            onChange={(event) => onChange({ field_name: event.target.value })}
          />
        </label>
        <label className="control-field">
          <span>比较运算符</span>
          <select
            value={draft.operator}
            disabled={actionsDisabled}
            onChange={(event) => onChange({ operator: event.target.value as RuleOperator })}
          >
            {operatorOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="control-field">
          <span>数值阈值</span>
          <input
            type="number"
            step="0.1"
            value={draft.threshold_value}
            disabled={actionsDisabled || !numericOperator}
            onChange={(event) => onChange({ threshold_value: event.target.value })}
          />
        </label>
        <label className="control-field">
          <span>文本阈值</span>
          <input
            type="text"
            value={draft.threshold_text}
            disabled={actionsDisabled || numericOperator}
            onChange={(event) => onChange({ threshold_text: event.target.value })}
          />
        </label>
        <label className="control-field">
          <span>严重级别</span>
          <select
            value={draft.severity}
            disabled={actionsDisabled}
            onChange={(event) => onChange({ severity: event.target.value as AlertSeverity })}
          >
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
            <option value="info">info</option>
          </select>
        </label>
        <label className="control-field alert-rule-message">
          <span>消息模板</span>
          <input
            type="text"
            value={draft.message_template}
            disabled={actionsDisabled}
            onChange={(event) => onChange({ message_template: event.target.value })}
            placeholder="{field}={value}"
          />
        </label>
      </div>

      <div className="alert-rule-actions">
        <div className="alert-side-note">模板可使用 {"{field}"}、{"{value}"}、{"{message}"} 变量。</div>
        <div className="alert-button-row">
          <button
            type="button"
            className="alert-action-button ghost"
            disabled={actionsDisabled}
            onClick={() => void onDelete()}
          >
            {deleting ? "删除中..." : "删除规则"}
          </button>
          <button
            type="button"
            className="alert-action-button primary"
            disabled={actionsDisabled}
            onClick={() => void onSave()}
          >
            {saving ? "保存中..." : "保存规则"}
          </button>
        </div>
      </div>
    </article>
  );
}

export function AlertCenterPage() {
  const [statusFilter, setStatusFilter] = useState<AlertStatusFilter>("active");
  const [severityFilter, setSeverityFilter] = useState<"all" | AlertSeverity>("all");
  const [deviceFilter, setDeviceFilter] = useState("");
  const [ruleFilter, setRuleFilter] = useState("");
  const [operatorName, setOperatorName] = useState("console");
  const [silenceMinutes, setSilenceMinutes] = useState(30);
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [busyActionKey, setBusyActionKey] = useState<string | null>(null);
  const [savingRuleKey, setSavingRuleKey] = useState<string | null>(null);
  const [ruleDrafts, setRuleDrafts] = useState<Record<string, AlertRuleDraft>>({});
  const [createDraft, setCreateDraft] = useState<AlertRuleDraft>(emptyRuleDraft);
  const [selectedAlertIds, setSelectedAlertIds] = useState<number[]>([]);
  const [importMode, setImportMode] = useState<RuleImportMode>("merge");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const deferredDeviceFilter = useDeferredValue(deviceFilter.trim());
  const deferredRuleFilter = useDeferredValue(ruleFilter.trim());

  const loadSummary = useCallback(() => api.getAlertSummary(), []);
  const loadTrends = useCallback(() => api.getAlertTrends(24), []);
  const loadRules = useCallback(() => api.getAlertRules(), []);
  const loadAlerts = useCallback(
    () =>
      api.getAlerts({
        status: statusFilter === "all" ? undefined : statusFilter,
        deviceId: deferredDeviceFilter || undefined,
        severity: severityFilter === "all" ? undefined : severityFilter,
        ruleKey: deferredRuleFilter || undefined,
        limit: 200,
      }),
    [deferredDeviceFilter, deferredRuleFilter, severityFilter, statusFilter]
  );
  const loadSilencedAlerts = useCallback(() => api.getAlerts({ status: "silenced", limit: 50 }), []);

  const { data: summary, loading: summaryLoading, error: summaryError, reload: reloadSummary } = usePollingData<AlertSummary>(
    loadSummary,
    5000
  );
  const { data: trends, reload: reloadTrends } = usePollingData<AlertTrendResponse>(loadTrends, 15000);
  const { data: alerts, loading, error, reload: reloadAlerts } = usePollingData<AlertRecord[]>(loadAlerts, 4000);
  const { data: silencedAlerts, reload: reloadSilencedAlerts } = usePollingData<AlertRecord[]>(loadSilencedAlerts, 4000);
  const { data: rules, reload: reloadRules } = usePollingData<AlertRuleRecord[]>(loadRules, 60000);

  useEffect(() => {
    if (!rules) {
      return;
    }
    setRuleDrafts((current) => {
      const next = { ...current };
      for (const rule of rules) {
        if (!next[rule.rule_key]) {
          next[rule.rule_key] = toRuleDraft(rule);
        }
      }
      for (const ruleKey of Object.keys(next)) {
        if (!rules.some((rule) => rule.rule_key === ruleKey)) {
          delete next[ruleKey];
        }
      }
      return next;
    });
  }, [rules]);

  useEffect(() => {
    const currentAlertIds = new Set((alerts ?? []).map((item) => item.id));
    setSelectedAlertIds((current) => current.filter((id) => currentAlertIds.has(id)));
  }, [alerts]);

  const trendChart = useMemo(
    () => ({
      labels: trends?.buckets ?? [],
      series: [
        { name: "告警触发", data: trends?.opened ?? [] },
        { name: "告警恢复", data: trends?.resolved ?? [] },
      ],
    }),
    [trends]
  );

  const selectedAlertSet = useMemo(() => new Set(selectedAlertIds), [selectedAlertIds]);
  const visibleRules = useMemo(() => {
    if (!rules) {
      return [];
    }
    return [...rules].sort((left, right) => left.rule_key.localeCompare(right.rule_key));
  }, [rules]);
  const allVisibleSelected = Boolean(alerts?.length) && (alerts ?? []).every((item) => selectedAlertSet.has(item.id));
  const operatorValue = operatorName.trim() || "console";
  const actionsDisabled = busyActionKey !== null || savingRuleKey !== null;

  function refreshAlertViews() {
    reloadSummary();
    reloadAlerts();
    reloadSilencedAlerts();
    reloadTrends();
  }

  function toggleAlertSelection(alertId: number, checked: boolean) {
    setSelectedAlertIds((current) => {
      if (checked) {
        return current.includes(alertId) ? current : [...current, alertId];
      }
      return current.filter((id) => id !== alertId);
    });
  }

  function toggleSelectAllVisible(checked: boolean) {
    const visibleIds = (alerts ?? []).map((item) => item.id);
    if (checked) {
      setSelectedAlertIds((current) => Array.from(new Set([...current, ...visibleIds])));
      return;
    }
    setSelectedAlertIds((current) => current.filter((id) => !visibleIds.includes(id)));
  }

  async function handleAcknowledge(alertId: number) {
    setBusyActionKey(`ack-${alertId}`);
    setFeedback(null);
    try {
      const updated = await api.acknowledgeAlert(alertId, { operator: operatorValue });
      setFeedback({ tone: "info", message: `告警 #${updated.id} 已确认。` });
      refreshAlertViews();
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "确认告警失败",
      });
    } finally {
      setBusyActionKey(null);
    }
  }

  async function handleBatchAcknowledge() {
    if (selectedAlertIds.length === 0) {
      setFeedback({ tone: "error", message: "请先选择要批量确认的告警。" });
      return;
    }
    setBusyActionKey("batch-ack");
    setFeedback(null);
    try {
      const result = await api.batchAcknowledgeAlerts({
        alert_ids: selectedAlertIds,
        operator: operatorValue,
      });
      setSelectedAlertIds(result.failed.map((item) => item.alert_id));
      setFeedback({ tone: result.failed.length > 0 ? "error" : "info", message: buildBatchFeedback("批量确认", result) });
      refreshAlertViews();
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "批量确认失败",
      });
    } finally {
      setBusyActionKey(null);
    }
  }

  async function handleSilence(alertId: number) {
    setBusyActionKey(`silence-${alertId}`);
    setFeedback(null);
    try {
      const updated = await api.silenceAlert(alertId, {
        operator: operatorValue,
        minutes: silenceMinutes,
      });
      setFeedback({ tone: "info", message: `告警 #${updated.id} 已静默 ${silenceMinutes} 分钟。` });
      refreshAlertViews();
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "静默告警失败",
      });
    } finally {
      setBusyActionKey(null);
    }
  }

  async function handleBatchSilence() {
    if (selectedAlertIds.length === 0) {
      setFeedback({ tone: "error", message: "请先选择要批量静默的告警。" });
      return;
    }
    setBusyActionKey("batch-silence");
    setFeedback(null);
    try {
      const result = await api.batchSilenceAlerts({
        alert_ids: selectedAlertIds,
        minutes: silenceMinutes,
        operator: operatorValue,
      });
      setSelectedAlertIds(result.failed.map((item) => item.alert_id));
      setFeedback({ tone: result.failed.length > 0 ? "error" : "info", message: buildBatchFeedback("批量静默", result) });
      refreshAlertViews();
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "批量静默失败",
      });
    } finally {
      setBusyActionKey(null);
    }
  }

  async function handleUnsilence(alertId: number) {
    setBusyActionKey(`unsilence-${alertId}`);
    setFeedback(null);
    try {
      const updated = await api.unsilenceAlert(alertId, { operator: operatorValue });
      setFeedback({ tone: "info", message: `告警 #${updated.id} 已解除静默。` });
      refreshAlertViews();
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "解除静默失败",
      });
    } finally {
      setBusyActionKey(null);
    }
  }

  async function handleSaveRule(ruleKey: string) {
    const draft = ruleDrafts[ruleKey];
    const validationError = validateRuleDraft(draft, false);
    if (validationError) {
      setFeedback({ tone: "error", message: validationError });
      return;
    }

    setSavingRuleKey(`save:${ruleKey}`);
    setFeedback(null);
    try {
      const updated = await api.updateAlertRule(ruleKey, toUpdatePayload(draft));
      setRuleDrafts((current) => ({ ...current, [updated.rule_key]: toRuleDraft(updated) }));
      setFeedback({ tone: "info", message: `规则 ${updated.rule_key} 已保存。` });
      reloadRules();
      reloadSummary();
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "保存规则失败",
      });
    } finally {
      setSavingRuleKey(null);
    }
  }

  async function handleDeleteRule(ruleKey: string) {
    const title = ruleDrafts[ruleKey]?.title || ruleKey;
    if (!window.confirm(`确定删除规则“${title}”吗？该规则关联的活动告警会被自动恢复。`)) {
      return;
    }

    setSavingRuleKey(`delete:${ruleKey}`);
    setFeedback(null);
    try {
      await api.deleteAlertRule(ruleKey, { operator: operatorValue });
      setRuleDrafts((current) => {
        const next = { ...current };
        delete next[ruleKey];
        return next;
      });
      setFeedback({ tone: "info", message: `规则 ${ruleKey} 已删除。` });
      reloadRules();
      refreshAlertViews();
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "删除规则失败",
      });
    } finally {
      setSavingRuleKey(null);
    }
  }

  async function handleCreateRule() {
    const validationError = validateRuleDraft(createDraft, true);
    if (validationError) {
      setFeedback({ tone: "error", message: validationError });
      return;
    }

    setSavingRuleKey("__create__");
    setFeedback(null);
    try {
      const created = await api.createAlertRule(toCreatePayload(createDraft));
      setRuleDrafts((current) => ({ ...current, [created.rule_key]: toRuleDraft(created) }));
      setCreateDraft(emptyRuleDraft);
      setFeedback({ tone: "info", message: `规则 ${created.rule_key} 已创建。` });
      reloadRules();
      reloadSummary();
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "创建规则失败",
      });
    } finally {
      setSavingRuleKey(null);
    }
  }

  async function handleExportRules() {
    setSavingRuleKey("__export__");
    setFeedback(null);
    try {
      const exported = await api.exportAlertRules();
      const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json;charset=utf-8" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `alert-rules-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      setFeedback({ tone: "info", message: `已导出 ${exported.rule_count} 条规则。` });
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "导出规则失败",
      });
    } finally {
      setSavingRuleKey(null);
    }
  }

  function handleRequestImport() {
    fileInputRef.current?.click();
  }

  async function handleImportFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setSavingRuleKey("__import__");
    setFeedback(null);
    try {
      const content = await file.text();
      const parsed = JSON.parse(content) as unknown;
      const importedRules = normalizeImportedRules(parsed);

      if (
        importMode === "replace" &&
        !window.confirm("覆盖导入会删除当前规则集中未出现在文件里的规则，确定继续吗？")
      ) {
        return;
      }

      const result = await api.importAlertRules({
        rules: importedRules,
        mode: importMode,
        operator: operatorValue,
      });
      setRuleDrafts(
        Object.fromEntries(result.rules.map((rule) => [rule.rule_key, toRuleDraft(rule)]))
      );
      setFeedback({
        tone: "info",
        message: `规则导入完成：新增 ${result.created_count} 条，更新 ${result.updated_count} 条，删除 ${result.deleted_count} 条。`,
      });
      reloadRules();
      refreshAlertViews();
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "导入规则失败",
      });
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      setSavingRuleKey(null);
    }
  }

  if (loading && !alerts && summaryLoading) {
    return <div className="status-panel">正在加载告警中心数据...</div>;
  }

  if ((error || summaryError) && !alerts && !summary) {
    return <div className="status-panel">告警中心数据加载失败：{error ?? summaryError}</div>;
  }

  return (
    <div className="alert-shell">
      <div className="alert-scroll">
        <header className="card alert-hero">
          <div>
            <div className="eyebrow">Alert Center</div>
            <h1>告警规则维护与处置中心</h1>
            <p>这里把规则维护、告警确认、静默管理和批量处置集中到同一张工作台，便于论文和演示时完整展示系统能力。</p>
          </div>
          <div className="control-hero-pills">
            <span className="hero-chip">活动告警 {summary?.active_total ?? 0}</span>
            <span className="hero-chip">静默中 {summary?.silenced_total ?? 0}</span>
            <span className="hero-chip">启用规则 {summary?.enabled_rule_total ?? 0}</span>
          </div>
        </header>

        {feedback ? <section className={`card control-feedback ${feedback.tone}`}>{feedback.message}</section> : null}

        <section className="alert-summary-grid">
          <SummaryCard title="活动告警" value={String(summary?.active_total ?? 0)} hint="open / acknowledged / silenced 的实时总数" />
          <SummaryCard title="待处理" value={String(summary?.open_total ?? 0)} hint="尚未确认的活动告警" />
          <SummaryCard title="静默中" value={String(summary?.silenced_total ?? 0)} hint="已压制通知但仍在持续跟踪" />
          <SummaryCard
            title="规则总数"
            value={String(summary?.rule_total ?? 0)}
            hint={`已启用 ${summary?.enabled_rule_total ?? 0} 条，禁用 ${summary?.disabled_rule_total ?? 0} 条`}
          />
        </section>

        <section className="alert-main-grid">
          <section className="card alert-workbench">
            <div className="alert-toolbar">
              <div className="section-title">告警处置台</div>
              <div className="alert-toolbar-grid">
                <label className="control-field">
                  <span>状态筛选</span>
                  <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as AlertStatusFilter)}>
                    {statusOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="control-field">
                  <span>严重级别</span>
                  <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value as "all" | AlertSeverity)}>
                    {severityOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="control-field">
                  <span>设备过滤</span>
                  <input type="text" value={deviceFilter} onChange={(event) => setDeviceFilter(event.target.value)} placeholder="如 cpu0" />
                </label>
                <label className="control-field">
                  <span>规则过滤</span>
                  <input type="text" value={ruleFilter} onChange={(event) => setRuleFilter(event.target.value)} placeholder="如 high_temperature" />
                </label>
                <label className="control-field">
                  <span>操作人</span>
                  <input type="text" value={operatorName} onChange={(event) => setOperatorName(event.target.value)} />
                </label>
                <label className="control-field">
                  <span>默认静默时长(分钟)</span>
                  <input
                    type="number"
                    min="1"
                    max="10080"
                    step="1"
                    value={silenceMinutes}
                    onChange={(event) => setSilenceMinutes(Number(event.target.value))}
                  />
                </label>
              </div>

              <div className="alert-batch-bar">
                <label className="alert-select-toggle">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    disabled={actionsDisabled || !(alerts?.length ?? 0)}
                    onChange={(event) => toggleSelectAllVisible(event.target.checked)}
                  />
                  <span>全选当前结果</span>
                </label>
                <div className="alert-batch-title">已选 {selectedAlertIds.length} 条告警</div>
                <div className="alert-button-row">
                  <button type="button" className="alert-action-button secondary" disabled={actionsDisabled} onClick={() => void handleBatchAcknowledge()}>
                    {busyActionKey === "batch-ack" ? "处理中..." : "批量确认"}
                  </button>
                  <button type="button" className="alert-action-button primary" disabled={actionsDisabled} onClick={() => void handleBatchSilence()}>
                    {busyActionKey === "batch-silence" ? "处理中..." : `批量静默 ${silenceMinutes} 分钟`}
                  </button>
                  <button
                    type="button"
                    className="alert-action-button ghost"
                    disabled={actionsDisabled || selectedAlertIds.length === 0}
                    onClick={() => setSelectedAlertIds([])}
                  >
                    清空选择
                  </button>
                </div>
              </div>
            </div>

            <div className="alert-list">
              {(alerts ?? []).length === 0 ? (
                <div className="alert-empty">当前筛选条件下没有告警记录。</div>
              ) : (
                (alerts ?? []).map((alert) => (
                  <AlertCard
                    key={alert.id}
                    alert={alert}
                    selected={selectedAlertSet.has(alert.id)}
                    operator={operatorValue}
                    silenceMinutes={silenceMinutes}
                    actionsDisabled={actionsDisabled}
                    busyKey={busyActionKey}
                    onToggleSelected={toggleAlertSelection}
                    onAcknowledge={handleAcknowledge}
                    onSilence={handleSilence}
                    onUnsilence={handleUnsilence}
                  />
                ))
              )}
            </div>
          </section>

          <div className="alert-side-stack">
            <LineChart title="近 24 小时告警趋势" labels={trendChart.labels} series={trendChart.series} yAxisName="次数" />

            <section className="card">
              <div className="section-title">处置概览</div>
              <div className="alert-severity-grid">
                <div className="alert-severity-box high">
                  <span>高等级</span>
                  <strong>{summary?.active_by_severity.high ?? 0}</strong>
                </div>
                <div className="alert-severity-box medium">
                  <span>中等级</span>
                  <strong>{summary?.active_by_severity.medium ?? 0}</strong>
                </div>
                <div className="alert-severity-box low">
                  <span>低等级</span>
                  <strong>{summary?.active_by_severity.low ?? 0}</strong>
                </div>
                <div className="alert-severity-box info">
                  <span>提示</span>
                  <strong>{summary?.active_by_severity.info ?? 0}</strong>
                </div>
              </div>
              <div className="alert-side-note">30 分钟内即将到期的静默：{summary?.expiring_silence_total ?? 0}</div>
              <div className="alert-side-note">已到期但仍未恢复的静默：{summary?.expired_silence_total ?? 0}</div>
            </section>

            <SilenceQueue
              alerts={silencedAlerts ?? []}
              actionsDisabled={actionsDisabled}
              busyKey={busyActionKey}
              onUnsilence={handleUnsilence}
            />
          </div>
        </section>

        <section className="alert-rule-section">
          <section className="card">
            <div className="rule-management-toolbar">
              <div>
                <div className="section-title">规则导入导出</div>
                <div className="alert-side-note">导出会生成当前规则集 JSON，导入支持合并和覆盖两种模式。</div>
              </div>
              <div className="rule-toolbar-actions">
                <label className="control-field compact-field">
                  <span>导入模式</span>
                  <select value={importMode} disabled={actionsDisabled} onChange={(event) => setImportMode(event.target.value as RuleImportMode)}>
                    {importModeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="alert-side-note compact-note">
                  {importModeOptions.find((option) => option.value === importMode)?.hint}
                </div>
                <div className="alert-button-row">
                  <button type="button" className="alert-action-button secondary" disabled={actionsDisabled} onClick={() => void handleExportRules()}>
                    {savingRuleKey === "__export__" ? "导出中..." : "导出规则"}
                  </button>
                  <button type="button" className="alert-action-button ghost" disabled={actionsDisabled} onClick={handleRequestImport}>
                    {savingRuleKey === "__import__" ? "导入中..." : "导入 JSON"}
                  </button>
                </div>
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json,.json"
              className="alert-hidden-input"
              onChange={handleImportFileChange}
            />
          </section>

          <section className="card">
            <div className="section-title">新增规则</div>
            <div className="alert-side-note">支持新增 metric / event 两类规则，保存后会立即进入规则库并参与后续判定。</div>
            <div className="alert-rule-grid">
              <label className="control-field">
                <span>规则键名</span>
                <input
                  type="text"
                  value={createDraft.rule_key}
                  disabled={actionsDisabled}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, rule_key: event.target.value }))}
                  placeholder="如 gpu_power_high"
                />
              </label>
              <label className="control-field">
                <span>规则标题</span>
                <input
                  type="text"
                  value={createDraft.title}
                  disabled={actionsDisabled}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, title: event.target.value }))}
                  placeholder="如 GPU 功耗过高"
                />
              </label>
              <label className="control-field">
                <span>规则来源</span>
                <select
                  value={createDraft.rule_source}
                  disabled={actionsDisabled}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, rule_source: event.target.value as RuleSource }))}
                >
                  {ruleSourceOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="control-field">
                <span>字段名</span>
                <input
                  type="text"
                  value={createDraft.field_name}
                  disabled={actionsDisabled}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, field_name: event.target.value }))}
                  placeholder="如 power_w / event_type"
                />
              </label>
              <label className="control-field">
                <span>比较运算符</span>
                <select
                  value={createDraft.operator}
                  disabled={actionsDisabled}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, operator: event.target.value as RuleOperator }))}
                >
                  {operatorOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="control-field">
                <span>数值阈值</span>
                <input
                  type="number"
                  step="0.1"
                  value={createDraft.threshold_value}
                  disabled={actionsDisabled || createDraft.operator === "eq" || createDraft.operator === "ne"}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, threshold_value: event.target.value }))}
                />
              </label>
              <label className="control-field">
                <span>文本阈值</span>
                <input
                  type="text"
                  value={createDraft.threshold_text}
                  disabled={actionsDisabled || createDraft.operator === "ge" || createDraft.operator === "gt"}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, threshold_text: event.target.value }))}
                />
              </label>
              <label className="control-field">
                <span>严重级别</span>
                <select
                  value={createDraft.severity}
                  disabled={actionsDisabled}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, severity: event.target.value as AlertSeverity }))}
                >
                  <option value="high">high</option>
                  <option value="medium">medium</option>
                  <option value="low">low</option>
                  <option value="info">info</option>
                </select>
              </label>
              <label className="control-field alert-rule-message">
                <span>消息模板</span>
                <input
                  type="text"
                  value={createDraft.message_template}
                  disabled={actionsDisabled}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, message_template: event.target.value }))}
                  placeholder="{field}={value}"
                />
              </label>
            </div>
            <div className="alert-rule-create-actions">
              <label className="alert-switch">
                <input
                  type="checkbox"
                  checked={createDraft.enabled}
                  disabled={actionsDisabled}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, enabled: event.target.checked }))}
                />
                <span>创建后立即启用</span>
              </label>
              <label className="alert-switch">
                <input
                  type="checkbox"
                  checked={createDraft.auto_resolve}
                  disabled={actionsDisabled}
                  onChange={(event) => setCreateDraft((current) => ({ ...current, auto_resolve: event.target.checked }))}
                />
                <span>支持自动恢复</span>
              </label>
              <button type="button" className="alert-action-button primary" disabled={actionsDisabled} onClick={() => void handleCreateRule()}>
                {savingRuleKey === "__create__" ? "创建中..." : "新增规则"}
              </button>
            </div>
          </section>

          <section className="alert-rule-list">
            {visibleRules.map((rule) => {
              const draft = ruleDrafts[rule.rule_key] ?? toRuleDraft(rule);
              return (
                <RuleEditorCard
                  key={rule.rule_key}
                  draft={draft}
                  saving={savingRuleKey === `save:${rule.rule_key}`}
                  deleting={savingRuleKey === `delete:${rule.rule_key}`}
                  actionsDisabled={actionsDisabled}
                  onChange={(updates) =>
                    setRuleDrafts((current) => ({
                      ...current,
                      [rule.rule_key]: { ...draft, ...updates },
                    }))
                  }
                  onSave={() => handleSaveRule(rule.rule_key)}
                  onDelete={() => handleDeleteRule(rule.rule_key)}
                />
              );
            })}
          </section>
        </section>
      </div>
    </div>
  );
}
