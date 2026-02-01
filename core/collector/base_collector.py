# core/collector/base_collector.py

from abc import ABC, abstractmethod
from core.model.base_xpu import XPUDynamicMetrics


class BaseCollector(ABC):
    """
    统一采集接口（论文接口标准化方法）
    所有 CPU/GPU/NPU Collector 必须实现 collect()
    """

    @abstractmethod
    def collect(self) -> XPUDynamicMetrics:
        """
        采集一次设备动态指标
        """
        pass
