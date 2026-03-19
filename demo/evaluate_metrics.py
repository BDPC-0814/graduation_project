import argparse
import json
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


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate fixed-frequency sampling against HAVFS.")
    parser.add_argument("--fixed", required=True, help="Path to fixed mode CSV")
    parser.add_argument("--havfs", required=True, help="Path to HAVFS mode CSV")
    parser.add_argument("--output-dir", default="experiments/evaluation/latest", help="Directory for reports and figures")
    parser.add_argument(
        "--curve-output",
        default="",
        help="Optional compatibility output for the merged time-series CSV. Defaults to <output-dir>/timeseries_metrics.csv",
    )
    parser.add_argument("--redundancy-value-threshold", type=float, default=1.0)
    parser.add_argument("--redundancy-time-window", type=float, default=5.0)
    parser.add_argument("--rolling-window", type=int, default=5)
    parser.add_argument("--latency-change-threshold", type=float, default=5.0)
    parser.add_argument("--latency-high-quantile", type=float, default=0.85)
    parser.add_argument("--latency-reaction-window", type=float, default=12.0)
    parser.add_argument("--latency-interval-drop-ratio", type=float, default=0.15)
    parser.add_argument("--figure-dpi", type=int, default=220)
    return parser.parse_args()


def round_or_none(value: Any, digits: int = 4):
    if value is None:
        return None
    if pd.isna(value):
        return None
    return round(float(value), digits)


def percentile_or_none(values: list[float], percentile: float):
    if not values:
        return None
    return float(np.percentile(values, percentile))


def native_value(value: Any):
    if isinstance(value, dict):
        return {key: native_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [native_value(item) for item in value]
    if isinstance(value, tuple):
        return [native_value(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def normalize_mode_name(mode: str):
    return "HAVFS" if mode.lower() == "havfs" else "固定频率"


def load_dataset(path: str, mode: str):
    df = pd.read_csv(path)
    work = df.copy()
    work["mode"] = mode
    work["time"] = pd.to_numeric(work.get("time"), errors="coerce")
    work["utilization"] = pd.to_numeric(work.get("utilization"), errors="coerce")
    work["overhead_cpu"] = pd.to_numeric(work.get("overhead_cpu"), errors="coerce")
    work["overhead_mem_mb"] = pd.to_numeric(work.get("overhead_mem_mb"), errors="coerce")

    interval = pd.to_numeric(work.get("interval"), errors="coerce") if "interval" in work.columns else pd.Series(dtype=float)
    sample_interval = (
        pd.to_numeric(work.get("sample_interval_s"), errors="coerce")
        if "sample_interval_s" in work.columns
        else pd.Series(dtype=float)
    )
    if len(interval) == len(work):
        work["effective_interval_s"] = interval
        if len(sample_interval) == len(work):
            work["effective_interval_s"] = work["effective_interval_s"].fillna(sample_interval)
    elif len(sample_interval) == len(work):
        work["effective_interval_s"] = sample_interval
    else:
        work["effective_interval_s"] = np.nan

    work = work.sort_values("time").reset_index(drop=True)
    work["sample_gap_s"] = work["time"].diff()
    if len(work) > 1:
        default_gap = work["sample_gap_s"].dropna().median()
    else:
        default_gap = work["effective_interval_s"].dropna().median()
    if pd.isna(default_gap):
        default_gap = 0.0
    work["sample_gap_s"] = work["sample_gap_s"].fillna(work["effective_interval_s"]).fillna(default_gap)
    work["effective_interval_s"] = work["effective_interval_s"].fillna(work["sample_gap_s"]).fillna(default_gap)
    work["state"] = work.get("state", "").fillna("").astype(str)
    return work


def compute_redundancy(df: pd.DataFrame, value_threshold: float, time_window: float, rolling_window: int):
    flags = []
    anchor_util = None
    anchor_time = None

    for row in df.itertuples(index=False):
        util = row.utilization
        current_time = row.time
        redundant = False

        if anchor_util is not None and pd.notna(util) and pd.notna(current_time):
            value_close = abs(float(util) - float(anchor_util)) <= value_threshold
            time_close = abs(float(current_time) - float(anchor_time)) <= time_window
            redundant = value_close and time_close

        flags.append(redundant)
        if not redundant and pd.notna(util) and pd.notna(current_time):
            anchor_util = float(util)
            anchor_time = float(current_time)

    work = df.copy()
    work["redundant"] = flags
    work["redundancy_score"] = pd.Series([float(flag) for flag in flags]).rolling(
        window=max(1, rolling_window), min_periods=1
    ).mean() * 100.0
    rate = float(np.mean(flags) * 100.0) if flags else 0.0
    return work, rate


def classify_event_type(is_jump: bool, is_high: bool):
    if is_jump and is_high:
        return "jump_and_high_load"
    if is_jump:
        return "jump"
    if is_high:
        return "high_load"
    return "proxy"


def is_accelerated_state(state_text: str):
    lowered = (state_text or "").lower()
    return "high" in lowered or "高频" in state_text


def compute_latency_distribution(
    df: pd.DataFrame,
    change_threshold: float,
    high_quantile: float,
    reaction_window: float,
    interval_drop_ratio: float,
):
    work = df.copy()
    util = work["utilization"]
    diffs = util.diff().abs().fillna(0.0)
    high_threshold = float(util.quantile(high_quantile)) if util.notna().any() else np.nan
    median_interval = work["effective_interval_s"].dropna().median()
    if pd.isna(median_interval) or median_interval <= 0:
        median_interval = 0.0
    candidate_mask = (diffs >= change_threshold) | (util >= high_threshold)
    events = []
    last_event_time = None

    for idx, row in work.loc[candidate_mask].iterrows():
        event_time = row["time"]
        if pd.isna(event_time):
            continue
        cooldown = max(median_interval, 1e-9)
        if last_event_time is not None and float(event_time) - float(last_event_time) < cooldown:
            continue

        current_interval = float(row["effective_interval_s"])
        is_jump = bool(diffs.iloc[idx] >= change_threshold)
        is_high = bool(pd.notna(high_threshold) and row["utilization"] >= high_threshold)

        future = work[work["time"] > event_time]
        future = future[future["time"] <= float(event_time) + reaction_window]
        accelerated = future[
            (future["effective_interval_s"] <= current_interval * (1.0 - interval_drop_ratio))
            | future["state"].map(is_accelerated_state)
        ]
        if not accelerated.empty:
            latency = float(accelerated.iloc[0]["time"] - event_time)
            source = "accelerated"
        elif not future.empty:
            latency = float(future.iloc[0]["time"] - event_time)
            source = "next_refresh"
        else:
            latency = float(max(current_interval, 0.0))
            source = "estimated_by_interval"

        events.append(
            {
                "mode": row["mode"],
                "event_time": float(event_time),
                "latency_s": latency,
                "latency_source": source,
                "event_type": classify_event_type(is_jump=is_jump, is_high=is_high),
                "event_utilization": round_or_none(row["utilization"], 4),
                "event_interval_s": round_or_none(current_interval, 4),
            }
        )
        last_event_time = float(event_time)

    if not events and len(work) > 1:
        for row in work.iloc[1:].itertuples(index=False):
            events.append(
                {
                    "mode": row.mode,
                    "event_time": float(row.time),
                    "latency_s": float(row.sample_gap_s),
                    "latency_source": "interval_proxy",
                    "event_type": "interval_proxy",
                    "event_utilization": round_or_none(row.utilization, 4),
                    "event_interval_s": round_or_none(row.effective_interval_s, 4),
                }
            )

    return pd.DataFrame(events), {"high_util_threshold": round_or_none(high_threshold, 4)}


def compute_interval_stats(df: pd.DataFrame):
    values = df["effective_interval_s"].dropna().tolist()
    if not values:
        return {
            "mean_s": None,
            "median_s": None,
            "std_s": None,
            "min_s": None,
            "max_s": None,
            "p95_s": None,
        }
    return {
        "mean_s": round_or_none(np.mean(values), 4),
        "median_s": round_or_none(np.median(values), 4),
        "std_s": round_or_none(np.std(values), 4),
        "min_s": round_or_none(np.min(values), 4),
        "max_s": round_or_none(np.max(values), 4),
        "p95_s": round_or_none(np.percentile(values, 95), 4),
    }


def compute_overhead_stats(df: pd.DataFrame):
    cpu_values = df["overhead_cpu"].dropna().tolist()
    mem_values = df["overhead_mem_mb"].dropna().tolist()
    return {
        "cpu_mean_percent": round_or_none(np.mean(cpu_values), 4) if cpu_values else None,
        "cpu_p95_percent": percentile_or_none(cpu_values, 95),
        "mem_mean_mb": round_or_none(np.mean(mem_values), 4) if mem_values else None,
        "mem_p95_mb": percentile_or_none(mem_values, 95),
    }


def build_summary_rows(report_summary: dict[str, Any]):
    sample = report_summary["sample_count"]
    redundancy = report_summary["redundancy_rate_percent"]
    interval_stats = report_summary["interval_stats_s"]
    latency = report_summary["latency_stats_s"]
    overhead = report_summary["overhead_stats"]

    rows = [
        {
            "metric": "sample_count",
            "fixed": sample["fixed"],
            "havfs": sample["havfs"],
            "delta_percent": sample["reduction_percent"],
            "unit": "points",
        },
        {
            "metric": "redundancy_rate",
            "fixed": redundancy["fixed"],
            "havfs": redundancy["havfs"],
            "delta_percent": round_or_none(redundancy["fixed"] - redundancy["havfs"], 4),
            "unit": "%",
        },
        {
            "metric": "interval_mean",
            "fixed": interval_stats["fixed"]["mean_s"],
            "havfs": interval_stats["havfs"]["mean_s"],
            "delta_percent": None,
            "unit": "s",
        },
        {
            "metric": "latency_p50",
            "fixed": latency["fixed"]["p50_s"],
            "havfs": latency["havfs"]["p50_s"],
            "delta_percent": None,
            "unit": "s",
        },
        {
            "metric": "latency_p95",
            "fixed": latency["fixed"]["p95_s"],
            "havfs": latency["havfs"]["p95_s"],
            "delta_percent": None,
            "unit": "s",
        },
        {
            "metric": "cpu_overhead_mean",
            "fixed": overhead["fixed"]["cpu_mean_percent"],
            "havfs": overhead["havfs"]["cpu_mean_percent"],
            "delta_percent": None,
            "unit": "%",
        },
        {
            "metric": "mem_overhead_mean",
            "fixed": overhead["fixed"]["mem_mean_mb"],
            "havfs": overhead["havfs"]["mem_mean_mb"],
            "delta_percent": None,
            "unit": "MB",
        },
    ]
    return rows


def build_chart_payload(series_frames: dict[str, pd.DataFrame], value_column: str, title: str, y_axis_name: str):
    label_map: dict[str, float] = {}
    for frame in series_frames.values():
        for value in frame["time"].dropna().tolist():
            label_map[f"{float(value):.2f}s"] = float(value)

    labels = [item[0] for item in sorted(label_map.items(), key=lambda entry: entry[1])]
    series = []
    for mode, frame in series_frames.items():
        points = {f"{float(row.time):.2f}s": row._asdict()[value_column] for row in frame.itertuples(index=False)}
        series.append(
            {
                "name": normalize_mode_name(mode),
                "data": [round_or_none(points.get(label), 4) for label in labels],
            }
        )
    return {"title": title, "labels": labels, "series": series, "y_axis_name": y_axis_name}


def build_latency_cdf_chart(latency_frames: dict[str, pd.DataFrame]):
    per_mode_values = {}
    for mode, frame in latency_frames.items():
        values = sorted(frame["latency_s"].dropna().astype(float).tolist())
        per_mode_values[mode] = values

    label_values = sorted({round(value, 4) for values in per_mode_values.values() for value in values})
    labels = [f"{value:.2f}s" for value in label_values]
    series = []

    for mode, values in per_mode_values.items():
        cdf_values = []
        if not values:
            cdf_values = [None for _ in labels]
        else:
            array = np.array(values)
            cdf_values = [round_or_none(float(np.searchsorted(array, value, side="right") / len(array)) * 100.0, 4) for value in label_values]
        series.append({"name": normalize_mode_name(mode), "data": cdf_values})

    return {"title": "延迟 CDF 曲线", "labels": labels, "series": series, "y_axis_name": "累计概率 (%)"}


def apply_plot_style():
    for style_name in ("seaborn-v0_8-whitegrid", "seaborn-whitegrid", "ggplot"):
        try:
            plt.style.use(style_name)
            return
        except OSError:
            continue


def write_line_figure(path: Path, series_frames: dict[str, pd.DataFrame], value_column: str, title: str, y_label: str, dpi: int):
    apply_plot_style()
    fig, ax = plt.subplots(figsize=(11, 4.8))
    palette = {"fixed": "#3b82f6", "havfs": "#ef4444"}

    for mode, frame in series_frames.items():
        ax.plot(
            frame["time"].to_numpy(),
            frame[value_column].to_numpy(),
            label=normalize_mode_name(mode),
            linewidth=2.2,
            color=palette.get(mode, None),
        )

    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(y_label)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def write_cdf_figure(path: Path, latency_frames: dict[str, pd.DataFrame], dpi: int):
    apply_plot_style()
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    palette = {"fixed": "#3b82f6", "havfs": "#ef4444"}

    for mode, frame in latency_frames.items():
        values = sorted(frame["latency_s"].dropna().astype(float).tolist())
        if not values:
            continue
        cdf = np.arange(1, len(values) + 1) / len(values)
        ax.plot(values, cdf * 100.0, label=normalize_mode_name(mode), linewidth=2.2, color=palette.get(mode, None))

    ax.set_title("延迟 CDF 曲线")
    ax.set_xlabel("Latency (s)")
    ax.set_ylabel("CDF (%)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def write_boxplot_figure(path: Path, latency_frames: dict[str, pd.DataFrame], dpi: int):
    apply_plot_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.8))

    labels = []
    series = []
    for mode, frame in latency_frames.items():
        values = frame["latency_s"].dropna().astype(float).tolist()
        if values:
            labels.append(normalize_mode_name(mode))
            series.append(values)

    if series:
        ax.boxplot(series, labels=labels, patch_artist=True)
    ax.set_title("Latency Distribution")
    ax.set_ylabel("Latency (s)")
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def write_markdown_report(path: Path, report: dict[str, Any]):
    summary = report["summary"]
    sample = summary["sample_count"]
    redundancy = summary["redundancy_rate_percent"]
    latency = summary["latency_stats_s"]
    interval_stats = summary["interval_stats_s"]
    overhead = summary["overhead_stats"]
    files = report["files"]
    figures = files["figures"]
    params = report["parameters"]
    latency_meta = report["latency_detection"]

    content = f"""# HAVFS 实验评估报告

Generated at: {report["generated_at"]}

## 1. 实验总览

| 指标 | 固定频率 | HAVFS | 说明 |
| --- | ---: | ---: | --- |
| 采样点数量 | {sample["fixed"]} | {sample["havfs"]} | HAVFS 采样点减少 {sample["reduction_percent"]:.2f}% |
| 冗余率 | {redundancy["fixed"]:.2f}% | {redundancy["havfs"]:.2f}% | 双层判定：|delta util| <= {params["redundancy_value_threshold"]} 且 delta time <= {params["redundancy_time_window"]} s |
| 平均采样间隔 | {interval_stats["fixed"]["mean_s"]} s | {interval_stats["havfs"]["mean_s"]} s | 已包含有效采样间隔填充 |
| 延迟 P50 | {latency["fixed"]["p50_s"]} s | {latency["havfs"]["p50_s"]} s | 事件驱动延迟 |
| 延迟 P95 | {latency["fixed"]["p95_s"]} s | {latency["havfs"]["p95_s"]} s | 无显式加速时回退到 next_refresh / interval estimate |
| CPU 平均开销 | {overhead["fixed"]["cpu_mean_percent"]} % | {overhead["havfs"]["cpu_mean_percent"]} % | |
| 内存平均开销 | {overhead["fixed"]["mem_mean_mb"]} MB | {overhead["havfs"]["mem_mean_mb"]} MB | |

## 2. 指标定义

- Latency: from a significant workload event to the first accelerated response. A significant event is detected when utilization jump >= {params["latency_change_threshold"]} or utilization >= the {params["latency_high_quantile"]:.0%} quantile threshold.
- Acceleration response: interval shrinks by at least {params["latency_interval_drop_ratio"]:.0%}, or the sampler enters a high-priority state.
- NaN avoidance: if no explicit acceleration is observed in the reaction window, latency falls back to `next_refresh`; if the trace ends, it falls back to `estimated_by_interval`.
- Redundancy: a point is redundant only when both numeric similarity and time-window similarity hold at the same time.

延迟阈值：

- 固定频率高负载阈值：{latency_meta["fixed"]["high_util_threshold"]}
- HAVFS 高负载阈值：{latency_meta["havfs"]["high_util_threshold"]}

## 3. 图表

### 3.1 利用率-时间曲线

![utilization_time]({figures["utilization_time"]})

### 3.2 采样间隔-时间曲线

![interval_time]({figures["interval_time"]})

### 3.3 延迟 CDF 曲线

![latency_cdf]({figures["latency_cdf"]})

### 3.4 延迟箱线图

![latency_boxplot]({figures["latency_boxplot"]})

## 4. 结构化输出

- 汇总 CSV：`{files["summary_csv"]}`
- 时序 CSV：`{files["timeseries_csv"]}`
- 延迟样本 CSV：`{files["latency_csv"]}`
- JSON 报告：`{files["json_report"]}`
"""
    path.write_text(content, encoding="utf-8")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    curve_output = Path(args.curve_output) if args.curve_output else output_dir / "timeseries_metrics.csv"
    curve_output.parent.mkdir(parents=True, exist_ok=True)

    fixed_df = load_dataset(args.fixed, mode="fixed")
    havfs_df = load_dataset(args.havfs, mode="havfs")

    fixed_df, fixed_redundancy = compute_redundancy(
        fixed_df,
        value_threshold=args.redundancy_value_threshold,
        time_window=args.redundancy_time_window,
        rolling_window=args.rolling_window,
    )
    havfs_df, havfs_redundancy = compute_redundancy(
        havfs_df,
        value_threshold=args.redundancy_value_threshold,
        time_window=args.redundancy_time_window,
        rolling_window=args.rolling_window,
    )

    fixed_latency_df, fixed_latency_meta = compute_latency_distribution(
        fixed_df,
        change_threshold=args.latency_change_threshold,
        high_quantile=args.latency_high_quantile,
        reaction_window=args.latency_reaction_window,
        interval_drop_ratio=args.latency_interval_drop_ratio,
    )
    havfs_latency_df, havfs_latency_meta = compute_latency_distribution(
        havfs_df,
        change_threshold=args.latency_change_threshold,
        high_quantile=args.latency_high_quantile,
        reaction_window=args.latency_reaction_window,
        interval_drop_ratio=args.latency_interval_drop_ratio,
    )

    merged_timeseries = pd.concat([fixed_df, havfs_df], ignore_index=True)
    latency_samples = pd.concat([fixed_latency_df, havfs_latency_df], ignore_index=True)

    summary = {
        "sample_count": {
            "fixed": int(len(fixed_df)),
            "havfs": int(len(havfs_df)),
            "reduction_percent": round_or_none((len(fixed_df) - len(havfs_df)) / max(len(fixed_df), 1) * 100.0, 4),
        },
        "redundancy_rate_percent": {
            "fixed": round_or_none(fixed_redundancy, 4),
            "havfs": round_or_none(havfs_redundancy, 4),
        },
        "interval_stats_s": {
            "fixed": compute_interval_stats(fixed_df),
            "havfs": compute_interval_stats(havfs_df),
        },
        "overhead_stats": {
            "fixed": compute_overhead_stats(fixed_df),
            "havfs": compute_overhead_stats(havfs_df),
        },
        "latency_stats_s": {
            "fixed": {
                "count": int(len(fixed_latency_df)),
                "p50_s": percentile_or_none(fixed_latency_df["latency_s"].tolist(), 50),
                "p95_s": percentile_or_none(fixed_latency_df["latency_s"].tolist(), 95),
                "mean_s": round_or_none(fixed_latency_df["latency_s"].mean(), 4) if len(fixed_latency_df) else None,
            },
            "havfs": {
                "count": int(len(havfs_latency_df)),
                "p50_s": percentile_or_none(havfs_latency_df["latency_s"].tolist(), 50),
                "p95_s": percentile_or_none(havfs_latency_df["latency_s"].tolist(), 95),
                "mean_s": round_or_none(havfs_latency_df["latency_s"].mean(), 4) if len(havfs_latency_df) else None,
            },
        },
    }

    summary_csv = output_dir / "summary_metrics.csv"
    interval_csv = output_dir / "interval_stats.csv"
    latency_csv = output_dir / "latency_samples.csv"
    json_report = output_dir / "report.json"
    markdown_report = output_dir / "report.md"

    pd.DataFrame(build_summary_rows(summary)).to_csv(summary_csv, index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {"mode": "fixed", **summary["interval_stats_s"]["fixed"]},
            {"mode": "havfs", **summary["interval_stats_s"]["havfs"]},
        ]
    ).to_csv(interval_csv, index=False, encoding="utf-8-sig")
    merged_timeseries.to_csv(curve_output, index=False, encoding="utf-8-sig")
    latency_samples.to_csv(latency_csv, index=False, encoding="utf-8-sig")

    figures = {
        "utilization_time": "figures/utilization_time.png",
        "interval_time": "figures/interval_time.png",
        "latency_cdf": "figures/latency_cdf.png",
        "latency_boxplot": "figures/latency_boxplot.png",
    }

    write_line_figure(
        figures_dir / "utilization_time.png",
        {"fixed": fixed_df, "havfs": havfs_df},
        "utilization",
        "利用率-时间曲线",
        "利用率 (%)",
        args.figure_dpi,
    )
    write_line_figure(
        figures_dir / "interval_time.png",
        {"fixed": fixed_df, "havfs": havfs_df},
        "effective_interval_s",
        "采样间隔-时间曲线",
        "采样间隔 (s)",
        args.figure_dpi,
    )
    write_cdf_figure(figures_dir / "latency_cdf.png", {"fixed": fixed_latency_df, "havfs": havfs_latency_df}, args.figure_dpi)
    write_boxplot_figure(
        figures_dir / "latency_boxplot.png",
        {"fixed": fixed_latency_df, "havfs": havfs_latency_df},
        args.figure_dpi,
    )

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {"fixed": str(Path(args.fixed)), "havfs": str(Path(args.havfs))},
        "parameters": {
            "redundancy_value_threshold": args.redundancy_value_threshold,
            "redundancy_time_window": args.redundancy_time_window,
            "rolling_window": args.rolling_window,
            "latency_change_threshold": args.latency_change_threshold,
            "latency_high_quantile": args.latency_high_quantile,
            "latency_reaction_window": args.latency_reaction_window,
            "latency_interval_drop_ratio": args.latency_interval_drop_ratio,
        },
        "summary": summary,
        "latency_detection": {"fixed": fixed_latency_meta, "havfs": havfs_latency_meta},
        "charts": {
            "utilization_time": build_chart_payload(
                {"fixed": fixed_df, "havfs": havfs_df}, "utilization", "利用率-时间曲线", "利用率 (%)"
            ),
            "interval_time": build_chart_payload(
                {"fixed": fixed_df, "havfs": havfs_df}, "effective_interval_s", "采样间隔-时间曲线", "采样间隔 (s)"
            ),
            "latency_cdf": build_latency_cdf_chart({"fixed": fixed_latency_df, "havfs": havfs_latency_df}),
            "redundancy_time": build_chart_payload(
                {"fixed": fixed_df, "havfs": havfs_df}, "redundancy_score", "冗余率-时间曲线", "冗余率 (%)"
            ),
        },
        "files": {
            "summary_csv": summary_csv.name,
            "interval_csv": interval_csv.name,
            "timeseries_csv": curve_output.name if curve_output.parent == output_dir else str(curve_output),
            "latency_csv": latency_csv.name,
            "json_report": json_report.name,
            "markdown_report": markdown_report.name,
            "figures": figures,
        },
    }

    json_report.write_text(json.dumps(native_value(report), ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown_report(markdown_report, report)

    fixed_p50 = report["summary"]["latency_stats_s"]["fixed"]["p50_s"]
    havfs_p50 = report["summary"]["latency_stats_s"]["havfs"]["p50_s"]
    fixed_p95 = report["summary"]["latency_stats_s"]["fixed"]["p95_s"]
    havfs_p95 = report["summary"]["latency_stats_s"]["havfs"]["p95_s"]

    print("==========================================================")
    print("      HAVFS 实验评估报告")
    print("==========================================================")
    print(
        f"[1] 采样点数量: fixed={summary['sample_count']['fixed']}, "
        f"havfs={summary['sample_count']['havfs']}, "
        f"reduction={summary['sample_count']['reduction_percent']:.2f}%"
    )
    print(
        f"[2] 冗余率: fixed={summary['redundancy_rate_percent']['fixed']:.2f}%, "
        f"havfs={summary['redundancy_rate_percent']['havfs']:.2f}%"
    )
    print(
        f"[3] 平均采样间隔: fixed={summary['interval_stats_s']['fixed']['mean_s']:.4f}s, "
        f"havfs={summary['interval_stats_s']['havfs']['mean_s']:.4f}s"
    )
    print(
        f"[4] 延迟 P50/P95: fixed={fixed_p50:.4f}/{fixed_p95:.4f}s, "
        f"havfs={havfs_p50:.4f}/{havfs_p95:.4f}s"
    )
    print(
        f"[5] 输出文件: csv={summary_csv}, curve={curve_output}, json={json_report}, "
        f"markdown={markdown_report}"
    )
    print("==========================================================")


if __name__ == "__main__":
    main()
