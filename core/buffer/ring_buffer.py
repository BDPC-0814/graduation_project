from collections import deque
from threading import Lock
from typing import Any, List, Optional


class RingBuffer:
    """
    Thread-safe fixed-size in-memory ring buffer.
    """

    def __init__(self, capacity: int = 1024):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._items = deque(maxlen=capacity)
        self._lock = Lock()

    def put(self, item: Any):
        with self._lock:
            self._items.append(item)

    def get_batch(self, size: int) -> List[Any]:
        if size <= 0:
            return []
        batch = []
        with self._lock:
            while self._items and len(batch) < size:
                batch.append(self._items.popleft())
        return batch

    def drain(self) -> List[Any]:
        return self.get_batch(self.capacity)

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def peek_latest(self) -> Optional[Any]:
        with self._lock:
            return self._items[-1] if self._items else None
