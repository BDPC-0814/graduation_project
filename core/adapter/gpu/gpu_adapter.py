import platform
import subprocess
import time
from collections import deque
from typing import Optional

from core.adapter.base_adapter import BaseAdapter
from core.adapter.windows_sensor_reader import WindowsSensorReader
from core.model.base_xpu import XPUStaticInfo, XPUDynamicMetrics

try:
    import pynvml

    HAS_NVML = True
except ImportError:
    HAS_NVML = False


class GPUAdapter(BaseAdapter):
    """
    GPU adapter.
    """

    def __init__(self, device_id: str = "gpu0", vendor: str = "auto", duty_window_size: int = 10):
        super().__init__(device_id=device_id, device_type="GPU")
        self.vendor = vendor
        self.mode = "unsupported"
        self.handle = None
        self.gpu_name = "Unknown GPU"
        self.init_error: Optional[str] = None
        self.collect_started_at = time.time()
        self._duty_window = deque(maxlen=duty_window_size)
        self._windows_sensor_reader = WindowsSensorReader()
        self._static_info = XPUStaticInfo(
            device_id=device_id,
            device_uid=device_id,
            device_type="GPU",
            arch=platform.machine(),
            vendor="Generic",
            model_name=self.gpu_name,
        )

        if self.vendor in ("auto", "nvidia"):
            self._init_nvidia()
            if self.mode == "nvidia_native":
                return

        if self.vendor in ("auto", "nvidia") and platform.system() == "Windows":
            detected_name = self._detect_windows_gpu_name("NVIDIA")
            if detected_name:
                self.gpu_name = detected_name
                self.mode = "windows_generic"
                self._static_info.vendor = "NVIDIA"
                self._static_info.model_name = detected_name
                print(f"[GPU] mode=windows_generic device={self.gpu_name}")
                return

        if self.vendor in ("auto", "intel") and platform.system() == "Windows":
            detected_name = self._detect_windows_gpu_name("Intel")
            if detected_name:
                self.gpu_name = detected_name
                self.mode = "windows_generic"
                self._static_info.vendor = "Intel"
                self._static_info.model_name = detected_name
                print(f"[GPU] mode=windows_generic device={self.gpu_name}")
                return

        print(f"[GPU] mode=unavailable reason={self.init_error or 'no supported GPU collection path'}")

    def get_static_info(self) -> XPUStaticInfo:
        return self._static_info

    def collect_fast(self) -> XPUDynamicMetrics:
        if self.mode == "nvidia_native":
            return self._collect_nvidia_fast()
        if self.mode == "windows_generic":
            return self._collect_windows_generic()
        return self._collect_unavailable(self.init_error or "gpu adapter unavailable")

    def collect_slow(self) -> dict:
        if self.mode == "nvidia_native":
            return self._collect_nvidia_slow()
        return {}

    def _init_nvidia(self):
        if not HAS_NVML:
            self.init_error = "pynvml is not installed"
            return
        try:
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(self.handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            self.gpu_name = name
            self.mode = "nvidia_native"
            self._static_info.vendor = "NVIDIA"
            self._static_info.model_name = name
            print(f"[GPU] mode=nvidia_native device={self.gpu_name}")
        except Exception as exc:  # noqa: BLE001
            self.init_error = f"NVML init failed: {exc}"
            self.mode = "unsupported"

    def _detect_windows_gpu_name(self, target_keyword: str):
        try:
            res = subprocess.check_output(
                "wmic path Win32_VideoController get Name", shell=True
            ).decode(errors="ignore").splitlines()
            for line in res:
                line = line.strip()
                if line and "Name" not in line and target_keyword.lower() in line.lower():
                    return line
        except Exception:
            return None
        return None

    def _collect_windows_generic(self) -> XPUDynamicMetrics:
        util = 0.0
        chip_temp_c = None
        power_w = None
        try:
            ps_cmd = (
                "(Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage').CounterSamples "
                "| Measure-Object -Property CookedValue -Maximum | Select-Object -ExpandProperty Maximum"
            )
            output = subprocess.check_output(["powershell", "-Command", ps_cmd])
            raw = output.decode().strip()
            util = float(raw) if raw else 0.0
        except Exception:
            util = 0.0

        sensor_snapshot = self._windows_sensor_reader.read()
        chip_temp_c = sensor_snapshot.gpu_temp_c
        power_w = sensor_snapshot.gpu_power_w

        if chip_temp_c is None or power_w is None:
            smi_temp_c, smi_power_w = self._read_nvidia_smi_fast_metrics()
            if chip_temp_c is None:
                chip_temp_c = smi_temp_c
            if power_w is None:
                power_w = smi_power_w

        self._duty_window.append(util)
        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=max(util, 0.0),
            temperature=chip_temp_c,
            power=power_w,
            collect_ts=int(time.time()),
            chip_temp_c=chip_temp_c,
            power_w=power_w,
            duty_cycle_percent=sum(self._duty_window) / len(self._duty_window),
        )

    def _read_nvidia_smi_fast_metrics(self) -> tuple[Optional[float], Optional[float]]:
        try:
            output = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=temperature.gpu,power.draw",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3,
            )
        except Exception:
            return None, None

        first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
        if not first_line:
            return None, None

        parts = [part.strip() for part in first_line.split(",")]
        if len(parts) < 2:
            return None, None

        try:
            temp_c = float(parts[0])
        except ValueError:
            temp_c = None

        try:
            power_w = float(parts[1])
        except ValueError:
            power_w = None

        return temp_c, power_w

    def _collect_nvidia_fast(self) -> XPUDynamicMetrics:
        try:
            util_rates = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            gpu_util = float(util_rates.gpu)
            self._duty_window.append(gpu_util)

            chip_temp_c = None
            power_w = None
            mem_util_percent = None
            mem_total_mib = None
            mem_used_mib = None

            try:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
                mem_total_mib = int(mem_info.total / 1024 / 1024)
                mem_used_mib = int(mem_info.used / 1024 / 1024)
                mem_util_percent = (mem_info.used / mem_info.total) * 100 if mem_info.total else 0.0
            except Exception:
                pass

            try:
                chip_temp_c = float(
                    pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)
                )
            except Exception:
                pass

            try:
                power_w = float(pynvml.nvmlDeviceGetPowerUsage(self.handle) / 1000.0)
            except Exception:
                pass

            return XPUDynamicMetrics(
                device_id=self.device_id,
                utilization=max(gpu_util, 0.0),
                temperature=chip_temp_c,
                power=power_w,
                memory_usage=mem_util_percent,
                collect_ts=int(time.time()),
                chip_temp_c=chip_temp_c,
                power_w=power_w,
                duty_cycle_percent=sum(self._duty_window) / len(self._duty_window),
                mem_total_mib=mem_total_mib,
                mem_used_mib=mem_used_mib,
                mem_util_percent=mem_util_percent,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[GPU][Warn] NVML sample failed: {exc}")
            return self._collect_unavailable(f"nvml sample failed: {exc}")

    def _collect_nvidia_slow(self) -> dict:
        freq_mhz = None
        freq_cap_mhz = None
        pcie_rx_mbps = None
        pcie_tx_mbps = None
        pstate = None
        power_limit_w = None
        fan_rpm = None
        nv_mem_clock_mhz = None
        nv_graphics_clock_mhz = None
        throttle_flag = None
        throttle_cause = None
        nv_throttle_reasons = None
        ecc_correctable = None
        ecc_uncorrectable = None

        try:
            nv_graphics_clock_mhz = float(
                pynvml.nvmlDeviceGetClockInfo(self.handle, pynvml.NVML_CLOCK_GRAPHICS)
            )
            freq_mhz = nv_graphics_clock_mhz
        except Exception:
            pass

        try:
            nv_mem_clock_mhz = float(
                pynvml.nvmlDeviceGetClockInfo(self.handle, pynvml.NVML_CLOCK_MEM)
            )
        except Exception:
            pass

        try:
            max_clock = pynvml.nvmlDeviceGetMaxClockInfo(self.handle, pynvml.NVML_CLOCK_GRAPHICS)
            freq_cap_mhz = float(max_clock)
        except Exception:
            pass

        try:
            pcie_rx_mbps = float(
                pynvml.nvmlDeviceGetPcieThroughput(self.handle, pynvml.NVML_PCIE_UTIL_RX_BYTES) / 1024.0
            )
        except Exception:
            pass

        try:
            pcie_tx_mbps = float(
                pynvml.nvmlDeviceGetPcieThroughput(self.handle, pynvml.NVML_PCIE_UTIL_TX_BYTES) / 1024.0
            )
        except Exception:
            pass

        try:
            pstate = f"P{pynvml.nvmlDeviceGetPerformanceState(self.handle)}"
        except Exception:
            pass

        try:
            power_limit_w = float(pynvml.nvmlDeviceGetEnforcedPowerLimit(self.handle) / 1000.0)
        except Exception:
            pass

        try:
            fan_rpm = int(pynvml.nvmlDeviceGetFanSpeed(self.handle))
        except Exception:
            pass

        try:
            reasons = pynvml.nvmlDeviceGetCurrentClocksThrottleReasons(self.handle)
            decoded = self._decode_throttle_reasons(reasons)
            nv_throttle_reasons = ",".join(decoded) if decoded else "none"
            throttle_flag = reasons != 0
            throttle_cause = nv_throttle_reasons if reasons != 0 else None
        except Exception:
            pass

        try:
            ecc_correctable = int(
                pynvml.nvmlDeviceGetTotalEccErrors(
                    self.handle,
                    pynvml.NVML_MEMORY_ERROR_TYPE_CORRECTED,
                    pynvml.NVML_VOLATILE_ECC,
                )
            )
        except Exception:
            pass

        try:
            ecc_uncorrectable = int(
                pynvml.nvmlDeviceGetTotalEccErrors(
                    self.handle,
                    pynvml.NVML_MEMORY_ERROR_TYPE_UNCORRECTED,
                    pynvml.NVML_VOLATILE_ECC,
                )
            )
        except Exception:
            pass

        return {
            "freq_mhz": freq_mhz,
            "freq_cap_mhz": freq_cap_mhz,
            "pcie_rx_MBps": pcie_rx_mbps,
            "pcie_tx_MBps": pcie_tx_mbps,
            "bandwidth": (pcie_rx_mbps + pcie_tx_mbps) if pcie_rx_mbps is not None and pcie_tx_mbps is not None else None,
            "pstate": pstate,
            "power_limit_w": power_limit_w,
            "device_uptime_s": int(time.time() - self.collect_started_at),
            "fan_rpm": fan_rpm,
            "throttle_flag": throttle_flag,
            "throttle_cause": throttle_cause,
            "nv_throttle_reasons": nv_throttle_reasons,
            "nv_ecc_correctable_total": ecc_correctable,
            "nv_ecc_ue_total": ecc_uncorrectable,
            "nv_mem_clock_mhz": nv_mem_clock_mhz,
            "nv_graphics_clock_mhz": nv_graphics_clock_mhz,
        }

    def _decode_throttle_reasons(self, reasons: int) -> list[str]:
        if not HAS_NVML:
            return []
        mappings = [
            ("gpu_idle", getattr(pynvml, "nvmlClocksThrottleReasonGpuIdle", None)),
            ("applications_clocks_setting", getattr(pynvml, "nvmlClocksThrottleReasonApplicationsClocksSetting", None)),
            ("sw_power_cap", getattr(pynvml, "nvmlClocksThrottleReasonSwPowerCap", None)),
            ("hw_slowdown", getattr(pynvml, "nvmlClocksThrottleReasonHwSlowdown", None)),
            ("sync_boost", getattr(pynvml, "nvmlClocksThrottleReasonSyncBoost", None)),
            ("sw_thermal_slowdown", getattr(pynvml, "nvmlClocksThrottleReasonSwThermalSlowdown", None)),
            ("hw_thermal_slowdown", getattr(pynvml, "nvmlClocksThrottleReasonHwThermalSlowdown", None)),
            ("hw_power_brake", getattr(pynvml, "nvmlClocksThrottleReasonHwPowerBrakeSlowdown", None)),
            ("display_clock_setting", getattr(pynvml, "nvmlClocksThrottleReasonDisplayClockSetting", None)),
        ]
        return [name for name, mask in mappings if mask is not None and (reasons & mask)]

    def _collect_unavailable(self, reason: str) -> XPUDynamicMetrics:
        return XPUDynamicMetrics(
            device_id=self.device_id,
            utilization=0.0,
            collect_ts=int(time.time()),
            status="unavailable",
            error=reason,
            last_error_code=reason,
            last_error_ts=int(time.time()),
        )

    def __del__(self):
        if self.mode == "nvidia_native" and HAS_NVML:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
