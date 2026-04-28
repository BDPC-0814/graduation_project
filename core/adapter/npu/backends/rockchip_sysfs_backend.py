from __future__ import annotations

import glob
import os
import platform
import re
from typing import Optional

from core.adapter.npu.backends.base_backend import NPUBackend
from core.model.base_xpu import XPUStaticInfo


class RockchipSysfsBackend(NPUBackend):
    """
    RK3588-style Rockchip backend backed by sysfs/debugfs nodes.
    """

    backend_name = "rockchip_sysfs"
    _DEBUG_DIR = "/sys/kernel/debug/rknpu"

    def __init__(self, device_id: str = "npu0", card_id: int = 0):
        super().__init__(device_id=device_id, card_id=card_id)
        self.devfreq_dir = self._discover_devfreq_dir()
        self.load_path = os.path.join(self._DEBUG_DIR, "load")
        self.power_path = os.path.join(self._DEBUG_DIR, "power")
        self.freq_debug_path = os.path.join(self._DEBUG_DIR, "freq")
        self.version_path = os.path.join(self._DEBUG_DIR, "version")
        self.volt_path = os.path.join(self._DEBUG_DIR, "volt")
        self.reset_path = os.path.join(self._DEBUG_DIR, "reset")
        self.cur_freq_path = os.path.join(self.devfreq_dir, "cur_freq") if self.devfreq_dir else None
        self.available_freqs_path = (
            os.path.join(self.devfreq_dir, "available_frequencies") if self.devfreq_dir else None
        )
        self.governor_path = os.path.join(self.devfreq_dir, "governor") if self.devfreq_dir else None
        self.thermal_temp_path = self._discover_thermal_temp_path()
        self._compatible_tokens = self._read_compatible_tokens()
        self._static_info = XPUStaticInfo(
            device_id=device_id,
            device_uid=device_id,
            device_type="NPU",
            arch=platform.machine(),
            vendor="Rockchip",
            model_name=self._detect_model_name(),
            driver_version=self._detect_driver_version(),
            core_count=self._detect_core_count(),
        )
        if not self.devfreq_dir and not os.path.exists("/sys/module/rknpu") and not os.path.exists(self._DEBUG_DIR):
            self.init_error = "Rockchip NPU sysfs/debugfs nodes not found"

    @classmethod
    def detect(cls) -> bool:
        if platform.system() != "Linux":
            return False
        if glob.glob("/sys/class/devfreq/*npu*"):
            return True
        return os.path.exists("/sys/module/rknpu") or os.path.exists(cls._DEBUG_DIR)

    def get_static_info(self) -> XPUStaticInfo:
        return self._static_info

    def collect_fast_snapshot(self) -> Optional[dict[str, object]]:
        if self.init_error and not self.detect():
            return None

        load_text = self._read_text(self.load_path)
        core_utils, utilization = self._parse_load(load_text or "")
        chip_temp_c = self._read_temperature_c()

        if load_text is None and self.devfreq_dir is None:
            self.init_error = "Rockchip NPU metrics are not accessible"
            return None

        return {
            "utilization": utilization,
            "chip_temp_c": chip_temp_c,
            "power_w": None,
            "mem_used_mib": None,
            "mem_total_mib": None,
            "mem_util_percent": None,
            "core_utilization": core_utils,
        }

    def collect_slow_snapshot(self, latest_fast_snapshot: Optional[dict[str, object]] = None) -> dict[str, object]:
        freq_mhz = self._read_scaled_number(self.cur_freq_path, 1_000_000.0)
        available_freqs_hz = self._parse_frequency_list(self._read_text(self.available_freqs_path))
        freq_cap_mhz = max(available_freqs_hz) / 1_000_000.0 if available_freqs_hz else None
        governor = self._read_text(self.governor_path)
        power_state = self._read_text(self.power_path)
        reset_count = self._parse_first_number(self._read_text(self.reset_path))

        util = None
        chip_temp_c = None
        if latest_fast_snapshot:
            util = self._safe_float(latest_fast_snapshot.get("utilization"))
            chip_temp_c = self._safe_float(latest_fast_snapshot.get("chip_temp_c"))
        throttle_flag, throttle_cause = self._detect_throttle(
            utilization=util,
            freq_mhz=freq_mhz,
            freq_cap_mhz=freq_cap_mhz,
            chip_temp_c=chip_temp_c,
            power_state=power_state,
        )

        return {
            "freq_mhz": freq_mhz,
            "freq_cap_mhz": freq_cap_mhz,
            "pstate": governor or power_state,
            "throttle_flag": throttle_flag,
            "throttle_cause": throttle_cause,
            "device_reset_count": int(reset_count) if reset_count is not None else None,
        }

    def _discover_devfreq_dir(self) -> Optional[str]:
        candidates = sorted(glob.glob("/sys/class/devfreq/*npu*"))
        return candidates[0] if candidates else None

    def _discover_thermal_temp_path(self) -> Optional[str]:
        for zone_dir in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
            zone_type = self._read_text(os.path.join(zone_dir, "type"))
            if zone_type and "npu" in zone_type.lower():
                temp_path = os.path.join(zone_dir, "temp")
                if os.path.exists(temp_path):
                    return temp_path
        return None

    def _read_compatible_tokens(self) -> list[str]:
        for path in (
            "/proc/device-tree/compatible",
            "/sys/firmware/devicetree/base/compatible",
        ):
            raw = self._read_bytes(path)
            if raw:
                return [token for token in raw.replace(b"\x00", b"\n").decode(errors="ignore").splitlines() if token]
        return []

    def _detect_model_name(self) -> str:
        for token in self._compatible_tokens:
            match = re.search(r"\brk(\d{4})\b", token, re.IGNORECASE)
            if match:
                return f"RK{match.group(1)} NPU"
        return "Rockchip NPU"

    def _detect_driver_version(self) -> Optional[str]:
        text = self._read_text(self.version_path)
        if not text:
            return None
        return next((line.strip() for line in text.splitlines() if line.strip()), None)

    def _detect_core_count(self) -> Optional[int]:
        load_text = self._read_text(self.load_path)
        core_utils, _ = self._parse_load(load_text or "")
        if core_utils:
            return len(core_utils)
        if any("rk3588" in token.lower() for token in self._compatible_tokens):
            return 3
        return None

    def _parse_load(self, text: str) -> tuple[list[float], float]:
        core_utils = [float(value) for value in re.findall(r"Core\d+:\s*([0-9]+(?:\.[0-9]+)?)%", text)]
        if not core_utils:
            return [], 0.0
        return core_utils, sum(core_utils) / len(core_utils)

    def _parse_frequency_list(self, text: Optional[str]) -> list[int]:
        if not text:
            return []
        values = []
        for token in text.split():
            try:
                values.append(int(token))
            except ValueError:
                continue
        return values

    def _read_temperature_c(self) -> Optional[float]:
        value = self._read_scaled_number(self.thermal_temp_path, 1000.0)
        if value is not None:
            return value
        return None

    def _detect_throttle(
        self,
        *,
        utilization: Optional[float],
        freq_mhz: Optional[float],
        freq_cap_mhz: Optional[float],
        chip_temp_c: Optional[float],
        power_state: Optional[str],
    ) -> tuple[Optional[bool], Optional[str]]:
        if utilization is None or freq_mhz is None or freq_cap_mhz is None:
            return None, None
        if utilization < 70.0:
            return False, None
        if chip_temp_c is not None and chip_temp_c >= 85.0 and freq_mhz < freq_cap_mhz:
            return True, "thermal"
        if power_state and "off" in power_state.lower():
            return True, "power_gated"
        if freq_mhz < freq_cap_mhz * 0.85:
            return True, "governor_limit"
        return False, None

    def _read_text(self, path: Optional[str]) -> Optional[str]:
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                return handle.read().strip()
        except OSError:
            return None

    def _read_bytes(self, path: str) -> Optional[bytes]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except OSError:
            return None

    def _read_scaled_number(self, path: Optional[str], divisor: float) -> Optional[float]:
        value = self._parse_first_number(self._read_text(path))
        if value is None:
            return None
        return float(value) / divisor

    def _parse_first_number(self, text: Optional[str]) -> Optional[float]:
        if not text:
            return None
        match = re.search(r"(-?[0-9]+(?:\.[0-9]+)?)", text)
        if not match:
            return None
        return float(match.group(1))

    def _safe_float(self, value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
