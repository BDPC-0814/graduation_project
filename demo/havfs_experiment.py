# demo/havfs_experiment.py

import argparse
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import psutil

from core.collector.cpu_collector import CPUCollector
from core.collector.gpu_collector import GPUCollector
from core.collector.npu_collector import NPUCollector
from core.reporter.console_reporter import ConsoleReporter
from core.reporter.prometheus_reporter import PrometheusReporter
from core.scheduler.havfs import HAVFS
from core.scheduler.unified_scheduler import UnifiedScheduler


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fixed", "havfs"], default="fixed", help="采样模式")
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="设备类型，支持单设备或多设备组合，如 cpu / gpu / npu / cpu,gpu / cpu,gpu,npu",
    )
    parser.add_argument("--vendor", choices=["auto", "nvidia", "intel"], default="auto", help="GPU厂商")
    parser.add_argument("--reporter", choices=["console", "prometheus"], default="console", help="上报方式")
    parser.add_argument("--fixed-interval", type=float, default=2.0)
    parser.add_argument("--t-min", type=float, default=0.5)
    parser.add_argument("--t-max", type=float, default=5.0)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--output", type=str, default="experiments/test.csv")
    return parser.parse_args()


def parse_devices(device_arg: str):
    devices = [item.strip().lower() for item in device_arg.split(",") if item.strip()]
    valid = {"cpu", "gpu", "npu"}
    invalid = [d for d in devices if d not in valid]
    if invalid:
        raise ValueError(f"不支持的设备类型: {invalid}，仅支持 {sorted(valid)}")
    return devices


def build_collectors(devices, vendor):
    collectors = {}
    if "cpu" in devices:
        collectors["cpu0"] = CPUCollector(device_id="cpu0")
    if "gpu" in devices:
        collectors["gpu0"] = GPUCollector(device_id="gpu0", vendor=vendor)
    if "npu" in devices:
        collectors["npu0"] = NPUCollector(device_id="npu0", card_id=0)
    return collectors


def collect_parallel(collectors):
    with ThreadPoolExecutor(max_workers=max(1, len(collectors))) as pool:
        futures = {
            device_id: pool.submit(collector.collect)
            for device_id, collector in collectors.items()
        }
        return {
            device_id: futures[device_id].result()
            for device_id in collectors
        }


def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"\n>>> 毕设实验系统启动 [PID: {os.getpid()}]")

    args = parse_args()
    devices = parse_devices(args.device)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    collectors = build_collectors(devices, args.vendor)
    print(f"[信息] 启用设备: {', '.join(collectors.keys())}")

    if args.mode == "havfs":
        if len(collectors) == 1:
            scheduler = HAVFS(t_min=args.t_min, t_max=args.t_max, static_limit=80.0)
        else:
            scheduler = UnifiedScheduler(
                device_ids=list(collectors.keys()),
                t_min=args.t_min,
                t_max=args.t_max,
                static_limit=80.0,
            )
    else:
        scheduler = None

    reporter = PrometheusReporter(port=8000) if args.reporter == "prometheus" else ConsoleReporter()

    process = psutil.Process(os.getpid())
    start_time = time.time()

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "time",
                "device_id",
                "utilization",
                "risk_score",
                "interval",
                "state",
                "overhead_cpu",
                "overhead_mem_mb",
            ]
        )

        try:
            while time.time() - start_time < args.duration:
                metrics_map = collect_parallel(collectors)

                if args.mode == "fixed":
                    global_interval = args.fixed_interval
                    schedule_detail = {
                        "global_risk": 0.0,
                        "per_device": {
                            device_id: {
                                "interval": args.fixed_interval,
                                "risk": 0.0,
                                "state": "固定频率",
                            }
                            for device_id in collectors
                        },
                    }
                else:
                    if isinstance(scheduler, UnifiedScheduler):
                        global_interval, schedule_detail = scheduler.update(metrics_map)
                    else:
                        only_id = list(metrics_map.keys())[0]
                        interval, risk, state = scheduler.update(metrics_map[only_id])
                        global_interval = interval
                        schedule_detail = {
                            "global_risk": risk,
                            "per_device": {
                                only_id: {"interval": interval, "risk": risk, "state": state}
                            },
                        }

                self_cpu = process.cpu_percent(interval=None)
                self_mem = process.memory_info().rss / 1024 / 1024
                now = round(time.time() - start_time, 2)
                current_time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                for device_id, metrics in metrics_map.items():
                    detail = schedule_detail["per_device"][device_id]

                    if isinstance(reporter, PrometheusReporter):
                        reporter.send(metrics, detail["risk"], detail["interval"])

                    writer.writerow(
                        [
                            current_time_str,
                            now,
                            metrics.device_id,
                            metrics.utilization,
                            detail["risk"],
                            detail["interval"],
                            detail["state"],
                            self_cpu,
                            self_mem,
                        ]
                    )

                    print(
                        f"[{current_time_str}] {device_id:<4} | util={metrics.utilization:6.2f}% | "
                        f"risk={detail['risk']:6.2f} | interval={detail['interval']:4.2f}s | "
                        f"state={detail['state']}"
                    )

                time.sleep(global_interval)

        except KeyboardInterrupt:
            print("\n[用户中断] 实验提前结束。")

    print(f">>> 实验结束. 数据已保存至: {args.output}")


if __name__ == "__main__":
    main()
