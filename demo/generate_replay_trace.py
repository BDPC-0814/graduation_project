import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a deterministic heterogeneous replay trace for reproducible sampling experiments.")
    parser.add_argument("--output", default="experiments/replay_profiles/heterogeneous_fault_trace.csv")
    parser.add_argument("--events-output", default="experiments/replay_profiles/heterogeneous_fault_events.csv")
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--step", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260407)
    return parser.parse_args()


def smooth_plateau(t: float, start: float, end: float, amplitude: float, edge: float = 2.0) -> float:
    if t <= start - edge or t >= end + edge:
        return 0.0
    if start <= t <= end:
        return amplitude
    if t < start:
        x = (t - (start - edge)) / max(edge, 1e-6)
        return amplitude * x
    x = 1.0 - (t - end) / max(edge, 1e-6)
    return amplitude * max(x, 0.0)


def gaussian(t: float, center: float, width: float, amplitude: float) -> float:
    return amplitude * np.exp(-((t - center) ** 2) / (2.0 * width * width))


def clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def cpu_row(t: float, rng: np.random.Generator) -> dict:
    util = (
        12.0
        + 2.5 * np.sin(t / 6.0)
        + gaussian(t, 24.0, 3.8, 26.0)
        + gaussian(t, 34.0, 4.8, 42.0)
        + gaussian(t, 78.0, 5.5, 24.0)
        + smooth_plateau(t, 96.0, 108.0, 46.0, edge=3.0)
        + rng.normal(0.0, 1.1)
    )
    util = clamp(util, 2.0, 96.0)
    duty = clamp(util * 0.82 + 6.0 * np.sin(t / 10.0), 0.0, 100.0)
    mem_util = clamp(34.0 + util * 0.22 + smooth_plateau(t, 70.0, 90.0, 9.0) + rng.normal(0.0, 0.6), 22.0, 96.0)
    mem_total = 65536
    mem_used = int(mem_total * mem_util / 100.0)
    freq_cap = 4800.0
    freq = clamp(2200.0 + util * 23.0 + rng.normal(0.0, 50.0), 1500.0, freq_cap)
    threads = int(round(1800 + util * 17.0))
    ctx_switch = clamp(9000.0 + util * 900.0 + rng.normal(0.0, 250.0), 4000.0, 90000.0)
    io_util = clamp(10.0 + util * 0.55 + smooth_plateau(t, 74.0, 84.0, 18.0), 0.0, 100.0)
    return {
        "time": round(t, 4),
        "device_id": "cpu0",
        "device_type": "cpu",
        "vendor": "HostCPU",
        "model_name": "Replay CPU Trace",
        "utilization": round(util, 4),
        "chip_temp_c": "",
        "board_temp_c": "",
        "power_w": "",
        "freq_mhz": round(freq, 4),
        "freq_cap_mhz": freq_cap,
        "mem_total_mib": mem_total,
        "mem_used_mib": mem_used,
        "mem_util_percent": round(mem_util, 4),
        "pcie_rx_MBps": 0.0,
        "pcie_tx_MBps": 0.0,
        "pstate": "",
        "power_limit_w": 125.0,
        "throttle_flag": False,
        "throttle_cause": "",
        "last_error_code": "",
        "last_error_ts": "",
        "fan_rpm": "",
        "perf_per_watt": "",
        "correctable_err_s": 0.0,
        "uncorrectable_err_s": 0.0,
        "device_uptime_s": int(round(t)),
        "device_reset_count": 0,
        "nv_throttle_reasons": "",
        "nv_ecc_correctable_total": "",
        "nv_ecc_ue_total": "",
        "nv_mem_clock_mhz": "",
        "nv_graphics_clock_mhz": "",
        "threads": threads,
        "ctx_switch_rate": round(ctx_switch, 4),
        "l3_cache_mib": 32,
        "io_util_percent": round(io_util, 4),
        "duty_cycle_percent": round(duty, 4),
        "status": "ok",
        "error": "",
    }


def gpu_row(t: float, rng: np.random.Generator) -> dict:
    util = (
        18.0
        + 4.5 * np.sin(t / 7.0)
        + smooth_plateau(t, 30.0, 56.0, 46.0, edge=3.0)
        + gaussian(t, 52.0, 4.0, 22.0)
        + gaussian(t, 88.0, 5.0, 18.0)
        + smooth_plateau(t, 96.0, 108.0, 32.0, edge=2.5)
        + rng.normal(0.0, 1.2)
    )
    util = clamp(util, 0.0, 99.0)
    mem_util = clamp(24.0 + util * 0.58 + smooth_plateau(t, 42.0, 63.0, 10.0) + rng.normal(0.0, 0.8), 10.0, 99.0)
    mem_total = 24576
    mem_used = int(mem_total * mem_util / 100.0)
    power_limit = 240.0
    throttle = smooth_plateau(t, 52.0, 60.0, 1.0) > 0 or smooth_plateau(t, 96.0, 108.0, 1.0) > 0
    pcie_rx = clamp(450.0 + util * 12.0 + rng.normal(0.0, 15.0), 100.0, 2800.0)
    pcie_tx = clamp(320.0 + util * 10.0 + rng.normal(0.0, 15.0), 80.0, 2200.0)
    graphics_clock = clamp(800.0 + util * 12.5, 500.0, 2200.0)
    mem_clock = clamp(3500.0 + util * 22.0, 3000.0, 9500.0)
    return {
        "time": round(t, 4),
        "device_id": "gpu0",
        "device_type": "gpu",
        "vendor": "NVIDIA",
        "model_name": "Replay NVIDIA GPU Trace",
        "utilization": round(util, 4),
        "chip_temp_c": "",
        "board_temp_c": "",
        "power_w": "",
        "freq_mhz": round(graphics_clock, 4),
        "freq_cap_mhz": 2200.0,
        "mem_total_mib": mem_total,
        "mem_used_mib": mem_used,
        "mem_util_percent": round(mem_util, 4),
        "pcie_rx_MBps": round(pcie_rx, 4),
        "pcie_tx_MBps": round(pcie_tx, 4),
        "pstate": "P0" if util >= 70.0 else "P2" if util >= 35.0 else "P5",
        "power_limit_w": power_limit,
        "throttle_flag": throttle,
        "throttle_cause": "synthetic_guard" if throttle else "",
        "last_error_code": "",
        "last_error_ts": "",
        "fan_rpm": int(round(1100 + util * 32.0)),
        "perf_per_watt": "",
        "correctable_err_s": round(max(0.0, smooth_plateau(t, 54.0, 60.0, 0.18)), 4),
        "uncorrectable_err_s": 0.0,
        "device_uptime_s": int(round(t)),
        "device_reset_count": 0,
        "nv_throttle_reasons": "sw_thermal_slowdown,sw_power_cap" if throttle else "none",
        "nv_ecc_correctable_total": int(round(max(0.0, t - 55.0))) if t >= 55.0 else 0,
        "nv_ecc_ue_total": 0,
        "nv_mem_clock_mhz": round(mem_clock, 4),
        "nv_graphics_clock_mhz": round(graphics_clock, 4),
        "threads": "",
        "ctx_switch_rate": "",
        "l3_cache_mib": "",
        "io_util_percent": "",
        "duty_cycle_percent": round(clamp(util * 0.92, 0.0, 100.0), 4),
        "status": "ok",
        "error": "",
    }


def npu_row(t: float, rng: np.random.Generator) -> dict:
    util = (
        14.0
        + 2.0 * np.sin(t / 5.0)
        + gaussian(t, 38.0, 4.5, 18.0)
        + smooth_plateau(t, 62.0, 74.0, 28.0, edge=2.0)
        + smooth_plateau(t, 96.0, 108.0, 36.0, edge=2.5)
        + rng.normal(0.0, 0.9)
    )
    error_window = 78.0 <= t <= 84.0
    util = clamp(util - (16.0 if error_window else 0.0), 0.0, 92.0)
    mem_util = clamp(18.0 + util * 0.47 + smooth_plateau(t, 62.0, 74.0, 6.0) + rng.normal(0.0, 0.6), 8.0, 94.0)
    mem_total = 32768
    mem_used = int(mem_total * mem_util / 100.0)
    return {
        "time": round(t, 4),
        "device_id": "npu0",
        "device_type": "npu",
        "vendor": "Huawei",
        "model_name": "Replay Ascend NPU Trace",
        "utilization": round(util, 4),
        "chip_temp_c": "",
        "board_temp_c": "",
        "power_w": "",
        "freq_mhz": round(clamp(900.0 + util * 8.0, 700.0, 1600.0), 4),
        "freq_cap_mhz": 1600.0,
        "mem_total_mib": mem_total,
        "mem_used_mib": mem_used,
        "mem_util_percent": round(mem_util, 4),
        "pcie_rx_MBps": round(clamp(120.0 + util * 5.0, 30.0, 900.0), 4),
        "pcie_tx_MBps": round(clamp(90.0 + util * 4.0, 20.0, 700.0), 4),
        "pstate": "AICORE_BUSY" if util >= 55.0 else "AICORE_READY",
        "power_limit_w": 150.0,
        "throttle_flag": False,
        "throttle_cause": "",
        "last_error_code": "fabric_retry" if error_window else "",
        "last_error_ts": int(round(t)) if error_window else "",
        "fan_rpm": "",
        "perf_per_watt": "",
        "correctable_err_s": round(0.08 if error_window else 0.0, 4),
        "uncorrectable_err_s": 0.0,
        "device_uptime_s": int(round(t)),
        "device_reset_count": 1 if t >= 84.0 else 0,
        "nv_throttle_reasons": "",
        "nv_ecc_correctable_total": "",
        "nv_ecc_ue_total": "",
        "nv_mem_clock_mhz": "",
        "nv_graphics_clock_mhz": "",
        "threads": "",
        "ctx_switch_rate": "",
        "l3_cache_mib": "",
        "io_util_percent": "",
        "duty_cycle_percent": round(clamp(util * 0.9, 0.0, 100.0), 4),
        "status": "degraded" if error_window else "ok",
        "error": "fabric_retry" if error_window else "",
    }


def build_events() -> list[dict]:
    return [
        {"time": 24.0, "device_id": "cpu0", "event_type": "cpu_fault_ramp", "severity": "high", "description": "CPU enters the first fault-evolution ramp window."},
        {"time": 34.0, "device_id": "cpu0", "event_type": "cpu_peak_load", "severity": "critical", "description": "CPU reaches a high-load burst that should trigger focused observation."},
        {"time": 32.0, "device_id": "gpu0", "event_type": "gpu_pipeline_fill", "severity": "high", "description": "GPU pipeline begins sustained filling with rising memory pressure."},
        {"time": 52.0, "device_id": "gpu0", "event_type": "gpu_thermal_pressure", "severity": "critical", "description": "GPU enters thermal/power constrained execution."},
        {"time": 64.0, "device_id": "npu0", "event_type": "npu_batch_pressure", "severity": "high", "description": "NPU receives a sustained inference batch burst."},
        {"time": 78.0, "device_id": "npu0", "event_type": "npu_fabric_retry", "severity": "critical", "description": "NPU begins retrying due to a synthetic fabric anomaly."},
        {"time": 96.0, "device_id": "", "event_type": "cross_device_fault_window", "severity": "critical", "description": "Cross-device fault-evolution window affecting all accelerators."},
    ]


def main():
    args = parse_args()
    output_path = Path(args.output)
    events_path = Path(args.events_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.parent.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    times = np.arange(0.0, args.duration + args.step, args.step)
    rows = []
    for t in times:
        rows.append(cpu_row(float(t), rng))
        rows.append(gpu_row(float(t), rng))
        rows.append(npu_row(float(t), rng))

    trace_df = pd.DataFrame(rows)
    event_df = pd.DataFrame(build_events())

    trace_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    event_df.to_csv(events_path, index=False, encoding="utf-8-sig")

    print(f"trace={output_path} rows={len(trace_df)} duration={args.duration}s step={args.step}s")
    print(f"events={events_path} rows={len(event_df)}")


if __name__ == "__main__":
    main()
