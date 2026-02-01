# demo/havfs_experiment.py

import argparse
import csv
import os
import time

from core.collector.cpu_collector import CPUCollector
from core.scheduler.havfs import HAVFS
from core.reporter.console_reporter import ConsoleReporter


# ==========================================================
# 参数解析
# ==========================================================

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=["fixed", "havfs"],
        default="fixed",
        help="采样模式：fixed 固定频率 / havfs 自适应变频"
    )

    parser.add_argument(
        "--fixed-interval",
        type=float,
        default=2.0,
        help="固定采样间隔（秒）"
    )

    parser.add_argument(
        "--t-min",
        type=float,
        default=0.5,
        help="HAVFS 最小采样间隔"
    )

    parser.add_argument(
        "--t-max",
        type=float,
        default=5.0,
        help="HAVFS 最大采样间隔"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="实验持续时间（秒）"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="experiments/test.csv",
        help="输出 CSV 文件路径"
    )

    return parser.parse_args()


# ==========================================================
# 主实验逻辑
# ==========================================================

def main():
    print("\n==============================")
    print(">>> HAVFS Experiment Started")
    print("==============================\n")

    args = parse_args()

    # 创建输出目录
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # 采集器（CPU真实采集）
    collector = CPUCollector()

    # 调度器（仅 HAVFS 模式启用）
    scheduler = HAVFS(
        t_min=args.t_min,
        t_max=args.t_max
    ) if args.mode == "havfs" else None

    # Reporter（阶段2 stub）
    reporter = ConsoleReporter()

    # 实验计时
    start_time = time.time()

    # ==========================================================
    # CSV 写入初始化
    # ==========================================================

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)

        # CSV 表头（论文指标字段补齐）
        writer.writerow([
            "time",
            "utilization",
            "temperature",
            "power",
            "memory_usage",
            "bandwidth",
            "risk",
            "interval",
            "state"
        ])

        # ==========================================================
        # 主循环
        # ==========================================================

        while time.time() - start_time < args.duration:

            # ✅ 直接采集完整动态指标对象
            metrics = collector.collect()

            # ======================================================
            # 固定频率模式
            # ======================================================
            if args.mode == "fixed":
                interval = args.fixed_interval
                risk = 0.0
                state = "FIXED"

            # ======================================================
            # HAVFS 自适应模式
            # ======================================================
            else:
                interval, risk, state = scheduler.update(metrics)

            # ======================================================
            # Reporter 上报（阶段2 stub）
            # ======================================================
            reporter.send(metrics)

            # ======================================================
            # 时间戳
            # ======================================================
            now = round(time.time() - start_time, 2)

            # ======================================================
            # 写入 CSV
            # ======================================================
            writer.writerow([
                now,
                metrics.utilization,
                metrics.temperature,
                metrics.power,
                metrics.memory_usage,
                metrics.bandwidth,
                risk,
                interval,
                state
            ])

            # ======================================================
            # 控制台输出
            # ======================================================
            print(
                f"t={now:5.1f}s | "
                f"CPU={metrics.utilization:5.1f}% | "
                f"risk={risk:.2f} | "
                f"interval={interval:.2f}s | "
                f"state={state}"
            )

            # ======================================================
            # Sleep（采样间隔）
            # ======================================================
            time.sleep(interval)

    print("\n==============================")
    print(">>> Experiment Finished")
    print(f">>> Saved to: {args.output}")
    print("==============================\n")


# ==========================================================
# 程序入口
# ==========================================================

if __name__ == "__main__":
    main()
