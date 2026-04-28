import type { RealtimeMetric } from "../types";

type Props = {
  rows: RealtimeMetric[];
};

function formatNumber(value?: number | null, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(2)}${suffix}`;
}

export function MetricTable({ rows }: Props) {
  return (
    <section className="card">
      <div className="section-title">实时设备快照</div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>设备</th>
              <th>利用率</th>
              <th>温度</th>
              <th>功耗</th>
              <th>演化分数</th>
              <th>采样间隔</th>
              <th>采样相位</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.device_id}>
                <td>{row.device_id}</td>
                <td>{formatNumber(row.utilization, "%")}</td>
                <td>{formatNumber(row.chip_temp_c, "C")}</td>
                <td>{formatNumber(row.power_w, "W")}</td>
                <td>{formatNumber(row.evolution_score)}</td>
                <td>{formatNumber(row.sample_interval_s, "s")}</td>
                <td>{row.phase ?? row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
