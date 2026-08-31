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
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

API_PREFIX = "/openclaw-api"
# Docling converts the formats the browser cannot read (CSV, HTML, ePub).
# RapidOCR handles the scanned PDFs for which PDF.js finds no text. Both run
# in the same optional converter environment.
DOCLING_PYTHON = Path(os.environ.get(
    "DOCLING_PYTHON", Path(__file__).resolve().parent.parent / ".docling-venv" / "bin" / "python"))
DOCLING_TIMEOUT = float(os.environ.get("DOCLING_TIMEOUT", "180"))
DOCLING_MAX_BYTES = int(os.environ.get("DOCLING_MAX_BYTES", str(25 * 1024 * 1024)))
UI_DIR = Path(__file__).resolve().parent
UI_FILE = UI_DIR / "index.html"
BIOFORMER_MODEL = os.environ.get("BIOFORMER_MODEL", "bioformers/bioformer-8L")
BIOFORMER_LABEL = os.environ.get("BIOFORMER_LABEL", "bioformers/bioformer-8L")
BIOFORMER_MAX_RESULTS = int(os.environ.get("BIOFORMER_MAX_RESULTS", "10"))
BIOFORMER_MAX_BYTES = int(os.environ.get("BIOFORMER_MAX_BYTES", str(64 * 1024)))


class BioformerRanker:
    """Lazy CPU-only semantic ranker for Health/Clinical search results."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._lock = threading.Lock()
        self._tokenizer = None
        self._model = None
        self._torch = None

    def load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            import torch
            from transformers import AutoModel, AutoTokenizer

            # Production is configured with local_files_only after deployment,
            # so requests never trigger an unexpected model download.
            local_only = os.environ.get("BIOFORMER_LOCAL_ONLY", "0") == "1"
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name, local_files_only=local_only)
            self._model = AutoModel.from_pretrained(
                self.model_name, local_files_only=local_only)
            self._model.eval()
            self._torch = torch

    def rank(self, query: str, results: list[dict]) -> list[dict]:
        self.load()
        texts = [query]
        for result in results:
            title = str(result.get("title", ""))
            snippet = str(result.get("snippet", ""))
            texts.append(f"{title}. {snippet}".strip())

        encoded = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        with self._lock, self._torch.inference_mode():
            hidden = self._model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            pooled = self._torch.nn.functional.normalize(pooled, p=2, dim=1)
            scores = (pooled[1:] @ pooled[0]).tolist()

        ranked = []
        for position, (result, score) in enumerate(zip(results, scores)):
            item = dict(result)
            item["healthScore"] = round(float(score), 6)
            item["originalPosition"] = position
            ranked.append(item)
        ranked.sort(key=lambda item: (-item["healthScore"], item["originalPosition"]))
        for item in ranked:
            item.pop("originalPosition", None)
        return ranked


BIOFORMER = BioformerRanker(BIOFORMER_MODEL)

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
        route = self.path.split("?", 1)[0].rstrip("/")
        if route == "/convert":
            self.convert_document()
            return
        if route == "/health-rank":
            self.rank_health_results()
            return
        self.send_error_json(404, "Not found")

    def rank_health_results(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            self.send_error_json(400, "No ranking request was sent.")
            return
        if length > BIOFORMER_MAX_BYTES:
            self.rfile.read(length)
            self.send_error_json(413, "The ranking request is too large.")
            return

        try:
            payload = json.loads(self.rfile.read(length))
            query = str(payload.get("query", "")).strip()
            results = payload.get("results")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            self.send_error_json(400, "The ranking request is not valid JSON.")
            return

        if not query:
            self.send_error_json(400, "A health search query is required.")
            return
        if not isinstance(results, list) or not results:
            self.send_error_json(400, "At least one search result is required.")
            return

        clean = []
        for result in results[:BIOFORMER_MAX_RESULTS]:
            if not isinstance(result, dict):
                continue
            clean.append({
                "title": str(result.get("title", ""))[:200],
                "url": str(result.get("url", ""))[:2048],
                "snippet": str(result.get("snippet", ""))[:1000],
            })
        if not clean:
            self.send_error_json(400, "No valid search results were supplied.")
            return

        try:
            ranked = BIOFORMER.rank(query, clean)
        except Exception as exc:  # noqa: BLE001 - surface model startup/runtime errors
            self.send_error_json(503, f"Bioformer is unavailable: {exc}")
            return
        self.send_body(200, json.dumps({
            "model": BIOFORMER_LABEL,
            "results": ranked,
        }).encode("utf-8"), "application/json; charset=utf-8")

    def convert_document(self) -> None:
        """Convert an uploaded document to Markdown with Docling.

        The page parses digital PDFs, .docx and plain text itself. Scanned PDFs
        and formats without a browser parser are sent here as a fallback.
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
        allowed = {".csv", ".html", ".htm", ".epub", ".xlsx", ".pptx", ".pdf"}
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
            if suffix == ".pdf":
                command = [str(DOCLING_PYTHON), str(UI_DIR / "ocr_pdf.py"), str(src)]
            else:
                script = (
                    "import sys\n"
                    "from docling.document_converter import DocumentConverter\n"
                    "print(DocumentConverter().convert(sys.argv[1])"
                    ".document.export_to_markdown())\n"
                )
                command = [str(DOCLING_PYTHON), "-c", script, str(src)]
            try:
                result = subprocess.run(
                    command,
                    capture_output=True, text=True, timeout=DOCLING_TIMEOUT)
            except subprocess.TimeoutExpired:
                self.send_error_json(504, "Converting that document timed out.")
                return

        if result.returncode != 0:
            detail = (result.stderr or "Conversion failed").strip().splitlines()
            # Docling is noisy on stderr; the last line is the useful part.
            action = "OCR" if suffix == ".pdf" else "conversion"
            self.send_error_json(422, f"Could not read {name} with {action}. {detail[-1][:200]}")
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

    if os.environ.get("BIOFORMER_PRELOAD", "1") == "1":
        def warm_bioformer() -> None:
            try:
                BIOFORMER.load()
                print(f"Bioformer ranker ready  ->  {BIOFORMER_LABEL}", flush=True)
            except Exception as exc:  # noqa: BLE001 - retry lazily on a request
                print(f"Bioformer preload failed: {exc}", flush=True)

        threading.Thread(target=warm_bioformer, daemon=True).start()

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
