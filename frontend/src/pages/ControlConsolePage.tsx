import { useState } from "react";

import { api } from "../api";
import { usePollingData } from "../hooks";
import type {
  ControlFileState,
  ControlJob,
  LiveCollectionPayload,
  ReplayComparePayload,
  ReplayTracePayload,
} from "../types";


const initialTraceForm: ReplayTracePayload = {
  duration: 120,
  step: 0.5,
  seed: 20260407,
};

const initialLiveForm: LiveCollectionPayload = {
  devices: "cpu",
  gpu_vendor: "auto",
  npu_backend: "auto",
  mode: "evolution",
  duration: 60,
  fixed_interval: 5,
  t_min: 0.5,
  t_max: 8,
};

const livePresets: Array<{
  key: string;
  label: string;
  description: string;
  payload: LiveCollectionPayload;
}> = [
  {
    key: "cpu-demo",
    label: "仅 CPU 演示",
    description: "快速验证实时采集链路和仪表盘刷新。",
    payload: {
      devices: "cpu",
      gpu_vendor: "auto",
      npu_backend: "auto",
      mode: "evolution",
      duration: 30,
      fixed_interval: 5,
      t_min: 0.5,
      t_max: 6,
    },
  },
  {
    key: "cpu-gpu-monitor",
    label: "CPU+GPU 实时监控",
    description: "同时采集 CPU 与 GPU，更适合完整展示监控页。",
    payload: {
      devices: "cpu,gpu",
      gpu_vendor: "auto",
      npu_backend: "auto",
      mode: "evolution",
      duration: 60,
      fixed_interval: 5,
      t_min: 0.5,
      t_max: 8,
    },
  },
  {
    key: "openharmony-npu",
    label: "OpenHarmony NPU",
    description: "Collect RK3588 NPU metrics through hdc from the connected OpenHarmony board.",
    payload: {
      devices: "npu",
      gpu_vendor: "auto",
      npu_backend: "openharmony_hdc",
      mode: "evolution",
      duration: 120,
      fixed_interval: 5,
      t_min: 0.5,
      t_max: 8,
    },
  },
];

const initialCompareForm: ReplayComparePayload = {
  devices: "all",
  gpu_vendor: "auto",
  npu_backend: "auto",
  duration: 85,
  fixed_interval: 5,
  t_min: 0.5,
  t_max: 8,
  regenerate_trace: false,
  trace_duration: 120,
  trace_step: 0.5,
  trace_seed: 20260407,
};


function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }
  return value.replace("T", " ");
}


function formatStatus(status?: string | null) {
  const dictionary: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已取消",
    pending: "待执行",
  };
  return dictionary[status ?? ""] ?? status ?? "--";
}


function formatFileSize(bytes?: number | null) {
  if (bytes === null || bytes === undefined) {
    return "--";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}


function StatusBadge({ status }: { status?: string | null }) {
  return <span className={`console-status-badge ${status ?? "unknown"}`}>{formatStatus(status)}</span>;
}


function FileStateCard({
  title,
  subtitle,
  state,
}: {
  title: string;
  subtitle: string;
  state: ControlFileState;
}) {
  return (
    <section className="card control-info-card">
      <div className="control-card-top">
        <div>
          <div className="control-card-title">{title}</div>
          <div className="control-card-subtitle">{subtitle}</div>
        </div>
        <StatusBadge status={state.exists ? "succeeded" : "failed"} />
      </div>

      <div className="control-card-metric">{state.exists ? "可用" : "缺失"}</div>
      <div className="control-card-text">主文件：{state.path}</div>
      {state.secondary_path ? <div className="control-card-text">配套文件：{state.secondary_path}</div> : null}
      <div className="control-card-text">最近更新：{formatDateTime(state.updated_at)}</div>
      <div className="control-card-text">文件大小：{formatFileSize(state.size_bytes)}</div>
    </section>
  );
}


function JobArtifacts({ job }: { job?: ControlJob | null }) {
  const items = Object.entries(job?.artifacts ?? {});
  if (items.length === 0) {
    return <div className="control-empty">当前任务还没有产出文件。</div>;
  }

  return (
    <div className="artifact-list">
      {items.map(([key, value]) => (
        <div key={key} className="artifact-item">
          <div className="artifact-key">{key}</div>
          <div className="artifact-value">{value}</div>
        </div>
      ))}
    </div>
  );
}


function RecentJobs({ jobs }: { jobs: ControlJob[] }) {
  if (jobs.length === 0) {
    return <div className="control-empty">还没有通过图形控制台提交过任务。</div>;
  }

  return (
    <div className="recent-job-list">
      {jobs.map((job) => (
        <div key={job.id} className="recent-job-item">
          <div className="recent-job-top">
            <div>
              <div className="recent-job-title">{job.title}</div>
              <div className="recent-job-meta">
                {job.id} · {formatDateTime(job.created_at)}
              </div>
            </div>
            <StatusBadge status={job.status} />
          </div>
          <div className="recent-job-meta">当前步骤：{job.current_step ?? "无"}</div>
          {job.error ? <div className="recent-job-error">错误：{job.error}</div> : null}
        </div>
      ))}
    </div>
  );
}


export function ControlConsolePage() {
  const [traceForm, setTraceForm] = useState<ReplayTracePayload>(initialTraceForm);
  const [liveForm, setLiveForm] = useState<LiveCollectionPayload>(initialLiveForm);
  const [compareForm, setCompareForm] = useState<ReplayComparePayload>(initialCompareForm);
  const [selectedLivePreset, setSelectedLivePreset] = useState<string>("cpu-demo");
  const [submitState, setSubmitState] = useState<"trace" | "live" | "compare" | "cancel" | null>(null);
  const [feedback, setFeedback] = useState<{ tone: "info" | "error"; message: string } | null>(null);

  const { data: status, loading, error } = usePollingData(() => api.getControlStatus(), 2500);
  const activeJob = status?.active_job ?? null;
  const latestJob = activeJob ?? status?.recent_jobs?.[0] ?? null;
  const busy = Boolean(activeJob);

  async function handleGenerateTrace() {
    setSubmitState("trace");
    setFeedback(null);
    try {
      const job = await api.generateReplayTrace(traceForm);
      setFeedback({ tone: "info", message: `已提交回放轨迹任务：${job.id}` });
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "提交任务失败",
      });
    } finally {
      setSubmitState(null);
    }
  }

  async function handleLiveCollection() {
    setSubmitState("live");
    setFeedback(null);
    try {
      const job = await api.startLiveCollection(liveForm);
      setFeedback({ tone: "info", message: `已提交实时采集任务：${job.id}` });
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "提交任务失败",
      });
    } finally {
      setSubmitState(null);
    }
  }

  async function handleReplayCompare() {
    setSubmitState("compare");
    setFeedback(null);
    try {
      const job = await api.startReplayCompare(compareForm);
      setFeedback({ tone: "info", message: `已提交对比评估任务：${job.id}` });
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "提交任务失败",
      });
    } finally {
      setSubmitState(null);
    }
  }

  async function handleCancel() {
    setSubmitState("cancel");
    setFeedback(null);
    try {
      await api.cancelActiveJob();
      setFeedback({ tone: "info", message: "已发送取消请求，稍后会自动刷新状态。" });
    } catch (submitError) {
      setFeedback({
        tone: "error",
        message: submitError instanceof Error ? submitError.message : "取消任务失败",
      });
    } finally {
      setSubmitState(null);
    }
  }

  function applyLivePreset(presetKey: string) {
    const preset = livePresets.find((item) => item.key === presetKey);
    if (!preset) {
      return;
    }
    setSelectedLivePreset(presetKey);
    setLiveForm(preset.payload);
    setFeedback({
      tone: "info",
      message: `已应用预设：${preset.label}`,
    });
  }

  return (
    <div className="control-shell">
      <div className="control-scroll">
        <header className="card control-hero">
          <div>
            <div className="eyebrow">System Console</div>
            <h1>图形化启动与实验控制台</h1>
            <p>
              这里把实时采集、回放轨迹生成、fixed/evolution 对比评估和任务日志放在同一个页面里。常用操作不需要再手动输入一长串命令。
            </p>
          </div>
          <div className="control-hero-pills">
            <span className="hero-chip">后端启动：{formatDateTime(status?.service.started_at)}</span>
            <span className="hero-chip">前端托管：{status?.service.frontend_dist_ready ? "已启用" : "未构建"}</span>
            <span className="hero-chip">运行中任务：{activeJob ? activeJob.title : "无"}</span>
          </div>
        </header>

        {loading && !status ? <div className="status-panel">正在读取控制台状态...</div> : null}
        {error ? <div className="status-panel">控制台状态读取失败：{error}</div> : null}

        {feedback ? (
          <section className={`card control-feedback ${feedback.tone}`}>{feedback.message}</section>
        ) : null}

        {status ? (
          <>
            <section className="control-status-grid">
              <section className="card control-info-card">
                <div className="control-card-top">
                  <div>
                    <div className="control-card-title">系统入口状态</div>
                    <div className="control-card-subtitle">当前浏览器访问的是后端统一托管的入口</div>
                  </div>
                  <StatusBadge status={status.service.frontend_dist_ready ? "succeeded" : "failed"} />
                </div>
                <div className="control-card-metric">单入口运行</div>
                <div className="control-card-text">后端启动时间：{formatDateTime(status.service.started_at)}</div>
                <div className="control-card-text">Python：{status.service.python_path}</div>
                <div className="control-card-text">前端构建目录：{status.service.frontend_dist_path}</div>
              </section>

              <FileStateCard title="回放轨迹" subtitle="用于可复现实验的统一输入基线" state={status.trace} />
              <FileStateCard title="评估报告" subtitle="仪表盘实验页会直接读取 latest 结果" state={status.latest_report} />

              <section className="card control-info-card">
                <div className="control-card-top">
                  <div>
                    <div className="control-card-title">当前任务</div>
                    <div className="control-card-subtitle">同一时刻只运行一个长任务，避免互相抢资源</div>
                  </div>
                  <StatusBadge status={activeJob?.status ?? "pending"} />
                </div>
                <div className="control-card-metric">{activeJob ? activeJob.title : "空闲"}</div>
                <div className="control-card-text">当前步骤：{activeJob?.current_step ?? "--"}</div>
                <div className="control-card-text">任务编号：{activeJob?.id ?? "--"}</div>
                <div className="control-card-text">开始时间：{formatDateTime(activeJob?.started_at)}</div>
              </section>
            </section>

            <section className="control-main-grid">
              <section className="card control-form-card">
                <div className="section-title">任务参数</div>

                <div className="control-form-block">
                  <div className="control-block-title">1. 实时采集当前机器状态</div>
                  <div className="control-preset-row">
                    {livePresets.map((preset) => (
                      <button
                        key={preset.key}
                        type="button"
                        className={`control-preset-button ${preset.key === selectedLivePreset ? "active" : ""}`}
                        onClick={() => applyLivePreset(preset.key)}
                        disabled={busy || submitState !== null}
                      >
                        <span className="control-preset-label">{preset.label}</span>
                        <span className="control-preset-description">{preset.description}</span>
                      </button>
                    ))}
                  </div>

                  <div className="control-field-grid four-column">
                    <label className="control-field">
                      <span>采集模式</span>
                      <select
                        value={liveForm.mode}
                        onChange={(event) =>
                          setLiveForm((current) => ({
                            ...current,
                            mode: event.target.value as LiveCollectionPayload["mode"],
                          }))
                        }
                      >
                        <option value="evolution">evolution</option>
                        <option value="fixed">fixed</option>
                      </select>
                    </label>
                    <label className="control-field">
                      <span>设备集合</span>
                      <input
                        type="text"
                        value={liveForm.devices}
                        onChange={(event) =>
                          setLiveForm((current) => ({
                            ...current,
                            devices: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>GPU 厂商</span>
                      <select
                        value={liveForm.gpu_vendor}
                        onChange={(event) =>
                          setLiveForm((current) => ({
                            ...current,
                            gpu_vendor: event.target.value as LiveCollectionPayload["gpu_vendor"],
                          }))
                        }
                      >
                        <option value="auto">auto</option>
                        <option value="nvidia">nvidia</option>
                        <option value="intel">intel</option>
                      </select>
                    </label>
                    <label className="control-field">
                      <span>NPU backend</span>
                      <select
                        value={compareForm.npu_backend}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            npu_backend: event.target.value as ReplayComparePayload["npu_backend"],
                          }))
                        }
                      >
                        <option value="auto">auto</option>
                        <option value="openharmony_hdc">openharmony_hdc</option>
                        <option value="rockchip_sysfs">rockchip_sysfs</option>
                        <option value="ascend">ascend</option>
                      </select>
                    </label>
                    <label className="control-field">
                      <span>NPU backend</span>
                      <select
                        value={liveForm.npu_backend}
                        onChange={(event) =>
                          setLiveForm((current) => ({
                            ...current,
                            npu_backend: event.target.value as LiveCollectionPayload["npu_backend"],
                          }))
                        }
                      >
                        <option value="auto">auto</option>
                        <option value="openharmony_hdc">openharmony_hdc</option>
                        <option value="rockchip_sysfs">rockchip_sysfs</option>
                        <option value="ascend">ascend</option>
                      </select>
                    </label>
                    <label className="control-field">
                      <span>采集时长（秒）</span>
                      <input
                        type="number"
                        min="5"
                        step="1"
                        value={liveForm.duration}
                        onChange={(event) =>
                          setLiveForm((current) => ({
                            ...current,
                            duration: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>固定频率间隔</span>
                      <input
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={liveForm.fixed_interval}
                        onChange={(event) =>
                          setLiveForm((current) => ({
                            ...current,
                            fixed_interval: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>t_min</span>
                      <input
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={liveForm.t_min}
                        onChange={(event) =>
                          setLiveForm((current) => ({
                            ...current,
                            t_min: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>t_max</span>
                      <input
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={liveForm.t_max}
                        onChange={(event) =>
                          setLiveForm((current) => ({
                            ...current,
                            t_max: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <div className="control-field control-hint-field">
                      <span>说明</span>
                      <div className="control-hint-text">
                        不传 <code>--trace-file</code>，系统就会直接读取本机当前 CPU/GPU/NPU 状态。实时结果会通过
                        <code>/api/ingest</code> 回灌到后端，仪表盘会同步更新。
                      </div>
                    </div>
                  </div>
                </div>

                <div className="control-form-block">
                  <div className="control-block-title">2. 生成回放轨迹</div>
                  <div className="control-field-grid three-column">
                    <label className="control-field">
                      <span>轨迹时长（秒）</span>
                      <input
                        type="number"
                        min="10"
                        step="1"
                        value={traceForm.duration}
                        onChange={(event) =>
                          setTraceForm((current) => ({
                            ...current,
                            duration: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>轨迹步长（秒）</span>
                      <input
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={traceForm.step}
                        onChange={(event) =>
                          setTraceForm((current) => ({
                            ...current,
                            step: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>随机种子</span>
                      <input
                        type="number"
                        step="1"
                        value={traceForm.seed}
                        onChange={(event) =>
                          setTraceForm((current) => ({
                            ...current,
                            seed: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                  </div>
                </div>

                <div className="control-form-block">
                  <div className="control-block-title">3. 一键回放对比评估</div>
                  <div className="control-field-grid four-column">
                    <label className="control-field">
                      <span>设备集合</span>
                      <input
                        type="text"
                        value={compareForm.devices}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            devices: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>GPU 厂商</span>
                      <select
                        value={compareForm.gpu_vendor}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            gpu_vendor: event.target.value as ReplayComparePayload["gpu_vendor"],
                          }))
                        }
                      >
                        <option value="auto">auto</option>
                        <option value="nvidia">nvidia</option>
                        <option value="intel">intel</option>
                      </select>
                    </label>
                    <label className="control-field">
                      <span>实验时长（秒）</span>
                      <input
                        type="number"
                        min="10"
                        step="1"
                        value={compareForm.duration}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            duration: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>固定频率间隔</span>
                      <input
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={compareForm.fixed_interval}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            fixed_interval: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>t_min</span>
                      <input
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={compareForm.t_min}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            t_min: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>t_max</span>
                      <input
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={compareForm.t_max}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            t_max: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field control-checkbox">
                      <span>运行前重建轨迹</span>
                      <input
                        type="checkbox"
                        checked={compareForm.regenerate_trace}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            regenerate_trace: event.target.checked,
                          }))
                        }
                      />
                    </label>
                    <div className="control-field control-hint-field">
                      <span>默认输出</span>
                      <div className="control-hint-text">
                        数据写入 <code>experiments/gui_runs/&lt;timestamp&gt;</code>，评估报告同步刷新到
                        <code>experiments/evaluation/latest</code>。
                      </div>
                    </div>
                  </div>

                  <div className="control-field-grid three-column compact">
                    <label className="control-field">
                      <span>轨迹时长（重建时）</span>
                      <input
                        type="number"
                        min="10"
                        step="1"
                        value={compareForm.trace_duration}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            trace_duration: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>轨迹步长（重建时）</span>
                      <input
                        type="number"
                        min="0.1"
                        step="0.1"
                        value={compareForm.trace_step}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            trace_step: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="control-field">
                      <span>轨迹种子（重建时）</span>
                      <input
                        type="number"
                        step="1"
                        value={compareForm.trace_seed}
                        onChange={(event) =>
                          setCompareForm((current) => ({
                            ...current,
                            trace_seed: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                  </div>
                </div>

                <div className="control-button-row">
                  <button
                    type="button"
                    className="control-button secondary"
                    onClick={handleLiveCollection}
                    disabled={busy || submitState !== null}
                  >
                    {submitState === "live" ? "提交中..." : "开始实时采集"}
                  </button>
                  <button
                    type="button"
                    className="control-button secondary"
                    onClick={handleGenerateTrace}
                    disabled={busy || submitState !== null}
                  >
                    {submitState === "trace" ? "提交中..." : "生成回放轨迹"}
                  </button>
                  <button
                    type="button"
                    className="control-button primary"
                    onClick={handleReplayCompare}
                    disabled={busy || submitState !== null}
                  >
                    {submitState === "compare" ? "提交中..." : "一键运行对比评估"}
                  </button>
                  <button
                    type="button"
                    className="control-button danger"
                    onClick={handleCancel}
                    disabled={!busy || submitState !== null}
                  >
                    {submitState === "cancel" ? "发送中..." : "取消当前任务"}
                  </button>
                </div>
              </section>

              <section className="card control-job-card">
                <div className="section-title">任务进度</div>
                {latestJob ? (
                  <>
                    <div className="control-job-header">
                      <div>
                        <div className="control-job-title">{latestJob.title}</div>
                        <div className="control-job-meta">
                          {latestJob.id} · 创建于 {formatDateTime(latestJob.created_at)}
                        </div>
                      </div>
                      <StatusBadge status={latestJob.status} />
                    </div>

                    <div className="step-list">
                      {latestJob.steps.map((step) => (
                        <div key={step.key} className="step-item">
                          <div className="step-main">
                            <div className="step-title">{step.label}</div>
                            <div className="step-time">
                              {formatDateTime(step.started_at)} 至 {formatDateTime(step.finished_at)}
                            </div>
                          </div>
                          <StatusBadge status={step.status} />
                        </div>
                      ))}
                    </div>

                    {latestJob.error ? <div className="recent-job-error">错误：{latestJob.error}</div> : null}

                    <div className="section-subtitle">产出文件</div>
                    <JobArtifacts job={latestJob} />
                  </>
                ) : (
                  <div className="control-empty">提交任务后，这里会显示每一步的执行状态、日志和产物路径。</div>
                )}
              </section>
            </section>

            <section className="control-bottom-grid">
              <section className="card">
                <div className="section-title">任务日志</div>
                <div className="control-log-panel">
                  {(latestJob?.log_lines ?? []).length > 0 ? (
                    (latestJob?.log_lines ?? []).map((line, index) => (
                      <div key={`${index}-${line.slice(0, 24)}`} className="control-log-line">
                        {line}
                      </div>
                    ))
                  ) : (
                    <div className="control-empty">暂无任务日志。</div>
                  )}
                </div>
              </section>

              <section className="card">
                <div className="section-title">最近任务</div>
                <RecentJobs jobs={status.recent_jobs} />
              </section>
            </section>
          </>
        ) : null}
      </div>
    </div>
  );
}
