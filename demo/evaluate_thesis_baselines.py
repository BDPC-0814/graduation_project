import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo.evaluate_metrics import (
    build_latency_cdf_chart,
    build_chart_payload,
    compute_behavior_stats,
    compute_interval_stats,
    compute_latency_distribution,
    compute_overhead_stats,
    compute_redundancy,
    load_dataset,
    load_ground_truth_events,
    native_value,
    percentile_or_none,
    round_or_none,
    write_boxplot_figure,
    write_cdf_figure,
    write_line_figure,
)


MODE_LABELS = {
    "fixed": "固定频率",
    "threshold": "简单阈值触发",
    "trend": "趋势感知采样",
    "evolution": "本文方法",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate thesis baselines for adaptive variable-frequency sampling.")
    parser.add_argument("--fixed", required=True)
    parser.add_argument("--threshold", required=True)
    parser.add_argument("--trend", required=True)
    parser.add_argument("--evolution", required=True)
    parser.add_argument("--ground-truth-events", required=True)
    parser.add_argument("--output-dir", default="experiments/thesis_multi_baseline/latest")
    parser.add_argument("--redundancy-value-threshold", type=float, default=3.0)
    parser.add_argument("--redundancy-time-window", type=float, default=5.0)
    parser.add_argument("--rolling-window", type=int, default=5)
    parser.add_argument("--latency-change-threshold", type=float, default=5.0)
    parser.add_argument("--latency-high-quantile", type=float, default=0.85)
    parser.add_argument("--latency-reaction-window", type=float, default=12.0)
    parser.add_argument("--pre-event-window", type=float, default=3.0)
    parser.add_argument("--latency-interval-drop-ratio", type=float, default=0.15)
    parser.add_argument("--figure-dpi", type=int, default=220)
    return parser.parse_args()


def is_accelerated_phase(phase: str) -> bool:
    text = str(phase or "").lower()
    return any(keyword in text for keyword in ("focus", "recovery", "high")) or any(
        keyword in str(phase or "") for keyword in ("聚焦", "恢复", "高频", "设备失联")
    )


def is_response_sample(row: pd.Series, baseline_interval: float, interval_drop_ratio: float) -> bool:
    status = str(row.get("status", "ok")).lower()
    if status not in {"ok", "", "nan"}:
        return True
    if str(row.get("error", "")).strip() not in {"", "nan", "None"}:
        return True
    if str(row.get("last_error_code", "")).strip() not in {"", "nan", "None"}:
        return True
    if str(row.get("throttle_flag", "")).lower() in {"true", "1", "yes"}:
        return True
    if is_accelerated_phase(str(row.get("phase", ""))):
        return True

    interval = pd.to_numeric(row.get("effective_interval_s"), errors="coerce")
    if pd.notna(interval) and baseline_interval > 0 and interval <= baseline_interval * (1.0 - interval_drop_ratio):
        return True

    utilization = pd.to_numeric(row.get("utilization"), errors="coerce")
    mem_util = pd.to_numeric(row.get("mem_util_percent"), errors="coerce")
    chip_temp = pd.to_numeric(row.get("chip_temp_c"), errors="coerce")
    return bool(
        (pd.notna(utilization) and utilization >= 75.0)
        or (pd.notna(mem_util) and mem_util >= 85.0)
        or (pd.notna(chip_temp) and chip_temp >= 80.0)
    )


def row_in_event_window(row: pd.Series, events: pd.DataFrame, reaction_window: float, pre_event_window: float) -> bool:
    sample_time = pd.to_numeric(row.get("time"), errors="coerce")
    if pd.isna(sample_time):
        return False
    device_id = str(row.get("device_id", ""))
    for event in events.itertuples(index=False):
        event_time = float(event.time)
        event_device = str(getattr(event, "device_id", "") or "")
        if event_device and event_device != device_id:
            continue
        if event_time - pre_event_window <= float(sample_time) <= event_time + reaction_window:
            return True
    return False


def compute_detection_stats(
    df: pd.DataFrame,
    events: pd.DataFrame,
    baseline_interval: float,
    reaction_window: float,
    pre_event_window: float,
    interval_drop_ratio: float,
) -> dict[str, Any]:
    responses = df.apply(
        lambda row: is_response_sample(row, baseline_interval=baseline_interval, interval_drop_ratio=interval_drop_ratio),
        axis=1,
    )
    truth = df.apply(
        lambda row: row_in_event_window(
            row,
            events=events,
            reaction_window=reaction_window,
            pre_event_window=pre_event_window,
        ),
        axis=1,
    )

    tp = int((responses & truth).sum())
    fp = int((responses & ~truth).sum())
    tn = int((~responses & ~truth).sum())
    fn = int((~responses & truth).sum())

    delays: list[float] = []
    captured = 0
    missed = 0
    for event in events.itertuples(index=False):
        event_time = float(event.time)
        event_device = str(getattr(event, "device_id", "") or "")
        scope = df[df["time"].between(event_time - pre_event_window, event_time + reaction_window, inclusive="both")]
        if event_device:
            scope = scope[scope["device_id"].astype(str) == event_device]
        if scope.empty:
            missed += 1
            continue
        scope_response = scope.apply(
            lambda row: is_response_sample(row, baseline_interval=baseline_interval, interval_drop_ratio=interval_drop_ratio),
            axis=1,
        )
        matched = scope[scope_response]
        if matched.empty:
            missed += 1
            continue
        first = matched.sort_values("time").iloc[0]
        captured += 1
        delays.append(float(first["time"]) - event_time)

    total_events = captured + missed
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "false_positive_rate": round_or_none(fp / max(fp + tn, 1) * 100.0, 4),
        "false_negative_rate": round_or_none(fn / max(fn + tp, 1) * 100.0, 4),
        "event_count": total_events,
        "captured_events": captured,
        "missed_events": missed,
        "capture_rate": round_or_none(captured / max(total_events, 1) * 100.0, 4),
        "event_delay_mean_s": round_or_none(np.mean(delays), 4) if delays else None,
        "event_delay_p95_s": percentile_or_none(delays, 95) if delays else None,
    }


def mode_summary_row(
    mode: str,
    df: pd.DataFrame,
    fixed_count: int,
    redundancy_rate: float,
    latency_df: pd.DataFrame,
    detection: dict[str, Any],
) -> dict[str, Any]:
    interval_stats = compute_interval_stats(df)
    overhead_stats = compute_overhead_stats(df)
    behavior_stats = compute_behavior_stats(df)
    return {
        "mode": mode,
        "mode_label": MODE_LABELS.get(mode, mode),
        "sample_count": int(len(df)),
        "sample_reduction_vs_fixed_percent": round_or_none((fixed_count - len(df)) / max(fixed_count, 1) * 100.0, 4),
        "redundancy_rate_percent": round_or_none(redundancy_rate, 4),
        "interval_mean_s": interval_stats["mean_s"],
        "interval_p95_s": interval_stats["p95_s"],
        "interval_min_s": interval_stats["min_s"],
        "latency_p50_s": percentile_or_none(latency_df["latency_s"].tolist(), 50),
        "latency_p95_s": percentile_or_none(latency_df["latency_s"].tolist(), 95),
        "capture_rate_percent": detection["capture_rate"],
        "false_positive_rate_percent": detection["false_positive_rate"],
        "false_negative_rate_percent": detection["false_negative_rate"],
        "slow_lane_ratio_percent": behavior_stats["slow_lane_ratio_percent"],
        "buffered_transport_ratio_percent": behavior_stats["buffered_transport_ratio_percent"],
        "cpu_mean_percent": overhead_stats["cpu_mean_percent"],
        "mem_mean_mb": overhead_stats["mem_mean_mb"],
    }


def write_detection_figure(path: Path, summary_rows: list[dict[str, Any]], dpi: int):
    labels = [row["mode"] for row in summary_rows]
    capture = [row["capture_rate_percent"] for row in summary_rows]
    fpr = [row["false_positive_rate_percent"] for row in summary_rows]
    fnr = [row["false_negative_rate_percent"] for row in summary_rows]

    x = np.arange(len(labels))
    width = 0.25
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    ax.bar(x - width, capture, width, label="Capture Rate")
    ax.bar(x, fpr, width, label="False Positive Rate")
    ax.bar(x + width, fnr, width, label="False Negative Rate")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0)
    ax.set_ylim(0, 105)
    ax.set_ylabel("%")
    ax.set_title("Detection Metrics")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def write_markdown_report(path: Path, report: dict[str, Any]):
    rows = report["summary_rows"]
    lines = [
        "# 多基线自适应采样评估报告",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 1. 多基线汇总",
        "",
        "| 方法 | 采样点数 | 相对固定频率减少率/% | 冗余率/% | P95延迟/s | 异常捕获率/% | 误报率/% | 漏报率/% |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {mode_label} | {sample_count} | {sample_reduction_vs_fixed_percent} | {redundancy_rate_percent} | "
            "{latency_p95_s} | {capture_rate_percent} | {false_positive_rate_percent} | {false_negative_rate_percent} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## 2. 指标说明",
            "",
            "- 固定频率为传统周期采样基线。",
            "- 简单阈值触发根据利用率、内存、温度、限频和异常状态调整采样间隔。",
            "- 趋势感知采样根据相邻采样的利用率、温度和内存变化幅度调整采样间隔。",
            "- 本文方法综合紧迫度、字段优先级和边端执行压力，并输出采样相位、字段策略和传输策略。",
            "- 误报率、漏报率基于统一真值事件窗口进行样本级统计；异常捕获率基于事件级统计。",
            "- 考虑故障预警场景，检测统计将事件发生前的短时提前响应纳入有效窗口；延迟统计仍按事件发生后的首次响应计算。",
            "",
            "## 3. 输出文件",
            "",
            f"- 多基线汇总：`{report['files']['summary_csv']}`",
            f"- 检测指标：`{report['files']['detection_csv']}`",
            f"- 延迟样本：`{report['files']['latency_csv']}`",
            f"- JSON 报告：`{report['files']['json_report']}`",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    figures_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    events = load_ground_truth_events(args.ground_truth_events)
    paths = {
        "fixed": args.fixed,
        "threshold": args.threshold,
        "trend": args.trend,
        "evolution": args.evolution,
    }

    frames: dict[str, pd.DataFrame] = {}
    latency_frames: dict[str, pd.DataFrame] = {}
    redundancy_rates: dict[str, float] = {}
    detection_stats: dict[str, dict[str, Any]] = {}
    latency_meta: dict[str, dict[str, Any]] = {}

    for mode, path in paths.items():
        df = load_dataset(path, mode=mode)
        df, redundancy = compute_redundancy(
            df,
            value_threshold=args.redundancy_value_threshold,
            time_window=args.redundancy_time_window,
            rolling_window=args.rolling_window,
        )
        latency_df, meta = compute_latency_distribution(
            df,
            change_threshold=args.latency_change_threshold,
            high_quantile=args.latency_high_quantile,
            reaction_window=args.latency_reaction_window,
            interval_drop_ratio=args.latency_interval_drop_ratio,
            ground_truth_events=events,
        )
        frames[mode] = df
        redundancy_rates[mode] = redundancy
        latency_frames[mode] = latency_df
        latency_meta[mode] = meta

    fixed_interval = frames["fixed"]["effective_interval_s"].dropna().median()
    if pd.isna(fixed_interval):
        fixed_interval = 0.0
    for mode, frame in frames.items():
        detection_stats[mode] = compute_detection_stats(
            frame,
            events=events,
            baseline_interval=float(fixed_interval),
            reaction_window=args.latency_reaction_window,
            pre_event_window=args.pre_event_window,
            interval_drop_ratio=args.latency_interval_drop_ratio,
        )

    fixed_count = len(frames["fixed"])
    summary_rows = [
        mode_summary_row(
            mode=mode,
            df=frames[mode],
            fixed_count=fixed_count,
            redundancy_rate=redundancy_rates[mode],
            latency_df=latency_frames[mode],
            detection=detection_stats[mode],
        )
        for mode in paths
    ]

    merged_timeseries = pd.concat(frames.values(), ignore_index=True)
    latency_samples = pd.concat(latency_frames.values(), ignore_index=True)
    summary_csv = output_dir / "multi_baseline_summary.csv"
    detection_csv = output_dir / "detection_metrics.csv"
    latency_csv = output_dir / "latency_samples.csv"
    timeseries_csv = output_dir / "timeseries_metrics.csv"
    json_report = output_dir / "report.json"
    markdown_report = output_dir / "report.md"

    pd.DataFrame(summary_rows).to_csv(summary_csv, index=False, encoding="utf-8-sig")
    pd.DataFrame([{"mode": mode, "mode_label": MODE_LABELS.get(mode, mode), **stats} for mode, stats in detection_stats.items()]).to_csv(
        detection_csv,
        index=False,
        encoding="utf-8-sig",
    )
    latency_samples.to_csv(latency_csv, index=False, encoding="utf-8-sig")
    merged_timeseries.to_csv(timeseries_csv, index=False, encoding="utf-8-sig")

    write_line_figure(
        figures_dir / "utilization_time.png",
        frames,
        "utilization",
        "Utilization Over Time",
        "Utilization (%)",
        args.figure_dpi,
    )
    write_line_figure(
        figures_dir / "interval_time.png",
        frames,
        "effective_interval_s",
        "Effective Sampling Interval",
        "Sampling Interval (s)",
        args.figure_dpi,
    )
    write_cdf_figure(figures_dir / "latency_cdf.png", latency_frames, args.figure_dpi)
    write_boxplot_figure(figures_dir / "latency_boxplot.png", latency_frames, args.figure_dpi)
    write_detection_figure(figures_dir / "detection_metrics.png", summary_rows, args.figure_dpi)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": paths | {"ground_truth_events": args.ground_truth_events},
        "parameters": {
            "latency_reaction_window": args.latency_reaction_window,
            "latency_interval_drop_ratio": args.latency_interval_drop_ratio,
            "redundancy_value_threshold": args.redundancy_value_threshold,
            "redundancy_time_window": args.redundancy_time_window,
        },
        "summary_rows": summary_rows,
        "detection_stats": detection_stats,
        "latency_detection": latency_meta,
        "charts": {
            "utilization_time": build_chart_payload(frames, "utilization", "Utilization Over Time", "Utilization (%)"),
            "interval_time": build_chart_payload(frames, "effective_interval_s", "Effective Sampling Interval", "Sampling Interval (s)"),
            "latency_cdf": build_latency_cdf_chart(latency_frames),
            "redundancy_time": build_chart_payload(frames, "redundancy_score", "Redundancy Score Over Time", "Redundancy (%)"),
        },
        "files": {
            "summary_csv": summary_csv.name,
            "detection_csv": detection_csv.name,
            "latency_csv": latency_csv.name,
            "timeseries_csv": timeseries_csv.name,
            "json_report": json_report.name,
            "markdown_report": markdown_report.name,
            "figures_dir": "figures",
        },
    }
    json_report.write_text(json.dumps(native_value(report), ensure_ascii=False, indent=2), encoding="utf-8-sig")
    write_markdown_report(markdown_report, report)

    print("==========================================================")
    print("      多基线自适应采样评估报告")
    print("==========================================================")
    for row in summary_rows:
        print(
            f"{row['mode_label']}: samples={row['sample_count']}, "
            f"redundancy={row['redundancy_rate_percent']}%, "
            f"p95_latency={row['latency_p95_s']}s, "
            f"capture={row['capture_rate_percent']}%, "
            f"fpr={row['false_positive_rate_percent']}%, "
            f"fnr={row['false_negative_rate_percent']}%"
        )
    print(f"输出目录: {output_dir}")
    print("==========================================================")


if __name__ == "__main__":
    main()
