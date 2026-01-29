# core/collector/cpu_collector.py

# import psutil
# from core.collector.base_collector import BaseCollector


# class CPUCollector(BaseCollector):
#     def collect(self) -> float:
#         # interval=None 表示“自上次调用以来的 CPU 利用率”
#         return psutil.cpu_percent(interval=0.1)


import psutil
from core.collector.base_collector import BaseCollector
from core.model.xpu_metrics import XPUDynamicMetrics


class CPUCollector(BaseCollector):

    def __init__(self, device_id="cpu0"):
        self.device_id = device_id

    def collect(self) -> XPUDynamicMetrics:
        util = psutil.cpu_percent(interval=0.2)

        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=util,
            temperature=50.0,      # 可扩展：lm-sensors
            power=30.0,            # 占位
            memory_usage=psutil.virtual_memory().percent,
            bandwidth=0.0
        )
