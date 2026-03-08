# core/collector/npu_collector.py

import re
import shutil
import subprocess
from typing import Optional

from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics


class NPUCollector(BaseCollector):
    """
    NPU采集器（真实采集优先）

    当前支持：
    - Ascend CANN 环境: 调用 `npu-smi info` 解析利用率/温度/功耗/显存
    - 不可用时返回 0 值并打印原因
    """

    def __init__(self, device_id: str = "npu0", card_id: int = 0):
        self.device_id = device_id
        self.card_id = card_id
        self.mode = "unavailable"  # ascend_npu_smi / unavailable
        self.init_error: Optional[str] = None

        self.npu_smi_path = shutil.which("npu-smi")
        if self.npu_smi_path:
            self.mode = "ascend_npu_smi"
            print(f"[NPU] 模式: Ascend npu-smi | 设备: card{self.card_id}")
        else:
            self.init_error = "未找到 npu-smi 命令"
            print(f"[NPU] 模式: 不可用 | 原因: {self.init_error}")

    def collect(self) -> XPUDynamicMetrics:
        if self.mode == "ascend_npu_smi":
            return self._collect_ascend()
        return self._collect_unavailable()

    def _collect_ascend(self) -> XPUDynamicMetrics:
        try:
            output = subprocess.check_output(
                [self.npu_smi_path, "info"], stderr=subprocess.STDOUT, text=True
            )

            row = self._find_card_row(output)
            if row is None:
                return self._collect_unavailable()

            util = self._extract_percent(row, ("AICore", "Util", "AICore(%)"))
            temperature = self._extract_number(row, ("Temp", "Temperature"))
            power = self._extract_number(row, ("Power", "Power(W)"))
            mem_usage = self._extract_memory_percent(row)

            return XPUDynamicMetrics(
                device_id=self.device_id,
                utilization=util if util is not None else 0.0,
                temperature=temperature,
                power=power,
                memory_usage=mem_usage,
                bandwidth=None,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[NPU][Warn] npu-smi采样失败，回退0值: {exc}")
            return self._collect_unavailable()

    def _find_card_row(self, text: str) -> Optional[str]:
        for line in text.splitlines():
            if re.search(rf"\b{self.card_id}\b", line) and ("%" in line or "W" in line):
                return line
        return None

    def _extract_percent(self, line: str, aliases) -> Optional[float]:
        for alias in aliases:
            match = re.search(rf"{re.escape(alias)}[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*%", line, re.IGNORECASE)
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

    def _extract_memory_percent(self, line: str) -> Optional[float]:
        ratio = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*(MiB|MB|GiB|GB)", line, re.IGNORECASE)
        if ratio:
            used = float(ratio.group(1))
            total = float(ratio.group(2))
            if total > 0:
                return used / total * 100.0
        return None

    def _collect_unavailable(self) -> XPUDynamicMetrics:
        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=0.0,
            temperature=None,
            power=None,
            memory_usage=None,
            bandwidth=None,
        )
