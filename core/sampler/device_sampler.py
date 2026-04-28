from dataclasses import asdict, dataclass
from typing import Optional

from core.adapter.base_adapter import BaseAdapter
from core.model.base_xpu import XPUDynamicMetrics
from core.scheduler.fault_evolution_scheduler import FaultEvolutionScheduler, RuntimeFeedback


@dataclass
class DeviceSample:
    device_id: str
    metrics: XPUDynamicMetrics
    interval: float
    evolution_score: float
    phase: str
    field_policy: str
    transport_policy: str
    sampled_slow: bool
    urgency_score: float = 0.0
    field_priority_score: float = 0.0
    execution_pressure_score: float = 0.0
    control_score: float = 0.0

    @property
    def risk(self) -> float:
        return self.evolution_score

    @property
    def state(self) -> str:
        return self.phase


class DeviceSampler:
    """
    Per-device sampler with layered field collection and fault-evolution control.
    """

    def __init__(
        self,
        device_id: str,
        adapter: BaseAdapter,
        mode: str = "fixed",
        fixed_interval: float = 2.0,
        t_min: float = 1.0,
        t_max: float = 6.0,
        static_limit: float = 80.0,
    ):
        self.device_id = device_id
        self.adapter = adapter
        normalized_mode = (mode or "fixed").lower()
        if normalized_mode in {"adaptive", "evolution"}:
            normalized_mode = "evolution"
        self.mode = normalized_mode
        self.fixed_interval = fixed_interval
        self.t_min = t_min
        self.t_max = t_max
        self.static_info = self.adapter.get_static_info()
        self.scheduler = (
            FaultEvolutionScheduler(t_min=t_min, t_max=t_max)
            if self.mode == "evolution"
            else None
        )
        self.tick_count = 0
        self.last_slow_fields: dict = {}
        self.slow_cycles_since_last = 0
        self.runtime_feedback = RuntimeFeedback()

    def set_runtime_feedback(self, feedback: Optional[RuntimeFeedback]):
        self.runtime_feedback = feedback or RuntimeFeedback()

    def sample(self) -> DeviceSample:
        self.tick_count += 1
        fast_metrics = self.adapter.collect_fast()

        if fast_metrics.status != "ok":
            if self.mode == "evolution" and self.scheduler is not None:
                decision = self.scheduler.unavailable_decision(runtime_feedback=self.runtime_feedback)
                return DeviceSample(
                    device_id=self.device_id,
                    metrics=fast_metrics,
                    interval=decision.interval,
                    evolution_score=decision.breakdown.urgency,
                    phase="设备失联",
                    field_policy=decision.field_policy,
                    transport_policy=decision.transport_policy,
                    sampled_slow=False,
                    urgency_score=decision.breakdown.urgency,
                    field_priority_score=decision.breakdown.field_priority,
                    execution_pressure_score=decision.breakdown.execution_pressure,
                    control_score=decision.breakdown.control_score,
                )
            return DeviceSample(
                device_id=self.device_id,
                metrics=fast_metrics,
                interval=self.fixed_interval,
                evolution_score=0.0,
                phase="设备失联",
                field_policy="快线必采",
                transport_policy="本地缓存",
                sampled_slow=False,
                urgency_score=0.0,
                field_priority_score=0.0,
                execution_pressure_score=0.0,
                control_score=0.0,
            )

        decision = None
        if self.mode == "evolution" and self.scheduler is not None:
            decision = self.scheduler.decide(
                fast_metrics,
                runtime_feedback=self.runtime_feedback,
                slow_cycles_since_last=self.slow_cycles_since_last,
                device_profile={
                    "device_id": self.static_info.device_id,
                    "device_type": self.static_info.device_type,
                    "vendor": self.static_info.vendor,
                    "model_name": self.static_info.model_name,
                },
            )
            sampled_slow = decision.sample_slow
        else:
            sampled_slow = self._should_sample_slow()

        if sampled_slow:
            self.last_slow_fields = self.adapter.collect_slow()
            self.slow_cycles_since_last = 0
        else:
            self.slow_cycles_since_last += 1

        metrics = self._merge_metrics(fast_metrics, self.last_slow_fields)

        if decision is not None:
            interval = decision.interval
            evolution_score = decision.breakdown.urgency
            phase = decision.phase
            field_policy = decision.field_policy
            transport_policy = decision.transport_policy
            breakdown = decision.breakdown
        else:
            interval = self.fixed_interval
            evolution_score = 0.0
            phase = "固定频率"
            field_policy = "周期补采" if sampled_slow else "快线必采"
            transport_policy = "本地缓存"
            breakdown = None

        return DeviceSample(
            device_id=self.device_id,
            metrics=metrics,
            interval=interval,
            evolution_score=evolution_score,
            phase=phase,
            field_policy=field_policy,
            transport_policy=transport_policy,
            sampled_slow=sampled_slow,
            urgency_score=breakdown.urgency if breakdown is not None else 0.0,
            field_priority_score=breakdown.field_priority if breakdown is not None else 0.0,
            execution_pressure_score=breakdown.execution_pressure if breakdown is not None else 0.0,
            control_score=breakdown.control_score if breakdown is not None else 0.0,
        )

    def _should_sample_slow(self) -> bool:
        if self.tick_count == 1:
            return True

        return self.tick_count % 5 == 0

    def _merge_metrics(self, fast_metrics: XPUDynamicMetrics, slow_fields: Optional[dict]) -> XPUDynamicMetrics:
        merged = asdict(fast_metrics)
        merged.update(slow_fields or {})
        return XPUDynamicMetrics(**merged)
