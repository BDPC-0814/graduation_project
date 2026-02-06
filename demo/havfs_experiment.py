# demo/havfs_experiment.py

import argparse
import csv
import json
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
from core.storage.sqlite_outbox import SQLiteOutbox
from core.uploader.http_uploader import HTTPUploader


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
    parser.add_argument("--event-output", type=str, default="experiments/events.csv")
    parser.add_argument("--outbox-db", type=str, default="experiments/outbox.db")
    parser.add_argument("--remote-endpoint", type=str, default="", help="云侧接收端点（HTTP POST）")
    parser.add_argument("--retry-batch-size", type=int, default=50)
    parser.add_argument("--retry-max-attempts", type=int, default=8)
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


def collect_parallel(collectors, executor):
    """复用外部传入的线程池进行并发采集"""
    futures = {device_id: executor.submit(collector.collect) for device_id, collector in collectors.items()}
    return {device_id: futures[device_id].result() for device_id in collectors}


def flush_outbox(outbox: SQLiteOutbox, uploader: HTTPUploader, batch_size: int, max_attempts: int):
    if uploader is None:
        return 0, 0

    sent = 0
    failed = 0
    for row in outbox.fetch_due(limit=batch_size):
        payload = json.loads(row["payload"])
        attempts = row["attempts"] + 1
        try:
            uploader.upload(row["record_type"], payload)
            outbox.mark_sent(row["id"])
            sent += 1
        except Exception as exc:  # noqa: BLE001
            outbox.mark_retry(
                row_id=row["id"],
                attempts=attempts,
                last_error=str(exc),
                max_attempts=max_attempts,
            )
            failed += 1
    return sent, failed


def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"\n>>> 毕设实验系统启动 [PID: {os.getpid()}]")

    args = parse_args()
    devices = parse_devices(args.device)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(os.path.dirname(args.event_output), exist_ok=True)

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
    outbox = SQLiteOutbox(args.outbox_db)
    uploader = HTTPUploader(args.remote_endpoint) if args.remote_endpoint else None

    process = psutil.Process(os.getpid())
    start_time = time.time()

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f, open(
        args.event_output, "w", newline="", encoding="utf-8-sig"
    ) as ef:
        writer = csv.writer(f)
        event_writer = csv.writer(ef)

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
                "status",
                "error",
            ]
        )
        event_writer.writerow(
            [
                "timestamp",
                "time",
                "device_id",
                "event_type",
                "severity",
                "message",
                "detail",
            ]
        )

        try:
            with ThreadPoolExecutor(max_workers=max(1, len(collectors))) as executor:
                while time.time() - start_time < args.duration:
                    metrics_map = collect_parallel(collectors, executor)
                    schedule_input = {
                        device_id: metrics
                        for device_id, metrics in metrics_map.items()
                        if metrics.status == "ok"
                    }

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
                        if not schedule_input:
                            global_interval = args.t_min
                            schedule_detail = {
                                "global_risk": 100.0,
                                "per_device": {
                                    device_id: {
                                        "interval": args.t_min,
                                        "risk": 100.0,
                                        "state": "设备不可用(快速重试)",
                                    }
                                    for device_id in collectors
                                },
                            }
                        elif isinstance(scheduler, UnifiedScheduler):
                            global_interval, schedule_detail = scheduler.update(schedule_input)
                            for device_id in collectors:
                                if device_id not in schedule_detail["per_device"]:
                                    schedule_detail["per_device"][device_id] = {
                                        "interval": args.t_min,
                                        "risk": 100.0,
                                        "state": "设备不可用(快速重试)",
                                    }
                        else:
                            only_id = list(schedule_input.keys())[0]
                            interval, risk, state = scheduler.update(schedule_input[only_id])
                            global_interval = interval
                            schedule_detail = {
                                "global_risk": risk,
                                "per_device": {only_id: {"interval": interval, "risk": risk, "state": state}},
                            }
                            for device_id in collectors:
                                if device_id not in schedule_detail["per_device"]:
                                    schedule_detail["per_device"][device_id] = {
                                        "interval": args.t_min,
                                        "risk": 100.0,
                                        "state": "设备不可用(快速重试)",
                                    }

                    self_cpu = process.cpu_percent(interval=None)
                    self_mem = process.memory_info().rss / 1024 / 1024
                    now = round(time.time() - start_time, 2)
                    current_time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                    for device_id, metrics in metrics_map.items():
                        detail = schedule_detail["per_device"][device_id]

                        if metrics.status != "ok":
                            event_payload = {
                                "timestamp": current_time_str,
                                "time": now,
                                "device_id": metrics.device_id,
                                "event_type": "collector_unavailable",
                                "severity": "high",
                                "message": metrics.error or "collector unavailable",
                                "detail": metrics.summary(),
                            }
                            event_writer.writerow(event_payload.values())
                            outbox.enqueue("event", event_payload)

                        if isinstance(reporter, PrometheusReporter):
                            reporter.send(metrics, detail["risk"], detail["interval"])

                        metric_payload = {
                            "timestamp": current_time_str,
                            "time": now,
                            "device_id": metrics.device_id,
                            "utilization": metrics.utilization,
                            "temperature": metrics.temperature,
                            "power": metrics.power,
                            "memory_usage": metrics.memory_usage,
                            "risk_score": detail["risk"],
                            "interval": detail["interval"],
                            "state": detail["state"],
                            "status": metrics.status,
                            "error": metrics.error,
                        }
                        outbox.enqueue("metric", metric_payload)

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
                                metrics.status,
                                metrics.error,
                            ]
                        )

                        print(
                            f"[{current_time_str}] {device_id:<4} | util={metrics.utilization:6.2f}% | "
                            f"risk={detail['risk']:6.2f} | interval={detail['interval']:4.2f}s | "
                            f"state={detail['state']} | status={metrics.status}"
                        )

                    sent, failed = flush_outbox(
                        outbox=outbox,
                        uploader=uploader,
                        batch_size=args.retry_batch_size,
                        max_attempts=args.retry_max_attempts,
                    )
                    pending, dead = outbox.stats()
                    if uploader is not None:
                        print(f"[OUTBOX] sent={sent}, failed={failed}, pending={pending}, dead={dead}")

                    time.sleep(global_interval)

        except KeyboardInterrupt:
            print("\n[用户中断] 实验提前结束。")

    outbox.close()
    print(f">>> 实验结束. 指标数据: {args.output} | 事件数据: {args.event_output} | 队列DB: {args.outbox_db}")


if __name__ == "__main__":
    main()