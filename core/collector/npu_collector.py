from core.adapter.npu.npu_adapter import NPUAdapter
from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics


class NPUCollector(BaseCollector):
    """
    Backward-compatible wrapper around NPUAdapter.
    """

    def __init__(self, device_id: str = "npu0", card_id: int = 0):
        self.adapter = NPUAdapter(device_id=device_id, card_id=card_id)

    def collect(self) -> XPUDynamicMetrics:
        return self.adapter.collect_full()
