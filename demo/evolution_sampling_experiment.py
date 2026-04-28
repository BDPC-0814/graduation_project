import argparse
import csv
import os
import sys
from typing import Optional

import psutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.adapter.cpu.cpu_adapter import CPUAdapter
from core.adapter.gpu.gpu_adapter import GPUAdapter
from core.adapter.npu.npu_adapter import NPUAdapter
from core.adapter.replay.replay_adapter import ReplayTraceDataset
from core.reporter.console_reporter import ConsoleReporter
from core.runtime.edge_agent import EdgeAgent
from core.sampler.device_sampler import DeviceSampler
from core.storage.sqlite_outbox import SQLiteOutbox
from core.uploader.http_uploader import HTTPUploader

try:
    from core.reporter.prometheus_reporter import PrometheusReporter
except ModuleNotFoundError:
    PrometheusReporter = None


METRIC_HEADERS = [
    "timestamp",
    "time",
    "device_id",
    "utilization",
    "chip_temp_c",
    "board_temp_c",
    "power_w",
    "freq_mhz",
    "freq_cap_mhz",
    "mem_total_mib",
    "mem_used_mib",
    "mem_util_percent",
    "pcie_rx_MBps",
    "pcie_tx_MBps",
    "pstate",
    "power_limit_w",
    "throttle_flag",
    "throttle_cause",
    "last_error_code",
    "last_error_ts",
    "fan_rpm",
    "perf_per_watt",
    "correctable_err_s",
    "uncorrectable_err_s",
    "device_uptime_s",
    "device_reset_count",
    "nv_throttle_reasons",
    "nv_ecc_correctable_total",
    "nv_ecc_ue_total",
    "nv_mem_clock_mhz",
    "nv_graphics_clock_mhz",
    "threads",
    "ctx_switch_rate",
    "l3_cache_mib",
    "io_util_percent",
    "duty_cycle_percent",
    "collect_ts",
    "sample_interval_s",
    "evolution_score",
    "field_priority_score",
    "execution_pressure_score",
    "control_score",
    "interval",
    "phase",
    "field_policy",
    "transport_policy",
    "sampled_slow",
    "outbox_pending",
    "outbox_dead",
    "ring_backlog",
    "overhead_cpu",
    "overhead_mem_mb",
    "status",
    "error",
]

EVENT_HEADERS = [
    "timestamp",
    "time",
    "device_id",
    "event_type",
    "severity",
    "message",
    "detail",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fixed", "evolution"], default="fixed")
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--vendor", choices=["auto", "nvidia", "intel"], default="auto")
    parser.add_argument(
        "--npu-backend",
        choices=["auto", "ascend", "openharmony_hdc", "rockchip_sysfs"],
        default="auto",
    )
    parser.add_argument("--trace-file", type=str, default="", help="Replay trace CSV for reproducible experiments")
    parser.add_argument("--reporter", choices=["console", "prometheus"], default="console")
    parser.add_argument("--fixed-interval", type=float, default=5.0)
    parser.add_argument("--t-min", type=float, default=1.0)
    parser.add_argument("--t-max", type=float, default=6.0)
    parser.add_argument("--duration", type=float, default=0.0, help="Experiment duration in seconds; <=0 auto-uses trace length or 60s")
    parser.add_argument("--output", type=str, default="experiments/test.csv")
    parser.add_argument("--event-output", type=str, default="experiments/events.csv")
    parser.add_argument("--outbox-db", type=str, default="experiments/outbox.db")
    parser.add_argument("--remote-endpoint", type=str, default="")
    parser.add_argument("--retry-batch-size", type=int, default=100)
    parser.add_argument("--retry-max-attempts", type=int, default=8)
    return parser.parse_args()


def parse_devices(device_arg: str):
    devices = [item.strip().lower() for item in device_arg.split(",") if item.strip()]
    valid = {"cpu", "gpu", "npu", "all"}
    invalid = [d for d in devices if d not in valid]
    if invalid:
        raise ValueError(f"unsupported devices: {invalid}, supported={sorted(valid)}")
    if "all" in devices:
        return ["all"]
    return devices


def build_adapters(devices, vendor, npu_backend: str = "auto", trace_dataset: Optional[ReplayTraceDataset] = None):
    if trace_dataset is not None:
        return trace_dataset.build_adapters(requested_devices=devices, gpu_vendor=vendor)
    adapters = {}
    if "cpu" in devices:
        adapters["cpu0"] = CPUAdapter(device_id="cpu0")
    if "gpu" in devices:
        adapters["gpu0"] = GPUAdapter(device_id="gpu0", vendor=vendor)
    if "npu" in devices:
        adapters["npu0"] = NPUAdapter(device_id="npu0", card_id=0, backend=npu_backend)
    return adapters


def build_samplers(adapters, args):
    return {
        device_id: DeviceSampler(
            device_id=device_id,
            adapter=adapter,
            mode=args.mode,
            fixed_interval=args.fixed_interval,
            t_min=args.t_min,
            t_max=args.t_max,
            static_limit=80.0,
        )
        for device_id, adapter in adapters.items()
    }


def print_device_inventory(adapters):
    print("[Info] device inventory:")
    for device_id, adapter in adapters.items():
        try:
            info = adapter.get_static_info()
        except Exception:  # noqa: BLE001
            info = None
        if info is None:
            print(f"  - {device_id}: type={getattr(adapter, 'device_type', 'unknown')}")
            continue
        vendor = info.vendor or "Unknown"
        model = info.model_name or "Unknown"
        print(f"  - {device_id}: type={info.device_type}, vendor={vendor}, model={model}")


def make_metric_payload(metrics, result, elapsed, wallclock, overhead_cpu, overhead_mem_mb):
    sample_time = metrics.trace_time_s if metrics.trace_time_s is not None else elapsed
    return {
        "timestamp": wallclock,
        "time": sample_time,
        "device_id": metrics.device_id,
        "utilization": metrics.utilization,
        "chip_temp_c": metrics.chip_temp_c,
        "board_temp_c": metrics.board_temp_c,
        "power_w": metrics.power_w,
        "freq_mhz": metrics.freq_mhz,
        "freq_cap_mhz": metrics.freq_cap_mhz,
        "mem_total_mib": metrics.mem_total_mib,
        "mem_used_mib": metrics.mem_used_mib,
        "mem_util_percent": metrics.mem_util_percent,
        "pcie_rx_MBps": metrics.pcie_rx_MBps,
        "pcie_tx_MBps": metrics.pcie_tx_MBps,
        "pstate": metrics.pstate,
        "power_limit_w": metrics.power_limit_w,
        "throttle_flag": metrics.throttle_flag,
        "throttle_cause": metrics.throttle_cause,
        "last_error_code": metrics.last_error_code,
        "last_error_ts": metrics.last_error_ts,
        "fan_rpm": metrics.fan_rpm,
        "perf_per_watt": metrics.perf_per_watt,
        "correctable_err_s": metrics.correctable_err_s,
        "uncorrectable_err_s": metrics.uncorrectable_err_s,
        "device_uptime_s": metrics.device_uptime_s,
        "device_reset_count": metrics.device_reset_count,
        "nv_throttle_reasons": metrics.nv_throttle_reasons,
        "nv_ecc_correctable_total": metrics.nv_ecc_correctable_total,
        "nv_ecc_ue_total": metrics.nv_ecc_ue_total,
        "nv_mem_clock_mhz": metrics.nv_mem_clock_mhz,
        "nv_graphics_clock_mhz": metrics.nv_graphics_clock_mhz,
        "threads": metrics.threads,
        "ctx_switch_rate": metrics.ctx_switch_rate,
        "l3_cache_mib": metrics.l3_cache_mib,
        "io_util_percent": metrics.io_util_percent,
        "duty_cycle_percent": metrics.duty_cycle_percent,
        "collect_ts": metrics.collect_ts,
        "sample_interval_s": metrics.sample_interval_s,
        "evolution_score": result.evolution_score,
        "field_priority_score": result.field_priority_score,
        "execution_pressure_score": result.execution_pressure_score,
        "control_score": result.control_score,
        "interval": result.interval,
        "phase": result.phase,
        "field_policy": result.field_policy,
        "transport_policy": result.transport_policy,
        "sampled_slow": result.sampled_slow,
        "overhead_cpu": overhead_cpu,
        "overhead_mem_mb": overhead_mem_mb,
        "status": metrics.status,
        "error": metrics.error,
    }


def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"\n>>>Experiment started [PID: {os.getpid()}]")

    args = parse_args()
    devices = parse_devices(args.device)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(os.path.dirname(args.event_output), exist_ok=True)

    trace_dataset = ReplayTraceDataset.load(args.trace_file) if args.trace_file else None
    adapters = build_adapters(devices, args.vendor, npu_backend=args.npu_backend, trace_dataset=trace_dataset)
    samplers = build_samplers(adapters, args)
    print(f"[Info] enabled devices: {', '.join(samplers.keys())}")
    print_device_inventory(adapters)
    if trace_dataset is not None:
        if trace_dataset.legacy_trace:
            print("[Warn] legacy replay trace detected: inferred device vendor/model and cleared synthetic temp/power fields.")
        print(f"[Info] replay trace: {args.trace_file} (duration={trace_dataset.duration_s:.2f}s, step={trace_dataset.step_s:.2f}s)")

    if args.reporter == "prometheus":
        if PrometheusReporter is None:
            raise ModuleNotFoundError("prometheus_client is required when --reporter=prometheus")
        reporter = PrometheusReporter(port=8000)
    else:
        reporter = ConsoleReporter()

    outbox = SQLiteOutbox(args.outbox_db)
    uploader = HTTPUploader(args.remote_endpoint) if args.remote_endpoint else None
    process = psutil.Process(os.getpid())
    agent = EdgeAgent(
        samplers=samplers,
        outbox=outbox,
        uploader=uploader,
        wal_batch_size=max(10, args.retry_batch_size),
        upload_batch_size=args.retry_batch_size,
        retry_max_attempts=args.retry_max_attempts,
    )

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f, open(
        args.event_output, "w", newline="", encoding="utf-8-sig"
    ) as ef:
        writer = csv.DictWriter(f, fieldnames=METRIC_HEADERS)
        event_writer = csv.DictWriter(ef, fieldnames=EVENT_HEADERS)
        writer.writeheader()
        event_writer.writeheader()

        def on_metric(result, elapsed, wallclock):
            metrics = result.metrics
            overhead_cpu = process.cpu_percent(interval=None)
            overhead_mem_mb = process.memory_info().rss / 1024 / 1024
            pending, dead = outbox.stats()
            ring_backlog = agent.ring_buffer.size()
            metric_payload = make_metric_payload(
                metrics=metrics,
                result=result,
                elapsed=elapsed,
                wallclock=wallclock,
                overhead_cpu=overhead_cpu,
                overhead_mem_mb=overhead_mem_mb,
            )
            metric_payload["outbox_pending"] = pending
            metric_payload["outbox_dead"] = dead
            metric_payload["ring_backlog"] = ring_backlog
            writer.writerow(metric_payload)

            if PrometheusReporter is not None and isinstance(reporter, PrometheusReporter):
                reporter.send(
                    metrics=metrics,
                    evolution_score=result.evolution_score,
                    field_priority_score=result.field_priority_score,
                    execution_pressure_score=result.execution_pressure_score,
                    interval=result.interval,
                )

            print(
                f"[{wallclock}] {metrics.device_id:<4} | util={metrics.utilization:6.2f}% | "
                f"temp={metrics.chip_temp_c if metrics.chip_temp_c is not None else 'NA'} | "
                f"power={metrics.power_w if metrics.power_w is not None else 'NA'} | "
                f"urgency={result.evolution_score:6.2f} | interval={result.interval:4.2f}s | "
                f"phase={result.phase} | fields={result.field_policy} | "
                f"transport={result.transport_policy} | slow={result.sampled_slow} | status={metrics.status}"
            )
            return [("metric", metric_payload)]

        def on_event(result, elapsed, wallclock):
            event_payload = {
                "timestamp": wallclock,
                "time": elapsed,
                "device_id": result.metrics.device_id,
                "event_type": "collector_unavailable",
                "severity": "high",
                "message": result.metrics.error or "collector unavailable",
                "detail": result.metrics.summary(),
            }
            event_writer.writerow(event_payload)
            return [("event", event_payload)]

        def on_cycle_end(_results, _interval):
            pending, dead = outbox.stats()
            if uploader is not None:
                print(f"[OUTBOX] pending={pending}, dead={dead}")

        try:
            experiment_duration = args.duration if args.duration and args.duration > 0 else (
                trace_dataset.duration_s if trace_dataset is not None else 60.0
            )
            agent.run(
                duration=experiment_duration,
                on_metric=on_metric,
                on_event=on_event,
                on_cycle_end=on_cycle_end,
            )
        except KeyboardInterrupt:
            print("\n[Interrupted] experiment stopped early.")

    outbox.close()
    print(f">>> experiment finished. metrics={args.output} events={args.event_output} outbox={args.outbox_db}")


if __name__ == "__main__":
    main()
