from abc import ABC, abstractmethod
from core.model.xpu_metrics import XPUDynamicMetrics


class BaseCollector(ABC):

    @abstractmethod
    def collect(self) -> XPUDynamicMetrics:
        """采集一次设备指标"""
        pass
