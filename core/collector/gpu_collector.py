from core.adapter.gpu.gpu_adapter import GPUAdapter
from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics


class GPUCollector(BaseCollector):
    """
    Backward-compatible wrapper around GPUAdapter.
    """

    def __init__(self, device_id: str = "gpu0", vendor: str = "auto"):
        self.adapter = GPUAdapter(device_id=device_id, vendor=vendor)

    def collect(self) -> XPUDynamicMetrics:
        return self.adapter.collect_full()
