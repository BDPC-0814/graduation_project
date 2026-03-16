from core.adapter.cpu.cpu_adapter import CPUAdapter
from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics


class CPUCollector(BaseCollector):
    """
    Backward-compatible wrapper around CPUAdapter.
    """

    def __init__(self, device_id: str = "cpu0", sample_interval: float = 0.1):
        self.adapter = CPUAdapter(device_id=device_id, sample_interval=sample_interval)

    def collect(self) -> XPUDynamicMetrics:
        return self.adapter.collect_full()
