# core/collector/gpu_collector.py

import random
import subprocess
import platform
import re
from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics

try:
    import pynvml
    HAS_NVML = True
except ImportError:
    HAS_NVML = False

class GPUCollector(BaseCollector):
    """
    全能 GPU 采集器
    - NVIDIA模式: 使用 pynvml (速度快，精度高)
    - Intel/AMD模式: 使用 Windows 性能计数器 (通用，但有 0.5s~1s 延迟)
    """

    def __init__(self, device_id="gpu0", vendor="auto"):
        self.device_id = device_id
        self.vendor = vendor # auto, nvidia, intel
        self.mode = "simulation" # simulation, nvidia_native, windows_generic
        self.handle = None
        self.gpu_name = "Unknown GPU"

        # 1. 自动检测逻辑
        if self.vendor == "auto" or self.vendor == "nvidia":
            if HAS_NVML:
                try:
                    pynvml.nvmlInit()
                    self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    name = pynvml.nvmlDeviceGetName(self.handle)
                    if isinstance(name, bytes): name = name.decode("utf-8")
                    
                    self.gpu_name = name
                    self.mode = "nvidia_native"
                    print(f"[GPU] 模式: NVIDIA原生 | 设备: {self.gpu_name}")
                    return
                except:
                    pass
        
        # 2. 如果指定了 Intel 或 自动检测 NVIDIA 失败，尝试 Windows 通用模式
        if (self.vendor == "auto" or self.vendor == "intel") and platform.system() == "Windows":
            detected_name = self._detect_windows_gpu_name("Intel")
            if detected_name:
                self.gpu_name = detected_name
                self.mode = "windows_generic"
                print(f"[GPU] 模式: Windows通用 | 设备: {self.gpu_name}")
                print(f"[Warn] 注意: Intel 核显采集依赖 PowerShell，可能会有 0.5s 左右的系统延迟")
                return

        # 3. 兜底
        print(f"[GPU] 模式: 模拟仿真 (未检测到驱动或指定设备)")
        self.mode = "simulation"

    def _detect_windows_gpu_name(self, target_keyword):
        """通过 WMIC 查找包含关键字(如 Intel)的显卡名称"""
        try:
            # 获取所有显卡名称
            cmd = "wmic path Win32_VideoController get Name"
            res = subprocess.check_output(cmd, shell=True).decode().split('\n')
            for line in res:
                line = line.strip()
                if line and "Name" not in line:
                    # 如果关键字匹配 (或者用户没指定，默认取第一个非NVIDIA)
                    if target_keyword.lower() in line.lower():
                        return line
            return None
        except:
            return None

    def collect(self) -> XPUDynamicMetrics:
        if self.mode == "nvidia_native":
            return self._collect_nvidia()
        elif self.mode == "windows_generic":
            return self._collect_windows_generic()
        else:
            return self._collect_simulated()

    def _collect_windows_generic(self) -> XPUDynamicMetrics:
        """
        Windows 通用采集: 调用 PowerShell 读取 3D 引擎负载
        """
        util = 0.0
        try:
            # PowerShell 命令: 获取所有 3D 引擎的利用率并取最大值
            # 这种方式不依赖语言(engtype_3D 是内部ID)
            ps_cmd = "(Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage').CounterSamples | Measure-Object -Property CookedValue -Maximum | Select-Object -ExpandProperty Maximum"
            
            # 运行命令 (注意: 这会阻塞进程约 0.5s-1s)
            output = subprocess.check_output(
                ["powershell", "-Command", ps_cmd], 
                creationflags=subprocess.CREATE_NO_WINDOW # 防止弹出黑框
            )
            util = float(output.decode().strip())
        except Exception:
            util = 0.0

        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=util,
            temperature=0.0, # 核显很难直接读温度
            power=0.0,
            memory_usage=0.0,
            bandwidth=0.0
        )

    def _collect_nvidia(self) -> XPUDynamicMetrics:
        # ... (保留原有的 NVIDIA 采集逻辑) ...
        try:
            util_rates = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            gpu_util = float(util_rates.gpu)
            
            try:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
                mem_usage = (mem_info.used / mem_info.total) * 100
            except: mem_usage = 0.0
            
            try:
                temp = pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)
            except: temp = 0.0
            
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(self.handle) / 1000.0
            except: power = 0.0

            return XPUDynamicMetrics(
                device_id=self.device_id,
                utilization=gpu_util,
                temperature=float(temp),
                power=float(power),
                memory_usage=mem_usage,
                bandwidth=0.0
            )
        except:
            return self._collect_simulated()

    def _collect_simulated(self) -> XPUDynamicMetrics:
        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=random.uniform(10, 90),
            temperature=0.0, power=0.0, memory_usage=0.0, bandwidth=0.0
        )

    def __del__(self):
        if self.mode == "nvidia_native" and HAS_NVML:
            try: pynvml.nvmlShutdown()
            except: pass