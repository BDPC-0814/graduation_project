from dataclasses import dataclass
from typing import Optional

from core.model.base_xpu import XPUDynamicMetrics


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _scale(value: Optional[float], lower: float, upper: float) -> float:
    if value is None:
        return 0.0
    if upper <= lower:
        return 0.0
    if value <= lower:
        return 0.0
    if value >= upper:
        return 1.0
    return (value - lower) / (upper - lower)


def _ema(previous: Optional[float], current: Optional[float], alpha: float) -> Optional[float]:
    if current is None:
        return previous
    if previous is None:
        return float(current)
    return float(previous + alpha * (float(current) - previous))


@dataclass
class RuntimeFeedback:
    pending: int = 0
    dead: int = 0
    ring_backlog: int = 0
    ring_capacity: int = 1
    uploader_active: bool = False


@dataclass
class ControlBreakdown:
    urgency: float = 0.0
    field_priority: float = 0.0
    execution_pressure: float = 0.0
    control_score: float = 0.0


@dataclass
class SamplingDecision:
    interval: float
    phase: str
    field_policy: str
    transport_policy: str
    sample_slow: bool
    breakdown: ControlBreakdown


class FaultEvolutionScheduler:
    """
    Phase-driven adaptive sampler for fault-evolution monitoring.

    The controller is intentionally not a closed-loop "risk -> frequency" mapper.
    It tracks three control quantities:
    - urgency: fault-evolution tension on the device itself
    - field_priority: whether slow fields should be refreshed this round
    - execution_pressure: pressure introduced by the edge execution and upload path
    """

    PHASE_LABELS = {
        "FOCUS": "聚焦采样",
        "RECOVERY": "恢复观测",
        "CRUISE": "巡航巡检",
        "DEGRADED": "边端降级",
    }

    FIELD_POLICY_LABELS = {
        "full-focus": "全量聚焦",
        "layered-sync": "分层补采",
        "event-probe": "事件补采",
        "cruise-refresh": "巡检补采",
        "fast-only": "快线必采",
        "guarded-fast": "降级保活",
    }

    TRANSPORT_POLICY_LABELS = {
        "direct-upload": "直传",
        "buffered-upload": "缓冲上传",
        "degraded-buffer": "降级缓冲",
        "local-buffer": "本地缓存",
    }

    def __init__(
        self,
        t_min: float = 1.0,
        t_max: float = 6.0,
        slow_refresh_cycles: int = 6,
        focus_hold_cycles: int = 1,
        recovery_hold_cycles: int = 1,
        thermal_limit_c: float = 85.0,
        baseline_alpha: float = 0.12,
    ):
        self.t_min = t_min
        self.t_max = t_max
        self.slow_refresh_cycles = max(1, slow_refresh_cycles)
        self.focus_hold_cycles = max(0, focus_hold_cycles)
        self.recovery_hold_cycles = max(0, recovery_hold_cycles)
        self.thermal_limit_c = thermal_limit_c
        self.baseline_alpha = max(0.01, min(baseline_alpha, 0.5))

        self.current_interval = t_max
        self.last_utilization: Optional[float] = None
        self.last_temperature: Optional[float] = None
        self.last_power: Optional[float] = None
        self.utilization_baseline: Optional[float] = None
        self.temperature_baseline: Optional[float] = None
        self.power_baseline: Optional[float] = None
        self.focus_hold_remaining = 0
        self.recovery_hold_remaining = 0
        self.last_breakdown = ControlBreakdown()

    def decide(
        self,
        metrics: XPUDynamicMetrics,
        runtime_feedback: Optional[RuntimeFeedback] = None,
        slow_cycles_since_last: int = 0,
        device_profile: Optional[dict] = None,
    ) -> SamplingDecision:
        feedback = runtime_feedback or RuntimeFeedback()
        breakdown = self._compute_breakdown(metrics, feedback, slow_cycles_since_last, device_profile=device_profile)
        phase_code = self._select_phase(metrics, breakdown)
        field_policy_code, sample_slow = self._select_field_policy(
            phase_code=phase_code,
            breakdown=breakdown,
            slow_cycles_since_last=slow_cycles_since_last,
        )
        transport_policy_code = self._select_transport_policy(feedback, breakdown)
        interval = self._select_interval(
            phase_code=phase_code,
            breakdown=breakdown,
            sample_slow=sample_slow,
        )

        self.current_interval = interval
        self.last_breakdown = breakdown
        self.last_utilization = metrics.utilization
        self.last_temperature = metrics.chip_temp_c
        self.last_power = metrics.power_w
        self._update_baselines(metrics, phase_code)

        return SamplingDecision(
            interval=interval,
            phase=self.PHASE_LABELS[phase_code],
            field_policy=self.FIELD_POLICY_LABELS[field_policy_code],
            transport_policy=self.TRANSPORT_POLICY_LABELS[transport_policy_code],
            sample_slow=sample_slow,
            breakdown=breakdown,
        )

    def unavailable_decision(self, runtime_feedback: Optional[RuntimeFeedback] = None) -> SamplingDecision:
        feedback = runtime_feedback or RuntimeFeedback()
        breakdown = ControlBreakdown(
            urgency=100.0,
            field_priority=0.0,
            execution_pressure=self._compute_execution_pressure(feedback),
            control_score=100.0,
        )
        self.last_breakdown = breakdown
        self.current_interval = self.t_min
        return SamplingDecision(
            interval=self.t_min,
            phase=self.PHASE_LABELS["FOCUS"],
            field_policy=self.FIELD_POLICY_LABELS["fast-only"],
            transport_policy=self.TRANSPORT_POLICY_LABELS[self._select_transport_policy(feedback, breakdown)],
            sample_slow=False,
            breakdown=breakdown,
        )

    def _compute_breakdown(
        self,
        metrics: XPUDynamicMetrics,
        feedback: RuntimeFeedback,
        slow_cycles_since_last: int,
        device_profile: Optional[dict] = None,
    ) -> ControlBreakdown:
        delta_util = 0.0 if self.last_utilization is None else abs(metrics.utilization - self.last_utilization)
        delta_temp = (
            0.0
            if self.last_temperature is None or metrics.chip_temp_c is None
            else abs(metrics.chip_temp_c - self.last_temperature)
        )
        delta_power = 0.0 if self.last_power is None or metrics.power_w is None else abs(metrics.power_w - self.last_power)

        util_rise = 0.0
        if self.utilization_baseline is not None:
            util_rise = max(metrics.utilization - self.utilization_baseline, 0.0)

        temp_rise = 0.0
        if self.temperature_baseline is not None and metrics.chip_temp_c is not None:
            temp_rise = max(metrics.chip_temp_c - self.temperature_baseline, 0.0)

        power_rise = 0.0
        if self.power_baseline is not None and metrics.power_w is not None:
            power_rise = max(metrics.power_w - self.power_baseline, 0.0)

        profile = device_profile or {}
        device_type = str(profile.get("device_type", "")).upper()
        vendor = str(profile.get("vendor", "")).lower()
        model_name = str(profile.get("model_name", "")).lower()
        is_intel_gpu = device_type == "GPU" and ("intel" in vendor or "intel" in model_name)

        if is_intel_gpu:
            util_component = _scale(metrics.utilization, 38.0, 92.0) * 14.0
            rise_component = _scale(util_rise, 12.0, 28.0) * 14.0
            jump_component = _scale(delta_util, 14.0, 30.0) * 18.0
        else:
            util_component = _scale(metrics.utilization, 28.0, 88.0) * 16.0
            rise_component = _scale(util_rise, 5.0, 20.0) * 16.0
            jump_component = _scale(delta_util, 6.0, 22.0) * 20.0
        temp_component = _scale(metrics.chip_temp_c, 55.0, self.thermal_limit_c) * 12.0
        temp_rise_component = _scale(temp_rise, 1.0, 8.0) * 6.0
        mem_component = _scale(metrics.mem_util_percent, 55.0, 95.0) * 6.0

        power_component = 0.0
        if metrics.power_limit_w is not None and metrics.power_limit_w > 0 and metrics.power_w is not None:
            power_component = _scale(metrics.power_w / metrics.power_limit_w, 0.45, 0.92) * 10.0
        elif metrics.power_w is not None:
            power_component = _scale(metrics.power_w, 35.0, 220.0) * 6.0

        throttle_bonus = 18.0 if metrics.throttle_flag else 0.0
        abnormal = metrics.status != "ok" or bool(metrics.error) or bool(metrics.last_error_code)
        error_bonus = 24.0 if abnormal else 0.0

        urgency = _clamp(
            util_component
            + rise_component
            + jump_component
            + temp_component
            + temp_rise_component
            + mem_component
            + power_component
            + throttle_bonus
            + error_bonus
        )

        staleness_component = _scale(float(slow_cycles_since_last), 0.0, float(self.slow_refresh_cycles + 2)) * 10.0
        volatility_source = max(delta_util, delta_temp * 2.0, delta_power / 4.0)
        volatility_component = _scale(volatility_source, 2.0, 16.0) * 24.0
        drift_component = _scale(util_rise, 1.0, 14.0) * 18.0
        thermal_refresh_component = _scale(temp_rise, 0.5, 6.0) * 10.0
        power_refresh_component = _scale(power_rise, 2.0, 30.0) * 8.0
        field_flag_bonus = 16.0 if metrics.throttle_flag or abnormal else 0.0

        field_priority = _clamp(
            staleness_component
            + volatility_component
            + drift_component
            + thermal_refresh_component
            + power_refresh_component
            + field_flag_bonus
        )

        execution_pressure = self._compute_execution_pressure(feedback)
        control_score = _clamp((urgency * 0.52) + (field_priority * 0.36) - (execution_pressure * 0.30))

        return ControlBreakdown(
            urgency=round(urgency, 4),
            field_priority=round(field_priority, 4),
            execution_pressure=round(execution_pressure, 4),
            control_score=round(control_score, 4),
        )

    def _compute_execution_pressure(self, feedback: RuntimeFeedback) -> float:
        pending_component = _scale(float(feedback.pending), 40.0, 300.0) * 28.0
        dead_component = _scale(float(feedback.dead), 0.0, 10.0) * 35.0
        ring_ratio = 0.0
        if feedback.ring_capacity > 0:
            ring_ratio = min(max(feedback.ring_backlog / float(feedback.ring_capacity), 0.0), 1.0)
        ring_component = ring_ratio * 25.0
        offline_penalty = 10.0 if not feedback.uploader_active and (feedback.pending > 0 or feedback.ring_backlog > 0) else 0.0
        return _clamp(pending_component + dead_component + ring_component + offline_penalty)

    def _select_phase(self, metrics: XPUDynamicMetrics, breakdown: ControlBreakdown) -> str:
        abnormal = metrics.status != "ok" or bool(metrics.error) or bool(metrics.last_error_code)
        focus_trigger = (
            abnormal
            or breakdown.urgency >= 58.0
            or breakdown.control_score >= 50.0
            or (breakdown.urgency >= 44.0 and breakdown.field_priority >= 52.0)
        )
        degraded_trigger = breakdown.execution_pressure >= 78.0 and breakdown.urgency < 58.0
        recovery_trigger = (
            breakdown.urgency >= 30.0
            or breakdown.field_priority >= 40.0
            or breakdown.control_score >= 28.0
        )

        if focus_trigger:
            self.focus_hold_remaining = self.focus_hold_cycles
            self.recovery_hold_remaining = self.recovery_hold_cycles
            return "FOCUS"
        if self.focus_hold_remaining > 0:
            self.focus_hold_remaining -= 1
            self.recovery_hold_remaining = max(self.recovery_hold_remaining, self.recovery_hold_cycles)
            return "FOCUS"
        if degraded_trigger:
            return "DEGRADED"
        if recovery_trigger:
            self.recovery_hold_remaining = max(self.recovery_hold_remaining, self.recovery_hold_cycles)
            return "RECOVERY"
        if self.recovery_hold_remaining > 0:
            self.recovery_hold_remaining -= 1
            return "RECOVERY"
        return "CRUISE"

    def _select_field_policy(
        self,
        phase_code: str,
        breakdown: ControlBreakdown,
        slow_cycles_since_last: int,
    ) -> tuple[str, bool]:
        if phase_code == "FOCUS":
            if breakdown.execution_pressure >= 88.0 and breakdown.urgency < 85.0:
                return "guarded-fast", False
            return "full-focus", True
        if phase_code == "DEGRADED":
            if breakdown.urgency >= 70.0 and breakdown.execution_pressure < 92.0:
                return "event-probe", True
            return "guarded-fast", False
        if phase_code == "RECOVERY":
            if breakdown.field_priority >= 50.0 or slow_cycles_since_last >= self.slow_refresh_cycles + 1:
                return "layered-sync", True
            if breakdown.urgency >= 38.0:
                return "event-probe", True
            return "fast-only", False
        if breakdown.field_priority >= 46.0:
            return "event-probe", True
        if slow_cycles_since_last >= self.slow_refresh_cycles and breakdown.execution_pressure < 72.0:
            return "cruise-refresh", True
        return "fast-only", False

    def _select_transport_policy(self, feedback: RuntimeFeedback, breakdown: ControlBreakdown) -> str:
        if breakdown.execution_pressure >= 80.0:
            return "degraded-buffer"
        if feedback.ring_backlog >= 8:
            return "buffered-upload"
        if feedback.ring_backlog > 0 and feedback.pending > 16:
            return "buffered-upload"
        if feedback.pending > 30:
            return "buffered-upload"
        if feedback.uploader_active:
            return "direct-upload"
        return "local-buffer"

    def _select_interval(self, phase_code: str, breakdown: ControlBreakdown, sample_slow: bool) -> float:
        if phase_code == "FOCUS":
            if breakdown.execution_pressure >= 85.0 and breakdown.urgency < 78.0:
                return round(min(self.t_max, max(self.t_min, 0.8)), 4)
            return round(self.t_min, 4)

        if phase_code == "RECOVERY":
            if breakdown.control_score >= 55.0 or breakdown.field_priority >= 65.0:
                return round(min(self.t_max, max(self.t_min, 1.5)), 4)
            if sample_slow:
                return round(min(self.t_max, max(self.t_min * 2.0, 2.5)), 4)
            if breakdown.urgency >= 35.0:
                return round(min(self.t_max, 3.0), 4)
            return round(min(self.t_max, 4.0), 4)

        if phase_code == "DEGRADED":
            if breakdown.urgency >= 62.0:
                return round(min(self.t_max, 2.5), 4)
            return round(min(self.t_max, max(4.0, self.t_max * 0.78)), 4)

        if breakdown.execution_pressure >= 60.0:
            return round(min(self.t_max, max(5.5, self.t_max * 0.85)), 4)
        if breakdown.field_priority >= 42.0 or breakdown.urgency >= 28.0:
            return round(min(self.t_max, 4.0), 4)
        if sample_slow or breakdown.field_priority >= 24.0:
            return round(min(self.t_max, 5.5), 4)
        if breakdown.urgency <= 10.0 and breakdown.field_priority <= 16.0:
            return round(self.t_max, 4)
        return round(min(self.t_max, max(6.0, self.t_max - 1.0)), 4)

    def _update_baselines(self, metrics: XPUDynamicMetrics, phase_code: str) -> None:
        alpha = self.baseline_alpha * (0.55 if phase_code in {"FOCUS", "RECOVERY"} else 1.0)
        self.utilization_baseline = _ema(self.utilization_baseline, metrics.utilization, alpha)
        self.temperature_baseline = _ema(self.temperature_baseline, metrics.chip_temp_c, alpha)
        self.power_baseline = _ema(self.power_baseline, metrics.power_w, alpha)
