import argparse
import csv
import json
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

from core.scheduler.fault_evolution_scheduler import RuntimeFeedback
from demo.evaluate_metrics import (
    compute_behavior_stats,
    compute_interval_stats,
    compute_latency_distribution,
    compute_overhead_stats,
    compute_redundancy,
    load_dataset,
    load_ground_truth_events,
    percentile_or_none,
    round_or_none,
)
from demo.evaluate_thesis_baselines import compute_detection_stats
from demo.evolution_sampling_experiment import EVENT_HEADERS, METRIC_HEADERS
from demo.run_thesis_statistical_experiment import (
    generate_trace,
    make_samplers,
    metric_record,
    parse_seed_list,
    set_replay_time,
)


ABLATIONS = {
    "full_ufe": {
        "label": "完整方法 U+F+E",
        "enable_urgency": True,
        "enable_field_priority": True,
        "enable_execution_pressure": True,
    },
    "no_u": {
        "label": "去除紧迫度 U",
        "enable_urgency": False,
        "enable_field_priority": True,
        "enable_execution_pressure": True,
    },
    "no_f": {
        "label": "去除字段优先级 F",
        "enable_urgency": True,
        "enable_field_priority": False,
        "enable_execution_pressure": True,
    },
    "no_e": {
        "label": "去除执行压力 E",
        "enable_urgency": True,
        "enable_field_priority": True,
        "enable_execution_pressure": False,
    },
}

METRICS_FOR_STATS = (
    "sample_count",
    "redundancy_rate_percent",
    "latency_p50_s",
    "latency_p95_s",
    "capture_rate_percent",
    "false_positive_rate_percent",
    "false_negative_rate_percent",
    "slow_lane_ratio_percent",
    "buffered_transport_ratio_percent",
    "degraded_phase_ratio_percent",
    "guarded_fast_ratio_percent",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Run thesis ablation experiments for adaptive-frequency sampling.")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--seeds", default="20260407,20260408,20260409,20260410,20260411,20260412,20260413,20260414")
    parser.add_argument("--duration", type=float, default=110.0)
    parser.add_argument("--trace-step", type=float, default=0.5)
    parser.add_argument("--fixed-interval", type=float, default=5.0)
    parser.add_argument("--t-min", type=float, default=1.0)
    parser.add_argument("--t-max", type=float, default=8.0)
    parser.add_argument("--devices", default="all")
    parser.add_argument("--gpu-vendor", default="auto", choices=["auto", "nvidia", "intel"])
    parser.add_argument("--pending-scale", type=float, default=1.0)
    parser.add_argument("--ring-backlog-scale", type=float, default=0.0)
    parser.add_argument("--dead-count", type=int, default=0)
    return parser.parse_args()


def make_ablation_samplers(trace_csv: Path, ablation_key: str, args):
    samplers = make_samplers(trace_csv, "evolution", args)
    config = ABLATIONS[ablation_key]
    for sampler in samplers.values():
        if sampler.scheduler is None:
            continue
        sampler.scheduler.enable_urgency = bool(config["enable_urgency"])
        sampler.scheduler.enable_field_priority = bool(config["enable_field_priority"])
        sampler.scheduler.enable_execution_pressure = bool(config["enable_execution_pressure"])
    return samplers


def run_ablation_fast(trace_csv: Path, metrics_csv: Path, events_out: Path, ablation_key: str, args) -> None:
    samplers = make_ablation_samplers(trace_csv, ablation_key, args)
    next_due = {device_id: 0.0 for device_id in samplers}
    pending = 0
    records = []
    event_records = []
    while next_due:
        trace_time = min(next_due.values())
        if trace_time > args.duration + 1e-9:
            break
        due_ids = [device_id for device_id, due_at in next_due.items() if due_at <= trace_time + 1e-9]
        feedback = RuntimeFeedback(
            pending=max(0, int(pending * args.pending_scale)),
            dead=max(0, int(args.dead_count)),
            ring_backlog=min(256, max(0, int(pending * args.ring_backlog_scale))),
            ring_capacity=256,
            uploader_active=False,
        )
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


def evaluate_ablation(metrics_csv: Path, events_csv: Path, ablation_key: str, args) -> dict:
    events = load_ground_truth_events(str(events_csv))
    df = load_dataset(str(metrics_csv), mode=ablation_key)
    df, redundancy = compute_redundancy(
        df,
        value_threshold=3.0,
        time_window=5.0,
        rolling_window=5,
    )
    latency_df, _ = compute_latency_distribution(
        df,
        change_threshold=5.0,
        high_quantile=0.85,
        reaction_window=12.0,
        interval_drop_ratio=0.15,
        ground_truth_events=events,
    )
    detection = compute_detection_stats(
        df,
        events=events,
        baseline_interval=args.fixed_interval,
        reaction_window=12.0,
        pre_event_window=3.0,
        interval_drop_ratio=0.15,
    )
    interval_stats = compute_interval_stats(df)
    behavior_stats = compute_behavior_stats(df)
    overhead_stats = compute_overhead_stats(df)
    degraded_phase_ratio = (df["phase"].astype(str) == "边端降级").mean() * 100.0 if len(df) else 0.0
    guarded_fast_ratio = (df["field_policy"].astype(str) == "降级保活").mean() * 100.0 if len(df) else 0.0
    return {
        "variant": ablation_key,
        "variant_label": ABLATIONS[ablation_key]["label"],
        "sample_count": int(len(df)),
        "redundancy_rate_percent": round_or_none(redundancy, 4),
        "interval_mean_s": interval_stats["mean_s"],
        "latency_p50_s": percentile_or_none(latency_df["latency_s"].tolist(), 50),
        "latency_p95_s": percentile_or_none(latency_df["latency_s"].tolist(), 95),
        "capture_rate_percent": detection["capture_rate"],
        "false_positive_rate_percent": detection["false_positive_rate"],
        "false_negative_rate_percent": detection["false_negative_rate"],
        "slow_lane_ratio_percent": behavior_stats["slow_lane_ratio_percent"],
        "buffered_transport_ratio_percent": behavior_stats["buffered_transport_ratio_percent"],
        "degraded_phase_ratio_percent": round_or_none(degraded_phase_ratio, 4),
        "guarded_fast_ratio_percent": round_or_none(guarded_fast_ratio, 4),
        "cpu_mean_percent": overhead_stats["cpu_mean_percent"],
        "mem_mean_mb": overhead_stats["mem_mean_mb"],
    }


def build_outputs(output_dir: Path, rows: list[dict], seeds: list[int]) -> None:
    combined = pd.DataFrame(rows)
    replicate_csv = output_dir / "ablation_replicate_summary.csv"
    combined.to_csv(replicate_csv, index=False, encoding="utf-8-sig")

    mean_rows = []
    for variant, config in ABLATIONS.items():
        scope = combined[combined["variant"] == variant]
        row = {"variant": variant, "variant_label": config["label"], "n": int(len(scope))}
        for metric in METRICS_FOR_STATS:
            values = pd.to_numeric(scope[metric], errors="coerce").dropna()
            row[f"{metric}_mean"] = round_or_none(values.mean(), 4)
            row[f"{metric}_std"] = round_or_none(values.std(ddof=1), 4)
        mean_rows.append(row)
    mean_std = pd.DataFrame(mean_rows)
    mean_csv = output_dir / "ablation_mean_std.csv"
    mean_std.to_csv(mean_csv, index=False, encoding="utf-8-sig")

    test_rows = []
    for metric in METRICS_FOR_STATS:
        pivot = combined.pivot(index="seed", columns="variant", values=metric).reindex(seeds)
        full = pd.to_numeric(pivot["full_ufe"], errors="coerce")
        for variant in ("no_u", "no_f", "no_e"):
            ablated = pd.to_numeric(pivot[variant], errors="coerce")
            valid = pd.concat([full, ablated], axis=1).dropna()
            if stats is None or len(valid) < 2:
                t_stat = p_value = None
            else:
                t_stat, p_value = stats.ttest_rel(valid.iloc[:, 0], valid.iloc[:, 1])
            test_rows.append(
                {
                    "metric": metric,
                    "comparison": f"full_ufe_vs_{variant}",
                    "test": "paired t-test",
                    "statistic": round_or_none(t_stat, 4),
                    "p_value": round_or_none(p_value, 6),
                    "n": int(len(valid)),
                    "full_mean": round_or_none(valid.iloc[:, 0].mean(), 4) if not valid.empty else None,
                    "ablated_mean": round_or_none(valid.iloc[:, 1].mean(), 4) if not valid.empty else None,
                }
            )
    tests = pd.DataFrame(test_rows)
    test_csv = output_dir / "ablation_paired_t_tests.csv"
    tests.to_csv(test_csv, index=False, encoding="utf-8-sig")

    def markdown_table(frame: pd.DataFrame) -> str:
        columns = [str(column) for column in frame.columns]
        lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
        for _, row in frame.iterrows():
            values = []
            for column in frame.columns:
                value = row[column]
                values.append("" if pd.isna(value) else str(value))
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    report_lines = [
        "# 自适应变频采样消融实验报告",
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
        markdown_table(tests),
        "",
        "## 输出文件",
        "",
        f"- `{replicate_csv.name}`",
        f"- `{mean_csv.name}`",
        f"- `{test_csv.name}`",
    ]
    (output_dir / "ablation_report.md").write_text("\n".join(report_lines), encoding="utf-8-sig")


def main():
    args = parse_args()
    seeds = parse_seed_list(args.seeds)
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = PROJECT_ROOT / "experiments" / "thesis_ablation" / datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ablation_config.json").write_text(
        json.dumps(
            {
                "seeds": seeds,
                "duration": args.duration,
                "trace_step": args.trace_step,
                "fixed_interval": args.fixed_interval,
                "t_min": args.t_min,
                "t_max": args.t_max,
                "devices": args.devices,
                "gpu_vendor": args.gpu_vendor,
                "pending_scale": args.pending_scale,
                "ring_backlog_scale": args.ring_backlog_scale,
                "dead_count": args.dead_count,
                "ablations": ABLATIONS,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    rows = []
    for index, seed in enumerate(seeds, start=1):
        run_dir = output_dir / f"seed_{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        trace_csv = run_dir / "trace.csv"
        events_csv = run_dir / "events.csv"
        generate_trace(seed, args.duration, args.trace_step, trace_csv, events_csv)
        for variant in ABLATIONS:
            metrics_csv = run_dir / f"{variant}_metrics.csv"
            events_out = run_dir / f"{variant}_events.csv"
            run_ablation_fast(trace_csv, metrics_csv, events_out, variant, args)
            row = evaluate_ablation(metrics_csv, events_csv, variant, args)
            row["seed"] = seed
            row["replicate"] = index
            rows.append(row)
        print(f"[{index}/{len(seeds)}] seed={seed}")

    build_outputs(output_dir, rows, seeds)
    print(f"ablation_run={output_dir}")


if __name__ == "__main__":
    main()
