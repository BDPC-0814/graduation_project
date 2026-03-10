import argparse

import numpy as np
import pandas as pd


def calculate_redundancy(df, threshold=1.0):
    """冗余率：相邻利用率变化 < threshold 的比例"""
    if len(df) < 2:
        return 0.0
    diffs = df["utilization"].diff().abs()
    redundant_count = (diffs[1:] < threshold).sum()
    return (redundant_count / len(df)) * 100


def calculate_latency_distribution(df, load_threshold=50.0, response_interval=1.0, max_window=5.0):
    """事件触发 -> 进入高频 的延迟分布"""
    spikes = df[df["utilization"] > load_threshold].index
    if len(spikes) == 0:
        return []

    delays = []
    for idx in spikes:
        begin = df.loc[idx, "time"]
        future = df.loc[idx:]
        future = future[future["time"] <= begin + max_window]
        reacted = future[future["interval"] < response_interval]
        if not reacted.empty:
            delay = reacted.iloc[0]["time"] - begin
            if delay >= 0:
                delays.append(float(delay))
    return delays


def build_overhead_curve(df, bin_seconds=1.0):
    work = df.copy()
    work["time_bin"] = (work["time"] / bin_seconds).astype(int) * bin_seconds
    curve = (
        work.groupby("time_bin")[["overhead_cpu", "overhead_mem_mb"]]
        .mean()
        .reset_index()
        .sort_values("time_bin")
    )
    return curve


def build_redundancy_curve(df, window=10, threshold=1.0):
    diffs = df["utilization"].diff().abs()
    is_redundant = (diffs < threshold).astype(float)
    rolling = is_redundant.rolling(window=window, min_periods=1).mean() * 100
    return pd.DataFrame({"time": df["time"], "redundancy_percent": rolling.fillna(0.0)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed", required=True, help="Path to fixed mode CSV")
    parser.add_argument("--havfs", required=True, help="Path to HAVFS mode CSV")
    parser.add_argument("--curve-output", default="experiments/curve_metrics.csv")
    args = parser.parse_args()

    df_fix = pd.read_csv(args.fixed)
    df_hav = pd.read_csv(args.havfs)

    count_fix = len(df_fix)
    count_hav = len(df_hav)
    reduction = (count_fix - count_hav) / max(1, count_fix) * 100

    red_fix = calculate_redundancy(df_fix, threshold=1.0)
    red_hav = calculate_redundancy(df_hav, threshold=1.0)

    cpu_hav = df_hav["overhead_cpu"].mean()
    mem_hav = df_hav["overhead_mem_mb"].mean()

    latency = calculate_latency_distribution(df_hav)
    lat_p50 = float(np.percentile(latency, 50)) if latency else np.nan
    lat_p95 = float(np.percentile(latency, 95)) if latency else np.nan

    overhead_curve = build_overhead_curve(df_hav)
    redundancy_curve = build_redundancy_curve(df_hav)
    curve = overhead_curve.merge(redundancy_curve, left_on="time_bin", right_on="time", how="left").drop(columns=["time"])
    curve.to_csv(args.curve_output, index=False)

    print("==========================================================")
    print("      统一实验协议评估报告 (P95延迟/冗余率/开销曲线)        ")
    print("==========================================================")
    print(f"[1] 采集效率: fixed={count_fix}, havfs={count_hav}, reduction={reduction:.2f}%")
    print(f"[2] 冗余率: fixed={red_fix:.2f}%, havfs={red_hav:.2f}%")
    print(f"[3] 开销均值: cpu={cpu_hav:.2f}%, mem={mem_hav:.2f}MB")
    print(f"[4] 实时性: latency P50={lat_p50:.4f}s, P95={lat_p95:.4f}s")
    print(f"[5] 曲线文件: {args.curve_output}")
    print("==========================================================")


if __name__ == "__main__":
    main()
