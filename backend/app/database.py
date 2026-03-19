import csv
import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "backend" / "data"
DEFAULT_DB_PATH = DATA_DIR / "havfs.db"
EXPERIMENT_DIR = ROOT_DIR / "experiments"


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, "", "NA"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value in (None, "", "NA"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _device_type(device_id: str) -> str:
    if device_id.startswith("cpu"):
        return "CPU"
    if device_id.startswith("gpu"):
        return "GPU"
    if device_id.startswith("npu"):
        return "NPU"
    return "Unknown"


def _normalize_state_label(value: Optional[str]) -> Optional[str]:
    mapping = {
        "\ub474\ud2c9(\ud2f1\ubeb4\ub7df\ub9bf)": "\u4f4e\u9891(\u5e73\u6ed1\u6062\u590d)",
        "\u6977\ud658\ue576(\u7ed0\ue640\u892f\u50af\ue351\ue6f0\u7bbf)": "\u9ad8\u9891(\u7a81\u53d1\u6355\u83b7)",
        "\u6977\ud658\ue576(\u6924\ue3a4\u6c99\ue09f\u5f1f\u67bb)": "\u9ad8\u9891(\u9a7b\u7559\u89c2\u5bdf)",
        "\u6d63\ue236\ue576(\u9aa0\ue215\u7cea\u9ac1\u928f\u72c0\u69bb)": "\u4f4e\u9891(\u5e73\u6ed1\u6062\u590d)",
        "\u6d63\ue236\ue576(\u7f01\ue29f\u7568\u60f6\ue18f\u68be)": "\u4f4e\u9891(\u7a33\u5b9a\u5de1\u68c0)",
    }
    if value is None:
        return None
    return mapping.get(value, value)


def _pick_latest_file(patterns: Sequence[str], suffix: str = "") -> Optional[Path]:
    candidates: List[Path] = []
    if not EXPERIMENT_DIR.exists():
        return None
    for pattern in patterns:
        candidates.extend(EXPERIMENT_DIR.rglob(pattern))
    if suffix:
        candidates = [path for path in candidates if str(path).endswith(suffix)]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


class DatabaseService:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
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
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    device_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latest_timestamp TEXT,
                    utilization REAL,
                    chip_temp_c REAL,
                    power_w REAL,
                    sample_interval_s REAL,
                    risk_score REAL,
                    state TEXT,
                    updated_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    time REAL,
                    device_id TEXT NOT NULL,
                    utilization REAL,
                    chip_temp_c REAL,
                    board_temp_c REAL,
                    power_w REAL,
                    freq_mhz REAL,
                    freq_cap_mhz REAL,
                    mem_total_mib INTEGER,
                    mem_used_mib INTEGER,
                    mem_util_percent REAL,
                    pcie_rx_MBps REAL,
                    pcie_tx_MBps REAL,
                    pstate TEXT,
                    power_limit_w REAL,
                    throttle_flag INTEGER,
                    throttle_cause TEXT,
                    last_error_code TEXT,
                    last_error_ts REAL,
                    fan_rpm INTEGER,
                    perf_per_watt REAL,
                    correctable_err_s REAL,
                    uncorrectable_err_s REAL,
                    device_uptime_s INTEGER,
                    device_reset_count INTEGER,
                    nv_throttle_reasons TEXT,
                    nv_ecc_correctable_total INTEGER,
                    nv_ecc_ue_total INTEGER,
                    nv_mem_clock_mhz REAL,
                    nv_graphics_clock_mhz REAL,
                    threads INTEGER,
                    ctx_switch_rate REAL,
                    l3_cache_mib INTEGER,
                    io_util_percent REAL,
                    duty_cycle_percent REAL,
                    collect_ts REAL,
                    sample_interval_s REAL,
                    risk_score REAL,
                    interval REAL,
                    state TEXT,
                    overhead_cpu REAL,
                    overhead_mem_mb REAL,
                    status TEXT NOT NULL,
                    error TEXT,
                    risk_anomaly REAL,
                    risk_jump REAL,
                    risk_pressure REAL,
                    risk_drift REAL,
                    sampled_slow INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_metrics_device_id ON metrics(device_id, id)")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    time REAL,
                    device_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    detail TEXT,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_events_device_id ON events(device_id, id)")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    rule_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    first_seen_at REAL NOT NULL,
                    last_seen_at REAL NOT NULL,
                    acknowledged_by TEXT,
                    acknowledged_at REAL,
                    silenced_until REAL,
                    closed_at REAL,
                    event_count INTEGER NOT NULL DEFAULT 1,
                    last_value REAL,
                    UNIQUE(device_id, rule_key, status)
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(status, last_seen_at DESC)")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_rules (
                    rule_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    rule_source TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    threshold_value REAL,
                    threshold_text TEXT,
                    severity TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    auto_resolve INTEGER NOT NULL DEFAULT 1,
                    message_template TEXT
                )
                """
            )
            self.conn.commit()
        self._seed_default_rules()

    def _seed_default_rules(self):
        default_rules = [
            (
                "device_unavailable",
                "设备不可用",
                "metric",
                "status",
                "ne",
                None,
                "ok",
                "high",
                1,
                1,
                "{field}={value}",
            ),
            (
                "high_risk",
                "高风险采样状态",
                "metric",
                "risk_score",
                "ge",
                60.0,
                None,
                "high",
                1,
                1,
                "{field}={value}",
            ),
            (
                "high_temperature",
                "温度过高",
                "metric",
                "chip_temp_c",
                "ge",
                80.0,
                None,
                "medium",
                1,
                1,
                "{field}={value}",
            ),
            (
                "collector_unavailable",
                "采集器异常",
                "event",
                "event_type",
                "eq",
                None,
                "collector_unavailable",
                "high",
                1,
                0,
                "{message}",
            ),
        ]
        with self._lock:
            self.conn.executemany(
                """
                INSERT OR IGNORE INTO alert_rules (
                    rule_key, title, rule_source, field_name, operator, threshold_value,
                    threshold_text, severity, enabled, auto_resolve, message_template
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                default_rules,
            )
            self.conn.commit()

    def bootstrap_from_latest_csv(self):
        with self._lock:
            metric_count = self.conn.execute("SELECT COUNT(1) FROM metrics").fetchone()[0]
        if metric_count > 0:
            return

        metric_file = _pick_latest_file(("*_metrics.csv", "metrics.csv"))
        event_file = _pick_latest_file(("*_events.csv", "events.csv"))
        if metric_file and metric_file.exists():
            with metric_file.open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            self.ingest_records([("metric", row) for row in rows], source="bootstrap")
        if event_file and event_file.exists():
            with event_file.open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            self.ingest_records([("event", row) for row in rows], source="bootstrap")

    def ingest_records(self, records: Iterable[Tuple[str, Dict[str, Any]]], source: str = "ingest") -> Dict[str, int]:
        metric_count = 0
        event_count = 0
        for record_type, payload in records:
            if record_type == "metric":
                self._insert_metric(payload)
                metric_count += 1
                self._evaluate_metric_alerts(payload)
            elif record_type == "event":
                self._insert_event(payload, source=source)
                event_count += 1
                self._evaluate_event_alerts(payload)
        return {"metrics": metric_count, "events": event_count}

    def _insert_metric(self, payload: Dict[str, Any]):
        now = time.time()
        device_id = payload.get("device_id", "unknown")
        row = (
            payload.get("timestamp"),
            _safe_float(payload.get("time")),
            device_id,
            _safe_float(payload.get("utilization")),
            _safe_float(payload.get("chip_temp_c")),
            _safe_float(payload.get("board_temp_c")),
            _safe_float(payload.get("power_w")),
            _safe_float(payload.get("freq_mhz")),
            _safe_float(payload.get("freq_cap_mhz")),
            _safe_int(payload.get("mem_total_mib")),
            _safe_int(payload.get("mem_used_mib")),
            _safe_float(payload.get("mem_util_percent")),
            _safe_float(payload.get("pcie_rx_MBps")),
            _safe_float(payload.get("pcie_tx_MBps")),
            payload.get("pstate"),
            _safe_float(payload.get("power_limit_w")),
            1 if str(payload.get("throttle_flag")).lower() == "true" else 0,
            payload.get("throttle_cause"),
            payload.get("last_error_code"),
            _safe_float(payload.get("last_error_ts")),
            _safe_int(payload.get("fan_rpm")),
            _safe_float(payload.get("perf_per_watt")),
            _safe_float(payload.get("correctable_err_s")),
            _safe_float(payload.get("uncorrectable_err_s")),
            _safe_int(payload.get("device_uptime_s")),
            _safe_int(payload.get("device_reset_count")),
            payload.get("nv_throttle_reasons"),
            _safe_int(payload.get("nv_ecc_correctable_total")),
            _safe_int(payload.get("nv_ecc_ue_total")),
            _safe_float(payload.get("nv_mem_clock_mhz")),
            _safe_float(payload.get("nv_graphics_clock_mhz")),
            _safe_int(payload.get("threads")),
            _safe_float(payload.get("ctx_switch_rate")),
            _safe_int(payload.get("l3_cache_mib")),
            _safe_float(payload.get("io_util_percent")),
            _safe_float(payload.get("duty_cycle_percent")),
            _safe_float(payload.get("collect_ts")),
            _safe_float(payload.get("sample_interval_s")),
            _safe_float(payload.get("risk_score")),
            _safe_float(payload.get("interval")),
            _normalize_state_label(payload.get("state")),
            _safe_float(payload.get("overhead_cpu")),
            _safe_float(payload.get("overhead_mem_mb")),
            payload.get("status", "unknown"),
            payload.get("error"),
            _safe_float(payload.get("risk_anomaly")),
            _safe_float(payload.get("risk_jump")),
            _safe_float(payload.get("risk_pressure")),
            _safe_float(payload.get("risk_drift")),
            1 if str(payload.get("sampled_slow")).lower() == "true" else 0,
            now,
        )
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO metrics (
                    timestamp, time, device_id, utilization, chip_temp_c, board_temp_c, power_w,
                    freq_mhz, freq_cap_mhz, mem_total_mib, mem_used_mib, mem_util_percent,
                    pcie_rx_MBps, pcie_tx_MBps, pstate, power_limit_w, throttle_flag, throttle_cause,
                    last_error_code, last_error_ts, fan_rpm, perf_per_watt, correctable_err_s,
                    uncorrectable_err_s, device_uptime_s, device_reset_count, nv_throttle_reasons,
                    nv_ecc_correctable_total, nv_ecc_ue_total, nv_mem_clock_mhz, nv_graphics_clock_mhz,
                    threads, ctx_switch_rate, l3_cache_mib, io_util_percent, duty_cycle_percent,
                    collect_ts, sample_interval_s, risk_score, interval, state, overhead_cpu,
                    overhead_mem_mb, status, error, risk_anomaly, risk_jump, risk_pressure,
                    risk_drift, sampled_slow, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
            self.conn.execute(
                """
                INSERT INTO devices (
                    device_id, device_type, status, latest_timestamp, utilization, chip_temp_c,
                    power_w, sample_interval_s, risk_score, state, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    device_type=excluded.device_type,
                    status=excluded.status,
                    latest_timestamp=excluded.latest_timestamp,
                    utilization=excluded.utilization,
                    chip_temp_c=excluded.chip_temp_c,
                    power_w=excluded.power_w,
                    sample_interval_s=excluded.sample_interval_s,
                    risk_score=excluded.risk_score,
                    state=excluded.state,
                    updated_at=excluded.updated_at
                """,
                (
                    device_id,
                    _device_type(device_id),
                    payload.get("status", "unknown"),
                    payload.get("timestamp"),
                    _safe_float(payload.get("utilization")),
                    _safe_float(payload.get("chip_temp_c")),
                    _safe_float(payload.get("power_w")),
                    _safe_float(payload.get("interval")) or _safe_float(payload.get("sample_interval_s")),
                    _safe_float(payload.get("risk_score")),
                    _normalize_state_label(payload.get("state")),
                    now,
                ),
            )
            self.conn.commit()

    def _insert_event(self, payload: Dict[str, Any], source: str):
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO events (timestamp, time, device_id, event_type, severity, message, detail, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("timestamp"),
                    _safe_float(payload.get("time")),
                    payload.get("device_id", "unknown"),
                    payload.get("event_type", "unknown"),
                    payload.get("severity", "info"),
                    payload.get("message", ""),
                    payload.get("detail"),
                    source,
                    time.time(),
                ),
            )
            self.conn.commit()

    def _list_rules_by_source(self, rule_source: str) -> List[sqlite3.Row]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT rule_key, title, rule_source, field_name, operator, threshold_value,
                       threshold_text, severity, enabled, auto_resolve, message_template
                FROM alert_rules
                WHERE enabled = 1 AND rule_source = ?
                ORDER BY rule_key
                """,
                (rule_source,),
            ).fetchall()
        return rows

    def _matches_rule(self, rule: sqlite3.Row, payload: Dict[str, Any]) -> Tuple[bool, Optional[float], str]:
        field_name = rule["field_name"]
        operator = rule["operator"]
        raw_value = payload.get(field_name)
        value_num = _safe_float(raw_value)
        threshold_num = rule["threshold_value"]
        threshold_text = rule["threshold_text"]

        if operator == "ge":
            if value_num is None or threshold_num is None:
                return False, value_num, f"{field_name}=NA"
            return value_num >= float(threshold_num), value_num, f"{field_name}={value_num:.1f}"
        if operator == "gt":
            if value_num is None or threshold_num is None:
                return False, value_num, f"{field_name}=NA"
            return value_num > float(threshold_num), value_num, f"{field_name}={value_num:.1f}"
        if operator == "eq":
            value_text = "" if raw_value is None else str(raw_value)
            return value_text == (threshold_text or ""), value_num, f"{field_name}={value_text}"
        if operator == "ne":
            value_text = "" if raw_value is None else str(raw_value)
            return value_text != (threshold_text or ""), value_num, f"{field_name}={value_text}"
        return False, value_num, f"{field_name}={raw_value}"

    def list_rules(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT rule_key, title, rule_source, field_name, operator, threshold_value,
                       threshold_text, severity, enabled, auto_resolve, message_template
                FROM alert_rules
                ORDER BY rule_key
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def update_rule(self, rule_key: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fields = {
            "title",
            "severity",
            "enabled",
            "auto_resolve",
            "threshold_value",
            "threshold_text",
            "message_template",
        }
        set_clauses = []
        params: List[Any] = []
        for key, value in updates.items():
            if key not in fields:
                continue
            set_clauses.append(f"{key} = ?")
            params.append(value)
        if not set_clauses:
            with self._lock:
                row = self.conn.execute("SELECT * FROM alert_rules WHERE rule_key = ?", (rule_key,)).fetchone()
            return dict(row) if row is not None else None

        params.append(rule_key)
        with self._lock:
            self.conn.execute(
                f"UPDATE alert_rules SET {', '.join(set_clauses)} WHERE rule_key = ?",
                params,
            )
            row = self.conn.execute("SELECT * FROM alert_rules WHERE rule_key = ?", (rule_key,)).fetchone()
            self.conn.commit()
        return dict(row) if row is not None else None

    def _open_or_update_alert(self, device_id: str, rule_key: str, title: str, severity: str, message: str, last_value: Optional[float]):
        now = time.time()
        with self._lock:
            row = self.conn.execute(
                """
                SELECT * FROM alerts
                WHERE device_id = ? AND rule_key = ? AND status IN ('open', 'acknowledged', 'silenced')
                ORDER BY id DESC LIMIT 1
                """,
                (device_id, rule_key),
            ).fetchone()
            if row is None:
                self.conn.execute(
                    """
                    INSERT INTO alerts (
                        device_id, rule_key, title, severity, status, message,
                        first_seen_at, last_seen_at, last_value
                    )
                    VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?)
                    """,
                    (device_id, rule_key, title, severity, message, now, now, last_value),
                )
                self.conn.execute(
                    """
                    INSERT INTO events (timestamp, time, device_id, event_type, severity, message, detail, source, created_at)
                    VALUES (?, ?, ?, 'alert_opened', ?, ?, ?, 'alert-engine', ?)
                    """,
                    (None, None, device_id, severity, title, message, now),
                )
            else:
                next_status = row["status"]
                silenced_until = row["silenced_until"]
                if next_status == "silenced" and silenced_until is not None and silenced_until <= now:
                    next_status = "open"
                self.conn.execute(
                    """
                    UPDATE alerts
                    SET severity = ?, message = ?, last_seen_at = ?, last_value = ?,
                        status = ?, event_count = event_count + 1
                    WHERE id = ?
                    """,
                    (severity, message, now, last_value, next_status, row["id"]),
                )
            self.conn.commit()

    def _resolve_alert(self, device_id: str, rule_key: str, message: str):
        now = time.time()
        with self._lock:
            row = self.conn.execute(
                """
                SELECT * FROM alerts
                WHERE device_id = ? AND rule_key = ? AND status IN ('open', 'acknowledged', 'silenced')
                ORDER BY id DESC LIMIT 1
                """,
                (device_id, rule_key),
            ).fetchone()
            if row is None:
                return
            self.conn.execute(
                """
                UPDATE alerts
                SET status = 'resolved', closed_at = ?, last_seen_at = ?, message = ?
                WHERE id = ?
                """,
                (now, now, message, row["id"]),
            )
            self.conn.execute(
                """
                INSERT INTO events (timestamp, time, device_id, event_type, severity, message, detail, source, created_at)
                VALUES (?, ?, ?, 'alert_resolved', ?, ?, ?, 'alert-engine', ?)
                """,
                (None, None, device_id, row["severity"], row["title"], message, now),
            )
            self.conn.commit()

    def _evaluate_metric_alerts(self, payload: Dict[str, Any]):
        device_id = payload.get("device_id", "unknown")
        for rule in self._list_rules_by_source("metric"):
            matched, last_value, fallback_message = self._matches_rule(rule, payload)
            message_template = rule["message_template"] or "{field}={value}"
            field_name = rule["field_name"]
            message = message_template.format(
                field=field_name,
                value=payload.get(field_name),
                message=payload.get("message") or payload.get("error") or fallback_message,
            )
            if matched:
                self._open_or_update_alert(
                    device_id,
                    rule["rule_key"],
                    rule["title"],
                    rule["severity"],
                    message,
                    last_value,
                )
            elif rule["auto_resolve"]:
                self._resolve_alert(device_id, rule["rule_key"], f"{rule['title']}已恢复")

    def _evaluate_event_alerts(self, payload: Dict[str, Any]):
        for rule in self._list_rules_by_source("event"):
            matched, last_value, fallback_message = self._matches_rule(rule, payload)
            if matched:
                self._open_or_update_alert(
                    payload.get("device_id", "unknown"),
                    rule["rule_key"],
                    rule["title"],
                    payload.get("severity", rule["severity"]),
                    payload.get("message") or fallback_message,
                    last_value,
                )

    def get_devices(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT m.device_id,
                       CASE
                           WHEN m.device_id LIKE 'cpu%' THEN 'CPU'
                           WHEN m.device_id LIKE 'gpu%' THEN 'GPU'
                           WHEN m.device_id LIKE 'npu%' THEN 'NPU'
                           ELSE 'Unknown'
                       END AS device_type,
                       m.status,
                       m.timestamp AS latest_timestamp,
                       m.utilization,
                       m.chip_temp_c,
                       m.power_w,
                       COALESCE(m.interval, m.sample_interval_s) AS sample_interval_s,
                       m.risk_score,
                       m.state
                FROM metrics m
                INNER JOIN (
                    SELECT device_id, MAX(id) AS max_id
                    FROM metrics
                    GROUP BY device_id
                ) latest ON latest.max_id = m.id
                ORDER BY m.device_id
                """
            ).fetchall()
        devices = [dict(row) for row in rows]
        for item in devices:
            item["state"] = _normalize_state_label(item.get("state"))
        return devices

    def get_realtime_metrics(self) -> List[Dict[str, Any]]:
        return [
            {
                "device_id": row["device_id"],
                "timestamp": row["latest_timestamp"],
                "utilization": row["utilization"],
                "chip_temp_c": row["chip_temp_c"],
                "power_w": row["power_w"],
                "sample_interval_s": row["sample_interval_s"],
                "risk_score": row["risk_score"],
                "state": _normalize_state_label(row["state"]),
                "status": row["status"],
            }
            for row in self.get_devices()
        ]

    def get_history(self, device_id: str, limit: int = 120) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT timestamp, time, utilization, chip_temp_c, power_w,
                       COALESCE(interval, sample_interval_s) AS sample_interval_s,
                       risk_score, interval, state, status, risk_anomaly, risk_jump,
                       risk_pressure, risk_drift
                FROM metrics
                WHERE device_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (device_id, limit),
            ).fetchall()
        history = [dict(row) for row in reversed(rows)]
        for item in history:
            item["state"] = _normalize_state_label(item.get("state"))
        return history

    def get_compare_history(self, device_ids: Sequence[str], limit: int = 120) -> Dict[str, Any]:
        normalized_ids = [device_id for device_id in device_ids if device_id]
        series: Dict[str, List[Dict[str, Any]]] = {}
        with self._lock:
            if not normalized_ids:
                normalized_ids = [
                    row["device_id"]
                    for row in self.conn.execute("SELECT device_id FROM devices ORDER BY device_id").fetchall()
                ]
            for device_id in normalized_ids:
                rows = self.conn.execute(
                    """
                    SELECT timestamp, time, device_id, utilization, chip_temp_c, power_w,
                           COALESCE(interval, sample_interval_s) AS sample_interval_s,
                           risk_score, interval, state, status
                    FROM metrics
                    WHERE device_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (device_id, limit),
                ).fetchall()
                series[device_id] = [dict(row) for row in reversed(rows)]
                for item in series[device_id]:
                    item["state"] = _normalize_state_label(item.get("state"))
        return {"device_ids": normalized_ids, "series": series}

    def get_recent_logs(self, limit: int = 80) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT timestamp, device_id, utilization, chip_temp_c, power_w, risk_score,
                       interval, state, sampled_slow, status
                FROM metrics
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        logs = []
        for row in rows:
            temp_text = "NA" if row["chip_temp_c"] is None else f"{row['chip_temp_c']:.2f}"
            line = (
                f"[{row['timestamp'] or '--'}] {row['device_id']} | "
                f"util={row['utilization'] or 0:6.2f}% | "
                f"temp={temp_text} | "
                f"power={(row['power_w'] or 0):.2f} | "
                f"risk={(row['risk_score'] or 0):6.2f} | "
                f"interval={(row['interval'] or 0):.2f}s | "
                f"state={_normalize_state_label(row['state']) or '--'} | "
                f"slow={bool(row['sampled_slow'])} | "
                f"status={row['status']}"
            )
            logs.append({"line": line, "device_id": row["device_id"], "timestamp": row["timestamp"]})
        return logs

    def get_events(self, device_id: Optional[str] = None, severity: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        query = """
            SELECT timestamp, time, device_id, event_type, severity, message, detail, source
            FROM events
            WHERE 1 = 1
        """
        params: List[Any] = []
        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_alerts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT id, device_id, rule_key, title, severity, status, message,
                   first_seen_at, last_seen_at, acknowledged_by, acknowledged_at,
                   silenced_until, closed_at, event_count, last_value
            FROM alerts
            WHERE 1 = 1
        """
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY last_seen_at DESC LIMIT 200"
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_risk_heatmap(self, limit_per_device: int = 24) -> Dict[str, Any]:
        with self._lock:
            device_rows = self.conn.execute("SELECT device_id FROM devices ORDER BY device_id").fetchall()
            devices = [row["device_id"] for row in device_rows]
            timestamps: List[str] = []
            values: List[List[Any]] = []
            for device_index, device_id in enumerate(devices):
                rows = self.conn.execute(
                    """
                    SELECT timestamp, risk_score
                    FROM metrics
                    WHERE device_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (device_id, limit_per_device),
                ).fetchall()
                device_points = list(reversed(rows))
                point_labels: List[str] = []
                for row in device_points:
                    label = row["timestamp"] or f"t{len(timestamps)}"
                    point_labels.append(label)
                    if label not in timestamps:
                        timestamps.append(label)
                for row, label in zip(device_points, point_labels):
                    time_index = timestamps.index(label)
                    values.append([time_index, device_index, row["risk_score"] or 0.0])
        return {"times": timestamps, "devices": devices, "values": values}

    def get_alert_trends(self, hours: int = 24) -> Dict[str, Any]:
        window_start = time.time() - hours * 3600
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT strftime('%Y-%m-%d %H:00', datetime(created_at, 'unixepoch', 'localtime')) AS bucket,
                       SUM(CASE WHEN event_type = 'alert_opened' THEN 1 ELSE 0 END) AS opened,
                       SUM(CASE WHEN event_type = 'alert_resolved' THEN 1 ELSE 0 END) AS resolved
                FROM events
                WHERE source = 'alert-engine' AND created_at >= ?
                GROUP BY bucket
                ORDER BY bucket
                """,
                (window_start,),
            ).fetchall()
        buckets = [row["bucket"] for row in rows]
        opened = [row["opened"] for row in rows]
        resolved = [row["resolved"] for row in rows]
        return {"buckets": buckets, "opened": opened, "resolved": resolved}

    def acknowledge_alert(self, alert_id: int, operator: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            self.conn.execute(
                """
                UPDATE alerts
                SET status = 'acknowledged', acknowledged_by = ?, acknowledged_at = ?
                WHERE id = ? AND status IN ('open', 'silenced')
                """,
                (operator, now, alert_id),
            )
            row = self.conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if row is None:
                self.conn.commit()
                return None
            self.conn.execute(
                """
                INSERT INTO events (timestamp, time, device_id, event_type, severity, message, detail, source, created_at)
                VALUES (?, ?, ?, 'alert_acknowledged', ?, ?, ?, 'alert-engine', ?)
                """,
                (None, None, row["device_id"], row["severity"], row["title"], operator, now),
            )
            self.conn.commit()
        return dict(row)

    def silence_alert(self, alert_id: int, minutes: int, operator: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        silenced_until = now + minutes * 60
        with self._lock:
            self.conn.execute(
                """
                UPDATE alerts
                SET status = 'silenced', silenced_until = ?, acknowledged_by = ?, acknowledged_at = ?
                WHERE id = ? AND status IN ('open', 'acknowledged', 'silenced')
                """,
                (silenced_until, operator, now, alert_id),
            )
            row = self.conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if row is None:
                self.conn.commit()
                return None
            self.conn.execute(
                """
                INSERT INTO events (timestamp, time, device_id, event_type, severity, message, detail, source, created_at)
                VALUES (?, ?, ?, 'alert_silenced', ?, ?, ?, 'alert-engine', ?)
                """,
                (None, None, row["device_id"], row["severity"], row["title"], f"{operator}:{minutes}m", now),
            )
            self.conn.commit()
        return dict(row)

    def get_dashboard_overview(self) -> Dict[str, Any]:
        realtime = self.get_realtime_metrics()
        device_total = len(realtime)
        online_count = sum(1 for item in realtime if item["status"] == "ok")
        high_risk_count = sum(1 for item in realtime if (item["risk_score"] or 0) >= 60)
        intervals = [item["sample_interval_s"] for item in realtime if item["sample_interval_s"] is not None]
        avg_interval = round(sum(intervals) / len(intervals), 2) if intervals else 0.0
        active_alerts = len([item for item in self.list_alerts() if item["status"] in ("open", "acknowledged", "silenced")])
        pending, dead = self.get_outbox_stats()
        return {
            "device_total": device_total,
            "online_count": online_count,
            "high_risk_count": high_risk_count,
            "avg_interval": avg_interval,
            "active_alerts": active_alerts,
            "outbox_pending": pending,
            "outbox_dead": dead,
            "latest_realtime": realtime,
        }

    def get_outbox_stats(self) -> Tuple[int, int]:
        outbox_file = _pick_latest_file(("*outbox.db",), suffix=".db")
        if outbox_file is None or not outbox_file.exists():
            return 0, 0
        conn = sqlite3.connect(outbox_file)
        try:
            pending = conn.execute("SELECT COUNT(1) FROM outbox WHERE status='pending'").fetchone()[0]
            dead = conn.execute("SELECT COUNT(1) FROM outbox WHERE status='dead'").fetchone()[0]
            return pending, dead
        finally:
            conn.close()


_database_instance: Optional[DatabaseService] = None


def get_database() -> DatabaseService:
    global _database_instance
    if _database_instance is None:
        _database_instance = DatabaseService()
    return _database_instance
