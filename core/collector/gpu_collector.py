import random
import logging
from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics

# 尝试导入 pynvml，如果环境不支持则标记为不可用
try:
    import pynvml
    HAS_NVML = True
except ImportError:
    HAS_NVML = False

class GPUCollector(BaseCollector):
    """
    真实GPU采集器 (兼容模拟模式)
    自动检测环境：如果有 NVIDIA 驱动则采集真实数据，否则回退到模拟数据。
    """

    def __init__(self, device_id="gpu0", gpu_index=0):
        self.device_id = device_id
        self.gpu_index = gpu_index
        self.use_real_gpu = False
        self.handle = None

        if HAS_NVML:
            try:
                pynvml.nvmlInit()
                # 获取指定索引的GPU句柄
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)
                gpu_name = pynvml.nvmlDeviceGetName(self.handle)
                # 兼容不同版本的 pynvml 返回 bytes 或 str 的情况
                if isinstance(gpu_name, bytes):
                    gpu_name = gpu_name.decode("utf-8")
                    
                print(f"[GPU] Detected NVIDIA GPU: {gpu_name}")
                self.use_real_gpu = True
            except pynvml.NVMLError as e:
                print(f"[GPU] NVML Init failed ({e}). Fallback to simulation.")
        else:
            print("[GPU] 'nvidia-ml-py' not installed. Fallback to simulation.")

    def collect(self) -> XPUDynamicMetrics:
        """根据环境决定调用真实采集还是模拟采集"""
        if self.use_real_gpu:
            return self._collect_real()
        else:
            return self._collect_simulated()

    def _collect_real(self) -> XPUDynamicMetrics:
        """调用 NVML 获取真实指标"""
        try:
            # 1. 利用率 (GPU & Memory)
            # nvmlDeviceGetUtilizationRates 返回的是百分比整数
            util_rates = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            gpu_util = float(util_rates.gpu)
            
            # 2. 显存使用
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
            if mem_info.total > 0:
                mem_usage_percent = (mem_info.used / mem_info.total) * 100
            else:
                mem_usage_percent = 0.0

            # 3. 温度
            temp = pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)

            # 4. 功率 (mW -> W)
            try:
                power_mw = pynvml.nvmlDeviceGetPowerUsage(self.handle)
                power_w = power_mw / 1000.0
            except pynvml.NVMLError:
                # 部分消费级显卡(如GeForce笔记本版)可能不支持读取功率
                power_w = 0.0 

            return XPUDynamicMetrics(
                device_id=self.device_id,
                utilization=gpu_util,
                temperature=float(temp),
                power=float(power_w),
                memory_usage=float(mem_usage_percent),
                bandwidth=0.0 # 带宽通常需要更底层的计数器，暂置0
            )
        except pynvml.NVMLError as e:
            print(f"[GPU] Error collecting data: {e}")
            # 采集失败时临时回退到模拟数据，防止程序崩溃
            return self._collect_simulated()

    def _collect_simulated(self) -> XPUDynamicMetrics:
        """原有模拟逻辑：生成随机波动数据"""
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
        """析构时关闭 NVML"""
        if self.use_real_gpu and HAS_NVML:
            try:
                pynvml.nvmlShutdown()
            except:
                pass