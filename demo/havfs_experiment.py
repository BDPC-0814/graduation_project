# demo/havfs_experiment.py

import argparse
import csv
import os
import time
import psutil
from datetime import datetime

# 引入核心组件
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

def print_header():
    """打印漂亮的表格头"""
    print("=" * 138)
    # 调整列宽适配内容
    print(f"{'Timestamp':<14} | {'时间(s)':<9} | {'CPU利用率(%)':<6} | {'风险评分(0-100)':<15} | {'采样间隔(s)':<10} | {'变频决策状态':<14} | {'系统开销':<25}")
    print("-" * 138)

def print_row(timestamp, now, metrics, risk, interval, state, cpu, mem):
    """打印对齐的数据行"""
    
    # 对高风险数据进行视觉标记
    risk_str = f"{risk:.2f}"
    if risk > 40.0:
        risk_str += " (!)" # 超过阈值加感叹号提醒

    print(
        f"{timestamp:<14} | "
        f"{now:<11.1f} | "
        f"{metrics.utilization:<12.1f} | "
        f"{risk_str:<19} | "
        f"{interval:<14.2f} | "
        f"{state:<16} | "
        f"CPU:{cpu:4.1f}%  Mem:{mem:5.1f}MB"
    )

def main():
    # os.system('cls' if os.name == 'nt' else 'clear') 
    print(f"\n>>> 毕设实验系统启动 [PID: {os.getpid()}]")
    args = parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # 1. 初始化采集器
    if args.device == "gpu":
        print("[信息] 设备类型: GPU (真实/模拟)")
        collector = GPUCollector(device_id="gpu0")
    else:
        print("[信息] 设备类型: CPU (真实)")
        collector = CPUCollector(device_id="cpu0")

    # 2. 初始化调度器 (传递调优后的参数)
    # 注意: 这里虽然可以传参，但建议直接修改 havfs.py 的默认值以保持一致性
    scheduler = HAVFS(
        t_min=args.t_min, 
        t_max=args.t_max, 
        static_limit=80.0
    ) if args.mode == "havfs" else None

    # 3. 初始化 Reporter
    if args.reporter == "prometheus":
        reporter = PrometheusReporter(port=8000)
    else:
        reporter = ConsoleReporter()

    process = psutil.Process(os.getpid())
    start_time = time.time()

    print_header()

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "time", "device_id", "utilization", "risk_score", "interval", "state",
            "overhead_cpu", "overhead_mem_mb"
        ])

        try:
            while time.time() - start_time < args.duration:
                # A. 采集
                metrics = collector.collect()

                # B. 调度
                if args.mode == "fixed":
                    interval = args.fixed_interval
                    risk = 0.0
                    state = "固定频率"
                else:
                    # havfs.update 返回的是 (interval, risk_score_100, state_label)
                    interval, risk, state = scheduler.update(metrics)

                # C. 上报
                if isinstance(reporter, PrometheusReporter):
                    reporter.send(metrics, risk, interval)
                
                # D. 开销测量
                self_cpu = process.cpu_percent(interval=None)
                self_mem = process.memory_info().rss / 1024 / 1024

                # E. 准备数据
                now = round(time.time() - start_time, 2)
                current_time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                # F. 记录 CSV
                writer.writerow([
                    current_time_str,
                    now, metrics.device_id, metrics.utilization, risk, interval, state,
                    self_cpu, self_mem
                ])

                # G. 打印
                print_row(current_time_str, now, metrics, risk, interval, state, self_cpu, self_mem)
                
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[用户中断] 实验提前结束。")
    
    print("-" * 138)
    print(f">>> 实验结束. 数据已保存至: {args.output}")

if __name__ == "__main__":
    main()