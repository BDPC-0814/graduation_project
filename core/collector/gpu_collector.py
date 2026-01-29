import random
from core.collector.base_collector import BaseCollector
from core.model.xpu_metrics import XPUDynamicMetrics


class GPUCollector(BaseCollector):
    """
    GPU占位实现：无真实GPU时模拟指标波动
    """

    def __init__(self, device_id="gpu0"):
        self.device_id = device_id

    def collect(self):

        util = random.uniform(10, 90)

        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=util,
            temperature=random.uniform(40, 80),
            power=random.uniform(50, 200),
            memory_usage=random.uniform(10, 90),
            bandwidth=random.uniform(100, 800)
        )
