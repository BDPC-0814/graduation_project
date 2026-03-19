from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Any, Dict

from core.model.base_xpu import XPUStaticInfo, XPUDynamicMetrics


class BaseAdapter(ABC):
    """
    Device adapter abstraction.
    """

    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type

    @abstractmethod
    def get_static_info(self) -> XPUStaticInfo:
        """
        Return static metadata for the device.
        """

    @abstractmethod
    def collect_fast(self) -> XPUDynamicMetrics:
        """
        Collect high-priority metrics such as utilization, temperature, and power.
        """

    @abstractmethod
    def collect_slow(self) -> Dict[str, Any]:
        """
        Collect lower-priority extended fields.
        """

    def collect_full(self) -> XPUDynamicMetrics:
        fast_metrics = self.collect_fast()
        if fast_metrics.status != "ok":
            return fast_metrics

        merged = asdict(fast_metrics)
        merged.update(self.collect_slow())
        return XPUDynamicMetrics(**merged)
