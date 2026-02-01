import pandas as pd
import numpy as np
import argparse

def calculate_redundancy(df, threshold=1.0):
    """
    计算冗余率：如果前后两次利用率变化小于 threshold，视为冗余数据
    冗余率 = 冗余点数 / 总点数
    """
    if len(df) < 2:
        return 0.0
    # 计算差分绝对值
    diffs = df['utilization'].diff().abs()
    # 统计小于阈值的点数 (忽略第一个 NaN)
    redundant_count = (diffs[1:] < threshold).sum()
    return (redundant_count / len(df)) * 100

def calculate_latency_score(df, load_threshold=50.0, response_interval=1.0):
    """
    实时性评分（简易版）：
    寻找负载突升 (>50%) 的时刻，计算紧接着采样间隔降至 <1.0s 所需的时间
    """
    spikes = df[df['utilization'] > load_threshold].index
    if len(spikes) == 0:
        return np.nan

    delays = []
    for idx in spikes:
        # 查找该时刻之后的记录
        future = df.loc[idx:]
        # 找到第一个 interval 小于目标的时刻
        reacted = future[future['interval'] < response_interval]
        if not reacted.empty:
            # 响应时间 = 响应时刻 - 突发时刻
            delay = reacted.iloc[0]['time'] - df.loc[idx]['time']
            delays.append(delay)
    
    return np.mean(delays) if delays else np.nan

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed", required=True, help="Path to fixed mode CSV")
    parser.add_argument("--havfs", required=True, help="Path to HAVFS mode CSV")
    args = parser.parse_args()

    # 1. 加载数据
    df_fix = pd.read_csv(args.fixed)
    df_hav = pd.read_csv(args.havfs)

    print("==========================================================")
    print("             Performance Evaluation Report                ")
    print("==========================================================")

    # Metric 1: 采集效率 (Collection Efficiency)
    # 比较数据量（行数）
    count_fix = len(df_fix)
    count_hav = len(df_hav)
    reduction = (count_fix - count_hav) / count_fix * 100
    print(f"\n[1] Collection Efficiency (Data Volume Reduction)")
    print(f"    - Fixed Points : {count_fix}")
    print(f"    - HAVFS Points : {count_hav}")
    print(f"    - Reduction    : {reduction:.2f}% (Higher is better)")

    # Metric 2: 冗余率 (Redundancy Rate)
    # 阈值设为 1.0% (即利用率变化小于1%认为无信息量)
    red_fix = calculate_redundancy(df_fix, threshold=1.0)
    red_hav = calculate_redundancy(df_hav, threshold=1.0)
    print(f"\n[2] Redundancy Rate (Threshold=1.0%)")
    print(f"    - Fixed Mode   : {red_fix:.2f}%")
    print(f"    - HAVFS Mode   : {red_hav:.2f}%")
    print(f"    - Improvement  : {red_fix - red_hav:.2f} pp (Lower is better)")

    # Metric 3: 系统开销 (System Overhead)
    # 计算 CPU 和 内存的平均值
    cpu_fix = df_fix['overhead_cpu'].mean()
    cpu_hav = df_hav['overhead_cpu'].mean()
    mem_fix = df_fix['overhead_mem_mb'].mean()
    mem_hav = df_hav['overhead_mem_mb'].mean()
    print(f"\n[3] System Overhead (Avg)")
    print(f"    - Fixed Mode   : CPU={cpu_fix:.2f}%, Mem={mem_fix:.2f} MB")
    print(f"    - HAVFS Mode   : CPU={cpu_hav:.2f}%, Mem={mem_hav:.2f} MB")
    print(f"    * Note: HAVFS implies higher compute cost for logic execution.")

    # Metric 4: 实时性 (Responsiveness)
    # 计算突发负载下的响应延迟
    lat_fix = calculate_latency_score(df_fix) # 对于 Fixed 来说，延迟通常是 0 或 随机 (因为它不响应，或者说响应时间就是采样间隔)
    lat_hav = calculate_latency_score(df_hav)
    print(f"\n[4] Burst Response Latency (Approx)")
    print(f"    - Avg delay to drop interval < 1.0s after load > 50%")
    print(f"    - HAVFS Mode   : {lat_hav:.4f} s")
    
    print("\n==========================================================")

if __name__ == "__main__":
    main()