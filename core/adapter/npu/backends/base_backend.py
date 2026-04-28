from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from core.model.base_xpu import XPUStaticInfo


class NPUBackend(ABC):
    """
    Backend contract for concrete NPU collection paths.
    """

    backend_name = "unknown"

    def __init__(self, device_id: str = "npu0", card_id: int = 0):
        self.device_id = device_id
        self.card_id = card_id
        self.init_error: Optional[str] = None

    @classmethod
    @abstractmethod
    def detect(cls) -> bool:
        """
        Return True when the backend appears usable on the current host.
        """

    @abstractmethod
    def get_static_info(self) -> XPUStaticInfo:
        """
        Return backend-specific static metadata.
        """

    @abstractmethod
    def collect_fast_snapshot(self) -> Optional[dict[str, Any]]:
        """
        Return a normalized fast-path snapshot, or None on failure.
        """

    def collect_slow_snapshot(self, latest_fast_snapshot: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Return lower-priority extended fields.
        """
        return {}
