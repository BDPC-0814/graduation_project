# core/reporter/console_reporter.py

from core.reporter.base_reporter import BaseReporter
from core.model.base_xpu import XPUDynamicMetrics


class ConsoleReporter(BaseReporter):
    """
    控制台上报器（实验阶段使用）

    论文阶段说明：
    - 用于验证采集→调度→上报链路完整性
    """

    def send(self, metrics: XPUDynamicMetrics):
        print(f"[REPORT] {metrics.device_id}: {metrics.summary()}")
