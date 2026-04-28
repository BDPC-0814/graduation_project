import time
from collections import deque
from typing import Optional

from core.adapter.base_adapter import BaseAdapter
from core.adapter.npu.backends import (
    AscendNPUSmiBackend,
    NPUBackend,
    OpenHarmonyHDCBackend,
    RockchipSysfsBackend,
)
from core.model.base_xpu import XPUStaticInfo, XPUDynamicMetrics


class NPUAdapter(BaseAdapter):
    """
    NPU adapter with pluggable backend support.

    Backends hide vendor-specific collection details while preserving the
    unified adapter contract used by the rest of the sampling pipeline.
    """

    _BACKENDS = {
        "ascend": AscendNPUSmiBackend,
        "ascend_npu_smi": AscendNPUSmiBackend,
        "openharmony_hdc": OpenHarmonyHDCBackend,
        "rockchip_sysfs": RockchipSysfsBackend,
    }
    _AUTO_ORDER = [
        AscendNPUSmiBackend,
        OpenHarmonyHDCBackend,
        RockchipSysfsBackend,
    ]

    def __init__(
        self,
        device_id: str = "npu0",
        card_id: int = 0,
        duty_window_size: int = 10,
        backend: str = "auto",
    ):
        super().__init__(device_id=device_id, device_type="NPU")
        self.card_id = card_id
        self.backend = backend
        self.mode = "unavailable"
        self.init_error: Optional[str] = None
        self.collect_started_at = time.time()
        self._duty_window = deque(maxlen=duty_window_size)
        self._last_fast_snapshot: Optional[dict] = None
        self._backend = self._build_backend(backend)
        self._static_info = self._backend.get_static_info() if self._backend else self._default_static_info()

        if self._backend:
            self.mode = self._backend.backend_name
            self.init_error = self._backend.init_error
            print(f"[NPU] mode={self.mode} device={self._static_info.model_name}")
        else:
            self.init_error = "no supported NPU backend detected"
            print(f"[NPU] mode=unavailable reason={self.init_error}")

    def get_static_info(self) -> XPUStaticInfo:
        return self._static_info

    def collect_fast(self) -> XPUDynamicMetrics:
        if self._backend is None:
            return self._collect_unavailable(self.init_error or "npu adapter unavailable")

        snapshot = self._backend.collect_fast_snapshot()
        if snapshot is None:
            self.init_error = self._backend.init_error or self.init_error or "npu adapter unavailable"
            return self._collect_unavailable(self.init_error)

        self._last_fast_snapshot = snapshot
        util_value = self._safe_float(snapshot.get("utilization"), default=0.0)
        self._duty_window.append(util_value)

        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=util_value,
            temperature=self._safe_float(snapshot.get("chip_temp_c")),
            power=self._safe_float(snapshot.get("power_w")),
            memory_usage=self._safe_float(snapshot.get("mem_util_percent")),
            collect_ts=int(time.time()),
            chip_temp_c=self._safe_float(snapshot.get("chip_temp_c")),
            board_temp_c=self._safe_float(snapshot.get("board_temp_c")),
            power_w=self._safe_float(snapshot.get("power_w")),
            duty_cycle_percent=sum(self._duty_window) / len(self._duty_window),
            mem_total_mib=self._safe_int(snapshot.get("mem_total_mib")),
            mem_used_mib=self._safe_int(snapshot.get("mem_used_mib")),
            mem_util_percent=self._safe_float(snapshot.get("mem_util_percent")),
            freq_mhz=self._safe_float(snapshot.get("freq_mhz")),
            freq_cap_mhz=self._safe_float(snapshot.get("freq_cap_mhz")),
            pstate=self._safe_str(snapshot.get("pstate")),
            status=self._safe_str(snapshot.get("status"), default="ok"),
            error=self._safe_str(snapshot.get("error")),
        )

    def collect_slow(self) -> dict:
        if self._backend is None:
            return {}
        snapshot = self._backend.collect_slow_snapshot(latest_fast_snapshot=self._last_fast_snapshot) or {}
        snapshot.setdefault("device_uptime_s", int(time.time() - self.collect_started_at))
        return snapshot

    def _build_backend(self, requested_backend: str) -> Optional[NPUBackend]:
        normalized = (requested_backend or "auto").strip().lower()
        if normalized == "auto":
            for backend_cls in self._AUTO_ORDER:
                if backend_cls.detect():
                    return backend_cls(device_id=self.device_id, card_id=self.card_id)
            return None

        backend_cls = self._BACKENDS.get(normalized)
        if backend_cls is None:
            raise ValueError(
                f"unsupported NPU backend '{requested_backend}', "
                f"supported={sorted(['auto', *self._BACKENDS.keys()])}"
            )
        return backend_cls(device_id=self.device_id, card_id=self.card_id)

    def _default_static_info(self) -> XPUStaticInfo:
        return XPUStaticInfo(
            device_id=self.device_id,
            device_uid=self.device_id,
            device_type="NPU",
            vendor="Generic",
            model_name="Unknown NPU",
        )

    def _safe_float(self, value, default: Optional[float] = None) -> Optional[float]:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _safe_str(self, value, default: Optional[str] = None) -> Optional[str]:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    def _collect_unavailable(self, reason: str) -> XPUDynamicMetrics:
        now = int(time.time())
        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=0.0,
            collect_ts=now,
            status="unavailable",
            error=reason,
            last_error_code=reason,
            last_error_ts=now,
        )
