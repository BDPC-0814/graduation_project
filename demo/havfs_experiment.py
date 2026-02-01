# demo/havfs_experiment.py

import argparse
import csv
import os
import time
import psutil  # 用于系统开销评测

from core.collector.cpu_collector import CPUCollector
from core.collector.gpu_collector import GPUCollector
from core.scheduler.havfs import HAVFS
from core.reporter.console_reporter import ConsoleReporter
from core.reporter.prometheus_reporter import PrometheusReporter

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fixed", "havfs"], default="fixed", help="采样模式")
    parser.add_argument("--device", choices=["cpu", "gpu"], default="cpu", help="设备类型")
    parser.add_argument("--reporter", choices=["console", "prometheus"], default="console", help="上报方式")
    parser.add_argument("--fixed-interval", type=float, default=2.0)
    parser.add_argument("--t-min", type=float, default=0.5)
    parser.add_argument("--t-max", type=float, default=5.0)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--output", type=str, default="experiments/test.csv")
    return parser.parse_args()

def main():
    print(f"\n>>> Experiment Started [PID: {os.getpid()}]")
    args = parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # 1. 初始化采集器
    if args.device == "gpu":
        print("[INFO] Device: GPU (Real/Sim)")
        collector = GPUCollector(device_id="gpu0")
    else:
        print("[INFO] Device: CPU (Real)")
        collector = CPUCollector(device_id="cpu0")

    # 2. 初始化调度器
    scheduler = HAVFS(t_min=args.t_min, t_max=args.t_max) if args.mode == "havfs" else None

    # 3. 初始化 Reporter
    if args.reporter == "prometheus":
        reporter = PrometheusReporter(port=8000)
    else:
        reporter = ConsoleReporter()

    # 用于测量自身开销
    process = psutil.Process(os.getpid())
    
    start_time = time.time()

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        # 更新表头：增加 overhead_cpu, overhead_mem
        writer.writerow([
            "time", "device_id", "utilization", "risk", "interval", "state",
            "overhead_cpu", "overhead_mem_mb"
        ])

        while time.time() - start_time < args.duration:
            # A. 采集业务指标
            metrics = collector.collect()

            # B. 调度决策
            if args.mode == "fixed":
                interval = args.fixed_interval
                risk = 0.0
                state = "FIXED"
            else:
                interval, risk, state = scheduler.update(metrics)

            # C. 上报 (传递 risk 和 interval 供 Prometheus 展示)
            # 注意：需修改 base_reporter 接口或动态传参，这里假设 reporter 已更新
            if isinstance(reporter, PrometheusReporter):
                reporter.send(metrics, risk, interval)
            else:
                reporter.send(metrics)

            # D. 测量系统自身开销 (System Overhead)
            # cpu_percent(interval=None) 非阻塞测量
            self_cpu = process.cpu_percent(interval=None)
            self_mem = process.memory_info().rss / 1024 / 1024  # MB

            # E. 记录数据
            now = round(time.time() - start_time, 2)
            writer.writerow([
                now, metrics.device_id, metrics.utilization, risk, interval, state,
                self_cpu, self_mem
            ])

            print(f"t={now:5.1f}s | Util={metrics.utilization:4.1f}% | Int={interval:.2f}s | Overhead: CPU={self_cpu:.1f}% Mem={self_mem:.1f}MB")
            
            time.sleep(interval)

    print(f"\n>>> Saved to: {args.output}")

if __name__ == "__main__":
    main()