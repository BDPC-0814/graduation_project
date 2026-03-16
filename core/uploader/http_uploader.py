import gzip
import json
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Tuple


class HTTPUploader:
    """
    HTTP uploader with gzip-compressed batch upload support.
    """

    def __init__(self, endpoint: str, timeout: float = 2.0):
        self.endpoint = endpoint
        self.timeout = timeout

    def upload(self, record_type: str, payload: Dict[str, Any]):
        self.upload_batch([(record_type, payload)])

    def upload_batch(self, records: Iterable[Tuple[str, Dict[str, Any]]]):
        batch: List[Tuple[str, Dict[str, Any]]] = list(records)
        if not batch:
            return

        body = gzip.compress(
            json.dumps(
                {
                    "records": [
                        {"type": record_type, "payload": payload}
                        for record_type, payload in batch
                    ]
                },
                ensure_ascii=False,
            ).encode("utf-8")
        )
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Content-Encoding": "gzip",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                code = resp.getcode()
                if code < 200 or code >= 300:
                    raise RuntimeError(f"http status {code}")
        except urllib.error.URLError as exc:
            raise RuntimeError(str(exc)) from exc
