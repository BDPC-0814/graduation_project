import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event, Thread
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from core.buffer.ring_buffer import RingBuffer
from core.sampler.device_sampler import DeviceSample, DeviceSampler
from core.scheduler.fault_evolution_scheduler import RuntimeFeedback
from core.storage.sqlite_outbox import SQLiteOutbox
from core.uploader.http_uploader import HTTPUploader

OutboxRecord = Tuple[str, dict]


class EdgeAgent:
    """
    Runtime orchestrator for samplers with background WAL and upload workers.
    """

    def __init__(
        self,
        samplers: Dict[str, DeviceSampler],
        ring_buffer: Optional[RingBuffer] = None,
        outbox: Optional[SQLiteOutbox] = None,
        uploader: Optional[HTTPUploader] = None,
        wal_batch_size: int = 100,
        upload_batch_size: int = 50,
        upload_poll_interval: float = 0.5,
        wal_poll_interval: float = 0.2,
        retry_max_attempts: int = 8,
    ):
        self.samplers = samplers
        self.ring_buffer = ring_buffer or RingBuffer(capacity=max(256, len(samplers) * 64))
        self.outbox = outbox
        self.uploader = uploader
        self.wal_batch_size = wal_batch_size
        self.upload_batch_size = upload_batch_size
        self.upload_poll_interval = upload_poll_interval
        self.wal_poll_interval = wal_poll_interval
        self.retry_max_attempts = retry_max_attempts
        self._stop_event = Event()
        self._workers: List[Thread] = []

    def run(
        self,
        duration: int,
        on_metric: Callable[[DeviceSample, float, str], Optional[Iterable[OutboxRecord]]],
        on_event: Optional[Callable[[DeviceSample, float, str], Optional[Iterable[OutboxRecord]]]] = None,
        on_cycle_end: Optional[Callable[[Dict[str, DeviceSample], float], None]] = None,
    ):
        self._start_workers()
        start_monotonic = time.monotonic()
        next_due = {
            device_id: start_monotonic
            for device_id in self.samplers
        }
        has_sampled = {
            device_id: False
            for device_id in self.samplers
        }
        try:
            with ThreadPoolExecutor(max_workers=max(1, len(self.samplers))) as executor:
                while time.monotonic() - start_monotonic < duration:
                    now = time.monotonic()
                    due_device_ids = [
                        device_id
                        for device_id, due_at in next_due.items()
                        if due_at <= now + 1e-6
                    ]
                    if not due_device_ids:
                        nearest_due = min(next_due.values()) if next_due else now
                        sleep_time = max(nearest_due - now, 0.0)
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                        continue

                    runtime_feedback = self._build_runtime_feedback()
                    for device_id in due_device_ids:
                        self.samplers[device_id].set_runtime_feedback(runtime_feedback)

                    dispatch_started_at = time.monotonic()
                    futures = {
                        device_id: executor.submit(self.samplers[device_id].sample)
                        for device_id in due_device_ids
                    }
                    results = {
                        device_id: future.result()
                        for device_id, future in futures.items()
                    }
                    cycle_finished_at = time.monotonic()
                    elapsed = round(cycle_finished_at - start_monotonic, 2)
                    wallclock = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                    for result in results.values():
                        metric_records = on_metric(result, elapsed, wallclock)
                        self._enqueue_records(metric_records)
                        if result.metrics.status != "ok" and on_event is not None:
                            event_records = on_event(result, elapsed, wallclock)
                            self._enqueue_records(event_records)

                    for device_id, result in results.items():
                        if not has_sampled.get(device_id, False):
                            next_due[device_id] = cycle_finished_at + max(result.interval, 0.0)
                            has_sampled[device_id] = True
                            continue
                        scheduled_base = max(next_due.get(device_id, dispatch_started_at), dispatch_started_at)
                        next_due[device_id] = max(cycle_finished_at, scheduled_base + max(result.interval, 0.0))

                    wait_hint = (
                        min(max(due_at - time.monotonic(), 0.0) for due_at in next_due.values())
                        if next_due
                        else 0.0
                    )
                    if on_cycle_end is not None:
                        on_cycle_end(results, wait_hint)
        finally:
            self.stop()

    def stop(self):
        self._stop_event.set()
        for worker in self._workers:
            worker.join(timeout=2.0)
        self._workers.clear()

    def _enqueue_records(self, records: Optional[Iterable[OutboxRecord]]):
        if records is None:
            return
        for record in records:
            self.ring_buffer.put(record)

    def _start_workers(self):
        if self.outbox is not None:
            wal_worker = Thread(target=self._wal_worker_loop, name="wal-writer", daemon=True)
            wal_worker.start()
            self._workers.append(wal_worker)

        if self.outbox is not None and self.uploader is not None:
            uploader_worker = Thread(target=self._upload_worker_loop, name="upload-worker", daemon=True)
            uploader_worker.start()
            self._workers.append(uploader_worker)

    def _wal_worker_loop(self):
        while not self._stop_event.is_set() or self.ring_buffer.size() > 0:
            batch = self.ring_buffer.get_batch(self.wal_batch_size)
            if not batch:
                time.sleep(self.wal_poll_interval)
                continue
            self.outbox.enqueue_many(batch)

    def _upload_worker_loop(self):
        while not self._stop_event.is_set():
            due_rows = self.outbox.fetch_due(limit=self.upload_batch_size)
            if not due_rows:
                time.sleep(self.upload_poll_interval)
                continue

            records = [
                (row["record_type"], json.loads(row["payload"]))
                for row in due_rows
            ]
            try:
                self.uploader.upload_batch(records)
                self.outbox.mark_sent_many([row["id"] for row in due_rows])
            except Exception as exc:  # noqa: BLE001
                self.outbox.mark_retry_many(
                    [
                        (row["id"], row["attempts"] + 1, str(exc))
                        for row in due_rows
                    ],
                    max_attempts=self.retry_max_attempts,
                )
                time.sleep(self.upload_poll_interval)

    def _build_runtime_feedback(self) -> RuntimeFeedback:
        pending = 0
        dead = 0
        if self.outbox is not None:
            pending, dead = self.outbox.stats()
        return RuntimeFeedback(
            pending=pending,
            dead=dead,
            ring_backlog=self.ring_buffer.size(),
            ring_capacity=getattr(self.ring_buffer, "capacity", 1),
            uploader_active=self.uploader is not None,
        )
