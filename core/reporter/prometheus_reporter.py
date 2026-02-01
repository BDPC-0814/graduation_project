# core/reporter/prometheus_reporter.py

from core.reporter.base_reporter import BaseReporter
from core.model.base_xpu import XPUDynamicMetrics


class PrometheusReporter(BaseReporter):
    """
    Prometheus Exporter Stub（阶段2占位）

    后续阶段可扩展：
    - 启动 HTTP /metrics 服务
    - 输出 Prometheus 格式指标
    """

    def __init__(self, port=8000):
        self.port = port
        print(f"[PrometheusReporter] Stub initialized on port {port}")

    def send(self, metrics: XPUDynamicMetrics):
        # 阶段2：占位实现
        print(
            f"[PrometheusReporter Stub] would export utilization={metrics.utilization}"
        )
