import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event, Thread
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from core.buffer.ring_buffer import RingBuffer
from core.sampler.device_sampler import DeviceSample, DeviceSampler
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
        self.ring_buffer = ring_buffer or RingBuffer(capacity=max(1024, len(samplers) * 64))
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
        start_time = time.time()
        try:
            with ThreadPoolExecutor(max_workers=max(1, len(self.samplers))) as executor:
                while time.time() - start_time < duration:
                    futures = {
                        device_id: executor.submit(sampler.sample)
                        for device_id, sampler in self.samplers.items()
                    }
                    results = {
                        device_id: future.result()
                        for device_id, future in futures.items()
                    }
                    elapsed = round(time.time() - start_time, 2)
                    wallclock = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                    for result in results.values():
                        metric_records = on_metric(result, elapsed, wallclock)
                        self._enqueue_records(metric_records)
                        if result.metrics.status != "ok" and on_event is not None:
                            event_records = on_event(result, elapsed, wallclock)
                            self._enqueue_records(event_records)

                    global_interval = min(result.interval for result in results.values()) if results else 1.0
                    if on_cycle_end is not None:
                        on_cycle_end(results, global_interval)

                    time.sleep(global_interval)
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
