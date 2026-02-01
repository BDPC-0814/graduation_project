# core/collector/npu_collector.py

from core.collector.base_collector import BaseCollector
from core.model.base_xpu import XPUDynamicMetrics


class NPUCollector(BaseCollector):
    """
    NPU采集器（接口占位）

    论文阶段说明：
    - 支持未来昇腾/寒武纪等NPU设备扩展
    """

    def __init__(self, device_id="npu0"):
        self.device_id = device_id

    def collect(self) -> XPUDynamicMetrics:
        raise NotImplementedError(
            "NPUCollector is a stub for future hardware support."
        )
