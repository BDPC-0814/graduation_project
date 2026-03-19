import argparse
import gzip
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--fail-first", type=int, default=0, help="Return HTTP 500 for the first N POST requests.")
    parser.add_argument("--fail-every", type=int, default=0, help="Return HTTP 500 for every Nth POST request.")
    parser.add_argument("--log-file", default="experiments/mock_ingest/server_log.jsonl")
    parser.add_argument("--stop-after", type=int, default=0, help="Stop after handling N POST requests.")
    return parser.parse_args()


class MockIngestHandler(BaseHTTPRequestHandler):
    server_version = "MockIngest/1.0"

    def do_POST(self):
        server = self.server
        server.request_count += 1
        request_id = server.request_count

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        encoding = self.headers.get("Content-Encoding", "").lower()

        try:
            body = gzip.decompress(raw_body) if encoding == "gzip" else raw_body
            payload = json.loads(body.decode("utf-8"))
            records = payload.get("records", [])
            parse_error = None
        except Exception as exc:  # noqa: BLE001
            payload = None
            records = []
            parse_error = str(exc)

        should_fail = False
        if server.fail_first > 0 and request_id <= server.fail_first:
            should_fail = True
        if server.fail_every > 0 and request_id % server.fail_every == 0:
            should_fail = True
        if parse_error is not None:
            should_fail = True

        record = {
            "request_id": request_id,
            "path": self.path,
            "timestamp": time.time(),
            "content_encoding": encoding or "identity",
            "content_length": content_length,
            "record_count": len(records),
            "status": 500 if should_fail else 200,
            "parse_error": parse_error,
            "sample_types": sorted({item.get("type", "unknown") for item in records}) if records else [],
        }
        server.append_log(record)

        if should_fail:
            response = {
                "ok": False,
                "request_id": request_id,
                "error": parse_error or "mock failure",
            }
            self.send_response(500)
        else:
            response = {
                "ok": True,
                "request_id": request_id,
                "records": len(records),
            }
            self.send_response(200)

        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

        if server.stop_after > 0 and request_id >= server.stop_after:
            threading.Thread(target=server.shutdown, daemon=True).start()

    def log_message(self, format, *args):  # noqa: A003
        return


class MockIngestServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, fail_first: int, fail_every: int, log_file: Path, stop_after: int):
        super().__init__(server_address, handler_class)
        self.fail_first = fail_first
        self.fail_every = fail_every
        self.log_file = log_file
        self.stop_after = stop_after
        self.request_count = 0
        self._log_lock = threading.Lock()
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def append_log(self, record: dict):
        line = json.dumps(record, ensure_ascii=False)
        with self._log_lock:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


def main():
    args = parse_args()
    server = MockIngestServer(
        (args.host, args.port),
        MockIngestHandler,
        fail_first=args.fail_first,
        fail_every=args.fail_every,
        log_file=Path(args.log_file),
        stop_after=args.stop_after,
    )
    print(
        f"[mock-ingest] listening on http://{args.host}:{args.port} "
        f"fail_first={args.fail_first} fail_every={args.fail_every} log={args.log_file}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("[mock-ingest] stopped")


if __name__ == "__main__":
    main()
