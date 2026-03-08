# core/collector/cpu_collector.py

import random

import psutil

from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics


class CPUCollector(BaseCollector):
    """
    CPU 指标采集器（真实采集）
    数据来源：psutil
    """

    def __init__(self, device_id="cpu0", sample_interval=0.1):
        self.device_id = device_id
        # 关键修复：使用短采样窗口，避免 interval=None + 新线程首次调用长期返回0
        self.sample_interval = sample_interval

    def collect(self) -> XPUDynamicMetrics:
        # CPU利用率（真实）
        utilization = psutil.cpu_percent(interval=self.sample_interval)

        # 温度（部分机器支持）
        temperature = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                first_key = list(temps.keys())[0]
                temperature = temps[first_key][0].current
        except Exception:
            temperature = None

        # 功耗（CPU一般无法直接获取，论文阶段可模拟）
        power = 30 + utilization * 0.5

        # 内存占用（系统内存）
        memory_usage = psutil.virtual_memory().percent

        # 带宽（阶段2可用随机模拟）
        bandwidth = random.uniform(10, 60)

        return XPUDynamicMetrics(
            utilization=utilization,
            temperature=temperature,
            power=power,
            memory_usage=memory_usage,
            bandwidth=bandwidth,
            device_id=self.device_id,
        )
