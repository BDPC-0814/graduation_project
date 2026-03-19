import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .database import get_database


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_EVALUATION_REPORT = ROOT_DIR / "experiments" / "evaluation" / "latest" / "report.json"


def bootstrap_database():
    get_database().bootstrap_from_latest_csv()


def ingest_records(records, source: str = "ingest") -> Dict[str, int]:
    return get_database().ingest_records(records, source=source)


def get_realtime_metrics() -> List[Dict[str, Any]]:
    return get_database().get_realtime_metrics()


def get_devices() -> List[Dict[str, Any]]:
    return get_database().get_devices()


def get_history(device_id: str, limit: int = 120) -> List[Dict[str, Any]]:
    return get_database().get_history(device_id=device_id, limit=limit)


def get_compare_history(device_ids: List[str], limit: int = 120) -> Dict[str, Any]:
    return get_database().get_compare_history(device_ids=device_ids, limit=limit)


def get_recent_logs(limit: int = 80) -> List[Dict[str, Any]]:
    return get_database().get_recent_logs(limit=limit)


def get_events(device_id: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
    return get_database().get_events(device_id=device_id, severity=severity)


def get_alerts(status: Optional[str] = None) -> List[Dict[str, Any]]:
    return get_database().list_alerts(status=status)


def acknowledge_alert(alert_id: int, operator: str) -> Optional[Dict[str, Any]]:
    return get_database().acknowledge_alert(alert_id=alert_id, operator=operator)


def silence_alert(alert_id: int, minutes: int, operator: str) -> Optional[Dict[str, Any]]:
    return get_database().silence_alert(alert_id=alert_id, minutes=minutes, operator=operator)


def get_dashboard_overview() -> Dict[str, Any]:
    return get_database().get_dashboard_overview()


def get_risk_heatmap(limit_per_device: int = 24) -> Dict[str, Any]:
    return get_database().get_risk_heatmap(limit_per_device=limit_per_device)


def get_alert_trends(hours: int = 24) -> Dict[str, Any]:
    return get_database().get_alert_trends(hours=hours)


def get_rules() -> List[Dict[str, Any]]:
    return get_database().list_rules()


def update_rule(rule_key: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return get_database().update_rule(rule_key=rule_key, updates=updates)


def get_experiment_evaluation_report(report_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    target = Path(report_path) if report_path else DEFAULT_EVALUATION_REPORT
    if not target.is_absolute():
        target = ROOT_DIR / target
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))
