import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


class SQLiteOutbox:
    """边端持久化队列（SQLite + WAL）"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
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
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO outbox(record_type, payload, status, attempts, next_retry_at, created_at, updated_at)
            VALUES (?, ?, 'pending', 0, ?, ?, ?)
            """,
            (record_type, json.dumps(payload, ensure_ascii=False), now, now, now),
        )
        self.conn.commit()

    def fetch_due(self, limit: int = 50) -> List[sqlite3.Row]:
        now = time.time()
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
        self.conn.execute("DELETE FROM outbox WHERE id = ?", (row_id,))
        self.conn.commit()

    def mark_retry(self, row_id: int, attempts: int, last_error: str, base_delay: float = 1.0, max_delay: float = 60.0, max_attempts: int = 8):
        if attempts >= max_attempts:
            status = "dead"
            next_retry_at = time.time()
        else:
            status = "pending"
            next_retry_at = time.time() + min(max_delay, base_delay * (2 ** max(0, attempts - 1)))

        self.conn.execute(
            """
            UPDATE outbox
            SET attempts = ?, status = ?, last_error = ?, next_retry_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (attempts, status, last_error[:500], next_retry_at, time.time(), row_id),
        )
        self.conn.commit()

    def stats(self) -> Tuple[int, int]:
        pending = self.conn.execute("SELECT COUNT(1) FROM outbox WHERE status='pending'").fetchone()[0]
        dead = self.conn.execute("SELECT COUNT(1) FROM outbox WHERE status='dead'").fetchone()[0]
        return pending, dead

    def close(self):
        self.conn.close()
