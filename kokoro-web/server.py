#!/usr/bin/env python3
"""Small authenticated HTTP bridge for the local Kokoro TTS CLI."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import time


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
# Streaming plays as it generates, so a longer document is practical there.
MAX_STREAM_TEXT_LENGTH = int(os.environ.get("KOKORO_MAX_STREAM_TEXT_LENGTH", "10000"))
FRONTEND = Path(os.environ.get("KOKORO_FRONTEND", "/home/ubuntu/kokoro-frontend.html"))
OPENCLAW_CONFIG = Path(os.environ.get("OPENCLAW_CONFIG", "/home/ubuntu/.openclaw/openclaw.json"))
KOKORO = os.environ.get("KOKORO_BIN", "/home/ubuntu/.local/bin/kokoro-tts")
# How long to wait for the CLI to produce the next chunk before giving up.
STREAM_CHUNK_TIMEOUT = float(os.environ.get("KOKORO_STREAM_CHUNK_TIMEOUT", "180"))
SYNTHESIS_LOCK = threading.Lock()


def parse_wav(data: bytes) -> tuple[dict, bytes]:
    """Split a WAV file into its format fields and raw PCM frames."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Not a RIFF/WAVE file")

    fmt = None
    frames = b""
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset:offset + 4]
        (size,) = struct.unpack_from("<I", data, offset + 4)
        body = data[offset + 8:offset + 8 + size]
        if chunk_id == b"fmt ":
            audio_format, channels, rate, _, _, bits = struct.unpack_from("<HHIIHH", body, 0)
            # WAVE_FORMAT_EXTENSIBLE hides the real tag in the extension block;
            # unwrap it so downstream players see plain PCM or IEEE float.
            if audio_format == 0xFFFE and len(body) >= 26:
                (audio_format,) = struct.unpack_from("<H", body, 24)
            fmt = {
                "audio_format": audio_format,
                "channels": channels,
                "sample_rate": rate,
                "bits_per_sample": bits,
            }
        elif chunk_id == b"data":
            frames = body
        # Chunks are word-aligned, so an odd size carries a pad byte.
        offset += 8 + size + (size & 1)

    if fmt is None:
        raise ValueError("WAV file has no fmt chunk")
    return fmt, frames


def wav_header(fmt: dict, data_size: int) -> bytes:
    """Build a 44-byte WAV header. Streaming uses a placeholder data size.

    The format tag must match the samples being forwarded: Kokoro writes
    32-bit IEEE float (tag 3), not 16-bit PCM (tag 1). Declaring the wrong
    tag makes players decode noise or reject the stream outright.
    """
    channels = fmt["channels"]
    rate = fmt["sample_rate"]
    bits = fmt["bits_per_sample"]
    audio_format = fmt.get("audio_format", 1)
    block_align = channels * bits // 8
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, audio_format, channels, rate,
                      rate * block_align, block_align, bits)
        + b"data"
        + struct.pack("<I", data_size)
    )


def chunk_sort_key(path: Path) -> tuple:
    """Order chunk_001.wav, chunk_002.wav ... numerically, not lexically."""
    match = re.search(r"(\d+)", path.stem)
    return (int(match.group(1)) if match else 0, path.name)


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
        if self.path not in ("/api/tts", "/api/tts/stream"):
            self.send_json_error(404, "Not found")
            return
        supplied = self.headers.get("X-Kokoro-Key", "")
        if not supplied or not hmac.compare_digest(supplied, expected_token()):
            self.send_json_error(401, "Invalid API access token")
            return
        streaming = self.path == "/api/tts/stream"
        max_text = MAX_STREAM_TEXT_LENGTH if streaming else MAX_TEXT_LENGTH
        try:
            length = int(self.headers.get("Content-Length", "0"))
            # A character can take several bytes once JSON-escaped (CJK and
            # emoji especially), so allow generous headroom over the text limit.
            if length <= 0 or length > max_text * 12 + 2_000:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length))
            text = str(payload.get("text", "")).strip()
            voice = str(payload.get("voice", "af_sarah"))
            language = str(payload.get("language", "en-us"))
            speed = float(payload.get("speed", 1.0))
            if not text or len(text) > max_text:
                raise ValueError(f"Text must contain 1-{max_text} characters")
            if not 0.5 <= speed <= 2.0:
                raise ValueError("Speed must be between 0.5 and 2.0")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json_error(400, str(exc))
            return

        if streaming:
            self.stream_synthesis(text, voice, language, speed)
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

    def stream_synthesis(self, text: str, voice: str, language: str, speed: float) -> None:
        """Synthesise with --split-output and forward each chunk as it lands.

        The CLI writes chunk_001.wav, chunk_002.wav ... into a chapter directory
        as it works. Watching that directory lets playback start on the first
        chunk instead of waiting for the whole document. Each chunk is a
        complete WAV, so headers are stripped and only PCM frames are appended
        to the single header sent up front.
        """
        tmp = tempfile.mkdtemp(prefix="kokoro-stream-")
        process = None
        headers_sent = False
        fmt = None
        sent_files: set[str] = set()

        try:
            with SYNTHESIS_LOCK:
                input_path = Path(tmp) / "input.txt"
                output_dir = Path(tmp) / "chunks"
                input_path.write_text(text, encoding="utf-8")

                process = subprocess.Popen(
                    [KOKORO, str(input_path), "--split-output", str(output_dir),
                     "--format", "wav", "--lang", language, "--voice", voice,
                     "--speed", str(speed)],
                    cwd=tmp,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                last_progress = time.monotonic()
                while True:
                    ready = []
                    if output_dir.is_dir():
                        for path in sorted(output_dir.rglob("chunk_*.wav"), key=chunk_sort_key):
                            if path.name in sent_files:
                                continue
                            # A chunk still being written has no final size yet;
                            # take it only once it stops growing.
                            size = path.stat().st_size
                            if size == 0:
                                continue
                            time.sleep(0.05)
                            if path.stat().st_size != size:
                                continue
                            ready.append(path)

                    for path in ready:
                        try:
                            chunk_fmt, frames = parse_wav(path.read_bytes())
                        except ValueError:
                            continue
                        if not frames:
                            sent_files.add(path.name)
                            continue

                        if not headers_sent:
                            fmt = chunk_fmt
                            self.send_response(200)
                            self.send_header("Content-Type", "audio/wav")
                            self.send_header("Cache-Control", "no-store")
                            self.send_header("X-Content-Type-Options", "nosniff")
                            self.send_header("Transfer-Encoding", "chunked")
                            self.end_headers()
                            # Streaming length is unknown up front, so declare the
                            # maximum; players read until the connection closes.
                            self.write_chunked(wav_header(fmt, 0xFFFFFFFF - 36))
                            headers_sent = True
                        elif (chunk_fmt["sample_rate"] != fmt["sample_rate"]
                              or chunk_fmt["channels"] != fmt["channels"]
                              or chunk_fmt["bits_per_sample"] != fmt["bits_per_sample"]
                              or chunk_fmt["audio_format"] != fmt["audio_format"]):
                            # Format shifts mid-stream would corrupt playback.
                            raise RuntimeError("Audio format changed mid-stream")

                        self.write_chunked(frames)
                        sent_files.add(path.name)
                        last_progress = time.monotonic()

                    if process.poll() is not None:
                        # Drain whatever the final pass produced, then stop.
                        if not ready and not self.pending_chunks(output_dir, sent_files):
                            break
                    elif time.monotonic() - last_progress > STREAM_CHUNK_TIMEOUT:
                        raise TimeoutError("Timed out waiting for the next audio chunk")

                    if not ready:
                        time.sleep(0.1)

                code = process.wait()
                if not headers_sent:
                    detail = (process.stderr.read() or process.stdout.read()
                              or "Synthesis produced no audio")[-1000:]
                    raise RuntimeError(detail if code != 0 else "Synthesis produced no audio")

            # Terminating zero-length chunk closes the chunked response.
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()

        except (BrokenPipeError, ConnectionResetError):
            # The listener navigated away; stop synthesising for them.
            pass
        except Exception as exc:
            if headers_sent:
                # Mid-stream failure: close the response, the client hears a short clip.
                try:
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                except OSError:
                    pass
            else:
                message = "Speech generation timed out" if isinstance(exc, TimeoutError) else str(exc)
                status = 504 if isinstance(exc, TimeoutError) else 500
                self.send_json_error(status, f"Speech generation failed: {message}"
                                     if status == 500 else message)
        finally:
            if process and process.poll() is None:
                process.kill()
                process.wait()
            shutil.rmtree(tmp, ignore_errors=True)

    @staticmethod
    def pending_chunks(output_dir: Path, sent_files: set[str]) -> bool:
        """True when the CLI left chunk files we have not forwarded yet."""
        if not output_dir.is_dir():
            return False
        return any(p.name not in sent_files for p in output_dir.rglob("chunk_*.wav"))

    def write_chunked(self, payload: bytes) -> None:
        """Write one HTTP chunked-transfer frame."""
        if not payload:
            return
        self.wfile.write(f"{len(payload):X}\r\n".encode("ascii"))
        self.wfile.write(payload)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
