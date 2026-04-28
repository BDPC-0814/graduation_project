from core.adapter.npu.backends.ascend_backend import AscendNPUSmiBackend
from core.adapter.npu.backends.base_backend import NPUBackend
from core.adapter.npu.backends.openharmony_hdc_backend import OpenHarmonyHDCBackend
from core.adapter.npu.backends.rockchip_sysfs_backend import RockchipSysfsBackend

__all__ = [
    "AscendNPUSmiBackend",
    "NPUBackend",
    "OpenHarmonyHDCBackend",
    "RockchipSysfsBackend",
]
