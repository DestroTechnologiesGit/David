#!/usr/bin/env python3
"""Local dev server for OpenClaw Studio.

Serves index.html and proxies /openclaw-api/* to the gateway, mirroring what
Caddy does on the VPS. Same-origin, so the browser's CORS rules are satisfied
(the gateway sends no CORS headers of its own).

    python3 serve.py                 # http://127.0.0.1:8080
    python3 serve.py --port 9000
    python3 serve.py --gateway http://127.0.0.1:18789
"""

import argparse
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

API_PREFIX = "/openclaw-api"
UI_FILE = Path(__file__).resolve().parent / "index.html"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "OpenClawStudioDev/1.0"

    # ---- helpers -------------------------------------------------------
    def send_body(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_body(status, json.dumps({"error": message}).encode(),
                       "application/json; charset=utf-8")

    # ---- proxy ---------------------------------------------------------
    def proxy(self, method: str) -> None:
        target = urlparse(self.server.gateway)
        path = self.path[len(API_PREFIX):] or "/"

        length = int(self.headers.get("Content-Length", "0") or 0)
        payload = self.rfile.read(length) if length else None

        conn_cls = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
        # Agent replies can take minutes; do not cut them short.
        conn = conn_cls(target.hostname, target.port, timeout=self.server.timeout_s)

        headers = {}
        for key in ("Authorization", "Content-Type", "Accept"):
            if self.headers.get(key):
                headers[key] = self.headers[key]
        if payload is not None:
            headers["Content-Length"] = str(len(payload))

        try:
            conn.request(method, path, body=payload, headers=headers)
            upstream = conn.getresponse()
        except Exception as exc:                     # noqa: BLE001 - report any transport failure
            self.send_error_json(502, f"Cannot reach gateway at {self.server.gateway}: {exc}")
            return

        self.send_response(upstream.status)
        content_type = upstream.getheader("Content-Type", "application/octet-stream")
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        # Forward as it arrives so SSE tokens reach the page immediately.
        # readinto on a small buffer returns as soon as any bytes are available.
        buffer = bytearray(8192)
        try:
            while True:
                count = upstream.readinto(buffer)
                if not count:
                    break
                self.wfile.write(b"%X\r\n" % count + bytes(buffer[:count]) + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass                                      # browser navigated away
        finally:
            conn.close()

    # ---- routes --------------------------------------------------------
    def do_GET(self) -> None:
        if self.path.startswith(API_PREFIX):
            self.proxy("GET")
            return
        if not UI_FILE.is_file():
            self.send_error_json(500, f"index.html not found next to {Path(__file__).name}")
            return
        self.send_body(200, UI_FILE.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if self.path.startswith(API_PREFIX):
            self.proxy("POST")
            return
        self.send_error_json(404, "Not found")

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"  {fmt % args}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=int(os.environ.get("STUDIO_PORT", "8080")))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--gateway", default=os.environ.get("OPENCLAW_GATEWAY", "http://127.0.0.1:18789"))
    ap.add_argument("--timeout", type=float, default=600.0,
                    help="seconds to wait on the gateway (agent replies can be slow)")
    args = ap.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.gateway = args.gateway.rstrip("/")
    httpd.timeout_s = args.timeout

    url = f"http://{args.host}:{args.port}/"
    print(f"OpenClaw Studio  ->  {url}")
    print(f"proxying {API_PREFIX}/*  ->  {httpd.gateway}")
    print("\nIn the settings dialog use:")
    print(f"  Gateway base URL : {API_PREFIX}")
    print("  Gateway token    : your gateway.auth.token")
    print("  Agent target     : openclaw/default")
    print("\nCtrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
