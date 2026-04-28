from __future__ import annotations

import re
import shutil
import subprocess
from typing import Optional

from core.adapter.npu.backends.base_backend import NPUBackend
from core.model.base_xpu import XPUStaticInfo


class AscendNPUSmiBackend(NPUBackend):
    """
    Huawei Ascend backend backed by `npu-smi info`.
    """

    backend_name = "ascend_npu_smi"

    def __init__(self, device_id: str = "npu0", card_id: int = 0):
        super().__init__(device_id=device_id, card_id=card_id)
        self.npu_smi_path = shutil.which("npu-smi")
        self._static_info = XPUStaticInfo(
            device_id=device_id,
            device_uid=device_id,
            device_type="NPU",
            vendor="Huawei",
            model_name=f"Ascend card{card_id}",
        )
        if not self.npu_smi_path:
            self.init_error = "npu-smi command not found"

    @classmethod
    def detect(cls) -> bool:
        return shutil.which("npu-smi") is not None

    def get_static_info(self) -> XPUStaticInfo:
        return self._static_info

    def collect_fast_snapshot(self) -> Optional[dict[str, object]]:
        if not self.npu_smi_path:
            self.init_error = "npu-smi command not found"
            return None
        try:
            output = subprocess.check_output(
                [self.npu_smi_path, "info"],
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception as exc:  # noqa: BLE001
            self.init_error = f"npu-smi sample failed: {exc}"
            return None

        row = self._find_card_row(output)
        if row is None:
            self.init_error = "npu-smi output parse failed"
            return None

        util = self._extract_percent(row, ("AICore", "Util", "AICore(%)"))
        chip_temp_c = self._extract_number(row, ("Temp", "Temperature"))
        power_w = self._extract_number(row, ("Power", "Power(W)"))
        mem_used_mib, mem_total_mib = self._extract_memory_usage(row)
        mem_util_percent = None
        if mem_used_mib is not None and mem_total_mib:
            mem_util_percent = mem_used_mib / mem_total_mib * 100.0

        return {
            "utilization": util if util is not None else 0.0,
            "chip_temp_c": chip_temp_c,
            "power_w": power_w,
            "mem_used_mib": mem_used_mib,
            "mem_total_mib": mem_total_mib,
            "mem_util_percent": mem_util_percent,
        }

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
            match = re.search(
                rf"{re.escape(alias)}[^0-9]*([0-9]+(?:\.[0-9]+)?)",
                line,
                re.IGNORECASE,
            )
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
