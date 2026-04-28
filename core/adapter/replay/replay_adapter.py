import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from core.adapter.base_adapter import BaseAdapter
from core.model.base_xpu import XPUStaticInfo, XPUDynamicMetrics


NUMERIC_COLUMNS = [
    "time",
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
    "power_limit_w",
    "fan_rpm",
    "perf_per_watt",
    "correctable_err_s",
    "uncorrectable_err_s",
    "device_uptime_s",
    "device_reset_count",
    "nv_ecc_correctable_total",
    "nv_ecc_ue_total",
    "nv_mem_clock_mhz",
    "nv_graphics_clock_mhz",
    "threads",
    "ctx_switch_rate",
    "l3_cache_mib",
    "io_util_percent",
    "duty_cycle_percent",
]

FAST_NUMERIC_COLUMNS = [
    "utilization",
    "chip_temp_c",
    "board_temp_c",
    "power_w",
    "mem_util_percent",
    "duty_cycle_percent",
]

FAST_LITERAL_COLUMNS = [
    "status",
    "error",
    "last_error_code",
    "throttle_flag",
    "throttle_cause",
    "last_error_ts",
]

SLOW_COLUMNS = [
    "freq_mhz",
    "freq_cap_mhz",
    "mem_total_mib",
    "mem_used_mib",
    "pcie_rx_MBps",
    "pcie_tx_MBps",
    "pstate",
    "power_limit_w",
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
]


def _infer_device_type(device_id: str) -> str:
    lowered = (device_id or "").lower()
    if lowered.startswith("cpu"):
        return "CPU"
    if lowered.startswith("gpu"):
        return "GPU"
    if lowered.startswith("npu"):
        return "NPU"
    return "Replay"


def _coerce_bool(value: Any) -> Optional[bool]:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


@dataclass
class ReplayDeviceTrace:
    device_id: str
    device_type: str
    vendor: str
    model_name: str
    identity_is_inferred: bool
    frame: pd.DataFrame


class ReplayTraceDataset:
    def __init__(
        self,
        trace_path: str,
        device_traces: Dict[str, ReplayDeviceTrace],
        step_s: float,
        duration_s: float,
        legacy_trace: bool = False,
    ):
        self.trace_path = str(trace_path)
        self.device_traces = device_traces
        self.step_s = step_s
        self.duration_s = duration_s
        self.legacy_trace = legacy_trace

    @classmethod
    def load(cls, trace_path: str) -> "ReplayTraceDataset":
        frame = pd.read_csv(trace_path)
        if frame.empty:
            raise ValueError(f"trace file is empty: {trace_path}")
        if "device_id" not in frame.columns or "time" not in frame.columns:
            raise ValueError("trace file must contain at least 'time' and 'device_id' columns")

        work = frame.copy()
        has_vendor_column = "vendor" in work.columns
        has_model_name_column = "model_name" in work.columns
        legacy_trace = not has_vendor_column or not has_model_name_column

        if legacy_trace:
            for column in ("chip_temp_c", "board_temp_c", "power_w", "perf_per_watt"):
                if column in work.columns:
                    work[column] = np.nan

        for column in NUMERIC_COLUMNS:
            if column in work.columns:
                work[column] = pd.to_numeric(work[column], errors="coerce")
        if "throttle_flag" in work.columns:
            work["throttle_flag"] = work["throttle_flag"].map(_coerce_bool)

        work["device_id"] = work["device_id"].fillna("").astype(str)
        if "device_type" in work.columns:
            work["device_type"] = work["device_type"].fillna("").astype(str)
        else:
            work["device_type"] = work["device_id"].map(_infer_device_type)

        device_traces: Dict[str, ReplayDeviceTrace] = {}
        for device_id, device_frame in work.groupby("device_id", sort=False):
            trace = device_frame.sort_values("time").reset_index(drop=True)
            if trace.empty:
                continue
            device_type = trace.iloc[0].get("device_type") or _infer_device_type(device_id)
            raw_vendor = trace.iloc[0].get("vendor") if has_vendor_column else None
            raw_model_name = trace.iloc[0].get("model_name") if has_model_name_column else None
            identity_is_inferred = pd.isna(raw_vendor) or pd.isna(raw_model_name) or not raw_vendor or not raw_model_name
            if identity_is_inferred:
                vendor, model_name = _default_replay_identity(
                    device_id=device_id,
                    device_type=str(device_type),
                    gpu_vendor="auto",
                )
            else:
                vendor = str(raw_vendor)
                model_name = str(raw_model_name)
            device_traces[device_id] = ReplayDeviceTrace(
                device_id=device_id,
                device_type=device_type,
                vendor=vendor,
                model_name=model_name,
                identity_is_inferred=identity_is_inferred,
                frame=trace,
            )

        if not device_traces:
            raise ValueError(f"trace file has no usable device rows: {trace_path}")

        sorted_times = np.unique(work["time"].dropna().sort_values().to_numpy(dtype=float))
        if len(sorted_times) > 1:
            diffs = np.diff(sorted_times)
            diffs = diffs[diffs > 0]
            step_s = float(np.median(diffs)) if len(diffs) else 1.0
        else:
            step_s = 1.0
        duration_s = float(work["time"].max())
        return cls(
            trace_path=trace_path,
            device_traces=device_traces,
            step_s=step_s,
            duration_s=duration_s,
            legacy_trace=legacy_trace,
        )

    def list_device_ids(self, requested_devices: Optional[list[str]] = None) -> list[str]:
        if not requested_devices or requested_devices == ["all"]:
            return list(self.device_traces.keys())

        selected: list[str] = []
        requested = {item.lower() for item in requested_devices}
        for device_id, trace in self.device_traces.items():
            if device_id.lower() in requested or trace.device_type.lower() in requested:
                selected.append(device_id)
        return selected

    def build_adapters(
        self,
        requested_devices: Optional[list[str]] = None,
        gpu_vendor: str = "auto",
    ) -> Dict[str, "ReplayTraceAdapter"]:
        selected_device_ids = self.list_device_ids(requested_devices)
        if not selected_device_ids:
            raise ValueError(
                f"requested devices {requested_devices} were not found in replay trace {self.trace_path}"
            )
        adapters: Dict[str, ReplayTraceAdapter] = {}
        for device_id in selected_device_ids:
            trace = self.device_traces[device_id]
            vendor = trace.vendor
            model_name = trace.model_name
            if trace.identity_is_inferred:
                vendor, model_name = _default_replay_identity(
                    device_id=device_id,
                    device_type=str(trace.device_type),
                    gpu_vendor=gpu_vendor,
                )
            adapters[device_id] = ReplayTraceAdapter(
                device_id=device_id,
                device_type=trace.device_type,
                vendor=vendor,
                model_name=model_name,
                frame=trace.frame,
                trace_duration_s=self.duration_s,
                trace_step_s=self.step_s,
            )
        return adapters


class ReplayTraceAdapter(BaseAdapter):
    def __init__(
        self,
        device_id: str,
        device_type: str,
        vendor: str,
        model_name: str,
        frame: pd.DataFrame,
        trace_duration_s: float,
        trace_step_s: float,
    ):
        super().__init__(device_id=device_id, device_type=device_type)
        self.frame = frame.reset_index(drop=True).copy()
        self.trace_duration_s = trace_duration_s
        self.trace_step_s = max(trace_step_s, 1e-3)
        self._started_at = time.monotonic()
        self._times = self.frame["time"].to_numpy(dtype=float)
        self._static_info = XPUStaticInfo(
            device_id=device_id,
            device_uid=f"replay::{device_id}",
            device_type=device_type.upper(),
            vendor=vendor,
            model_name=model_name,
        )

    def get_static_info(self) -> XPUStaticInfo:
        return self._static_info

    def collect_fast(self) -> XPUDynamicMetrics:
        trace_time = self.current_trace_time_s()
        prev_row, next_row, ratio = self._locate_rows(trace_time)

        payload = {
            "device_id": self.device_id,
            "utilization": self._interpolate_numeric(prev_row, next_row, ratio, "utilization", default=0.0),
            "sample_interval_s": self.trace_step_s,
            "trace_time_s": round(trace_time, 4),
            "collect_ts": int(round(trace_time * 1000.0)),
        }

        for column in FAST_NUMERIC_COLUMNS:
            if column == "utilization":
                continue
            payload[column] = self._interpolate_numeric(prev_row, next_row, ratio, column)

        for column in FAST_LITERAL_COLUMNS:
            payload[column] = self._read_literal(prev_row, next_row, column)

        if payload.get("status") is None:
            payload["status"] = "ok"

        return XPUDynamicMetrics(**payload)

    def collect_slow(self) -> Dict[str, Any]:
        trace_time = self.current_trace_time_s()
        prev_row, next_row, ratio = self._locate_rows(trace_time)
        payload: Dict[str, Any] = {}
        for column in SLOW_COLUMNS:
            if column in NUMERIC_COLUMNS:
                payload[column] = self._interpolate_numeric(prev_row, next_row, ratio, column)
            else:
                payload[column] = self._read_literal(prev_row, next_row, column)
        return payload

    def current_trace_time_s(self) -> float:
        elapsed = time.monotonic() - self._started_at
        return float(max(0.0, min(elapsed, self.trace_duration_s)))

    def _locate_rows(self, trace_time: float) -> tuple[pd.Series, pd.Series, float]:
        if len(self._times) == 1:
            row = self.frame.iloc[0]
            return row, row, 0.0

        next_index = int(np.searchsorted(self._times, trace_time, side="left"))
        if next_index <= 0:
            row = self.frame.iloc[0]
            return row, row, 0.0
        if next_index >= len(self._times):
            row = self.frame.iloc[-1]
            return row, row, 0.0

        prev_index = next_index - 1
        prev_row = self.frame.iloc[prev_index]
        next_row = self.frame.iloc[next_index]
        prev_time = float(prev_row["time"])
        next_time = float(next_row["time"])
        if next_time <= prev_time:
            return prev_row, next_row, 0.0
        ratio = (trace_time - prev_time) / (next_time - prev_time)
        return prev_row, next_row, float(max(0.0, min(ratio, 1.0)))

    def _interpolate_numeric(
        self,
        prev_row: pd.Series,
        next_row: pd.Series,
        ratio: float,
        column: str,
        default: Optional[float] = None,
    ) -> Optional[float]:
        prev_value = prev_row.get(column)
        next_value = next_row.get(column)
        if pd.isna(prev_value) and pd.isna(next_value):
            return default
        if pd.isna(prev_value):
            return float(next_value)
        if pd.isna(next_value):
            return float(prev_value)
        return float(prev_value + (next_value - prev_value) * ratio)

    def _read_literal(self, prev_row: pd.Series, next_row: pd.Series, column: str) -> Any:
        prev_value = prev_row.get(column)
        if not pd.isna(prev_value):
            if column == "throttle_flag":
                return _coerce_bool(prev_value)
            return prev_value

        next_value = next_row.get(column)
        if pd.isna(next_value):
            return None
        if column == "throttle_flag":
            return _coerce_bool(next_value)
        return next_value


def _default_replay_identity(device_id: str, device_type: str, gpu_vendor: str = "auto") -> tuple[str, str]:
    lowered_device = (device_id or "").lower()
    lowered_type = (device_type or "").lower()

    if lowered_device.startswith("cpu") or lowered_type == "cpu":
        return "HostCPU", "Replay CPU Trace"

    if lowered_device.startswith("gpu") or lowered_type == "gpu":
        normalized_gpu_vendor = (gpu_vendor or "auto").lower()
        if normalized_gpu_vendor == "intel":
            return "Intel", "Replay Intel GPU Trace"
        if normalized_gpu_vendor == "nvidia":
            return "NVIDIA", "Replay NVIDIA GPU Trace"
        return "GPU", "Replay GPU Trace"

    if lowered_device.startswith("npu") or lowered_type == "npu":
        return "Huawei", "Replay Ascend NPU Trace"

    return "Replay", f"Replay {str(device_type).upper()} Trace"
