from dataclasses import dataclass
from typing import Optional


@dataclass
class XPUStaticInfo:
    """
    Static metadata shared by CPU, GPU, and NPU devices.
    """

    device_id: str
    device_uid: Optional[str] = None
    device_type: str = "Unknown"
    arch: Optional[str] = None
    vendor: str = "Generic"
    model_name: str = "Unknown"
    driver_version: Optional[str] = None
    firmware_version: Optional[str] = None
    core_count: Optional[int] = None

    @property
    def model(self) -> str:
        return self.model_name


@dataclass
class XPUDynamicMetrics:
    """
    Unified runtime metrics.

    Legacy fields such as `temperature`, `power`, and `memory_usage`
    are preserved for backward compatibility with the existing pipeline.
    """

    utilization: float
    device_id: str = "0"

    # Legacy compatibility fields
    temperature: Optional[float] = None
    power: Optional[float] = None
    memory_usage: Optional[float] = None
    bandwidth: Optional[float] = None

    # XPU common fields
    collect_ts: Optional[int] = None
    sample_interval_s: Optional[float] = None
    chip_temp_c: Optional[float] = None
    board_temp_c: Optional[float] = None
    power_w: Optional[float] = None
    freq_mhz: Optional[float] = None
    freq_cap_mhz: Optional[float] = None
    throttle_flag: Optional[bool] = None
    throttle_cause: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_ts: Optional[int] = None
    duty_cycle_percent: Optional[float] = None

    # Accelerator common fields
    mem_total_mib: Optional[int] = None
    mem_used_mib: Optional[int] = None
    mem_util_percent: Optional[float] = None
    pcie_rx_MBps: Optional[float] = None
    pcie_tx_MBps: Optional[float] = None
    pstate: Optional[str] = None
    power_limit_w: Optional[float] = None
    correctable_err_s: Optional[float] = None
    uncorrectable_err_s: Optional[float] = None
    device_uptime_s: Optional[int] = None
    device_reset_count: Optional[int] = None

    # CPU-specific fields
    threads: Optional[int] = None
    ctx_switch_rate: Optional[float] = None
    l3_cache_mib: Optional[int] = None
    io_util_percent: Optional[float] = None

    # GPU-specific fields
    fan_rpm: Optional[int] = None
    perf_per_watt: Optional[float] = None
    nv_throttle_reasons: Optional[str] = None
    nv_ecc_correctable_total: Optional[int] = None
    nv_ecc_ue_total: Optional[int] = None
    nv_mem_clock_mhz: Optional[float] = None
    nv_graphics_clock_mhz: Optional[float] = None

    status: str = "ok"
    error: Optional[str] = None

    def __post_init__(self):
        if self.chip_temp_c is None and self.temperature is not None:
            self.chip_temp_c = self.temperature
        if self.temperature is None and self.chip_temp_c is not None:
            self.temperature = self.chip_temp_c

        if self.power_w is None and self.power is not None:
            self.power_w = self.power
        if self.power is None and self.power_w is not None:
            self.power = self.power_w

        if self.mem_util_percent is None and self.memory_usage is not None:
            self.mem_util_percent = self.memory_usage
        if self.memory_usage is None and self.mem_util_percent is not None:
            self.memory_usage = self.mem_util_percent

        if self.bandwidth is None and self.pcie_rx_MBps is not None and self.pcie_tx_MBps is not None:
            self.bandwidth = self.pcie_rx_MBps + self.pcie_tx_MBps

        if self.last_error_code is None:
            self.last_error_code = self.error

    def summary(self) -> str:
        return (
            f"util={self.utilization:.1f}%, "
            f"temp={self.chip_temp_c}, "
            f"power={self.power_w}, "
            f"freq={self.freq_mhz}, "
            f"mem={self.mem_util_percent}, "
            f"status={self.status}, "
            f"error={self.error}"
        )
