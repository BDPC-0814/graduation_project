from core.collector.base_collector import BaseCollector


class NPUCollector(BaseCollector):
    """
    NPU接口占位：后续可接 Ascend/TPU API
    """

    def collect(self):
        raise NotImplementedError("NPUCollector not implemented yet")
