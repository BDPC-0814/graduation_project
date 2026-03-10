# core/collector/gpu_collector.py

import platform
import subprocess
from typing import Optional

from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics

try:
    import pynvml

    HAS_NVML = True
except ImportError:
    HAS_NVML = False


class GPUCollector(BaseCollector):
    """
    GPU 采集器
    - NVIDIA: NVML 实时采集
    - Intel(Windows): 性能计数器采集
    - 其他: 保底返回 0（不再返回随机值，避免误导）
    """

    def __init__(self, device_id: str = "gpu0", vendor: str = "auto"):
        self.device_id = device_id
        self.vendor = vendor
        self.mode = "unsupported"  # nvidia_native / windows_generic / unsupported
        self.handle = None
        self.gpu_name = "Unknown GPU"
        self.init_error: Optional[str] = None

        if self.vendor in ("auto", "nvidia"):
            self._init_nvidia()
            if self.mode == "nvidia_native":
                return

        if self.vendor in ("auto", "intel") and platform.system() == "Windows":
            detected_name = self._detect_windows_gpu_name("Intel")
            if detected_name:
                self.gpu_name = detected_name
                self.mode = "windows_generic"
                print(f"[GPU] 模式: Windows通用 | 设备: {self.gpu_name}")
                print("[Warn] Intel 核显采集依赖 PowerShell，可能存在 0.5s 左右系统延迟")
                return

        print(f"[GPU] 模式: 不可用 | 原因: {self.init_error or '未检测到可用GPU采集链路'}")

    def _init_nvidia(self):
        if not HAS_NVML:
            self.init_error = "未安装 pynvml/nvidia-ml-py"
            return
        try:
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(self.handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            self.gpu_name = name
            self.mode = "nvidia_native"
            print(f"[GPU] 模式: NVIDIA原生(NVML) | 设备: {self.gpu_name}")
        except Exception as exc:  # noqa: BLE001
            self.init_error = f"NVML初始化失败: {exc}"
            self.mode = "unsupported"

    def _detect_windows_gpu_name(self, target_keyword: str):
        try:
            cmd = "wmic path Win32_VideoController get Name"
            res = subprocess.check_output(cmd, shell=True).decode(errors="ignore").split("\n")
            for line in res:
                line = line.strip()
                if line and "Name" not in line and target_keyword.lower() in line.lower():
                    return line
            return None
        except Exception:  # noqa: BLE001
            return None

    def collect(self) -> XPUDynamicMetrics:
        if self.mode == "nvidia_native":
            return self._collect_nvidia()
        if self.mode == "windows_generic":
            return self._collect_windows_generic()
        return self._collect_unavailable(self.init_error or "gpu collector unavailable")

    def _collect_windows_generic(self) -> XPUDynamicMetrics:
        util = 0.0
        try:
            ps_cmd = (
                "(Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage').CounterSamples "
                "| Measure-Object -Property CookedValue -Maximum | Select-Object -ExpandProperty Maximum"
            )
            output = subprocess.check_output(["powershell", "-Command", ps_cmd])
            raw = output.decode().strip()
            util = float(raw) if raw else 0.0
        except Exception:
            util = 0.0

        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=max(util, 0.0),
            temperature=None,
            power=None,
            memory_usage=None,
            bandwidth=None,
        )

    def _collect_nvidia(self) -> XPUDynamicMetrics:
        try:
            util_rates = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            gpu_util = float(util_rates.gpu)

            mem_usage = None
            temp = None
            power = None

            try:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
                mem_usage = (mem_info.used / mem_info.total) * 100 if mem_info.total else 0.0
            except Exception:
                pass

            try:
                temp = float(
                    pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)
                )
            except Exception:
                pass

            try:
                power = float(pynvml.nvmlDeviceGetPowerUsage(self.handle) / 1000.0)
            except Exception:
                pass

            return XPUDynamicMetrics(
                device_id=self.device_id,
                utilization=max(gpu_util, 0.0),
                temperature=temp,
                power=power,
                memory_usage=mem_usage,
                bandwidth=None,
            )
        except Exception as exc:  # noqa: BLE001
            # 关键修复：NVML 单次采样失败时返回0并保留设备信息，不再回退“随机模拟值”
            print(f"[GPU][Warn] NVML采样失败，回退0值: {exc}")
            return self._collect_unavailable(f"nvml sample failed: {exc}")

    def _collect_unavailable(self, reason: str) -> XPUDynamicMetrics:
        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=0.0,
            temperature=None,
            power=None,
            memory_usage=None,
            bandwidth=None,
            status="unavailable",
            error=reason,
        )

    def __del__(self):
        if self.mode == "nvidia_native" and HAS_NVML:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
