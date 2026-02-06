# core/collector/gpu_collector.py

import random
from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics

try:
    import pynvml
    HAS_NVML = True
except ImportError:
    HAS_NVML = False

class GPUCollector(BaseCollector):
    """
    真实GPU采集器 (Windows/Linux 通用增强版)
    针对 Windows 笔记本显卡 (Optimus) 的休眠问题进行了容错处理：
    当显卡休眠导致 NVML 返回 Unknown Error 时，自动判定为 0 负载，而非报错。
    """

    def __init__(self, device_id="gpu0", gpu_index=0):
        self.device_id = device_id
        self.gpu_index = gpu_index
        self.use_real_gpu = False
        self.handle = None

        if HAS_NVML:
            try:
                pynvml.nvmlInit()
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)
                gpu_name = pynvml.nvmlDeviceGetName(self.handle)
                if isinstance(gpu_name, bytes):
                    gpu_name = gpu_name.decode("utf-8")
                    
                print(f"[GPU] Detected NVIDIA GPU: {gpu_name}")
                self.use_real_gpu = True
            except pynvml.NVMLError as e:
                print(f"[GPU] NVML Init failed ({e}). Fallback to simulation.")
        else:
            print("[GPU] 'pynvml' not installed. Fallback to simulation.")

    def collect(self) -> XPUDynamicMetrics:
        if self.use_real_gpu:
            return self._collect_real()
        else:
            return self._collect_simulated()

    def _collect_real(self) -> XPUDynamicMetrics:
        """
        调用 NVML 获取真实指标
        采用“尽力而为”策略：单个指标失败不影响整体，默认返回 0
        """
        # 默认值 (防止部分指标读取失败)
        gpu_util = 0.0
        mem_usage = 0.0
        temp = 0.0
        power = 0.0

        try:
            # 1. 利用率 (最易失败)
            try:
                util_rates = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
                gpu_util = float(util_rates.gpu)
            except pynvml.NVMLError:
                # Windows 笔记本显卡休眠时常报 Unknown Error，视为 0 负载
                gpu_util = 0.0

            # 2. 显存
            try:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
                if mem_info.total > 0:
                    mem_usage = (mem_info.used / mem_info.total) * 100
            except pynvml.NVMLError:
                mem_usage = 0.0

            # 3. 温度
            try:
                temp = pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)
            except pynvml.NVMLError:
                pass # 保持默认 0.0 或上一次的值

            # 4. 功率
            try:
                power_mw = pynvml.nvmlDeviceGetPowerUsage(self.handle)
                power = power_mw / 1000.0
            except pynvml.NVMLError:
                pass # 很多笔记本不支持读取功率，忽略错误

            return XPUDynamicMetrics(
                device_id=self.device_id,
                utilization=gpu_util,
                temperature=float(temp),
                power=float(power),
                memory_usage=float(mem_usage),
                bandwidth=0.0
            )

        except Exception as e:
            # 只有当发生严重错误（如句柄彻底失效）时，才回退到模拟
            # 但对于 Unknown Error，我们已经在内部 try-catch 处理为 0 了，不会走到这里
            # print(f"[GPU] Critical Error: {e}")
            return self._collect_simulated()

    def _collect_simulated(self) -> XPUDynamicMetrics:
        """模拟模式"""
        util = random.uniform(10, 90)
        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=util,
            temperature=random.uniform(40, 80),
            power=random.uniform(50, 200),
            memory_usage=random.uniform(10, 90),
            bandwidth=random.uniform(100, 800)
        )

    def __del__(self):
        if self.use_real_gpu and HAS_NVML:
            try:
                pynvml.nvmlShutdown()
            except:
                pass