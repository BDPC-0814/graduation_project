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
          tooltip: {
            trigger: "axis",
            backgroundColor: "rgba(96, 43, 18, 0.9)",
            borderWidth: 0,
            textStyle: { color: "#fff6ee" },
          },
          legend: { top: 0, textStyle: { color: "#8a4a37" } },
          color: ["#f26a3d", "#f0a03a", "#d95a77", "#ef8c4f", "#4daea1"],
          grid: { left: 42, right: 20, top: 46, bottom: 32 },
          xAxis: {
            type: "category",
            data: labels,
            axisLine: { lineStyle: { color: "rgba(168, 112, 87, 0.5)" } },
            axisLabel: { color: "#9d6551" },
          },
          yAxis: {
            type: "value",
            name: yAxisName,
            axisLine: { lineStyle: { color: "rgba(168, 112, 87, 0.5)" } },
            splitLine: { lineStyle: { color: "rgba(194, 127, 89, 0.12)" } },
            axisLabel: { color: "#9d6551" },
            nameTextStyle: { color: "#9d6551" },
          },
          series: series.map((item) => ({
            ...item,
            type: "line",
            smooth: true,
            connectNulls: true,
            showSymbol: true,
            symbol: "circle",
            symbolSize: 6,
            lineStyle: {
              width: 3,
              shadowBlur: 14,
              shadowColor: "rgba(242, 106, 61, 0.18)",
            },
            areaStyle: {
              opacity: 0.12,
            },
            emphasis: { focus: "series" },
          })),
        }}
      />
    </section>
  );
}
