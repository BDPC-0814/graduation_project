import ReactECharts from "echarts-for-react";

type SeriesItem = {
  name: string;
  data: Array<number | null | undefined>;
};

type Props = {
  title: string;
  labels: string[];
  series: SeriesItem[];
  yAxisName?: string;
};

export function LineChart({ title, labels, series, yAxisName }: Props) {
  return (
    <section className="card">
      <div className="section-title">{title}</div>
      <ReactECharts
        style={{ height: 320 }}
        option={{
          tooltip: { trigger: "axis" },
          legend: { top: 0, textStyle: { color: "#d9e2f2" } },
          color: ["#4cc9f0", "#ff8f6b", "#8ddf8b", "#f6c85f"],
          grid: { left: 42, right: 20, top: 46, bottom: 32 },
          xAxis: {
            type: "category",
            data: labels,
            axisLine: { lineStyle: { color: "#60708a" } },
            axisLabel: { color: "#aebbd0" },
          },
          yAxis: {
            type: "value",
            name: yAxisName,
            axisLine: { lineStyle: { color: "#60708a" } },
            splitLine: { lineStyle: { color: "rgba(142, 158, 184, 0.18)" } },
            axisLabel: { color: "#aebbd0" },
            nameTextStyle: { color: "#aebbd0" },
          },
          series: series.map((item) => ({
            ...item,
            type: "line",
            smooth: true,
            connectNulls: true,
            showSymbol: true,
            symbol: "circle",
            symbolSize: 6,
            lineStyle: { width: 2.5 },
            emphasis: { focus: "series" },
          })),
        }}
      />
    </section>
  );
}
