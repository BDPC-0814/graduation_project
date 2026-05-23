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
        if normalized_mode in {"threshold", "threshold_trigger"}:
            normalized_mode = "threshold"
        if normalized_mode in {"trend", "trend_aware"}:
            normalized_mode = "trend"
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
        self.last_fast_metrics: Optional[XPUDynamicMetrics] = None

    def set_runtime_feedback(self, feedback: Optional[RuntimeFeedback]):
        self.runtime_feedback = feedback or RuntimeFeedback()

    def sample(self) -> DeviceSample:
        self.tick_count += 1
        fast_metrics = self.adapter.collect_fast()

        if fast_metrics.status != "ok":
            if self.mode == "evolution" and self.scheduler is not None:
                decision = self.scheduler.unavailable_decision(runtime_feedback=self.runtime_feedback)
                self.last_fast_metrics = fast_metrics
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
            if self.mode in {"threshold", "trend"}:
                self.last_fast_metrics = fast_metrics
                return DeviceSample(
                    device_id=self.device_id,
                    metrics=fast_metrics,
                    interval=self.t_min,
                    evolution_score=100.0,
                    phase="设备失联",
                    field_policy="快线必采",
                    transport_policy="本地缓存",
                    sampled_slow=False,
                    urgency_score=100.0,
                    field_priority_score=0.0,
                    execution_pressure_score=0.0,
                    control_score=100.0,
                )
            self.last_fast_metrics = fast_metrics
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
        baseline_decision = None
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
        elif self.mode == "threshold":
            baseline_decision = self._threshold_decision(fast_metrics)
            sampled_slow = baseline_decision["sampled_slow"]
        elif self.mode == "trend":
            baseline_decision = self._trend_decision(fast_metrics)
            sampled_slow = baseline_decision["sampled_slow"]
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
        elif baseline_decision is not None:
            interval = baseline_decision["interval"]
            evolution_score = baseline_decision["score"]
            phase = baseline_decision["phase"]
            field_policy = baseline_decision["field_policy"]
            transport_policy = "本地缓存"
            breakdown = None
        else:
            interval = self.fixed_interval
            evolution_score = 0.0
            phase = "固定频率"
            field_policy = "周期补采" if sampled_slow else "快线必采"
            transport_policy = "本地缓存"
            breakdown = None

        self.last_fast_metrics = fast_metrics
        return DeviceSample(
            device_id=self.device_id,
            metrics=metrics,
            interval=interval,
            evolution_score=evolution_score,
            phase=phase,
            field_policy=field_policy,
            transport_policy=transport_policy,
            sampled_slow=sampled_slow,
            urgency_score=breakdown.urgency if breakdown is not None else evolution_score,
            field_priority_score=breakdown.field_priority if breakdown is not None else 0.0,
            execution_pressure_score=breakdown.execution_pressure if breakdown is not None else 0.0,
            control_score=breakdown.control_score if breakdown is not None else evolution_score,
        )

    def _should_sample_slow(self) -> bool:
        if self.tick_count == 1:
            return True

        return self.tick_count % 5 == 0

    @staticmethod
    def _scale(value: Optional[float], lower: float, upper: float) -> float:
        if value is None or upper <= lower:
            return 0.0
        if value <= lower:
            return 0.0
        if value >= upper:
            return 1.0
        return (float(value) - lower) / (upper - lower)

    def _threshold_decision(self, metrics: XPUDynamicMetrics) -> dict:
        abnormal = metrics.status != "ok" or bool(metrics.error) or bool(metrics.last_error_code)
        score = min(
            100.0,
            self._scale(metrics.utilization, 60.0, 90.0) * 42.0
            + self._scale(metrics.mem_util_percent, 70.0, 95.0) * 22.0
            + self._scale(metrics.chip_temp_c, 70.0, 90.0) * 18.0
            + (28.0 if metrics.throttle_flag else 0.0)
            + (35.0 if abnormal else 0.0),
        )
        return self._baseline_decision_from_score(
            score=score,
            high_phase="阈值触发-高频",
            mid_phase="阈值触发-中频",
            low_phase="阈值触发-低频",
            high_policy="阈值全量补采",
            mid_policy="阈值事件补采",
            low_policy="快线必采",
        )

    def _trend_decision(self, metrics: XPUDynamicMetrics) -> dict:
        previous = self.last_fast_metrics
        if previous is None:
            score = 0.0
        else:
            delta_util = abs(metrics.utilization - previous.utilization)
            delta_temp = (
                0.0
                if metrics.chip_temp_c is None or previous.chip_temp_c is None
                else abs(metrics.chip_temp_c - previous.chip_temp_c)
            )
            delta_mem = (
                0.0
                if metrics.mem_util_percent is None or previous.mem_util_percent is None
                else abs(metrics.mem_util_percent - previous.mem_util_percent)
            )
            score = min(
                100.0,
                self._scale(delta_util, 5.0, 22.0) * 48.0
                + self._scale(delta_temp, 1.0, 6.0) * 18.0
                + self._scale(delta_mem, 3.0, 15.0) * 18.0
                + self._scale(metrics.utilization, 72.0, 95.0) * 16.0
                + (25.0 if metrics.throttle_flag else 0.0)
                + (30.0 if metrics.status != "ok" or bool(metrics.error) or bool(metrics.last_error_code) else 0.0),
            )
        return self._baseline_decision_from_score(
            score=score,
            high_phase="趋势感知-高频",
            mid_phase="趋势感知-中频",
            low_phase="趋势感知-低频",
            high_policy="趋势全量补采",
            mid_policy="趋势事件补采",
            low_policy="快线必采",
        )

    def _baseline_decision_from_score(
        self,
        *,
        score: float,
        high_phase: str,
        mid_phase: str,
        low_phase: str,
        high_policy: str,
        mid_policy: str,
        low_policy: str,
    ) -> dict:
        if score >= 58.0:
            return {
                "interval": self.t_min,
                "score": round(score, 4),
                "phase": high_phase,
                "field_policy": high_policy,
                "sampled_slow": True,
            }
        if score >= 30.0:
            return {
                "interval": min(self.t_max, max(self.t_min, (self.t_min + self.t_max) / 2.0)),
                "score": round(score, 4),
                "phase": mid_phase,
                "field_policy": mid_policy,
                "sampled_slow": self.slow_cycles_since_last >= 2,
            }
        return {
            "interval": self.t_max,
            "score": round(score, 4),
            "phase": low_phase,
            "field_policy": low_policy,
            "sampled_slow": self._should_sample_slow(),
        }

    def _merge_metrics(self, fast_metrics: XPUDynamicMetrics, slow_fields: Optional[dict]) -> XPUDynamicMetrics:
        merged = asdict(fast_metrics)
        merged.update(slow_fields or {})
        return XPUDynamicMetrics(**merged)
