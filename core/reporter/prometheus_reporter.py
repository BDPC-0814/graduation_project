from prometheus_client import Gauge, start_http_server

from core.model.base_xpu import XPUDynamicMetrics
from core.reporter.base_reporter import BaseReporter


class PrometheusReporter(BaseReporter):
    """
    Prometheus exporter for core XPU metrics.
    """

    def __init__(self, port: int = 8000):
        self.port = port
        print(f"[Prometheus] starting exporter on port {port}")
        try:
            start_http_server(port)
        except OSError:
            print(f"[Warn] port {port} is busy; metrics may not be exposed")

        labels = ["device_id"]
        self.g_util = Gauge("xpu_utilization_percent", "Device utilization", labels)
        self.g_temp = Gauge("xpu_chip_temperature_celsius", "Chip temperature", labels)
        self.g_power = Gauge("xpu_power_watts", "Power consumption", labels)
        self.g_mem = Gauge("xpu_memory_usage_percent", "Memory usage percent", labels)
        self.g_freq = Gauge("xpu_frequency_mhz", "Current frequency", labels)
        self.g_freq_cap = Gauge("xpu_frequency_cap_mhz", "Frequency cap", labels)
        self.g_pcie_rx = Gauge("xpu_pcie_rx_megabytes_per_second", "PCIe RX throughput", labels)
        self.g_pcie_tx = Gauge("xpu_pcie_tx_megabytes_per_second", "PCIe TX throughput", labels)
        self.g_duty = Gauge("xpu_duty_cycle_percent", "Sliding window utilization", labels)
        self.g_threads = Gauge("xpu_threads", "Active threads", labels)
        self.g_io_util = Gauge("xpu_io_util_percent", "IO utilization", labels)
        self.g_status = Gauge("xpu_status_ok", "1 if collector status is ok else 0", labels)
        self.g_evolution = Gauge("xpu_evolution_score", "Fault-evolution urgency score", labels)
        self.g_field_priority = Gauge("xpu_field_priority_score", "Layered field priority score", labels)
        self.g_execution_pressure = Gauge("xpu_execution_pressure_score", "Edge execution pressure score", labels)
        self.g_int = Gauge("xpu_sampling_interval_seconds", "Current scheduling interval", labels)

    def send(
        self,
        metrics: XPUDynamicMetrics,
        evolution_score: float = 0.0,
        field_priority_score: float = 0.0,
        execution_pressure_score: float = 0.0,
        interval: float = 1.0,
    ):
        lbl = [metrics.device_id]

        self.g_util.labels(*lbl).set(metrics.utilization)
        self.g_status.labels(*lbl).set(1 if metrics.status == "ok" else 0)
        self.g_evolution.labels(*lbl).set(evolution_score)
        self.g_field_priority.labels(*lbl).set(field_priority_score)
        self.g_execution_pressure.labels(*lbl).set(execution_pressure_score)
        self.g_int.labels(*lbl).set(interval)

        if metrics.chip_temp_c is not None:
            self.g_temp.labels(*lbl).set(metrics.chip_temp_c)
        if metrics.power_w is not None:
            self.g_power.labels(*lbl).set(metrics.power_w)
        if metrics.mem_util_percent is not None:
            self.g_mem.labels(*lbl).set(metrics.mem_util_percent)
        if metrics.freq_mhz is not None:
            self.g_freq.labels(*lbl).set(metrics.freq_mhz)
        if metrics.freq_cap_mhz is not None:
            self.g_freq_cap.labels(*lbl).set(metrics.freq_cap_mhz)
        if metrics.pcie_rx_MBps is not None:
            self.g_pcie_rx.labels(*lbl).set(metrics.pcie_rx_MBps)
        if metrics.pcie_tx_MBps is not None:
            self.g_pcie_tx.labels(*lbl).set(metrics.pcie_tx_MBps)
        if metrics.duty_cycle_percent is not None:
            self.g_duty.labels(*lbl).set(metrics.duty_cycle_percent)
        if metrics.threads is not None:
            self.g_threads.labels(*lbl).set(metrics.threads)
        if metrics.io_util_percent is not None:
            self.g_io_util.labels(*lbl).set(metrics.io_util_percent)
