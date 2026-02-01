# core/reporter/prometheus_reporter.py
from prometheus_client import start_http_server, Gauge
from core.reporter.base_reporter import BaseReporter
from core.model.base_xpu import XPUDynamicMetrics

class PrometheusReporter(BaseReporter):
    """
    Prometheus Exporter 实现
    功能：
    - 启动 HTTP Server (默认端口 8000)
    - 将 XPUDynamicMetrics 映射为 Prometheus Gauge 指标
    """

    def __init__(self, port=8000):
        self.port = port
        print(f"[Prometheus] Starting exporter on port {port}...")
        
        # 启动后台 HTTP 服务，供 Prometheus Server 拉取
        # 注意：在多进程环境下需小心，但在毕设单脚本实验中没问题
        try:
            start_http_server(port)
        except OSError:
            print(f"[Warn] Port {port} is busy. Metrics might not be exposed.")

        # --- 定义指标 (Gauge) ---
        # 标签 (Labels): device_id, device_type
        labels = ['device_id']
        
        self.g_util = Gauge('xpu_utilization_percent', 'Device Utilization', labels)
        self.g_temp = Gauge('xpu_temperature_celsius', 'Device Temperature', labels)
        self.g_power = Gauge('xpu_power_watts', 'Device Power Consumption', labels)
        self.g_mem  = Gauge('xpu_memory_usage_percent', 'Memory Usage', labels)
        self.g_risk = Gauge('xpu_risk_score', 'Calculated Risk Score', labels)
        self.g_int  = Gauge('xpu_sampling_interval_seconds', 'Current Sampling Interval', labels)

    def send(self, metrics: XPUDynamicMetrics, risk: float = 0.0, interval: float = 1.0):
        """
        更新指标数值
        注意：send 方法签名增加了 risk 和 interval 参数，以便上报调度状态
        """
        # 提取标签值
        lbl = [metrics.device_id]

        # 更新 Gauges
        self.g_util.labels(*lbl).set(metrics.utilization)
        
        if metrics.temperature is not None:
            self.g_temp.labels(*lbl).set(metrics.temperature)
            
        if metrics.power is not None:
            self.g_power.labels(*lbl).set(metrics.power)
            
        if metrics.memory_usage is not None:
            self.g_mem.labels(*lbl).set(metrics.memory_usage)

        # 上报算法状态（这对可视化非常有价值）
        self.g_risk.labels(*lbl).set(risk)
        self.g_int.labels(*lbl).set(interval)