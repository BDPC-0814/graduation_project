# demo/evaluate_metrics.py

import pandas as pd
import numpy as np
import argparse

def calculate_redundancy(df, threshold=1.0):
    """计算冗余率 (利用率变化 < 1% 视为冗余)"""
    if len(df) < 2: return 0.0
    diffs = df['utilization'].diff().abs()
    redundant_count = (diffs[1:] < threshold).sum()
    return (redundant_count / len(df)) * 100

def calculate_latency_score(df, load_threshold=50.0, response_interval=1.0):
    """
    突发响应延迟：
    当负载 > 50% 时，系统多久能将采样间隔降到 1.0s 以下？
    """
    spikes = df[df['utilization'] > load_threshold].index
    if len(spikes) == 0: return np.nan

    delays = []
    # 简单的遍历查找 (优化版)
    for idx in spikes:
        # 只看该时刻之后 5 秒内的数据，避免查找太远
        future = df.loc[idx:]
        future = future[future['time'] <= df.loc[idx]['time'] + 5.0]
        
        reacted = future[future['interval'] < response_interval]
        if not reacted.empty:
            delay = reacted.iloc[0]['time'] - df.loc[idx]['time']
            # 过滤掉负值 (即已经在高频状态)
            if delay >= 0:
                delays.append(delay)
    
    return np.mean(delays) if delays else 0.0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed", required=True, help="Path to fixed mode CSV")
    parser.add_argument("--havfs", required=True, help="Path to HAVFS mode CSV")
    args = parser.parse_args()

    # 1. 加载数据
    try:
        df_fix = pd.read_csv(args.fixed)
        df_hav = pd.read_csv(args.havfs)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    print("==========================================================")
    print("             系统性能评估报告 (System Evaluation)          ")
    print("==========================================================")

    # Metric 1: 采集效率 (Collection Efficiency)
    count_fix = len(df_fix)
    count_hav = len(df_hav)
    reduction = (count_fix - count_hav) / count_fix * 100
    print(f"\n[1] 采集效率 (数据缩减量)")
    print(f"    - 固定频率点数 : {count_fix}")
    print(f"    - 自适应点数   : {count_hav}")
    print(f"    - 存储空间节省 : {reduction:.2f}% (越高越好)")

    # Metric 2: 冗余率 (Redundancy)
    red_fix = calculate_redundancy(df_fix, threshold=1.0)
    red_hav = calculate_redundancy(df_hav, threshold=1.0)
    print(f"\n[2] 数据冗余率 (变化 < 1%)")
    print(f"    - 固定模式     : {red_fix:.2f}%")
    print(f"    - 自适应模式   : {red_hav:.2f}%")
    print(f"    - 质量提升     : {red_fix - red_hav:.2f} pp (冗余降低)")

    # Metric 3: 系统开销 (Overhead)
    cpu_hav = df_hav['overhead_cpu'].mean()
    mem_hav = df_hav['overhead_mem_mb'].mean()
    print(f"\n[3] 算法自身开销 (Average)")
    print(f"    - CPU 占用     : {cpu_hav:.2f}%")
    print(f"    - 内存 驻留    : {mem_hav:.2f} MB")

    # Metric 4: 突发响应 (Latency)
    lat_hav = calculate_latency_score(df_hav)
    print(f"\n[4] 突发响应延迟 (Latency)")
    print(f"    - 响应速度     : {lat_hav:.4f} s (越快越好)")

    # Metric 5: 风险感知 (Risk Sensitivity) - [新增 v4.0 特性]
    # 检查是否有 risk_score 列
    if 'risk_score' in df_hav.columns:
        avg_risk = df_hav['risk_score'].mean()
        max_risk = df_hav['risk_score'].max()
        print(f"\n[5] 风险感知度 (Risk Score 0-100)")
        print(f"    - 平均风险分   : {avg_risk:.2f}")
        print(f"    - 最高风险分   : {max_risk:.2f}")
        print(f"    * 证明算法能有效量化系统负载的波动风险")
    else:
        print("\n[5] 风险感知度: (CSV中未找到 risk_score 列，跳过)")

    print("\n==========================================================")

if __name__ == "__main__":
    main()