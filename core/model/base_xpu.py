# core/model/base_xpu.py

from dataclasses import dataclass
from typing import Optional


# ==========================================================
# XPU Static Info（静态属性维度）
# ==========================================================

@dataclass
class XPUStaticInfo:
    """
    静态信息：描述设备的基本配置（论文属性维度）
    """
    device_id: str
    device_type: str   # CPU / GPU / NPU
    vendor: str = "Generic"
    model: str = "Unknown"


# ==========================================================
# XPU Dynamic Metrics（动态运行指标维度）
# ==========================================================

@dataclass
class XPUDynamicMetrics:
    """
    动态指标：描述设备运行状态的时序变化（论文动态指标）
    通用字段：所有XPU共享
    """

    # 通用字段（核心指标）
    utilization: float                  # 利用率 (%)
    temperature: Optional[float] = None # 温度 (°C)
    power: Optional[float] = None       # 功耗 (W)
    memory_usage: Optional[float] = None# 显存/内存占用 (%)
    bandwidth: Optional[float] = None   # 带宽利用率 (%)

    # 设备标识
    device_id: str = "0"

    def summary(self) -> str:
        """
        用于调试输出
        """
        return (
            f"util={self.utilization:.1f}%, "
            f"temp={self.temperature}, "
            f"power={self.power}, "
            f"mem={self.memory_usage}, "
            f"bw={self.bandwidth}"
        )
