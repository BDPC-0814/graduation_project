import re
import shutil
import subprocess
import time
from collections import deque
from typing import Optional

from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics


class NPUCollector(BaseCollector):
    """
    NPU collector with Ascend `npu-smi` support.
    """

    def __init__(self, device_id: str = "npu0", card_id: int = 0, duty_window_size: int = 10):
        self.device_id = device_id
        self.card_id = card_id
        self.mode = "unavailable"
        self.init_error: Optional[str] = None
        self.npu_smi_path = shutil.which("npu-smi")
        self.collect_started_at = time.time()
        self._duty_window = deque(maxlen=duty_window_size)

        if self.npu_smi_path:
            self.mode = "ascend_npu_smi"
            print(f"[NPU] mode=ascend_npu_smi device=card{self.card_id}")
        else:
            self.init_error = "npu-smi command not found"
            print(f"[NPU] mode=unavailable reason={self.init_error}")

    def collect(self) -> XPUDynamicMetrics:
        if self.mode == "ascend_npu_smi":
            return self._collect_ascend()
        return self._collect_unavailable(self.init_error or "npu collector unavailable")

    def _collect_ascend(self) -> XPUDynamicMetrics:
        try:
            output = subprocess.check_output(
                [self.npu_smi_path, "info"], stderr=subprocess.STDOUT, text=True
            )

            row = self._find_card_row(output)
            if row is None:
                return self._collect_unavailable("npu-smi output parse failed")

            util = self._extract_percent(row, ("AICore", "Util", "AICore(%)"))
            chip_temp_c = self._extract_number(row, ("Temp", "Temperature"))
            power_w = self._extract_number(row, ("Power", "Power(W)"))
            mem_used_mib, mem_total_mib = self._extract_memory_usage(row)
            mem_util_percent = None
            if mem_used_mib is not None and mem_total_mib:
                mem_util_percent = mem_used_mib / mem_total_mib * 100.0

            util_value = util if util is not None else 0.0
            self._duty_window.append(util_value)

            return XPUDynamicMetrics(
                device_id=self.device_id,
                utilization=util_value,
                temperature=chip_temp_c,
                power=power_w,
                memory_usage=mem_util_percent,
                collect_ts=int(time.time()),
                chip_temp_c=chip_temp_c,
                power_w=power_w,
                duty_cycle_percent=sum(self._duty_window) / len(self._duty_window),
                mem_total_mib=mem_total_mib,
                mem_used_mib=mem_used_mib,
                mem_util_percent=mem_util_percent,
                device_uptime_s=int(time.time() - self.collect_started_at),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[NPU][Warn] npu-smi sample failed: {exc}")
            return self._collect_unavailable(f"npu-smi sample failed: {exc}")

    def _find_card_row(self, text: str) -> Optional[str]:
        for line in text.splitlines():
            if re.search(rf"\b{self.card_id}\b", line) and ("%" in line or "W" in line):
                return line
        return None

    def _extract_percent(self, line: str, aliases) -> Optional[float]:
        for alias in aliases:
            match = re.search(
                rf"{re.escape(alias)}[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*%",
                line,
                re.IGNORECASE,
            )
            if match:
                return float(match.group(1))
        generic = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", line)
        if generic:
            return float(generic.group(1))
        return None

    def _extract_number(self, line: str, aliases) -> Optional[float]:
        for alias in aliases:
            match = re.search(rf"{re.escape(alias)}[^0-9]*([0-9]+(?:\.[0-9]+)?)", line, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def _extract_memory_usage(self, line: str) -> tuple[Optional[int], Optional[int]]:
        ratio = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*(MiB|MB|GiB|GB)",
            line,
            re.IGNORECASE,
        )
        if not ratio:
            return None, None

        used = self._to_mib(float(ratio.group(1)), ratio.group(3))
        total = self._to_mib(float(ratio.group(2)), ratio.group(3))
        return used, total

    def _to_mib(self, value: float, unit: str) -> int:
        if unit.lower() in {"gib", "gb"}:
            return int(round(value * 1024.0))
        return int(round(value))

    def _collect_unavailable(self, reason: str) -> XPUDynamicMetrics:
        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=0.0,
            collect_ts=int(time.time()),
            status="unavailable",
            error=reason,
            last_error_code=reason,
            last_error_ts=int(time.time()),
        )
