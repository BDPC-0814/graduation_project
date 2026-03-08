# core/scheduler/unified_scheduler.py

from typing import Dict, Tuple

from core.model.base_xpu import XPUDynamicMetrics
from core.scheduler.havfs import HAVFS


class UnifiedScheduler:
    """
    多设备统一调度器：
    - 每个设备维护独立 HAVFS
    - 聚合风险（max）后给出全局采样间隔（取最紧急设备的间隔）
    """

    def __init__(self, device_ids, t_min=0.5, t_max=5.0, static_limit=80.0):
        self.schedulers = {
            device_id: HAVFS(t_min=t_min, t_max=t_max, static_limit=static_limit)
            for device_id in device_ids
        }
        self.t_max = t_max

    def update(self, metrics_map: Dict[str, XPUDynamicMetrics]) -> Tuple[float, Dict[str, dict]]:
        details = {}
        intervals = []
        risks = []

        for device_id, metrics in metrics_map.items():
            scheduler = self.schedulers[device_id]
            interval, risk, state = scheduler.update(metrics)
            details[device_id] = {
                "interval": interval,
                "risk": risk,
                "state": state,
            }
            intervals.append(interval)
            risks.append(risk)

        global_interval = min(intervals) if intervals else self.t_max
        global_risk = max(risks) if risks else 0.0

        return global_interval, {"global_risk": global_risk, "per_device": details}
