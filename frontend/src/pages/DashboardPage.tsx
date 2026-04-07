import { useCallback, useMemo, useState, type CSSProperties } from "react";

import { api } from "../api";
import { LineChart } from "../charts/LineChart";
import { MetricTable } from "../components/MetricTable";
import { usePollingData } from "../hooks";
import type {
  EventRecord,
  ExperimentChart,
  ExperimentEvaluationReport,
  HistoryPoint,
  RealtimeMetric,
} from "../types";

type SectionKey = "overview" | "realtime" | "activity" | "experiment";

const sectionItems: Array<{
  key: SectionKey;
  navTitle: string;
  navHint: string;
  eyebrow: string;
  title: string;
  description: string;
}> = [
  {
    key: "overview",
    navTitle: "总体概览",
    navHint: "设备状态与核心指标",
    eyebrow: "Overview",
    title: "监控总览",
    description: "把设备运行态势、关键指标和实时快照放到一个视图里，更适合先看全局再深入。",
  },
  {
    key: "realtime",
    navTitle: "实时趋势",
    navHint: "利用率、风险与采样变化",
    eyebrow: "Realtime",
    title: "实时趋势分析",
    description: "按设备对比核心曲线，快速识别利用率波动、风险抬升和采样策略变化。",
  },
  {
    key: "activity",
    navTitle: "事件日志",
    navHint: "事件流与日志窗口",
    eyebrow: "Activity",
    title: "事件与日志",
    description: "把告警、事件和运行日志拆出来单独查看，排查问题时不用再穿过整页内容。",
  },
  {
    key: "experiment",
    navTitle: "实验评估",
    navHint: "HAVFS 与固定频率对比",
    eyebrow: "Experiment",
    title: "离线实验评估",
    description: "集中展示 HAVFS 与固定频率模式的评估结果，方便看节流效果与响应代价。",
  },
];

const particlePositions = [
  { left: "8%", top: "10%", size: 10, delay: "0s", duration: "13s" },
  { left: "18%", top: "68%", size: 6, delay: "1.2s", duration: "12s" },
  { left: "32%", top: "24%", size: 14, delay: "2.6s", duration: "18s" },
  { left: "44%", top: "78%", size: 8, delay: "0.8s", duration: "15s" },
  { left: "58%", top: "16%", size: 12, delay: "3.2s", duration: "14s" },
  { left: "72%", top: "56%", size: 18, delay: "1.8s", duration: "16s" },
  { left: "82%", top: "28%", size: 9, delay: "2.1s", duration: "12s" },
  { left: "91%", top: "74%", size: 7, delay: "0.5s", duration: "17s" },
];

function formatValue(value?: number | null, suffix = "", digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(digits)}${suffix}`;
}

function formatGeneratedAt(value?: string | null) {
  if (!value) {
    return "--";
  }
  return value.replace("T", " ");
}

function formatEventTime(value?: string | null, elapsed?: number | null) {
  if (value) {
    return value;
  }
  if (elapsed === null || elapsed === undefined || Number.isNaN(elapsed)) {
    return "--";
  }
  return `${elapsed.toFixed(2)}s`;
}

function formatStatus(status: string) {
  const dictionary: Record<string, string> = {
    ok: "运行正常",
    error: "需要关注",
    unavailable: "设备离线",
  };
  return dictionary[status] ?? status;
}

function formatSeverity(severity: string) {
  const dictionary: Record<string, string> = {
    high: "高",
    medium: "中",
    low: "低",
    info: "提示",
  };
  return dictionary[severity.toLowerCase()] ?? severity;
}

function normalizeSeriesName(name: string) {
  if (name === "Fixed Frequency") {
    return "固定频率";
  }
  return name;
}

function localizeExperimentChart(
  key: "utilization_time" | "interval_time" | "latency_cdf" | "redundancy_time",
  chart?: ExperimentChart | null
) {
  if (!chart) {
    return null;
  }

  const dictionary = {
    utilization_time: { title: "利用率-时间曲线", yAxisName: "利用率(%)" },
    interval_time: { title: "采样间隔-时间曲线", yAxisName: "采样间隔 (s)" },
    latency_cdf: { title: "延迟 CDF 曲线", yAxisName: "累计概率 (%)" },
    redundancy_time: { title: "冗余率-时间曲线", yAxisName: "冗余率(%)" },
  } as const;

  return {
    ...chart,
    title: dictionary[key].title,
    y_axis_name: dictionary[key].yAxisName,
    series: chart.series.map((item) => ({
      ...item,
      name: normalizeSeriesName(item.name),
    })),
  };
}

function buildCategorySeries(
  seriesMap: Record<string, HistoryPoint[]>,
  field: "utilization" | "risk_score" | "sample_interval_s"
) {
  const labels: string[] = [];
  Object.values(seriesMap).forEach((points) => {
    points.forEach((point, index) => {
      const label = point.timestamp ?? `${index}`;
      if (!labels.includes(label)) {
        labels.push(label);
      }
    });
  });

  const series = Object.entries(seriesMap).map(([deviceId, points]) => {
    const pointMap = new Map(points.map((point, index) => [point.timestamp ?? `${index}`, point]));
    return {
      name: deviceId,
      data: labels.map((label) => pointMap.get(label)?.[field] ?? null),
    };
  });

  return { labels, series };
}

function getLatestTimestamp(metrics: RealtimeMetric[]) {
  return metrics.reduce<string | null>((latest, current) => {
    if (!current.timestamp) {
      return latest;
    }
    if (!latest || current.timestamp > latest) {
      return current.timestamp;
    }
    return latest;
  }, null);
}

function averageValue(rows: RealtimeMetric[], selector: (row: RealtimeMetric) => number | null | undefined) {
  const values = rows.map(selector).filter((value): value is number => value !== null && value !== undefined);
  if (values.length === 0) {
    return null;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function ParticleField() {
  return (
    <div className="particle-field" aria-hidden="true">
      {particlePositions.map((particle, index) => {
        const style: CSSProperties = {
          left: particle.left,
          top: particle.top,
          width: `${particle.size}px`,
          height: `${particle.size}px`,
          animationDelay: particle.delay,
          animationDuration: particle.duration,
        };

        return <span key={`${particle.left}-${particle.top}-${index}`} className="particle-dot" style={style} />;
      })}
    </div>
  );
}

function OverviewStatCard({
  title,
  value,
  hint,
}: {
  title: string;
  value: string;
  hint: string;
}) {
  return (
    <section className="card overview-stat-card">
      <div className="overview-stat-title">{title}</div>
      <div className="overview-stat-value">{value}</div>
      <div className="overview-stat-hint">{hint}</div>
    </section>
  );
}

function DeviceCard({ item }: { item: RealtimeMetric }) {
  return (
    <section className="card device-card">
      <div className="device-card-top">
        <div>
          <div className="device-name">{item.device_id}</div>
          <div className="device-subtitle">{item.state ?? "等待状态更新"}</div>
        </div>
        <div className={`device-status ${item.status}`}>{formatStatus(item.status)}</div>
      </div>
      <div className="device-stats">
        <div>利用率：{formatValue(item.utilization, "%")}</div>
        <div>温度：{formatValue(item.chip_temp_c, "C")}</div>
        <div>功耗：{formatValue(item.power_w, "W")}</div>
        <div>风险分数：{formatValue(item.risk_score)}</div>
        <div>采样间隔：{formatValue(item.sample_interval_s, "s")}</div>
      </div>
    </section>
  );
}

function ExperimentStatCard({
  title,
  fixed,
  havfs,
  description,
  unit = "",
  digits = 2,
}: {
  title: string;
  fixed?: number | null;
  havfs?: number | null;
  description?: string;
  unit?: string;
  digits?: number;
}) {
  return (
    <section className="card experiment-stat-card">
      <div className="section-title">{title}</div>
      <div className="experiment-stat-lines">
        <div>固定频率：{formatValue(fixed, unit, digits)}</div>
        <div>HAVFS：{formatValue(havfs, unit, digits)}</div>
        <div>{description ?? "--"}</div>
      </div>
    </section>
  );
}

function EventPanel({ events }: { events: EventRecord[] }) {
  return (
    <section className="card">
      <div className="section-title">最近事件</div>
      <div className="event-list">
        {events.length === 0 ? (
          <div className="event-empty">当前暂无事件记录</div>
        ) : (
          events.map((event, index) => (
            <div key={`${event.timestamp ?? "event"}-${event.device_id}-${index}`} className="event-item">
              <div className="event-item-top">
                <div className="event-main">
                  <span className="event-device">{event.device_id}</span>
                  <span className={`event-severity ${event.severity}`}>{formatSeverity(event.severity)}</span>
                  <span className="event-type">{event.event_type}</span>
                </div>
                <div className="event-time">{formatEventTime(event.timestamp, event.time)}</div>
              </div>
              <div className="event-message">{event.message}</div>
              {event.detail ? <div className="event-detail">{event.detail}</div> : null}
              <div className="event-source">source: {event.source ?? "--"}</div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export function DashboardPage() {
  const [activeSection, setActiveSection] = useState<SectionKey>("overview");

  const loadRealtime = useCallback(() => api.getRealtime(), []);
  const loadOverview = useCallback(() => api.getOverview(), []);
  const { data: realtime, loading, error } = usePollingData(loadRealtime, 3000);
  const { data: overview } = usePollingData(loadOverview, 5000);

  const deviceIds = useMemo(() => realtime?.map((item) => item.device_id) ?? [], [realtime]);
  const loadCompare = useCallback(() => api.getCompareHistory(deviceIds, 80), [deviceIds]);
  const loadLogs = useCallback(() => api.getLogs(60), []);
  const loadEvents = useCallback(() => api.getEvents(40), []);
  const loadExperimentReport = useCallback(async () => {
    try {
      return await api.getExperimentEvaluation();
    } catch (err) {
      if (err instanceof Error && err.message.includes("404")) {
        return null;
      }
      throw err;
    }
  }, []);

  const { data: compareData } = usePollingData(loadCompare, 5000);
  const { data: logs } = usePollingData(loadLogs, 3000);
  const { data: events } = usePollingData(loadEvents, 4000);
  const { data: experimentReport, error: experimentError } = usePollingData<ExperimentEvaluationReport | null>(
    loadExperimentReport,
    15000
  );

  const utilizationChart = useMemo(
    () => buildCategorySeries(compareData?.series ?? {}, "utilization"),
    [compareData]
  );
  const riskChart = useMemo(
    () => buildCategorySeries(compareData?.series ?? {}, "risk_score"),
    [compareData]
  );
  const intervalChart = useMemo(
    () => buildCategorySeries(compareData?.series ?? {}, "sample_interval_s"),
    [compareData]
  );

  const experimentSummary = experimentReport?.summary;
  const experimentCharts = useMemo(
    () =>
      experimentReport
        ? {
            utilizationTime: localizeExperimentChart("utilization_time", experimentReport.charts.utilization_time),
            intervalTime: localizeExperimentChart("interval_time", experimentReport.charts.interval_time),
            latencyCdf: localizeExperimentChart("latency_cdf", experimentReport.charts.latency_cdf),
            redundancyTime: localizeExperimentChart("redundancy_time", experimentReport.charts.redundancy_time),
          }
        : null,
    [experimentReport]
  );

  const currentSection = sectionItems.find((item) => item.key === activeSection) ?? sectionItems[0];
  const latestTimestamp = realtime ? getLatestTimestamp(realtime) : null;
  const activeEvents = (events ?? []).filter((event) => ["high", "medium"].includes(event.severity.toLowerCase()));
  const activeAlertCount = overview?.active_alerts ?? activeEvents.length;
  const eventTotal = overview?.event_total ?? (events ?? []).length;
  const elevatedEventTotal = overview?.elevated_event_total ?? activeEvents.length;
  const overviewStats = realtime
    ? [
        {
          title: "设备总数",
          value: String(realtime.length),
          hint: "当前已接入监控的全部设备",
        },
        {
          title: "在线设备",
          value: String(realtime.filter((item) => item.status !== "unavailable").length),
          hint: "排除 unavailable 状态后的可用设备",
        },
        {
          title: "平均利用率",
          value: formatValue(averageValue(realtime, (item) => item.utilization), "%"),
          hint: "基于当前实时采样快照",
        },
        {
          title: "活跃告警",
          value: String(activeAlertCount),
          hint: "告警表中 open、acknowledged、silenced 的实时总数",
        },
      ]
    : [];

  if (loading) {
    return <div className="status-panel">正在加载实时监控数据...</div>;
  }

  if (error || !realtime) {
    return <div className="status-panel">实时监控数据加载失败：{error ?? "暂无数据"}</div>;
  }

  const renderSectionContent = () => {
    if (activeSection === "overview") {
      return (
        <div className="page-section">
          <section className="overview-stat-grid">
            {overviewStats.map((item) => (
              <OverviewStatCard key={item.title} title={item.title} value={item.value} hint={item.hint} />
            ))}
          </section>

          <section className="card spotlight-card">
            <div className="spotlight-copy">
              <div className="section-title">设备状态聚焦</div>
              <p>
                当前共有 {realtime.length} 台设备参与监控，最近更新时间为 {formatGeneratedAt(latestTimestamp)}。
                关键数值和状态卡片会更容易被快速扫视与对比。
              </p>
            </div>
            <div className="spotlight-pill-row">
              <span className="spotlight-pill">活跃告警 {activeAlertCount}</span>
              <span className="spotlight-pill">
                平均温度 {formatValue(averageValue(realtime, (item) => item.chip_temp_c), "C")}
              </span>
              <span className="spotlight-pill">
                平均功耗 {formatValue(averageValue(realtime, (item) => item.power_w), "W")}
              </span>
            </div>
          </section>

          <section className="device-card-grid">
            {realtime.map((item) => (
              <DeviceCard key={item.device_id} item={item} />
            ))}
          </section>

          <MetricTable rows={realtime} />
        </div>
      );
    }

    if (activeSection === "realtime") {
      return (
        <div className="page-section">
          <section className="card spotlight-card">
            <div className="spotlight-copy">
              <div className="section-title">实时趋势观察</div>
              <p>
                这里保留了原来的三组核心折线图，但拆到了独立页面。切页后你可以更专注地看动态趋势，而不用在长页面里来回寻找。
              </p>
            </div>
            <div className="spotlight-pill-row">
              <span className="spotlight-pill">采样设备 {deviceIds.length}</span>
              <span className="spotlight-pill">刷新间隔 3-5 秒</span>
              <span className="spotlight-pill">趋势维度 3 组</span>
            </div>
          </section>

          <section className="chart-stack">
            <LineChart title="设备利用率变化" labels={utilizationChart.labels} series={utilizationChart.series} yAxisName="%" />
            <LineChart title="设备风险分数变化" labels={riskChart.labels} series={riskChart.series} yAxisName="风险分数" />
            <LineChart
              title="设备采样间隔变化"
              labels={intervalChart.labels}
              series={intervalChart.series}
              yAxisName="秒"
            />
          </section>
        </div>
      );
    }

    if (activeSection === "activity") {
      return (
        <div className="page-section">
          <section className="activity-stat-row">
            <OverviewStatCard title="事件总数" value={String(eventTotal)} hint="事件表中的全部记录总数" />
            <OverviewStatCard title="高等级事件" value={String(elevatedEventTotal)} hint="事件表中 high 与 medium 的总数" />
            <OverviewStatCard title="日志行数" value={String((logs ?? []).length)} hint="日志窗口当前展示条数" />
          </section>

          <section className="monitor-two-column">
            <EventPanel events={events ?? []} />

            <section className="card">
              <div className="section-title">最近日志</div>
              <div className="log-panel">
                {(logs ?? []).map((item, index) => (
                  <div key={`${item.timestamp ?? "log"}-${index}`} className="log-line">
                    {item.line}
                  </div>
                ))}
              </div>
            </section>
          </section>
        </div>
      );
    }

    return (
      <div className="page-section">
        <section className="card">
          <div className="section-title">实验评估结果</div>
          {experimentSummary ? (
            <>
              <div className="experiment-meta">生成时间：{formatGeneratedAt(experimentReport?.generated_at)}</div>
              <div className="experiment-stat-grid">
                <ExperimentStatCard
                  title="采样点数量"
                  fixed={experimentSummary.sample_count.fixed}
                  havfs={experimentSummary.sample_count.havfs}
                  description={`采样点减少：${formatValue(experimentSummary.sample_count.reduction_percent, "%")}`}
                  digits={0}
                />
                <ExperimentStatCard
                  title="冗余率"
                  fixed={experimentSummary.redundancy_rate_percent.fixed}
                  havfs={experimentSummary.redundancy_rate_percent.havfs}
                  description="双层判定：数值阈值 + 时间窗口"
                  unit="%"
                />
                <ExperimentStatCard
                  title="平均采样间隔"
                  fixed={experimentSummary.interval_stats_s.fixed.mean_s}
                  havfs={experimentSummary.interval_stats_s.havfs.mean_s}
                  description="按有效采样间隔统计"
                  unit="s"
                />
                <ExperimentStatCard
                  title="P95 延迟"
                  fixed={experimentSummary.latency_stats_s.fixed.p95_s}
                  havfs={experimentSummary.latency_stats_s.havfs.p95_s}
                  description="事件触发后的响应延迟"
                  unit="s"
                />
              </div>
            </>
          ) : (
            <div className="experiment-empty">
              {experimentError
                ? `实验评估结果不可用：${experimentError}`
                : "请先运行 demo/evaluate_metrics.py 生成 experiments/evaluation/latest/report.json。"}
            </div>
          )}
        </section>

        {experimentCharts ? (
          <section className="chart-stack">
            {experimentCharts.utilizationTime ? (
              <LineChart
                title={experimentCharts.utilizationTime.title}
                labels={experimentCharts.utilizationTime.labels}
                series={experimentCharts.utilizationTime.series}
                yAxisName={experimentCharts.utilizationTime.y_axis_name ?? "利用率(%)"}
              />
            ) : null}
            {experimentCharts.intervalTime ? (
              <LineChart
                title={experimentCharts.intervalTime.title}
                labels={experimentCharts.intervalTime.labels}
                series={experimentCharts.intervalTime.series}
                yAxisName={experimentCharts.intervalTime.y_axis_name ?? "采样间隔 (s)"}
              />
            ) : null}
            {experimentCharts.latencyCdf ? (
              <LineChart
                title={experimentCharts.latencyCdf.title}
                labels={experimentCharts.latencyCdf.labels}
                series={experimentCharts.latencyCdf.series}
                yAxisName={experimentCharts.latencyCdf.y_axis_name ?? "累计概率 (%)"}
              />
            ) : null}
            {experimentCharts.redundancyTime ? (
              <LineChart
                title={experimentCharts.redundancyTime.title}
                labels={experimentCharts.redundancyTime.labels}
                series={experimentCharts.redundancyTime.series}
                yAxisName={experimentCharts.redundancyTime.y_axis_name ?? "冗余率(%)"}
              />
            ) : null}
          </section>
        ) : null}
      </div>
    );
  };

  return (
    <div className="monitor-shell">
      <ParticleField />
      <div className="ambient-orb ambient-orb-one" aria-hidden="true" />
      <div className="ambient-orb ambient-orb-two" aria-hidden="true" />

      <aside className="sidebar">
        <nav className="sidebar-nav" aria-label="页面导航">
          {sectionItems.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`nav-button ${item.key === activeSection ? "active" : ""}`}
              onClick={() => setActiveSection(item.key)}
            >
              <span className="nav-title">{item.navTitle}</span>
              <span className="nav-hint">{item.navHint}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer card">
          <div className="sidebar-footer-title">监控摘要</div>
          <div className="sidebar-footer-line">最近刷新：{formatGeneratedAt(latestTimestamp)}</div>
          <div className="sidebar-footer-line">在线设备：{realtime.filter((item) => item.status !== "unavailable").length}</div>
          <div className="sidebar-footer-line">活跃告警：{activeAlertCount}</div>
        </div>
      </aside>

      <main className="workspace">
        <section className="workspace-scroll">
          <header className="card page-hero">
            <div>
              <div className="eyebrow">{currentSection.eyebrow}</div>
              <h2>{currentSection.title}</h2>
              <p>{currentSection.description}</p>
            </div>
            <div className="hero-chip-row">
              <span className="hero-chip">设备数 {realtime.length}</span>
              <span className="hero-chip">更新时间 {formatGeneratedAt(latestTimestamp)}</span>
            </div>
          </header>

          {renderSectionContent()}
        </section>
      </main>
    </div>
  );
}
