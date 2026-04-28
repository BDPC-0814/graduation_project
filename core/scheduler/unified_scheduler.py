# core/scheduler/unified_scheduler.py

from typing import Dict, Optional, Tuple

from core.model.base_xpu import XPUDynamicMetrics
from core.scheduler.fault_evolution_scheduler import FaultEvolutionScheduler, RuntimeFeedback


class UnifiedScheduler:
    """
    多设备统一调度器：
    - 每个设备维护独立故障演化调度器
    - 聚合紧急度（max）后给出全局采样间隔（取最紧急设备的间隔）
    """

    def __init__(self, device_ids, t_min=0.5, t_max=8.0, static_limit=80.0):
        self.schedulers = {
            device_id: FaultEvolutionScheduler(t_min=t_min, t_max=t_max)
            for device_id in device_ids
        }
        self.t_max = t_max

    def update(
        self,
        metrics_map: Dict[str, XPUDynamicMetrics],
        runtime_feedback: Optional[RuntimeFeedback] = None,
        slow_cycles_since_last: int = 0,
    ) -> Tuple[float, Dict[str, dict]]:
        details = {}
        intervals = []
        risks = []

        for device_id, metrics in metrics_map.items():
            scheduler = self.schedulers[device_id]
            decision = scheduler.decide(
                metrics,
                runtime_feedback=runtime_feedback,
                slow_cycles_since_last=slow_cycles_since_last,
            )
            details[device_id] = {
                "interval": decision.interval,
                "evolution_score": decision.breakdown.urgency,
                "phase": decision.phase,
                "field_policy": decision.field_policy,
                "transport_policy": decision.transport_policy,
            }
            intervals.append(decision.interval)
            risks.append(decision.breakdown.urgency)

        global_interval = min(intervals) if intervals else self.t_max
        global_risk = max(risks) if risks else 0.0

        return global_interval, {"global_evolution_score": global_risk, "per_device": details}
