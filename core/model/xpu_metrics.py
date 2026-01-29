from dataclasses import dataclass


@dataclass
class XPUDynamicMetrics:
    """
    统一动态指标字段体系（论文版）
    """

    device_id: str

    # 通用字段（CPU/GPU/NPU共享）
    utilization: float          # %
    temperature: float = 0.0    # °C
    power: float = 0.0          # W
    memory_usage: float = 0.0   # %
    bandwidth: float = 0.0      # MB/s
