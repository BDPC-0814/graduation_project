import json
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SensorSnapshot:
    cpu_temp_c: Optional[float] = None
    cpu_power_w: Optional[float] = None
    cpu_board_temp_c: Optional[float] = None
    gpu_temp_c: Optional[float] = None
    gpu_power_w: Optional[float] = None


class WindowsSensorReader:
    """
    Read hardware telemetry on Windows.

    The preferred path is a bundled PowerShell probe backed by
    LibreHardwareMonitorLib. A WMI fallback is kept for machines that
    already expose sensor data via a compatible namespace.
    """

    _cache_ttl_s = 1.0

    def __init__(self) -> None:
        self._probe_script = (
            Path(__file__).resolve().parents[2] / "tools" / "hardware_probe" / "HardwareProbe.ps1"
        )
        self._last_snapshot = SensorSnapshot()
        self._last_read_at = 0.0

    def is_supported(self) -> bool:
        return platform.system() == "Windows"

    def read(self) -> SensorSnapshot:
        if not self.is_supported():
            return SensorSnapshot()

        now = time.monotonic()
        if now - self._last_read_at < self._cache_ttl_s:
            return self._last_snapshot

        snapshot = self._read_from_probe()
        if not any(vars(snapshot).values()):
            snapshot = self._read_from_wmi()

        self._last_snapshot = snapshot
        self._last_read_at = now
        return snapshot

    def _read_from_probe(self) -> SensorSnapshot:
        if not self._probe_script.exists():
            return SensorSnapshot()

        try:
            output = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(self._probe_script),
                ],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=8,
            )
        except Exception:
            return SensorSnapshot()

        if not output.strip():
            return SensorSnapshot()

        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return SensorSnapshot()

        if not isinstance(payload, dict):
            return SensorSnapshot()

        return SensorSnapshot(
            cpu_temp_c=self._safe_float(payload.get("cpu_temp_c")),
            cpu_power_w=self._safe_float(payload.get("cpu_power_w")),
            cpu_board_temp_c=self._safe_float(payload.get("cpu_board_temp_c")),
            gpu_temp_c=self._safe_float(payload.get("gpu_temp_c")),
            gpu_power_w=self._safe_float(payload.get("gpu_power_w")),
        )

    def _read_from_wmi(self) -> SensorSnapshot:
        sensors = self._load_lhm_sensors()
        if not sensors:
            return SensorSnapshot()

        cpu_temp = self._pick_value(
            sensors,
            sensor_type="Temperature",
            keywords=("cpu package", "package", "tdie", "tctl", "cpu core"),
            hardware_keywords=("cpu",),
        )
        cpu_power = self._pick_value(
            sensors,
            sensor_type="Power",
            keywords=("package", "cpu package", "package power", "cpu total", "cores"),
            hardware_keywords=("cpu",),
        )
        cpu_board_temp = self._pick_value(
            sensors,
            sensor_type="Temperature",
            keywords=("motherboard", "mainboard", "chipset", "system"),
            hardware_keywords=("mainboard", "motherboard"),
        )
        gpu_temp = self._pick_value(
            sensors,
            sensor_type="Temperature",
            keywords=("gpu core", "hot spot", "junction", "package"),
            hardware_keywords=("gpu", "nvidia", "amd", "intel"),
        )
        gpu_power = self._pick_value(
            sensors,
            sensor_type="Power",
            keywords=("gpu package", "board power draw", "package", "total"),
            hardware_keywords=("gpu", "nvidia", "amd", "intel"),
        )

        return SensorSnapshot(
            cpu_temp_c=cpu_temp,
            cpu_power_w=cpu_power,
            cpu_board_temp_c=cpu_board_temp,
            gpu_temp_c=gpu_temp,
            gpu_power_w=gpu_power,
        )

    def _load_lhm_sensors(self) -> list[dict]:
        namespaces = ("root/LibreHardwareMonitor", "root/OpenHardwareMonitor")
        for namespace in namespaces:
            command = (
                f"Get-CimInstance -Namespace {namespace} -ClassName Sensor -ErrorAction SilentlyContinue "
                "| Select-Object Name,SensorType,Value,Identifier,Parent | ConvertTo-Json -Compress"
            )
            try:
                output = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", command],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=5,
                )
            except Exception:
                continue

            if not output.strip():
                continue

            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                continue

            if isinstance(data, dict):
                return [data]
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        return []

    def _pick_value(
        self,
        sensors: list[dict],
        sensor_type: str,
        keywords: tuple[str, ...],
        hardware_keywords: tuple[str, ...],
    ) -> Optional[float]:
        exact_matches: list[float] = []
        hardware_matches: list[float] = []
        type_matches: list[float] = []

        for sensor in sensors:
            if str(sensor.get("SensorType", "")).lower() != sensor_type.lower():
                continue

            number = self._safe_float(sensor.get("Value"))
            if number is None:
                continue

            haystack = " ".join(str(sensor.get(field, "") or "").lower() for field in ("Name", "Identifier", "Parent"))
            if any(keyword in haystack for keyword in keywords):
                exact_matches.append(number)
                continue
            if any(keyword in haystack for keyword in hardware_keywords):
                hardware_matches.append(number)
                continue
            type_matches.append(number)

        if exact_matches:
            return exact_matches[0]
        if hardware_matches:
            return hardware_matches[0]
        if len(type_matches) == 1:
            return type_matches[0]
        return None

    def _safe_float(self, value: object) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
