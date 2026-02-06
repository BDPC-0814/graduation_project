import random
import time
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
        self._last_init_ts = 0.0

        self._init_nvml()

    def _init_nvml(self):
        """初始化 NVML 并获取 GPU 句柄"""
        if not HAS_NVML:
            print("[GPU] 'nvidia-ml-py' not installed. Fallback to simulation.")
            return

        try:
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)
            gpu_name = pynvml.nvmlDeviceGetName(self.handle)
            if isinstance(gpu_name, bytes):
                gpu_name = gpu_name.decode("utf-8")
            print(f"[GPU] Detected NVIDIA GPU: {gpu_name}")
            self.use_real_gpu = True
            self._last_init_ts = time.time()
        except pynvml.NVMLError as e:
            print(f"[GPU] NVML Init failed ({self._format_nvml_error(e)}). Fallback to simulation.")
            self.use_real_gpu = False
            self.handle = None

    def collect(self) -> XPUDynamicMetrics:
        """根据环境决定调用真实采集还是模拟采集"""
        if self.use_real_gpu:
            return self._collect_real()
        else:
            return self._collect_simulated()

    def _collect_real(self) -> XPUDynamicMetrics:
        """调用 NVML 获取真实指标"""
        try:
            util_rates = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            gpu_util = float(util_rates.gpu)

            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
            mem_usage_percent = (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0.0

            temp = pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)

            power_w = 0.0
            try:
                power_mw = pynvml.nvmlDeviceGetPowerUsage(self.handle)
                power_w = power_mw / 1000.0
            except pynvml.NVMLError:
                power_w = 0.0

            return XPUDynamicMetrics(
                device_id=self.device_id,
                utilization=gpu_util,
                temperature=float(temp),
                power=float(power_w),
                memory_usage=float(mem_usage_percent),
                bandwidth=0.0
            )
        except pynvml.NVMLError as e:
            print(f"[GPU] Error collecting data: {self._format_nvml_error(e)}")
            self._attempt_reinit()
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

    def _attempt_reinit(self):
        """尝试重新初始化 NVML，避免偶发状态异常"""
        now = time.time()
        if now - self._last_init_ts < 5.0:
            return
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
        self.use_real_gpu = False
        self.handle = None
        self._init_nvml()

    @staticmethod
    def _format_nvml_error(error: Exception) -> str:
        """格式化 NVML 错误信息"""
        try:
            code = error.value
            return f"{pynvml.nvmlErrorString(code).decode('utf-8')}"
        except Exception:
            return str(error)

    def __del__(self):
        """析构时关闭 NVML"""
        if self.use_real_gpu and HAS_NVML:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
