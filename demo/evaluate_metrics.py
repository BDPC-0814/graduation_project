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
    parser = argparse.ArgumentParser(description="Evaluate fixed-frequency sampling against fault-evolution adaptive sampling.")
    parser.add_argument("--fixed", required=True, help="Path to fixed mode CSV")
    parser.add_argument("--evolution", required=True, help="Path to fault-evolution mode CSV")
    parser.add_argument("--ground-truth-events", default="", help="Optional CSV of shared event timestamps for reproducible latency evaluation")
    parser.add_argument("--output-dir", default="experiments/evaluation/latest", help="Directory for reports and figures")
    parser.add_argument(
        "--curve-output",
        default="",
        help="Optional compatibility output for the merged time-series CSV. Defaults to <output-dir>/timeseries_metrics.csv",
    )
    parser.add_argument("--redundancy-value-threshold", type=float, default=3.0)
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
    return "Evolution Sampling" if mode.lower() == "evolution" else "Fixed Frequency"


def load_dataset(path: str, mode: str):
    df = pd.read_csv(path)
    work = df.copy()
    work["mode"] = mode
    work["device_id"] = work.get("device_id", pd.Series(["unknown"] * len(work))).fillna("unknown").astype(str)
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
        work["planned_interval_s"] = interval
        if len(sample_interval) == len(work):
            work["planned_interval_s"] = work["planned_interval_s"].fillna(sample_interval)
    elif len(sample_interval) == len(work):
        work["planned_interval_s"] = sample_interval
    else:
        work["planned_interval_s"] = np.nan

    work = work.sort_values(["device_id", "time"]).reset_index(drop=True)
    work["sample_gap_s"] = work.groupby("device_id")["time"].diff()
    if len(work) > 1:
        default_gap = work["sample_gap_s"].dropna().median()
    else:
        default_gap = work["planned_interval_s"].dropna().median()
    if pd.isna(default_gap):
        default_gap = 0.0
    work["sample_gap_s"] = work["sample_gap_s"].fillna(work["planned_interval_s"]).fillna(default_gap)
    work["planned_interval_s"] = work["planned_interval_s"].fillna(work["sample_gap_s"]).fillna(default_gap)
    work["realized_interval_s"] = work["sample_gap_s"].fillna(work["planned_interval_s"]).fillna(default_gap)
    work["effective_interval_s"] = work["realized_interval_s"]
    phase_source = work["phase"] if "phase" in work.columns else work.get("state", pd.Series([""] * len(work)))
    field_policy_source = work["field_policy"] if "field_policy" in work.columns else pd.Series([""] * len(work))
    transport_policy_source = work["transport_policy"] if "transport_policy" in work.columns else pd.Series([""] * len(work))
    work["phase"] = phase_source.fillna("").astype(str)
    work["field_policy"] = field_policy_source.fillna("").astype(str)
    work["transport_policy"] = transport_policy_source.fillna("").astype(str)
    work["evolution_score"] = pd.to_numeric(
        work.get("evolution_score", work.get("risk_score")), errors="coerce"
    )
    work["field_priority_score"] = pd.to_numeric(work.get("field_priority_score"), errors="coerce")
    work["execution_pressure_score"] = pd.to_numeric(work.get("execution_pressure_score"), errors="coerce")
    work["control_score"] = pd.to_numeric(work.get("control_score"), errors="coerce")
    sampled_slow = work.get("sampled_slow")
    if sampled_slow is not None:
        work["sampled_slow"] = sampled_slow.astype(str).str.lower().isin(["true", "1", "yes"])
    else:
        work["sampled_slow"] = False
    return work


def load_ground_truth_events(path: str):
    events = pd.read_csv(path)
    if events.empty:
        return events
    events["time"] = pd.to_numeric(events.get("time"), errors="coerce")
    events["device_id"] = events.get("device_id", pd.Series([""] * len(events))).fillna("").astype(str)
    events["event_type"] = events.get("event_type", pd.Series(["ground_truth"] * len(events))).fillna("ground_truth").astype(str)
    events["severity"] = events.get("severity", pd.Series([""] * len(events))).fillna("").astype(str)
    events["description"] = events.get("description", pd.Series([""] * len(events))).fillna("").astype(str)
    return events.sort_values("time").reset_index(drop=True)


def compute_redundancy(df: pd.DataFrame, value_threshold: float, time_window: float, rolling_window: int):
    work = df.copy()
    util_delta = work.groupby("device_id")["utilization"].diff().abs().fillna(np.inf)
    temp_delta = (
        pd.to_numeric(work["chip_temp_c"], errors="coerce").groupby(work["device_id"]).diff().abs().fillna(0.0)
        if "chip_temp_c" in work.columns
        else pd.Series(np.zeros(len(work)))
    )
    power_delta = (
        pd.to_numeric(work["power_w"], errors="coerce").groupby(work["device_id"]).diff().abs().fillna(0.0)
        if "power_w" in work.columns
        else pd.Series(np.zeros(len(work)))
    )
    sample_gap = work["sample_gap_s"].fillna(work["effective_interval_s"]).fillna(0.0)
    planned_gap = work.get("planned_interval_s", sample_gap).fillna(sample_gap).fillna(0.0)
    reference_gap = planned_gap.groupby(work["device_id"]).shift().fillna(planned_gap).fillna(time_window)
    information_gain = util_delta + (temp_delta * 0.35) + (power_delta * 0.15)
    information_threshold = value_threshold * (
        1.0 + np.minimum(sample_gap.to_numpy(), time_window) / max(time_window, 1.0) * 0.5
    )

    same_device = work["device_id"].eq(work["device_id"].shift()).fillna(False)
    same_phase = work["phase"].eq(work["phase"].shift()).fillna(False)
    same_field_policy = work["field_policy"].eq(work["field_policy"].shift()).fillna(False)
    same_transport_policy = work["transport_policy"].eq(work["transport_policy"].shift()).fillna(False)
    fast_lane_repeat = ~work["sampled_slow"].fillna(False)
    healthy = work.get("status", pd.Series(["ok"] * len(work))).fillna("ok").eq("ok")
    short_repeat = sample_gap <= np.maximum(reference_gap.to_numpy() * 1.15, time_window)

    redundant = (
        short_repeat
        & same_device
        & same_phase
        & same_field_policy
        & same_transport_policy
        & fast_lane_repeat
        & healthy
        & (information_gain.to_numpy() <= information_threshold)
    )
    if len(redundant):
        redundant.iloc[0] = False

    work["redundant"] = redundant
    work["redundancy_score"] = pd.Series(redundant.astype(float)).rolling(
        window=max(1, rolling_window), min_periods=1
    ).mean() * 100.0
    rate = float(work["redundant"].mean() * 100.0) if len(work) else 0.0
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
    return any(keyword in lowered for keyword in ("focus", "recovery")) or any(
        keyword in state_text for keyword in ("聚焦", "恢复")
    )


def compute_latency_from_ground_truth(
    df: pd.DataFrame,
    events: pd.DataFrame,
    reaction_window: float,
    interval_drop_ratio: float,
):
    work = df.copy().sort_values("time").reset_index(drop=True)
    if events.empty:
        return pd.DataFrame(), {"source": "ground_truth_events", "event_count": 0}

    median_interval = work["effective_interval_s"].dropna().median()
    if pd.isna(median_interval) or median_interval <= 0:
        median_interval = 0.0

    records = []
    for event in events.itertuples(index=False):
        event_time = event.time
        if pd.isna(event_time):
            continue

        if getattr(event, "device_id", ""):
            event_scope = work[work["device_id"].astype(str) == str(event.device_id)].sort_values("time").reset_index(drop=True)
        else:
            event_scope = work.sort_values("time").reset_index(drop=True)
        if event_scope.empty:
            continue

        baseline_frame = event_scope[event_scope["time"] < float(event_time)].tail(3)
        baseline_interval = baseline_frame["effective_interval_s"].median()
        if pd.isna(baseline_interval) or baseline_interval <= 0:
            baseline_interval = median_interval if median_interval > 0 else reaction_window

        future = event_scope[event_scope["time"] >= float(event_time)]
        future = future[future["time"] <= float(event_time) + reaction_window]
        accelerated = future[
            (future["effective_interval_s"] <= baseline_interval * (1.0 - interval_drop_ratio))
            | future["phase"].map(is_accelerated_state)
        ]
        if not accelerated.empty:
            matched = accelerated.iloc[0]
            latency = float(matched["time"] - event_time)
            source = "ground_truth_accelerated"
        elif not future.empty:
            matched = future.iloc[0]
            latency = float(matched["time"] - event_time)
            source = "ground_truth_first_observation"
        else:
            matched = None
            latency = float(max(baseline_interval, 0.0))
            source = "ground_truth_estimated_by_baseline"

        records.append(
            {
                "mode": work.iloc[0]["mode"] if len(work) else "",
                "device_id": getattr(event, "device_id", ""),
                "event_time": float(event_time),
                "latency_s": latency,
                "latency_source": source,
                "event_type": getattr(event, "event_type", "ground_truth"),
                "event_severity": getattr(event, "severity", ""),
                "event_description": getattr(event, "description", ""),
                "event_utilization": round_or_none(matched["utilization"], 4) if matched is not None else None,
                "event_interval_s": round_or_none(baseline_interval, 4),
            }
        )

    return pd.DataFrame(records), {"source": "ground_truth_events", "event_count": int(len(records))}


def compute_latency_distribution(
    df: pd.DataFrame,
    change_threshold: float,
    high_quantile: float,
    reaction_window: float,
    interval_drop_ratio: float,
    ground_truth_events=None,
):
    if ground_truth_events is not None:
        return compute_latency_from_ground_truth(
            df=df,
            events=ground_truth_events,
            reaction_window=reaction_window,
            interval_drop_ratio=interval_drop_ratio,
        )

    work = df.copy().sort_values("time").reset_index(drop=True)
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
            | future["phase"].map(is_accelerated_state)
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


def compute_behavior_stats(df: pd.DataFrame):
    sampled_ratio = float(df["sampled_slow"].mean() * 100.0) if "sampled_slow" in df.columns and len(df) else 0.0
    buffered_ratio = (
        float(df["transport_policy"].str.contains("缓冲", na=False).mean() * 100.0)
        if "transport_policy" in df.columns and len(df)
        else 0.0
    )
    phase_focus_ratio = (
        float(df["phase"].str.contains("聚焦", na=False).mean() * 100.0)
        if "phase" in df.columns and len(df)
        else 0.0
    )
    return {
        "slow_lane_ratio_percent": round_or_none(sampled_ratio, 4),
        "buffered_transport_ratio_percent": round_or_none(buffered_ratio, 4),
        "focus_phase_ratio_percent": round_or_none(phase_focus_ratio, 4),
        "execution_pressure_mean": round_or_none(df["execution_pressure_score"].dropna().mean(), 4)
        if "execution_pressure_score" in df.columns and df["execution_pressure_score"].notna().any()
        else None,
    }


def build_summary_rows(report_summary: dict[str, Any]):
    sample = report_summary["sample_count"]
    redundancy = report_summary["redundancy_rate_percent"]
    interval_stats = report_summary["interval_stats_s"]
    latency = report_summary["latency_stats_s"]
    overhead = report_summary["overhead_stats"]
    behavior = report_summary["behavior_stats"]

    return [
        {
            "metric": "sample_count",
            "fixed": sample["fixed"],
            "evolution": sample["evolution"],
            "delta_percent": sample["reduction_percent"],
            "unit": "points",
        },
        {
            "metric": "redundancy_rate",
            "fixed": redundancy["fixed"],
            "evolution": redundancy["evolution"],
            "delta_percent": round_or_none(redundancy["fixed"] - redundancy["evolution"], 4),
            "unit": "%",
        },
        {
            "metric": "interval_mean",
            "fixed": interval_stats["fixed"]["mean_s"],
            "evolution": interval_stats["evolution"]["mean_s"],
            "delta_percent": None,
            "unit": "s",
        },
        {
            "metric": "latency_p50",
            "fixed": latency["fixed"]["p50_s"],
            "evolution": latency["evolution"]["p50_s"],
            "delta_percent": None,
            "unit": "s",
        },
        {
            "metric": "latency_p95",
            "fixed": latency["fixed"]["p95_s"],
            "evolution": latency["evolution"]["p95_s"],
            "delta_percent": None,
            "unit": "s",
        },
        {
            "metric": "cpu_overhead_mean",
            "fixed": overhead["fixed"]["cpu_mean_percent"],
            "evolution": overhead["evolution"]["cpu_mean_percent"],
            "delta_percent": None,
            "unit": "%",
        },
        {
            "metric": "mem_overhead_mean",
            "fixed": overhead["fixed"]["mem_mean_mb"],
            "evolution": overhead["evolution"]["mem_mean_mb"],
            "delta_percent": None,
            "unit": "MB",
        },
        {
            "metric": "slow_lane_ratio",
            "fixed": behavior["fixed"]["slow_lane_ratio_percent"],
            "evolution": behavior["evolution"]["slow_lane_ratio_percent"],
            "delta_percent": None,
            "unit": "%",
        },
        {
            "metric": "buffered_transport_ratio",
            "fixed": behavior["fixed"]["buffered_transport_ratio_percent"],
            "evolution": behavior["evolution"]["buffered_transport_ratio_percent"],
            "delta_percent": None,
            "unit": "%",
        },
    ]


def aggregate_timeseries(frame: pd.DataFrame, value_column: str):
    usable = frame[["time", value_column]].copy()
    usable["time"] = pd.to_numeric(usable["time"], errors="coerce")
    usable[value_column] = pd.to_numeric(usable[value_column], errors="coerce")
    usable = usable.dropna(subset=["time"])
    if usable.empty:
        return usable
    return usable.groupby("time", as_index=False)[value_column].mean().sort_values("time").reset_index(drop=True)


def build_chart_payload(series_frames: dict[str, pd.DataFrame], value_column: str, title: str, y_axis_name: str):
    label_map: dict[str, float] = {}
    for frame in series_frames.values():
        aggregated = aggregate_timeseries(frame, value_column)
        for value in aggregated["time"].dropna().tolist():
            label_map[f"{float(value):.2f}s"] = float(value)

    labels = [item[0] for item in sorted(label_map.items(), key=lambda entry: entry[1])]
    series = []
    for mode, frame in series_frames.items():
        aggregated = aggregate_timeseries(frame, value_column)
        points = {f"{float(row.time):.2f}s": row._asdict()[value_column] for row in aggregated.itertuples(index=False)}
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
        if not values:
            cdf_values = [None for _ in labels]
        else:
            array = np.array(values)
            cdf_values = [
                round_or_none(float(np.searchsorted(array, value, side="right") / len(array)) * 100.0, 4)
                for value in label_values
            ]
        series.append({"name": normalize_mode_name(mode), "data": cdf_values})

    return {"title": "Latency CDF", "labels": labels, "series": series, "y_axis_name": "CDF (%)"}


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
    palette = {"fixed": "#3b82f6", "evolution": "#ef4444"}

    for mode, frame in series_frames.items():
        aggregated = aggregate_timeseries(frame, value_column)
        ax.plot(
            aggregated["time"].to_numpy(),
            aggregated[value_column].to_numpy(),
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
    palette = {"fixed": "#3b82f6", "evolution": "#ef4444"}

    for mode, frame in latency_frames.items():
        values = sorted(frame["latency_s"].dropna().astype(float).tolist())
        if not values:
            continue
        cdf = np.arange(1, len(values) + 1) / len(values)
        ax.plot(values, cdf * 100.0, label=normalize_mode_name(mode), linewidth=2.2, color=palette.get(mode, None))

    ax.set_title("Latency CDF")
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
    behavior = summary["behavior_stats"]
    files = report["files"]
    figures = files["figures"]
    params = report["parameters"]
    latency_meta = report["latency_detection"]
    using_ground_truth = params.get("latency_event_source") == "ground_truth_events"
    latency_definition = (
        "- Latency: measured from shared ground-truth event timestamps to the first accelerated response or first observation after the event."
        if using_ground_truth
        else f"- Latency: from a significant workload event to the first accelerated response. A significant event is detected when utilization jump >= {params['latency_change_threshold']} or utilization >= the {params['latency_high_quantile']:.0%} quantile threshold."
    )
    latency_meta_lines = (
        f"- Fixed mode latency source: {latency_meta['fixed'].get('source')} (events={latency_meta['fixed'].get('event_count')})\n"
        f"- Evolution mode latency source: {latency_meta['evolution'].get('source')} (events={latency_meta['evolution'].get('event_count')})"
        if using_ground_truth
        else f"- 固定频率高负载阈值：{latency_meta['fixed']['high_util_threshold']}\n- 故障演化采样高负载阈值：{latency_meta['evolution']['high_util_threshold']}"
    )

    content = f"""# 故障演化采样实验评估报告

Generated at: {report["generated_at"]}

## 1. 实验总览

| 指标 | 固定频率 | 故障演化采样 | 说明 |
| --- | ---: | ---: | --- |
| 采样点数量 | {sample["fixed"]} | {sample["evolution"]} | 故障演化采样采样点减少 {sample["reduction_percent"]:.2f}% |
| 冗余率 | {redundancy["fixed"]:.2f}% | {redundancy["evolution"]:.2f}% | 低信息量重复采样：变化增益低、相位未变、策略未变、且处于短间隔快线重复采样 |
| 平均采样间隔 | {interval_stats["fixed"]["mean_s"]} s | {interval_stats["evolution"]["mean_s"]} s | 已包含有效采样间隔补全 |
| 延迟 P50 | {latency["fixed"]["p50_s"]} s | {latency["evolution"]["p50_s"]} s | 事件驱动响应延迟 |
| 延迟 P95 | {latency["fixed"]["p95_s"]} s | {latency["evolution"]["p95_s"]} s | 无显式加速时回退到 next_refresh / interval estimate |
| 慢线激活率 | {behavior["fixed"]["slow_lane_ratio_percent"]} % | {behavior["evolution"]["slow_lane_ratio_percent"]} % | 字段分层补采活跃程度 |
| 缓冲上传占比 | {behavior["fixed"]["buffered_transport_ratio_percent"]} % | {behavior["evolution"]["buffered_transport_ratio_percent"]} % | 边端可靠执行链路参与程度 |
| CPU 平均开销 | {overhead["fixed"]["cpu_mean_percent"]} % | {overhead["evolution"]["cpu_mean_percent"]} % | |
| 内存平均开销 | {overhead["fixed"]["mem_mean_mb"]} MB | {overhead["evolution"]["mem_mean_mb"]} MB | |

## 2. 指标定义

{latency_definition}
- Acceleration response: interval shrinks by at least {params["latency_interval_drop_ratio"]:.0%}, or the sampler enters a focus / recovery phase.
- NaN avoidance: if no explicit acceleration is observed in the reaction window, latency falls back to `next_refresh`; if the trace ends, it falls back to `estimated_by_interval`.
- Redundancy: a point is counted as redundant only when information gain stays low, the phase and field policy do not change, and the point appears as a short-gap fast-lane repeat sample.

延迟阈值：

{latency_meta_lines}

## 3. 图表

### 3.1 利用率时间曲线

![utilization_time]({figures["utilization_time"]})

### 3.2 采样间隔时间曲线

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
    path.write_text(content, encoding="utf-8-sig")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    curve_output = Path(args.curve_output) if args.curve_output else output_dir / "timeseries_metrics.csv"
    curve_output.parent.mkdir(parents=True, exist_ok=True)

    fixed_df = load_dataset(args.fixed, mode="fixed")
    evolution_df = load_dataset(args.evolution, mode="evolution")
    ground_truth_events = load_ground_truth_events(args.ground_truth_events) if args.ground_truth_events else None

    fixed_df, fixed_redundancy = compute_redundancy(
        fixed_df,
        value_threshold=args.redundancy_value_threshold,
        time_window=args.redundancy_time_window,
        rolling_window=args.rolling_window,
    )
    evolution_df, evolution_redundancy = compute_redundancy(
        evolution_df,
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
        ground_truth_events=ground_truth_events,
    )
    evolution_latency_df, evolution_latency_meta = compute_latency_distribution(
        evolution_df,
        change_threshold=args.latency_change_threshold,
        high_quantile=args.latency_high_quantile,
        reaction_window=args.latency_reaction_window,
        interval_drop_ratio=args.latency_interval_drop_ratio,
        ground_truth_events=ground_truth_events,
    )

    merged_timeseries = pd.concat([fixed_df, evolution_df], ignore_index=True)
    latency_samples = pd.concat([fixed_latency_df, evolution_latency_df], ignore_index=True)

    summary = {
        "sample_count": {
            "fixed": int(len(fixed_df)),
            "evolution": int(len(evolution_df)),
            "reduction_percent": round_or_none((len(fixed_df) - len(evolution_df)) / max(len(fixed_df), 1) * 100.0, 4),
        },
        "redundancy_rate_percent": {
            "fixed": round_or_none(fixed_redundancy, 4),
            "evolution": round_or_none(evolution_redundancy, 4),
        },
        "interval_stats_s": {
            "fixed": compute_interval_stats(fixed_df),
            "evolution": compute_interval_stats(evolution_df),
        },
        "overhead_stats": {
            "fixed": compute_overhead_stats(fixed_df),
            "evolution": compute_overhead_stats(evolution_df),
        },
        "behavior_stats": {
            "fixed": compute_behavior_stats(fixed_df),
            "evolution": compute_behavior_stats(evolution_df),
        },
        "latency_stats_s": {
            "fixed": {
                "count": int(len(fixed_latency_df)),
                "p50_s": percentile_or_none(fixed_latency_df["latency_s"].tolist(), 50),
                "p95_s": percentile_or_none(fixed_latency_df["latency_s"].tolist(), 95),
                "mean_s": round_or_none(fixed_latency_df["latency_s"].mean(), 4) if len(fixed_latency_df) else None,
            },
            "evolution": {
                "count": int(len(evolution_latency_df)),
                "p50_s": percentile_or_none(evolution_latency_df["latency_s"].tolist(), 50),
                "p95_s": percentile_or_none(evolution_latency_df["latency_s"].tolist(), 95),
                "mean_s": round_or_none(evolution_latency_df["latency_s"].mean(), 4) if len(evolution_latency_df) else None,
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
            {"mode": "evolution", **summary["interval_stats_s"]["evolution"]},
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
        {"fixed": fixed_df, "evolution": evolution_df},
        "utilization",
        "Utilization Over Time",
        "Utilization (%)",
        args.figure_dpi,
    )
    write_line_figure(
        figures_dir / "interval_time.png",
        {"fixed": fixed_df, "evolution": evolution_df},
        "effective_interval_s",
        "Effective Sampling Interval",
        "Sampling Interval (s)",
        args.figure_dpi,
    )
    write_cdf_figure(figures_dir / "latency_cdf.png", {"fixed": fixed_latency_df, "evolution": evolution_latency_df}, args.figure_dpi)
    write_boxplot_figure(
        figures_dir / "latency_boxplot.png",
        {"fixed": fixed_latency_df, "evolution": evolution_latency_df},
        args.figure_dpi,
    )

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "fixed": str(Path(args.fixed)),
            "evolution": str(Path(args.evolution)),
            "ground_truth_events": str(Path(args.ground_truth_events)) if args.ground_truth_events else "",
        },
        "parameters": {
            "redundancy_value_threshold": args.redundancy_value_threshold,
            "redundancy_time_window": args.redundancy_time_window,
            "rolling_window": args.rolling_window,
            "latency_change_threshold": args.latency_change_threshold,
            "latency_high_quantile": args.latency_high_quantile,
            "latency_reaction_window": args.latency_reaction_window,
            "latency_interval_drop_ratio": args.latency_interval_drop_ratio,
            "latency_event_source": "ground_truth_events" if ground_truth_events is not None else "sampled_proxy",
        },
        "summary": summary,
        "latency_detection": {"fixed": fixed_latency_meta, "evolution": evolution_latency_meta},
        "charts": {
            "utilization_time": build_chart_payload(
                {"fixed": fixed_df, "evolution": evolution_df}, "utilization", "Utilization Over Time", "Utilization (%)"
            ),
            "interval_time": build_chart_payload(
                {"fixed": fixed_df, "evolution": evolution_df}, "effective_interval_s", "Effective Sampling Interval", "Sampling Interval (s)"
            ),
            "latency_cdf": build_latency_cdf_chart({"fixed": fixed_latency_df, "evolution": evolution_latency_df}),
            "redundancy_time": build_chart_payload(
                {"fixed": fixed_df, "evolution": evolution_df}, "redundancy_score", "Redundancy Score Over Time", "Redundancy (%)"
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

    json_report.write_text(json.dumps(native_value(report), ensure_ascii=False, indent=2), encoding="utf-8-sig")
    write_markdown_report(markdown_report, report)

    fixed_p50 = report["summary"]["latency_stats_s"]["fixed"]["p50_s"]
    evolution_p50 = report["summary"]["latency_stats_s"]["evolution"]["p50_s"]
    fixed_p95 = report["summary"]["latency_stats_s"]["fixed"]["p95_s"]
    evolution_p95 = report["summary"]["latency_stats_s"]["evolution"]["p95_s"]

    print("==========================================================")
    print("      故障演化采样实验评估报告")
    print("==========================================================")
    print(
        f"[1] 采样点数量: fixed={summary['sample_count']['fixed']}, "
        f"evolution={summary['sample_count']['evolution']}, "
        f"reduction={summary['sample_count']['reduction_percent']:.2f}%"
    )
    print(
        f"[2] 冗余率: fixed={summary['redundancy_rate_percent']['fixed']:.2f}%, "
        f"evolution={summary['redundancy_rate_percent']['evolution']:.2f}%"
    )
    print(
        f"[3] 平均采样间隔: fixed={summary['interval_stats_s']['fixed']['mean_s']:.4f}s, "
        f"evolution={summary['interval_stats_s']['evolution']['mean_s']:.4f}s"
    )
    print(
        f"[4] 延迟 P50/P95: fixed={fixed_p50:.4f}/{fixed_p95:.4f}s, "
        f"evolution={evolution_p50:.4f}/{evolution_p95:.4f}s"
    )
    print(
        f"[5] 输出文件: csv={summary_csv}, curve={curve_output}, json={json_report}, "
        f"markdown={markdown_report}"
    )
    print("==========================================================")


if __name__ == "__main__":
    main()
