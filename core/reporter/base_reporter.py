# core/reporter/base_reporter.py

from abc import ABC, abstractmethod
from core.model.base_xpu import XPUDynamicMetrics


class BaseReporter(ABC):
    """
    Reporter 上报模块抽象接口

    功能：
    - 将采集到的指标发送到外部系统
    - 支持 Prometheus / HTTP Push / TSDB 写入扩展
    """

    @abstractmethod
    def send(self, metrics: XPUDynamicMetrics):
        """
        上报一次指标数据
        """
        pass
