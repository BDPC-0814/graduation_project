# core/collector/gpu_collector.py

import random
from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics


class GPUCollector(BaseCollector):
    """
    GPU 指标采集器（模拟实现）

    阶段2说明：
    - 在无真实GPU环境下，使用模拟数据验证框架扩展性
    - 后续可替换为 nvidia-smi / DCGM
    """

    def __init__(self, device_id="gpu0"):
        self.device_id = device_id

    def collect(self) -> XPUDynamicMetrics:
        utilization = random.uniform(0, 100)
        temperature = random.uniform(40, 85)
        power = random.uniform(50, 200)
        memory_usage = random.uniform(0, 100)
        bandwidth = random.uniform(20, 90)

        return XPUDynamicMetrics(
            utilization=utilization,
            temperature=temperature,
            power=power,
            memory_usage=memory_usage,
            bandwidth=bandwidth,
            device_id=self.device_id
        )
