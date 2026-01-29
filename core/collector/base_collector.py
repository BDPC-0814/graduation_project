# from abc import ABC, abstractmethod
# from core.model.base_xpu import XPUDynamicMetric


# class BaseCollector(ABC):
#     """
#     Unified collector interface for heterogeneous XPU devices.
#     """

#     def __init__(self, device):
#         self.device = device

#     @abstractmethod
#     def collect(self) -> XPUDynamicMetric:
#         """
#         Collect dynamic metrics from the device.

#         Returns:
#             XPUDynamicMetric
#         """
#         pass


# # core/collector/base_collector.py

# from abc import ABC, abstractmethod


# class BaseCollector(ABC):
#     @abstractmethod
#     def collect(self) -> float:
#         """
#         返回一个核心负载指标（如 CPU 利用率）
#         """
#         pass


from abc import ABC, abstractmethod
from core.model.xpu_metrics import XPUDynamicMetrics


class BaseCollector(ABC):

    @abstractmethod
    def collect(self) -> XPUDynamicMetrics:
        """采集一次设备指标"""
        pass
