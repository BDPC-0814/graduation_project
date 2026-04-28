from __future__ import annotations

import re
import shutil
import subprocess
from typing import Optional

from core.adapter.npu.backends.base_backend import NPUBackend
from core.model.base_xpu import XPUStaticInfo


class OpenHarmonyHDCBackend(NPUBackend):
    """
    OpenHarmony backend that collects NPU metrics remotely via `hdc shell`.
    """

    backend_name = "openharmony_hdc"

    def __init__(self, device_id: str = "npu0", card_id: int = 0, target: Optional[str] = None):
        super().__init__(device_id=device_id, card_id=card_id)
        self.target = target
        self.hdc_path = shutil.which("hdc")
        self.devfreq_dir = self._discover_devfreq_dir()
        self.load_path = "/sys/kernel/debug/rknpu/load"
        self.power_path = "/sys/kernel/debug/rknpu/power"
        self.freq_debug_path = "/sys/kernel/debug/rknpu/freq"
        self.version_path = "/sys/kernel/debug/rknpu/version"
        self.volt_path = "/sys/kernel/debug/rknpu/volt"
        self.reset_path = "/sys/kernel/debug/rknpu/reset"
        self.cur_freq_path = f"{self.devfreq_dir}/cur_freq" if self.devfreq_dir else None
        self.available_freqs_path = f"{self.devfreq_dir}/available_frequencies" if self.devfreq_dir else None
        self.governor_path = f"{self.devfreq_dir}/governor" if self.devfreq_dir else None
        self.thermal_temp_path = self._discover_thermal_temp_path()
        self.ohos_fullname = self._run_shell("param get const.ohos.fullname")
        self.compatible = self._run_shell("cat /proc/device-tree/compatible")
        self._static_info = XPUStaticInfo(
            device_id=device_id,
            device_uid=device_id,
            device_type="NPU",
            arch=self._detect_arch(),
            vendor="Rockchip",
            model_name=self._detect_model_name(),
            driver_version=self._read_text(self.version_path),
            firmware_version=self.ohos_fullname or None,
            core_count=self._detect_core_count(),
        )

        if not self.hdc_path:
            self.init_error = "hdc command not found"
        elif not self._is_target_reachable():
            self.init_error = "OpenHarmony target is not reachable via hdc"

    @classmethod
    def detect(cls) -> bool:
        hdc_path = shutil.which("hdc")
        if not hdc_path:
            return False
        try:
            output = subprocess.check_output(
                [hdc_path, "list", "targets"],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
            )
        except Exception:
            return False
        return any(line.strip() for line in output.splitlines())

    def get_static_info(self) -> XPUStaticInfo:
        return self._static_info

    def collect_fast_snapshot(self) -> Optional[dict[str, object]]:
        if self.init_error and not self._is_target_reachable():
            return None

        load_text = self._read_text(self.load_path)
        core_utils, utilization = self._parse_load(load_text or "")
        chip_temp_c = self._read_temperature_c()

        if load_text is None and self.devfreq_dir is None:
            self.init_error = "OpenHarmony NPU metrics are not accessible via hdc"
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

        utilization = None
        chip_temp_c = None
        if latest_fast_snapshot:
            utilization = self._safe_float(latest_fast_snapshot.get("utilization"))
            chip_temp_c = self._safe_float(latest_fast_snapshot.get("chip_temp_c"))

        throttle_flag, throttle_cause = self._detect_throttle(
            utilization=utilization,
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

    def _is_target_reachable(self) -> bool:
        output = self._run_command(["list", "targets"])
        if output is None:
            return False
        targets = [line.strip() for line in output.splitlines() if line.strip()]
        if not targets:
            return False
        if self.target is None:
            self.target = targets[0]
            return True
        return self.target in targets

    def _run_command(self, args: list[str]) -> Optional[str]:
        if not self.hdc_path:
            return None
        command = [self.hdc_path]
        if self.target:
            command.extend(["-t", self.target])
        command.extend(args)
        try:
            return subprocess.check_output(
                command,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=8,
            ).strip()
        except Exception as exc:  # noqa: BLE001
            self.init_error = f"hdc command failed: {exc}"
            return None

    def _run_shell(self, shell_command: str) -> Optional[str]:
        return self._run_command(["shell", shell_command])

    def _discover_devfreq_dir(self) -> Optional[str]:
        output = self._run_shell("ls /sys/class/devfreq 2>/dev/null")
        if not output:
            return None
        for line in output.splitlines():
            entry = line.strip()
            if "npu" in entry.lower():
                return f"/sys/class/devfreq/{entry}"
        return None

    def _discover_thermal_temp_path(self) -> Optional[str]:
        output = self._run_shell(
            "for z in /sys/class/thermal/thermal_zone*; do "
            "type=$(cat $z/type 2>/dev/null); "
            "if echo \"$type\" | grep -qi npu; then echo $z/temp; break; fi; "
            "done"
        )
        if output:
            return output.splitlines()[0].strip()
        return None

    def _detect_arch(self) -> Optional[str]:
        output = self._run_shell("uname -m")
        return output or None

    def _detect_model_name(self) -> str:
        text = self.compatible or ""
        match = re.search(r"\brk(\d{4})\b", text, re.IGNORECASE)
        if match:
            return f"RK{match.group(1)} NPU"
        return "Rockchip NPU"

    def _detect_core_count(self) -> Optional[int]:
        load_text = self._read_text(self.load_path)
        core_utils, _ = self._parse_load(load_text or "")
        if core_utils:
            return len(core_utils)
        if self.compatible and "rk3588" in self.compatible.lower():
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
        if not path:
            return None
        result = self._run_shell(f"cat {path} 2>/dev/null")
        return result or None

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
