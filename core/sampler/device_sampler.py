from dataclasses import asdict, dataclass
from typing import Optional

from core.adapter.base_adapter import BaseAdapter
from core.model.base_xpu import XPUDynamicMetrics
from core.scheduler.havfs import HAVFS


@dataclass
class DeviceSample:
    device_id: str
    metrics: XPUDynamicMetrics
    interval: float
    risk: float
    state: str
    sampled_slow: bool
    risk_anomaly: float = 0.0
    risk_jump: float = 0.0
    risk_pressure: float = 0.0
    risk_drift: float = 0.0


class DeviceSampler:
    """
    Per-device sampler with independent HAVFS state and field-priority logic.
    """

    def __init__(
        self,
        device_id: str,
        adapter: BaseAdapter,
        mode: str = "fixed",
        fixed_interval: float = 2.0,
        t_min: float = 0.5,
        t_max: float = 5.0,
        static_limit: float = 80.0,
    ):
        self.device_id = device_id
        self.adapter = adapter
        self.mode = mode
        self.fixed_interval = fixed_interval
        self.t_min = t_min
        self.t_max = t_max
        self.scheduler = HAVFS(t_min=t_min, t_max=t_max, static_limit=static_limit) if mode == "havfs" else None
        self.tick_count = 0
        self.last_slow_fields: dict = {}

    def sample(self) -> DeviceSample:
        self.tick_count += 1
        fast_metrics = self.adapter.collect_fast()

        if fast_metrics.status != "ok":
            return DeviceSample(
                device_id=self.device_id,
                metrics=fast_metrics,
                interval=self.t_min if self.mode == "havfs" else self.fixed_interval,
                risk=100.0 if self.mode == "havfs" else 0.0,
                state="device unavailable",
                sampled_slow=False,
                risk_anomaly=100.0 if self.mode == "havfs" else 0.0,
            )

        sampled_slow = self._should_sample_slow(fast_metrics)
        if sampled_slow:
            self.last_slow_fields = self.adapter.collect_slow()

        metrics = self._merge_metrics(fast_metrics, self.last_slow_fields)

        if self.mode == "havfs" and self.scheduler is not None:
            interval, risk, state, breakdown = self.scheduler.update(metrics)
        else:
            interval, risk, state = self.fixed_interval, 0.0, "fixed interval"
            breakdown = None

        return DeviceSample(
            device_id=self.device_id,
            metrics=metrics,
            interval=interval,
            risk=risk,
            state=state,
            sampled_slow=sampled_slow,
            risk_anomaly=breakdown.anomaly if breakdown is not None else 0.0,
            risk_jump=breakdown.jump if breakdown is not None else 0.0,
            risk_pressure=breakdown.pressure if breakdown is not None else 0.0,
            risk_drift=breakdown.drift if breakdown is not None else 0.0,
        )

    def _should_sample_slow(self, fast_metrics: XPUDynamicMetrics) -> bool:
        if self.tick_count == 1:
            return True

        if self.mode != "havfs" or self.scheduler is None:
            return self.tick_count % 5 == 0

        current_interval = getattr(self.scheduler, "current_interval", self.t_max)
        if current_interval <= self.t_min + 0.5:
            cadence = 1
        elif current_interval <= (self.t_min + self.t_max) / 2.0:
            cadence = 2
        else:
            cadence = 5

        if fast_metrics.chip_temp_c is not None and fast_metrics.chip_temp_c >= 80:
            cadence = 1
        if fast_metrics.power_w is not None and fast_metrics.power_w > 0 and fast_metrics.utilization >= 85:
            cadence = min(cadence, 2)

        return self.tick_count % cadence == 0

    def _merge_metrics(self, fast_metrics: XPUDynamicMetrics, slow_fields: Optional[dict]) -> XPUDynamicMetrics:
        merged = asdict(fast_metrics)
        merged.update(slow_fields or {})
        return XPUDynamicMetrics(**merged)
