#!/usr/bin/env python3
"""Small authenticated HTTP bridge for the local Kokoro TTS CLI."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading


def load_dotenv(path: Path) -> None:
    """Populate os.environ from a simple KEY=VALUE file, without overriding."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_dotenv(Path(os.environ.get("KOKORO_ENV_FILE", Path(__file__).resolve().parent / ".env")))

HOST = os.environ.get("KOKORO_HOST", "127.0.0.1")
PORT = int(os.environ.get("KOKORO_PORT", "8890"))
MAX_TEXT_LENGTH = int(os.environ.get("KOKORO_MAX_TEXT_LENGTH", "5000"))
FRONTEND = Path(os.environ.get("KOKORO_FRONTEND", "/home/ubuntu/kokoro-frontend.html"))
OPENCLAW_CONFIG = Path(os.environ.get("OPENCLAW_CONFIG", "/home/ubuntu/.openclaw/openclaw.json"))
KOKORO = os.environ.get("KOKORO_BIN", "/home/ubuntu/.local/bin/kokoro-tts")
SYNTHESIS_LOCK = threading.Lock()


def expected_token() -> str:
    config = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
    return config["gateway"]["auth"]["token"]


class Handler(BaseHTTPRequestHandler):
    server_version = "KokoroWeb/1.0"

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_json_error(self, status: int, message: str) -> None:
        self.send_bytes(
            status,
            json.dumps({"error": message}).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self.send_json_error(404, "Not found")
            return
        self.send_bytes(200, FRONTEND.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if self.path != "/api/tts":
            self.send_json_error(404, "Not found")
            return
        supplied = self.headers.get("X-Kokoro-Key", "")
        if not supplied or not hmac.compare_digest(supplied, expected_token()):
            self.send_json_error(401, "Invalid API access token")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20_000:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length))
            text = str(payload.get("text", "")).strip()
            voice = str(payload.get("voice", "af_sarah"))
            language = str(payload.get("language", "en-us"))
            speed = float(payload.get("speed", 1.0))
            if not text or len(text) > MAX_TEXT_LENGTH:
                raise ValueError(f"Text must contain 1-{MAX_TEXT_LENGTH} characters")
            if not 0.5 <= speed <= 2.0:
                raise ValueError("Speed must be between 0.5 and 2.0")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json_error(400, str(exc))
            return

        try:
            with SYNTHESIS_LOCK, tempfile.TemporaryDirectory(prefix="kokoro-web-") as tmp:
                input_path = Path(tmp) / "input.txt"
                output_path = Path(tmp) / "speech.wav"
                input_path.write_text(text, encoding="utf-8")
                result = subprocess.run(
                    [KOKORO, str(input_path), str(output_path), "--lang", language,
                     "--voice", voice, "--speed", str(speed)],
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0 or not output_path.exists():
                    detail = (result.stderr or result.stdout or "Synthesis failed")[-1000:]
                    raise RuntimeError(detail)
                audio = output_path.read_bytes()
            self.send_bytes(200, audio, "audio/wav")
        except subprocess.TimeoutExpired:
            self.send_json_error(504, "Speech generation timed out")
        except Exception as exc:
            self.send_json_error(500, f"Speech generation failed: {exc}")

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
