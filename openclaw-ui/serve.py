#!/usr/bin/env python3
"""Local dev server for LiveContent Studio.

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
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

API_PREFIX = "/openclaw-api"
# Docling converts the formats the browser cannot read (CSV, HTML, ePub).
# Optional: without it those formats are simply refused, and PDF/.docx/.txt
# keep working in the browser as before.
DOCLING_PYTHON = Path(os.environ.get(
    "DOCLING_PYTHON", Path(__file__).resolve().parent.parent / ".docling-venv" / "bin" / "python"))
DOCLING_TIMEOUT = float(os.environ.get("DOCLING_TIMEOUT", "180"))
DOCLING_MAX_BYTES = int(os.environ.get("DOCLING_MAX_BYTES", str(25 * 1024 * 1024)))
UI_DIR = Path(__file__).resolve().parent
UI_FILE = UI_DIR / "index.html"

# The page's own stylesheet and script. Anything else still falls through to
# index.html so deep links keep working.
STATIC_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    # PDF.js ships as ES modules; browsers refuse a module served as anything
    # other than a JavaScript MIME type.
    ".mjs": "text/javascript; charset=utf-8",
    # library.html is a real second page, so it must be served as itself
    # rather than falling through to index.html.
    ".html": "text/html; charset=utf-8",
}


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
        # Pass through OpenClaw's own controls (model/agent/session overrides)
        # rather than silently dropping them.
        for key, value in self.headers.items():
            if key.lower().startswith("x-openclaw-"):
                headers[key] = value
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
        asset = self.static_asset()
        if asset is not None:
            path, content_type = asset
            self.send_body(200, path.read_bytes(), content_type)
            return
        if not UI_FILE.is_file():
            self.send_error_json(500, f"index.html not found next to {Path(__file__).name}")
            return
        self.send_body(200, UI_FILE.read_bytes(), "text/html; charset=utf-8")

    def static_asset(self):
        """Resolve the request to a static file under the UI directory, or None.

        Files sit either next to index.html or in vendor/ (the PDF.js build).
        The page refers to its assets as /studio/... because that is where Caddy
        serves them in production; here that prefix is simply stripped.
        """
        path = urlparse(self.path).path
        content_type = STATIC_TYPES.get(Path(path).suffix)
        if not content_type:
            return None
        relative = path.lstrip("/")
        if relative.startswith("studio/"):
            relative = relative[len("studio/"):]
        candidate = (UI_DIR / relative).resolve()
        # Confine the result to UI_DIR so no "../" can escape it.
        if not candidate.is_file():
            return None
        if UI_DIR.resolve() not in candidate.parents:
            return None
        return candidate, content_type

    def do_POST(self) -> None:
        if self.path.startswith(API_PREFIX):
            self.proxy("POST")
            return
        if self.path.split("?", 1)[0].rstrip("/") == "/convert":
            self.convert_document()
            return
        self.send_error_json(404, "Not found")

    def convert_document(self) -> None:
        """Convert an uploaded document to Markdown with Docling.

        The page parses PDF, .docx and plain text itself; this handles only
        what it cannot, so most documents still never leave the browser.
        """
        if not DOCLING_PYTHON.exists():
            self.send_error_json(503, (
                "Document conversion is not available. Install Docling and "
                "point DOCLING_PYTHON at its interpreter."))
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            self.send_error_json(400, "No file was sent.")
            return
        if length > DOCLING_MAX_BYTES:
            self.send_error_json(
                413, f"That file is larger than {DOCLING_MAX_BYTES // (1024 * 1024)} MB.")
            return

        # Only the formats the browser cannot parse itself are accepted here,
        # regardless of what a caller claims in the header.
        allowed = {".csv", ".html", ".htm", ".epub", ".xlsx", ".pptx"}
        name = self.headers.get("X-Filename", "document")
        suffix = Path(name).suffix.lower()
        if suffix not in allowed:
            # Body must still be drained, or the next request on this
            # keep-alive connection would read leftover bytes as its own.
            self.rfile.read(length)
            self.send_error_json(415, f"Unsupported file type: {suffix or name}")
            return
        payload = self.rfile.read(length)

        with tempfile.TemporaryDirectory(prefix="docling-") as tmp:
            src = Path(tmp) / ("input" + suffix)
            src.write_bytes(payload)
            script = (
                "import sys\n"
                "from docling.document_converter import DocumentConverter\n"
                "print(DocumentConverter().convert(sys.argv[1])"
                ".document.export_to_markdown())\n"
            )
            try:
                result = subprocess.run(
                    [str(DOCLING_PYTHON), "-c", script, str(src)],
                    capture_output=True, text=True, timeout=DOCLING_TIMEOUT)
            except subprocess.TimeoutExpired:
                self.send_error_json(504, "Converting that document timed out.")
                return

        if result.returncode != 0:
            detail = (result.stderr or "Conversion failed").strip().splitlines()
            # Docling is noisy on stderr; the last line is the useful part.
            self.send_error_json(422, f"Could not read {name}. {detail[-1][:200]}")
            return

        text = result.stdout.strip()
        if not text:
            self.send_error_json(422, f"No text could be read from {name}.")
            return
        self.send_body(200, json.dumps({"text": text}).encode("utf-8"),
                       "application/json; charset=utf-8")

    def handle_one_request(self) -> None:
        # Browsers open speculative keep-alive sockets and drop them without
        # sending anything. That is normal, not an error worth a traceback.
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError, TimeoutError):
            self.close_connection = True

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"  {fmt % args}", flush=True)


class DevServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        # Only report real faults; a peer hanging up is routine.
        import sys
        import traceback
        exc = sys.exception()
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, TimeoutError)):
            return
        traceback.print_exc()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=int(os.environ.get("STUDIO_PORT", "8080")))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--gateway", default=os.environ.get("OPENCLAW_GATEWAY", "http://127.0.0.1:18789"))
    ap.add_argument("--timeout", type=float, default=600.0,
                    help="seconds to wait on the gateway (agent replies can be slow)")
    args = ap.parse_args()

    httpd = DevServer((args.host, args.port), Handler)
    httpd.gateway = args.gateway.rstrip("/")
    httpd.timeout_s = args.timeout

    url = f"http://{args.host}:{args.port}/"
    print(f"LiveContent Studio  ->  {url}")
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
