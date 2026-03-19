import { useCallback, useMemo } from "react";

import { api } from "../api";
import { LineChart } from "../charts/LineChart";
import { MetricTable } from "../components/MetricTable";
import { usePollingData } from "../hooks";
import type {
  ExperimentChart,
  ExperimentEvaluationReport,
  HistoryPoint,
  RealtimeMetric,
} from "../types";

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
    utilization_time: { title: "利用率-时间曲线", yAxisName: "利用率 (%)" },
    interval_time: { title: "采样间隔-时间曲线", yAxisName: "采样间隔 (s)" },
    latency_cdf: { title: "延迟 CDF 曲线", yAxisName: "累计概率 (%)" },
    redundancy_time: { title: "冗余率-时间曲线", yAxisName: "冗余率 (%)" },
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

function DeviceCard({ item }: { item: RealtimeMetric }) {
  return (
    <section className="card device-card">
      <div className="device-card-top">
        <div className="device-name">{item.device_id}</div>
        <div className={`device-status ${item.status}`}>{item.status}</div>
      </div>
      <div className="device-stats">
        <div>利用率：{formatValue(item.utilization, "%")}</div>
        <div>温度：{formatValue(item.chip_temp_c, "C")}</div>
        <div>功耗：{formatValue(item.power_w, "W")}</div>
        <div>风险分数：{formatValue(item.risk_score)}</div>
        <div>采样间隔：{formatValue(item.sample_interval_s, "s")}</div>
        <div>状态：{item.state ?? "--"}</div>
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

export function DashboardPage() {
  const loadRealtime = useCallback(() => api.getRealtime(), []);
  const { data: realtime, loading, error } = usePollingData(loadRealtime, 3000);

  const deviceIds = useMemo(() => realtime?.map((item) => item.device_id) ?? [], [realtime]);
  const loadCompare = useCallback(() => api.getCompareHistory(deviceIds, 80), [deviceIds]);
  const loadLogs = useCallback(() => api.getLogs(60), []);
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

  if (loading) {
    return <div className="status-panel">正在加载实时监控数据...</div>;
  }

  if (error || !realtime) {
    return <div className="status-panel">实时监控数据加载失败：{error ?? "暂无数据"}</div>;
  }

  return (
    <div className="monitor-page">
      <header className="monitor-header">
        <div>
          <div className="eyebrow">实时监控大盘</div>
          <h1>HAVFS 设备监控与评估</h1>
          <p>查看实时状态、在线采样变化，以及固定频率与 HAVFS 的离线实验评估结果。</p>
        </div>
      </header>

      <section className="device-card-grid">
        {realtime.map((item) => (
          <DeviceCard key={item.device_id} item={item} />
        ))}
      </section>

      <MetricTable rows={realtime} />

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
              yAxisName={experimentCharts.utilizationTime.y_axis_name ?? "利用率 (%)"}
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
              yAxisName={experimentCharts.redundancyTime.y_axis_name ?? "冗余率 (%)"}
            />
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
