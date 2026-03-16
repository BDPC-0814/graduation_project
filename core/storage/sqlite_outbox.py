import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Sequence, Tuple


class SQLiteOutbox:
    """
    Persistent edge outbox backed by SQLite WAL.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_retry_at REAL NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_outbox_due ON outbox(status, next_retry_at, id)"
            )
            self.conn.commit()

    def enqueue(self, record_type: str, payload: Dict[str, Any]):
        self.enqueue_many([(record_type, payload)])

    def enqueue_many(self, records: Iterable[Tuple[str, Dict[str, Any]]]):
        rows = list(records)
        if not rows:
            return
        now = time.time()
        payloads = [
            (
                record_type,
                json.dumps(payload, ensure_ascii=False),
                now,
                now,
                now,
            )
            for record_type, payload in rows
        ]
        with self._lock:
            self.conn.executemany(
                """
                INSERT INTO outbox(record_type, payload, status, attempts, next_retry_at, created_at, updated_at)
                VALUES (?, ?, 'pending', 0, ?, ?, ?)
                """,
                payloads,
            )
            self.conn.commit()

    def fetch_due(self, limit: int = 50) -> List[sqlite3.Row]:
        now = time.time()
        with self._lock:
            cur = self.conn.execute(
                """
                SELECT * FROM outbox
                WHERE status = 'pending' AND next_retry_at <= ?
                ORDER BY id ASC LIMIT ?
                """,
                (now, limit),
            )
            return cur.fetchall()

    def mark_sent(self, row_id: int):
        self.mark_sent_many([row_id])

    def mark_sent_many(self, row_ids: Sequence[int]):
        ids = list(row_ids)
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._lock:
            self.conn.execute(f"DELETE FROM outbox WHERE id IN ({placeholders})", ids)
            self.conn.commit()

    def mark_retry(
        self,
        row_id: int,
        attempts: int,
        last_error: str,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        max_attempts: int = 8,
    ):
        self.mark_retry_many(
            [(row_id, attempts, last_error)],
            base_delay=base_delay,
            max_delay=max_delay,
            max_attempts=max_attempts,
        )

    def mark_retry_many(
        self,
        retries: Iterable[Tuple[int, int, str]],
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        max_attempts: int = 8,
    ):
        rows = list(retries)
        if not rows:
            return

        now = time.time()
        update_rows = []
        for row_id, attempts, last_error in rows:
            if attempts >= max_attempts:
                status = "dead"
                next_retry_at = now
            else:
                status = "pending"
                next_retry_at = now + min(max_delay, base_delay * (2 ** max(0, attempts - 1)))
            update_rows.append((attempts, status, last_error[:500], next_retry_at, now, row_id))

        with self._lock:
            self.conn.executemany(
                """
                UPDATE outbox
                SET attempts = ?, status = ?, last_error = ?, next_retry_at = ?, updated_at = ?
                WHERE id = ?
                """,
                update_rows,
            )
            self.conn.commit()

    def stats(self) -> Tuple[int, int]:
        with self._lock:
            pending = self.conn.execute("SELECT COUNT(1) FROM outbox WHERE status='pending'").fetchone()[0]
            dead = self.conn.execute("SELECT COUNT(1) FROM outbox WHERE status='dead'").fetchone()[0]
        return pending, dead

    def close(self):
        with self._lock:
            self.conn.close()
