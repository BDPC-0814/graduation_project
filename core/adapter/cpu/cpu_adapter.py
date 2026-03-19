import platform
import random
import re
import subprocess
import time
from collections import deque
from typing import Optional

import psutil

from core.adapter.base_adapter import BaseAdapter
from core.adapter.windows_sensor_reader import WindowsSensorReader
from core.model.base_xpu import XPUStaticInfo, XPUDynamicMetrics


class CPUAdapter(BaseAdapter):
    """
    CPU adapter backed by psutil and lightweight OS commands.
    """

    def __init__(self, device_id: str = "cpu0", sample_interval: float = 0.1, duty_window_size: int = 10):
        super().__init__(device_id=device_id, device_type="CPU")
        self.sample_interval = sample_interval
        self._duty_window = deque(maxlen=duty_window_size)
        self._prev_cpu_stats = psutil.cpu_stats()
        self._prev_disk_stats = psutil.disk_io_counters()
        self._prev_ctx_ts = time.time()
        self._l3_cache_mib = self._detect_l3_cache_mib()
        self._windows_sensor_reader = WindowsSensorReader()
        cpu_model = platform.processor() or "Unknown CPU"
        self._static_info = XPUStaticInfo(
            device_id=device_id,
            device_uid=device_id,
            device_type="CPU",
            arch=platform.machine(),
            vendor=cpu_model,
            model_name=cpu_model,
            core_count=psutil.cpu_count(logical=False) or psutil.cpu_count(),
        )

    def get_static_info(self) -> XPUStaticInfo:
        return self._static_info

    def collect_fast(self) -> XPUDynamicMetrics:
        utilization = psutil.cpu_percent(interval=self.sample_interval)
        collect_ts = int(time.time())

        chip_temp_c, board_temp_c = self._read_temperatures()
        power_w = None

        sensor_snapshot = self._windows_sensor_reader.read()
        if chip_temp_c is None:
            chip_temp_c = sensor_snapshot.cpu_temp_c
        if board_temp_c is None:
            board_temp_c = sensor_snapshot.cpu_board_temp_c
        power_w = sensor_snapshot.cpu_power_w

        if power_w is not None and power_w <= 0.0:
            power_w = None

        self._duty_window.append(utilization)
        duty_cycle_percent = sum(self._duty_window) / len(self._duty_window)

        return XPUDynamicMetrics(
            utilization=utilization,
            temperature=chip_temp_c,
            power=power_w,
            memory_usage=psutil.virtual_memory().percent,
            bandwidth=random.uniform(10, 60),
            device_id=self.device_id,
            collect_ts=collect_ts,
            sample_interval_s=self.sample_interval,
            chip_temp_c=chip_temp_c,
            board_temp_c=board_temp_c,
            power_w=power_w,
            duty_cycle_percent=duty_cycle_percent,
        )

    def collect_slow(self) -> dict:
        freq = psutil.cpu_freq()
        freq_mhz = float(freq.current) if freq and freq.current is not None else None
        freq_cap_mhz = float(freq.max) if freq and freq.max not in (None, 0) else None

        return {
            "freq_mhz": freq_mhz,
            "freq_cap_mhz": freq_cap_mhz,
            "threads": self._count_threads(),
            "ctx_switch_rate": self._calc_ctx_switch_rate(),
            "l3_cache_mib": self._l3_cache_mib,
            "io_util_percent": self._calc_io_util_percent(),
        }

    def _read_temperatures(self) -> tuple[Optional[float], Optional[float]]:
        chip_temp_c = None
        board_temp_c = None
        try:
            temps = psutil.sensors_temperatures()
        except Exception:
            temps = {}

        readings = []
        for entries in temps.values():
            for entry in entries:
                current = getattr(entry, "current", None)
                if current is not None:
                    readings.append((getattr(entry, "label", "") or "", float(current)))

        if readings:
            chip_temp_c = readings[0][1]
            if len(readings) > 1:
                board_temp_c = readings[1][1]
        return chip_temp_c, board_temp_c

    def _count_threads(self) -> Optional[int]:
        try:
            return sum(proc.info["num_threads"] for proc in psutil.process_iter(attrs=["num_threads"]))
        except Exception:
            return None

    def _calc_ctx_switch_rate(self) -> Optional[float]:
        now = time.time()
        current = psutil.cpu_stats()
        delta_t = max(now - self._prev_ctx_ts, 1e-6)
        delta_ctx = current.ctx_switches - self._prev_cpu_stats.ctx_switches
        self._prev_cpu_stats = current
        self._prev_ctx_ts = now
        return delta_ctx / delta_t

    def _calc_io_util_percent(self) -> Optional[float]:
        current = psutil.disk_io_counters()
        previous = self._prev_disk_stats
        self._prev_disk_stats = current
        if not current or not previous:
            return None
        if not hasattr(current, "busy_time") or not hasattr(previous, "busy_time"):
            return None
        busy_delta = current.busy_time - previous.busy_time
        util = busy_delta / max(self.sample_interval * 1000.0, 1.0) * 100.0
        return max(0.0, min(util, 100.0))

    def _detect_l3_cache_mib(self) -> Optional[int]:
        try:
            if platform.system() == "Linux":
                output = subprocess.check_output(["lscpu"], text=True, stderr=subprocess.DEVNULL)
                match = re.search(r"L3 cache:\s*([0-9]+(?:\.[0-9]+)?)\s*([KMG]iB|[KMG]B)?", output, re.IGNORECASE)
                if match:
                    return self._to_mib(float(match.group(1)), match.group(2))
            if platform.system() == "Windows":
                output = subprocess.check_output(
                    ["wmic", "cpu", "get", "L3CacheSize", "/value"], text=True, stderr=subprocess.DEVNULL
                )
                match = re.search(r"L3CacheSize=([0-9]+)", output)
                if match:
                    return int(round(float(match.group(1)) / 1024.0))
        except Exception:
            return None
        return None

    def _to_mib(self, value: float, unit: Optional[str]) -> int:
        unit_upper = (unit or "MiB").upper()
        if unit_upper in {"KB", "KIB"}:
            return int(round(value / 1024.0))
        if unit_upper in {"GB", "GIB"}:
            return int(round(value * 1024.0))
        return int(round(value))
