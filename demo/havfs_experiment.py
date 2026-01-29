"""
HAVFS Experiment Program (Stage 2)

功能：
1. 支持 fixed 固定频率采样 baseline
2. 支持 havfs 自适应变频采样策略
3. 支持 CPU/GPU 异构采集器（GPU为模拟占位）
4. 输出完整指标字段 + risk + interval + state
5. 保存实验结果为 CSV 文件（用于论文画图分析）

运行示例：

固定频率：
python -m demo.havfs_experiment \
  --mode fixed \
  --device cpu \
  --fixed-interval 2.0 \
  --duration 60 \
  --output experiments/fixed.csv

HAVFS：
python -m demo.havfs_experiment \
  --mode havfs \
  --device cpu \
  --t-min 0.5 \
  --t-max 5.0 \
  --duration 60 \
  --output experiments/havfs.csv
"""

import argparse
import csv
import os
import time

# ===== Collector Imports =====
from core.collector.cpu_collector import CPUCollector
from core.collector.gpu_collector import GPUCollector

# ===== HAVFS Scheduler =====
from core.scheduler.havfs import HAVFS


# ============================================================
# 1. 参数解析
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser("HAVFS Experiment (Stage2)")

    # 模式选择
    parser.add_argument(
        "--mode",
        choices=["fixed", "havfs"],
        default="fixed",
        help="Sampling mode: fixed baseline or havfs adaptive"
    )

    # 设备选择
    parser.add_argument(
        "--device",
        choices=["cpu", "gpu"],
        default="cpu",
        help="Select device type (cpu real, gpu simulated)"
    )

    # Fixed baseline interval
    parser.add_argument(
        "--fixed-interval",
        type=float,
        default=2.0,
        help="Fixed sampling interval (only for fixed mode)"
    )

    # HAVFS adaptive interval range
    parser.add_argument("--t-min", type=float, default=0.5)
    parser.add_argument("--t-max", type=float, default=5.0)

    # 实验时长
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Experiment duration (seconds)"
    )

    # 输出CSV文件路径
    parser.add_argument(
        "--output",
        type=str,
        default="experiments/test.csv",
        help="Output CSV path"
    )

    return parser.parse_args()


# ============================================================
# 2. 主实验流程
# ============================================================

def main():
    print("\n==============================")
    print(">>> HAVFS Experiment Started")
    print("==============================")

    args = parse_args()

    # 输出目录创建
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # ========================================================
    # Step A: 初始化采集器（Collector）
    # ========================================================

    if args.device == "cpu":
        collector = CPUCollector(device_id="cpu0")
    else:
        collector = GPUCollector(device_id="gpu0")

    print(f"[INFO] Device Type : {args.device}")
    print(f"[INFO] Mode        : {args.mode}")
    print(f"[INFO] Output File : {args.output}")

    # ========================================================
    # Step B: 初始化调度器（HAVFS）
    # ========================================================

    scheduler = None
    if args.mode == "havfs":
        scheduler = HAVFS(t_min=args.t_min, t_max=args.t_max)
        print(f"[INFO] HAVFS interval range = [{args.t_min}, {args.t_max}]")

    # ========================================================
    # Step C: 实验循环
    # ========================================================

    start_time = time.time()

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)

        # CSV表头（论文实验字段）
        writer.writerow([
            "time",
            "device_id",
            "utilization",
            "temperature",
            "power",
            "memory_usage",
            "bandwidth",
            "risk",
            "interval",
            "state"
        ])

        # 循环采样
        while time.time() - start_time < args.duration:

            # 采集一次完整指标
            metrics = collector.collect()

            # ====================================================
            # Fixed baseline
            # ====================================================
            if args.mode == "fixed":
                interval = args.fixed_interval
                risk = 0.0
                state = "FIXED"

            # ====================================================
            # HAVFS adaptive sampling
            # ====================================================
            else:
                interval, risk, state = scheduler.update(metrics)

            # 当前时间戳
            now = round(time.time() - start_time, 2)

            # 写入CSV
            writer.writerow([
                now,
                metrics.device_id,
                metrics.utilization,
                metrics.temperature,
                metrics.power,
                metrics.memory_usage,
                metrics.bandwidth,
                risk,
                interval,
                state
            ])

            # 打印输出（实时观察）
            print(
                f"t={now:6.1f}s | "
                f"{metrics.device_id} util={metrics.utilization:5.1f}% | "
                f"risk={risk:.2f} | "
                f"interval={interval:.2f}s | "
                f"state={state}"
            )

            # sleep到下一次采样
            time.sleep(interval)

    print("\n==============================")
    print(">>> Experiment Finished")
    print(f">>> Saved CSV -> {args.output}")
    print("==============================\n")


# ============================================================
# 3. 程序入口
# ============================================================

if __name__ == "__main__":
    main()
