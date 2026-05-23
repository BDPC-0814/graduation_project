import argparse
import csv
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    from scipy import stats
except ModuleNotFoundError:  # pragma: no cover
    stats = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.adapter.replay.replay_adapter import ReplayTraceDataset
from core.sampler.device_sampler import DeviceSampler
from core.scheduler.fault_evolution_scheduler import RuntimeFeedback
from demo.evolution_sampling_experiment import EVENT_HEADERS, METRIC_HEADERS
from demo.generate_replay_trace import build_events, cpu_row, gpu_row, npu_row


MODES = ("fixed", "threshold", "trend", "evolution")
MODE_LABELS = {
    "fixed": "固定频率",
    "threshold": "简单阈值触发",
    "trend": "趋势感知采样",
    "evolution": "自适应变频采样",
}
METRICS_FOR_STATS = (
    "redundancy_rate_percent",
    "latency_p50_s",
    "latency_p95_s",
    "capture_rate_percent",
    "false_positive_rate_percent",
    "false_negative_rate_percent",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Run multi-seed thesis replay experiments and statistical tests.")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--seeds", default="20260407,20260408,20260409,20260410,20260411,20260412,20260413,20260414")
    parser.add_argument("--duration", type=float, default=110.0)
    parser.add_argument("--trace-step", type=float, default=0.5)
    parser.add_argument("--fixed-interval", type=float, default=5.0)
    parser.add_argument("--t-min", type=float, default=1.0)
    parser.add_argument("--t-max", type=float, default=8.0)
    parser.add_argument("--devices", default="all")
    parser.add_argument("--gpu-vendor", default="auto", choices=["auto", "nvidia", "intel"])
    return parser.parse_args()


def parse_seed_list(text: str) -> list[int]:
    seeds = []
    for item in text.split(","):
        item = item.strip()
        if item:
            seeds.append(int(item))
    if len(seeds) < 2:
        raise ValueError("at least two seeds are required for statistical tests")
    return seeds


def generate_trace(seed: int, duration: float, step: float, trace_csv: Path, events_csv: Path) -> None:
    rng = np.random.default_rng(seed)
    times = np.arange(0.0, duration + step, step)
    rows = []
    for t in times:
        t = float(t)
        rows.append(cpu_row(t, rng))
        rows.append(gpu_row(t, rng))
        rows.append(npu_row(t, rng))
    pd.DataFrame(rows).to_csv(trace_csv, index=False, encoding="utf-8-sig")
    pd.DataFrame(build_events()).to_csv(events_csv, index=False, encoding="utf-8-sig")


def make_samplers(trace_csv: Path, mode: str, args) -> dict[str, DeviceSampler]:
    dataset = ReplayTraceDataset.load(str(trace_csv))
    adapters = dataset.build_adapters(requested_devices=[args.devices], gpu_vendor=args.gpu_vendor)
    return {
        device_id: DeviceSampler(
            device_id=device_id,
            adapter=adapter,
            mode=mode,
            fixed_interval=args.fixed_interval,
            t_min=args.t_min,
            t_max=args.t_max,
            static_limit=80.0,
        )
        for device_id, adapter in adapters.items()
    }


def set_replay_time(sampler: DeviceSampler, trace_time: float) -> None:
    adapter = sampler.adapter
    if hasattr(adapter, "_started_at"):
        adapter._started_at = time.monotonic() - trace_time


def metric_record(result, trace_time: float, pending: int, wallclock: str) -> dict:
    metrics = result.metrics
    return {
        "timestamp": wallclock,
        "time": metrics.trace_time_s if metrics.trace_time_s is not None else round(trace_time, 4),
        "device_id": metrics.device_id,
        "utilization": metrics.utilization,
        "chip_temp_c": metrics.chip_temp_c,
        "board_temp_c": metrics.board_temp_c,
        "power_w": metrics.power_w,
        "freq_mhz": metrics.freq_mhz,
        "freq_cap_mhz": metrics.freq_cap_mhz,
        "mem_total_mib": metrics.mem_total_mib,
        "mem_used_mib": metrics.mem_used_mib,
        "mem_util_percent": metrics.mem_util_percent,
        "pcie_rx_MBps": metrics.pcie_rx_MBps,
        "pcie_tx_MBps": metrics.pcie_tx_MBps,
        "pstate": metrics.pstate,
        "power_limit_w": metrics.power_limit_w,
        "throttle_flag": metrics.throttle_flag,
        "throttle_cause": metrics.throttle_cause,
        "last_error_code": metrics.last_error_code,
        "last_error_ts": metrics.last_error_ts,
        "fan_rpm": metrics.fan_rpm,
        "perf_per_watt": metrics.perf_per_watt,
        "correctable_err_s": metrics.correctable_err_s,
        "uncorrectable_err_s": metrics.uncorrectable_err_s,
        "device_uptime_s": metrics.device_uptime_s,
        "device_reset_count": metrics.device_reset_count,
        "nv_throttle_reasons": metrics.nv_throttle_reasons,
        "nv_ecc_correctable_total": metrics.nv_ecc_correctable_total,
        "nv_ecc_ue_total": metrics.nv_ecc_ue_total,
        "nv_mem_clock_mhz": metrics.nv_mem_clock_mhz,
        "nv_graphics_clock_mhz": metrics.nv_graphics_clock_mhz,
        "threads": metrics.threads,
        "ctx_switch_rate": metrics.ctx_switch_rate,
        "l3_cache_mib": metrics.l3_cache_mib,
        "io_util_percent": metrics.io_util_percent,
        "duty_cycle_percent": metrics.duty_cycle_percent,
        "collect_ts": metrics.collect_ts,
        "sample_interval_s": metrics.sample_interval_s,
        "evolution_score": result.evolution_score,
        "field_priority_score": result.field_priority_score,
        "execution_pressure_score": result.execution_pressure_score,
        "control_score": result.control_score,
        "interval": result.interval,
        "phase": result.phase,
        "field_policy": result.field_policy,
        "transport_policy": result.transport_policy,
        "sampled_slow": result.sampled_slow,
        "outbox_pending": pending,
        "outbox_dead": 0,
        "ring_backlog": 0,
        "overhead_cpu": 0.0,
        "overhead_mem_mb": 0.0,
        "status": metrics.status,
        "error": metrics.error,
    }


def run_mode_fast(trace_csv: Path, metrics_csv: Path, events_out: Path, mode: str, args) -> None:
    samplers = make_samplers(trace_csv, mode, args)
    next_due = {device_id: 0.0 for device_id in samplers}
    pending = 0
    records = []
    event_records = []
    while next_due:
        trace_time = min(next_due.values())
        if trace_time > args.duration + 1e-9:
            break
        due_ids = [device_id for device_id, due_at in next_due.items() if due_at <= trace_time + 1e-9]
        feedback = RuntimeFeedback(pending=pending, dead=0, ring_backlog=0, ring_capacity=256, uploader_active=False)
        wallclock = f"replay-{trace_time:.4f}"
        for device_id in due_ids:
            sampler = samplers[device_id]
            sampler.set_runtime_feedback(feedback)
            set_replay_time(sampler, trace_time)
            result = sampler.sample()
            records.append(metric_record(result, trace_time, pending, wallclock))
            pending += 1
            if result.metrics.status != "ok":
                event_records.append(
                    {
                        "timestamp": wallclock,
                        "time": result.metrics.trace_time_s if result.metrics.trace_time_s is not None else round(trace_time, 4),
                        "device_id": result.metrics.device_id,
                        "event_type": "collector_unavailable",
                        "severity": "high",
                        "message": result.metrics.error or "collector unavailable",
                        "detail": result.metrics.summary(),
                    }
                )
            next_due[device_id] = trace_time + max(float(result.interval), 1e-6)

    metrics_csv.parent.mkdir(parents=True, exist_ok=True)
    with metrics_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=METRIC_HEADERS)
        writer.writeheader()
        writer.writerows(records)
    with events_out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=EVENT_HEADERS)
        writer.writeheader()
        writer.writerows(event_records)


def run_evaluator(run_dir: Path, mode_files: dict[str, Path], events_csv: Path) -> Path:
    report_dir = run_dir / "report"
    command = [
        sys.executable,
        "demo/evaluate_thesis_baselines.py",
        "--fixed",
        str(mode_files["fixed"]),
        "--threshold",
        str(mode_files["threshold"]),
        "--trend",
        str(mode_files["trend"]),
        "--evolution",
        str(mode_files["evolution"]),
        "--ground-truth-events",
        str(events_csv),
        "--output-dir",
        str(report_dir),
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    return report_dir


def round_value(value: Optional[float], digits: int = 4) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def build_statistical_outputs(output_dir: Path, replicate_frames: list[pd.DataFrame], seeds: list[int]) -> None:
    combined = pd.concat(replicate_frames, ignore_index=True)
    combined["mode_label"] = combined["mode"].map(MODE_LABELS).fillna(combined["mode"])
    replicate_csv = output_dir / "replicate_summary.csv"
    combined.to_csv(replicate_csv, index=False, encoding="utf-8-sig")

    mean_std_rows = []
    for mode in MODES:
        scope = combined[combined["mode"] == mode]
        row = {"mode": mode, "mode_label": MODE_LABELS[mode], "n": int(len(scope))}
        for metric in METRICS_FOR_STATS:
            values = pd.to_numeric(scope[metric], errors="coerce").dropna()
            row[f"{metric}_mean"] = round_value(values.mean())
            row[f"{metric}_std"] = round_value(values.std(ddof=1))
        mean_std_rows.append(row)
    mean_std = pd.DataFrame(mean_std_rows)
    mean_std_csv = output_dir / "metric_mean_std.csv"
    mean_std.to_csv(mean_std_csv, index=False, encoding="utf-8-sig")

    t_rows = []
    a_rows = []
    for metric in METRICS_FOR_STATS:
        pivot = combined.pivot(index="seed", columns="mode", values=metric).reindex(seeds)
        if stats is None:
            anova_stat = anova_p = None
        else:
            groups = [pd.to_numeric(pivot[mode], errors="coerce").dropna().to_numpy(dtype=float) for mode in MODES]
            anova_stat, anova_p = stats.f_oneway(*groups)
        a_rows.append(
            {
                "metric": metric,
                "test": "one-way ANOVA",
                "statistic": round_value(anova_stat),
                "p_value": round_value(anova_p, 6),
                "n_per_mode": len(seeds),
            }
        )
        for baseline in ("fixed", "threshold", "trend"):
            evo = pd.to_numeric(pivot["evolution"], errors="coerce")
            base = pd.to_numeric(pivot[baseline], errors="coerce")
            valid = pd.concat([evo, base], axis=1).dropna()
            if stats is None or len(valid) < 2:
                t_stat = p_value = None
            else:
                t_stat, p_value = stats.ttest_rel(valid.iloc[:, 0], valid.iloc[:, 1])
            t_rows.append(
                {
                    "metric": metric,
                    "comparison": f"evolution_vs_{baseline}",
                    "test": "paired t-test",
                    "statistic": round_value(t_stat),
                    "p_value": round_value(p_value, 6),
                    "n": int(len(valid)),
                    "evolution_mean": round_value(valid.iloc[:, 0].mean()) if not valid.empty else None,
                    "baseline_mean": round_value(valid.iloc[:, 1].mean()) if not valid.empty else None,
                }
            )
    t_csv = output_dir / "paired_t_tests.csv"
    a_csv = output_dir / "anova_tests.csv"
    pd.DataFrame(t_rows).to_csv(t_csv, index=False, encoding="utf-8-sig")
    pd.DataFrame(a_rows).to_csv(a_csv, index=False, encoding="utf-8-sig")

    def markdown_table(frame: pd.DataFrame) -> str:
        columns = [str(column) for column in frame.columns]
        rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
        for _, row in frame.iterrows():
            rows.append("| " + " | ".join("" if pd.isna(row[column]) else str(row[column]) for column in frame.columns) + " |")
        return "\n".join(rows)

    t_frame = pd.DataFrame(t_rows)
    a_frame = pd.DataFrame(a_rows)
    lines = [
        "# 多轮回放统计检验报告",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"重复次数：{len(seeds)}",
        f"随机种子：{', '.join(str(seed) for seed in seeds)}",
        "",
        "## 均值与标准差",
        "",
        markdown_table(mean_std),
        "",
        "## 配对 t 检验",
        "",
        markdown_table(t_frame),
        "",
        "## 单因素方差分析",
        "",
        markdown_table(a_frame),
        "",
        "## 输出文件",
        "",
        f"- `{replicate_csv.name}`",
        f"- `{mean_std_csv.name}`",
        f"- `{t_csv.name}`",
        f"- `{a_csv.name}`",
    ]
    (output_dir / "statistical_report.md").write_text("\n".join(lines), encoding="utf-8-sig")


def main():
    args = parse_args()
    seeds = parse_seed_list(args.seeds)
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = PROJECT_ROOT / "experiments" / "thesis_statistical" / datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    replicate_frames = []
    for index, seed in enumerate(seeds, start=1):
        run_dir = output_dir / f"seed_{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        trace_csv = run_dir / "trace.csv"
        events_csv = run_dir / "events.csv"
        generate_trace(seed, args.duration, args.trace_step, trace_csv, events_csv)
        mode_files = {}
        for mode in MODES:
            metrics_csv = run_dir / f"{mode}_metrics.csv"
            events_out = run_dir / f"{mode}_events.csv"
            run_mode_fast(trace_csv, metrics_csv, events_out, mode, args)
            mode_files[mode] = metrics_csv
        report_dir = run_evaluator(run_dir, mode_files, events_csv)
        summary = pd.read_csv(report_dir / "multi_baseline_summary.csv")
        summary.insert(0, "seed", seed)
        summary.insert(1, "replicate", index)
        replicate_frames.append(summary)
        print(f"[{index}/{len(seeds)}] seed={seed} report={report_dir}")

    build_statistical_outputs(output_dir, replicate_frames, seeds)
    print(f"statistical_run={output_dir}")


if __name__ == "__main__":
    main()
