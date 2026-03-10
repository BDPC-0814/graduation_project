import json
import urllib.error
import urllib.request
from typing import Dict, Any


class HTTPUploader:
    """简单 HTTP 上送器，用于演示失败重传链路。"""

    def __init__(self, endpoint: str, timeout: float = 2.0):
        self.endpoint = endpoint
        self.timeout = timeout

    def upload(self, record_type: str, payload: Dict[str, Any]):
        body = json.dumps({"type": record_type, "payload": payload}).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                code = resp.getcode()
                if code < 200 or code >= 300:
                    raise RuntimeError(f"http status {code}")
        except urllib.error.URLError as exc:
            raise RuntimeError(str(exc)) from exc
