#!/usr/bin/env python3
"""Small authenticated HTTP bridge for the local Kokoro TTS CLI."""

import argparse
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
MAX_STREAM_TEXT_LENGTH = int(os.environ.get("KOKORO_MAX_STREAM_TEXT_LENGTH", "5000"))
FRONTEND = Path(os.environ.get("KOKORO_FRONTEND", "/home/ubuntu/kokoro-frontend.html"))
# API reference served at /docs. Ships beside this file.
API_DOCS = Path(os.environ.get(
    "KOKORO_API_DOCS", Path(__file__).resolve().parent / "API.md"))
# The page's stylesheet and script, served from beside the HTML file.
FRONTEND_ASSETS = {
    "kokoro-app.css": "text/css; charset=utf-8",
    "kokoro-classic.css": "text/css; charset=utf-8",
    "kokoro-app.js": "text/javascript; charset=utf-8",
}
OPENCLAW_CONFIG = Path(os.environ.get("OPENCLAW_CONFIG", "/home/ubuntu/.openclaw/openclaw.json"))
KOKORO = os.environ.get("KOKORO_BIN", "/home/ubuntu/.local/bin/kokoro-tts")
# How long to wait for the CLI to produce the next chunk before giving up.
STREAM_CHUNK_TIMEOUT = float(os.environ.get("KOKORO_STREAM_CHUNK_TIMEOUT", "180"))
CONTENT_TYPES = {"wav": "audio/wav", "mp3": "audio/mpeg"}
# Comma-separated origins allowed to call the API from a browser. "*" allows
# any origin; empty disables CORS entirely (same-origin use only).
DEFAULT_VOICE = os.environ.get("KOKORO_DEFAULT_VOICE", "af_sarah")
DEFAULT_LANGUAGE = os.environ.get("KOKORO_DEFAULT_LANGUAGE", "en-us")
EDGE_VOICE = "edge:auto"
EDGE_TTS_PYTHON = Path(os.environ.get(
    "EDGE_TTS_PYTHON", "/home/ubuntu/.livecontent-edge-tts-venv/bin/python"))
EDGE_TTS_HELPER = Path(os.environ.get(
    "EDGE_TTS_HELPER", Path(__file__).resolve().parent / "edge_tts_helper.py"))
FFMPEG = shutil.which("ffmpeg")
# Base language codes currently exposed by the installed edge-tts voice catalog.
# Keeping this local makes Studio's voice picker instant; synthesis still verifies
# the requested language against the live catalog before creating the file.
EDGE_LANGUAGES = sorted({
    "af", "am", "ar", "az", "bg", "bn", "bs", "ca", "cs", "cy", "da", "de",
    "el", "en", "es", "et", "fa", "fi", "fil", "fr", "ga", "gl", "gu", "he",
    "hi", "hr", "hu", "id", "is", "it", "iu", "ja", "jv", "ka", "kk", "km",
    "kn", "ko", "lo", "lt", "lv", "mk", "ml", "mn", "mr", "ms", "mt", "my",
    "nb", "ne", "nl", "pl", "ps", "pt", "ro", "ru", "si", "sk", "sl", "so",
    "sq", "sr", "su", "sv", "sw", "ta", "te", "th", "tr", "uk", "ur", "uz",
    "vi", "zh", "zu",
})

# The voice inventory, grouped by the language code each voice is trained
# for. Mirrors kokoro-tts; /api/voices serves it so callers need not hardcode.
VOICES = {
    "en-us": ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica",
              "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah",
              "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir",
              "am_liam", "am_michael", "am_onyx", "am_puck"],
    "en-gb": ["bf_alice", "bf_emma", "bf_isabella", "bf_lily",
              "bm_daniel", "bm_fable", "bm_george", "bm_lewis"],
    "fr-fr": ["ff_siwis"],
    "it": ["if_sara", "im_nicola"],
    "ja": ["jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo"],
    "cmn": ["zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
            "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang"],
    "es": ["ef_dora", "em_alex", "em_santa"],
    "hi": ["hf_alpha", "hf_beta", "hm_omega", "hm_psi"],
}

CORS_ORIGINS = [
    o.strip() for o in os.environ.get("KOKORO_CORS_ORIGINS", "*").split(",") if o.strip()
]
SYNTHESIS_LOCK = threading.Lock()


def edge_tts_available() -> bool:
    """Return whether the isolated online speech adapter can be launched."""
    return EDGE_TTS_PYTHON.is_file() and EDGE_TTS_HELPER.is_file()


def edge_language_codes() -> list[str]:
    """Return downloadable online voice languages without a network lookup."""
    return EDGE_LANGUAGES if edge_tts_available() else []


def synthesize_edge_tts(text_path: Path, output_path: Path, language: str,
                        speed: float, audio_format: str) -> None:
    """Generate downloadable online speech, converting MP3 to WAV if requested."""
    if not edge_tts_available():
        raise RuntimeError("The downloadable multilingual voice is not installed")
    edge_output = output_path if audio_format == "mp3" else output_path.with_suffix(".edge.mp3")
    result = subprocess.run(
        [str(EDGE_TTS_PYTHON), str(EDGE_TTS_HELPER),
         "--text-file", str(text_path), "--output", str(edge_output),
         "--language", language, "--speed", str(speed)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0 or not edge_output.is_file():
        detail = (result.stderr or result.stdout or "Online speech synthesis failed")[-1000:]
        raise RuntimeError(detail)
    if audio_format == "wav":
        if not FFMPEG:
            raise RuntimeError("ffmpeg is required to create downloadable WAV audio")
        conversion = subprocess.run(
            [FFMPEG, "-v", "error", "-y", "-i", str(edge_output),
             "-acodec", "pcm_s16le", str(output_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if conversion.returncode != 0 or not output_path.is_file():
            detail = (conversion.stderr or conversion.stdout or "WAV conversion failed")[-1000:]
            raise RuntimeError(detail)


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


MPEG_BITRATES_V1_L3 = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0)
MPEG_BITRATES_V2_L3 = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0)
MPEG_RATES = {0: (11025, 12000, 8000), 2: (22050, 24000, 16000), 3: (44100, 48000, 32000)}


def mpeg_frame_length(header: bytes) -> int:
    """Byte length of the MPEG audio frame described by a 4-byte header."""
    if len(header) < 4 or header[0] != 0xFF or (header[1] & 0xE0) != 0xE0:
        return 0
    version = (header[1] >> 3) & 0x03      # 3 = MPEG1, 2 = MPEG2, 0 = MPEG2.5
    layer = (header[1] >> 1) & 0x03        # 1 = Layer III
    bitrate_index = (header[2] >> 4) & 0x0F
    rate_index = (header[2] >> 2) & 0x03
    padding = (header[2] >> 1) & 0x01
    if layer != 1 or version == 1 or bitrate_index in (0, 15) or rate_index == 3:
        return 0
    table = MPEG_BITRATES_V1_L3 if version == 3 else MPEG_BITRATES_V2_L3
    bitrate = table[bitrate_index] * 1000
    sample_rate = MPEG_RATES[version][rate_index]
    if not bitrate or not sample_rate:
        return 0
    samples = 1152 if version == 3 else 576
    return int(samples // 8 * bitrate // sample_rate) + padding


def strip_mp3_metadata(data: bytes, drop_id3: bool = True) -> bytes:
    """Remove an ID3v2 tag and any leading Xing/Info header frame.

    Encoders put a Xing/Info frame at the start of every file. It carries no
    audio, but a decoder plays it as a short silence, so leaving one at the
    head of each concatenated chunk inserts gaps and glitches between chunks.
    """
    offset = 0
    if drop_id3 and len(data) >= 10 and data[:3] == b"ID3":
        # Size is 4 syncsafe bytes: 7 bits each.
        size = 0
        for byte in data[6:10]:
            size = (size << 7) | (byte & 0x7F)
        offset = 10 + size

    # Skip a leading Xing/Info frame if the first frame is one.
    length = mpeg_frame_length(data[offset:offset + 4])
    if length:
        frame = data[offset:offset + length]
        if b"Xing" in frame[:48] or b"Info" in frame[:48]:
            offset += length

    return data[offset:]


def chunk_sort_key(path: Path) -> tuple:
    """Order chunk_001, chunk_002 ... numerically, not lexically."""
    match = re.search(r"(\d+)", path.stem)
    return (int(match.group(1)) if match else 0, path.name)


def cli_path() -> str | None:
    """Resolve KOKORO_BIN to a real executable, via PATH for a bare name."""
    if os.sep in KOKORO or (os.altsep and os.altsep in KOKORO):
        return KOKORO if os.access(KOKORO, os.X_OK) else None
    return shutil.which(KOKORO)


def expected_token() -> str:
    """The token callers must present.

    KOKORO_API_TOKEN wins so the service can run on any host. The OpenClaw
    config is only a fallback, for the original deployment where the two
    services share one token.
    """
    token = os.environ.get("KOKORO_API_TOKEN", "").strip()
    if token:
        return token
    try:
        config = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
        return config["gateway"]["auth"]["token"]
    except (OSError, ValueError, KeyError) as exc:
        raise RuntimeError(
            "No API token configured. Set KOKORO_API_TOKEN, or point "
            f"OPENCLAW_CONFIG at a readable OpenClaw config ({exc})."
        ) from exc


DOCS_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0 auto; padding: 48px 24px 96px; max-width: 820px;
  font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
        "Helvetica Neue", Arial, sans-serif;
  color: #10132b; background: #ffffff;
}
h1, h2, h3 { line-height: 1.25; margin: 2em 0 .6em; font-weight: 600; }
h1 { font-size: 2em; margin-top: 0; letter-spacing: -.5px; }
h2 { font-size: 1.4em; padding-bottom: .3em; border-bottom: 1px solid #e2e6f5; }
h3 { font-size: 1.1em; }
p, ul, ol { margin: 0 0 1em; }
li { margin: .25em 0; }
a { color: #3730d8; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .88em; padding: .15em .4em; border-radius: 5px;
  background: #eef1fb; color: #2a2f52;
}
pre {
  margin: 0 0 1.2em; padding: 16px 18px; border-radius: 10px;
  background: #14162e; color: #e6e8f5; overflow-x: auto;
}
pre code { padding: 0; background: none; color: inherit; font-size: .85em; }
table { width: 100%; border-collapse: collapse; margin: 0 0 1.4em; font-size: .93em; }
th, td { padding: 9px 12px; border: 1px solid #e2e6f5; text-align: left; vertical-align: top; }
th { background: #f5f7ff; font-weight: 600; }
blockquote {
  margin: 0 0 1.2em; padding: 2px 16px; color: #565b7e;
  border-left: 3px solid #c9cfe8;
}
hr { border: none; border-top: 1px solid #e2e6f5; margin: 2em 0; }
@media (prefers-color-scheme: dark) {
  body { background: #101223; color: #e7e9f5; }
  h2 { border-bottom-color: #272a45; }
  code { background: #1d2039; color: #cdd2ee; }
  th, td { border-color: #272a45; }
  th { background: #191c33; }
  a { color: #9aa2ff; }
  blockquote { color: #a3a9c9; border-left-color: #383d61; }
  hr { border-top-color: #272a45; }
}
"""


def render_markdown(text: str) -> str:
    """Render the API reference to HTML.

    Deliberately small: it covers only what API.md uses. Everything is
    HTML-escaped first, so document content can never inject markup.
    """
    import html as html_mod

    def inline(chunk: str) -> str:
        chunk = html_mod.escape(chunk, quote=False)
        chunk = re.sub(r"`([^`]+)`", r"<code>\1</code>", chunk)
        chunk = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", chunk)
        chunk = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', chunk)
        return chunk

    out: list[str] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code: emitted verbatim, escaped, with no inline parsing.
        if line.startswith("```"):
            i += 1
            body = []
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(html_mod.escape(lines[i], quote=False))
                i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(body) + "</code></pre>")
            continue

        # Tables: a header row followed by a |---| separator.
        if (line.startswith("|") and i + 1 < len(lines)
                and set(lines[i + 1].replace("|", "").strip()) <= set("-: ")
                and "-" in lines[i + 1]):
            def cells(row: str) -> list[str]:
                return [c.strip() for c in row.strip().strip("|").split("|")]

            head = cells(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            html_rows = ["<tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"]
            for row in rows:
                html_rows.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
            out.append("<table>" + "".join(html_rows) + "</table>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        if line.startswith(">"):
            body = []
            while i < len(lines) and lines[i].startswith(">"):
                body.append(lines[i].lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + inline(" ".join(body)) + "</blockquote>")
            continue

        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue

        if not line.strip():
            i += 1
            continue

        # Paragraph: consume until a blank line or a block-level marker.
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|```|\||>|\s*[-*]\s)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")

    title = "Kokoro TTS API"
    match = re.search(r"^#\s+(.+)$", text, re.M)
    if match:
        title = match.group(1).strip()
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{html_mod.escape(title)}</title><style>{DOCS_CSS}</style>"
        "</head><body>" + "".join(out) + "</body></html>"
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "KokoroWeb/1.0"

    def cors_origin(self) -> str:
        """The value to echo in Access-Control-Allow-Origin, or "" for none."""
        if not CORS_ORIGINS:
            return ""
        origin = self.headers.get("Origin", "")
        if "*" in CORS_ORIGINS:
            # Echo the caller's origin so credentialed requests still work.
            return origin or "*"
        return origin if origin in CORS_ORIGINS else ""

    def send_cors_headers(self) -> None:
        origin = self.cors_origin()
        if not origin:
            return
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, X-Kokoro-Key",
        )
        self.send_header("Access-Control-Max-Age", "86400")

    def authorized(self) -> bool:
        """Accept an Authorization: Bearer token or the legacy header."""
        try:
            expected = expected_token()
        except RuntimeError as exc:
            self.send_json_error(500, str(exc))
            return False
        header = self.headers.get("Authorization", "")
        supplied = ""
        if header.lower().startswith("bearer "):
            supplied = header[7:].strip()
        if not supplied:
            supplied = self.headers.get("X-Kokoro-Key", "")
        if not supplied or not hmac.compare_digest(supplied, expected):
            self.send_json_error(401, "Invalid API access token")
            return False
        return True

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        """CORS preflight for cross-origin API callers."""
        self.send_response(204)
        self.send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_json_error(self, status: int, message: str) -> None:
        self.send_bytes(
            status,
            json.dumps({"error": message}).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def api_path(self) -> str:
        """The request path reduced to its known-route part.

        A reverse proxy may or may not strip its mount prefix, so
        /kokoro/api/tts and /api/tts are treated the same, as are
        /kokoro/docs and /docs.
        """
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        for route in ("/api", "/docs"):
            index = path.find(route)
            if index > 0:
                return path[index:]
        return path

    def send_json(self, status: int, payload: dict) -> None:
        self.send_bytes(
            status,
            json.dumps(payload, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def do_GET(self) -> None:
        path = self.api_path()

        # ---- Human-readable API reference ----
        if path == "/docs":
            if not API_DOCS.is_file():
                self.send_json_error(404, f"API docs not found at {API_DOCS}")
                return
            text = API_DOCS.read_text(encoding="utf-8")
            # ?raw=1 serves the Markdown source, for tooling.
            if "raw" in self.path.split("?", 1)[-1] and "?" in self.path:
                self.send_bytes(200, text.encode("utf-8"),
                                "text/markdown; charset=utf-8")
                return
            self.send_bytes(200, render_markdown(text).encode("utf-8"),
                            "text/html; charset=utf-8")
            return

        # ---- API: discovery and metadata (no token required) ----
        if path == "/api":
            self.send_json(200, {
                "service": "kokoro-tts",
                "version": "1.0",
                "endpoints": {
                    "GET /docs": "Human-readable API reference.",
                    "GET /api": "This description.",
                    "GET /api/health": "Liveness check.",
                    "GET /api/voices": "Voices grouped by language code.",
                    "POST /api/tts": "Synthesize text, returns a complete audio file.",
                    "POST /api/tts/stream": "Synthesize text, streamed as it is produced.",
                },
                "auth": "Authorization: Bearer <token>",
                "request": {
                    "text": "string, required",
                    "voice": f"string, default {DEFAULT_VOICE}",
                    "language": f"string, default {DEFAULT_LANGUAGE}",
                    "speed": "number 0.5-2.0, default 1.0",
                    "format": "wav or mp3, default wav",
                },
                "limits": {
                    "max_text_length": MAX_TEXT_LENGTH,
                    "max_stream_text_length": MAX_STREAM_TEXT_LENGTH,
                },
            })
            return

        if path == "/api/health":
            resolved = cli_path()
            self.send_json(200, {
                "status": "ok" if resolved else "degraded",
                "cli": resolved or KOKORO,
                "cli_present": bool(resolved),
                "online_tts_present": edge_tts_available(),
            })
            return

        if path == "/api/voices":
            self.send_json(200, {
                "languages": sorted(VOICES),
                "voices": VOICES,
                "default_voice": DEFAULT_VOICE,
                "default_language": DEFAULT_LANGUAGE,
                "online_voice": EDGE_VOICE,
                "online_languages": edge_language_codes(),
            })
            return

        # Match on the bare filename so no path can escape the frontend's
        # directory, and so the /kokoro prefix is irrelevant here.
        name = self.path.split("?", 1)[0].rsplit("/", 1)[-1]
        content_type = FRONTEND_ASSETS.get(name)
        if content_type:
            asset = FRONTEND.parent / name
            if not asset.is_file():
                self.send_json_error(404, "Not found")
                return
            self.send_bytes(200, asset.read_bytes(), content_type)
            return
        if self.path.split("?", 1)[0] not in ("/", "/index.html"):
            self.send_json_error(404, "Not found")
            return
        self.send_bytes(200, FRONTEND.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        path = self.api_path()
        if path not in ("/api/tts", "/api/tts/stream"):
            self.send_json_error(404, "Not found")
            return
        if not self.authorized():
            return
        streaming = path == "/api/tts/stream"
        max_text = MAX_STREAM_TEXT_LENGTH if streaming else MAX_TEXT_LENGTH
        try:
            length = int(self.headers.get("Content-Length", "0"))
            # A character can take several bytes once JSON-escaped (CJK and
            # emoji especially), so allow generous headroom over the text limit.
            if length <= 0 or length > max_text * 12 + 2_000:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length))
            text = str(payload.get("text", "")).strip()
            voice = str(payload.get("voice", DEFAULT_VOICE))
            language = str(payload.get("language", DEFAULT_LANGUAGE))
            speed = float(payload.get("speed", 1.0))
            audio_format = str(payload.get("format", "wav")).lower()
            if audio_format not in ("wav", "mp3"):
                raise ValueError("Format must be either 'wav' or 'mp3'")
            if not text or len(text) > max_text:
                raise ValueError(f"Text must contain 1-{max_text} characters")
            if not 0.5 <= speed <= 2.0:
                raise ValueError("Speed must be between 0.5 and 2.0")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json_error(400, str(exc))
            return

        if streaming and voice == EDGE_VOICE:
            self.send_json_error(400, "The online multilingual voice supports complete downloads only")
            return
        if streaming:
            self.stream_synthesis(text, voice, language, speed, audio_format)
            return

        try:
            with SYNTHESIS_LOCK, tempfile.TemporaryDirectory(prefix="kokoro-web-") as tmp:
                input_path = Path(tmp) / "input.txt"
                output_path = Path(tmp) / f"speech.{audio_format}"
                input_path.write_text(text, encoding="utf-8")
                if voice == EDGE_VOICE:
                    synthesize_edge_tts(input_path, output_path, language, speed, audio_format)
                else:
                    result = subprocess.run(
                        [KOKORO, str(input_path), str(output_path), "--lang", language,
                         "--voice", voice, "--speed", str(speed),
                         "--format", audio_format],
                        cwd=tmp,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if result.returncode != 0 or not output_path.exists():
                        detail = (result.stderr or result.stdout or "Synthesis failed")[-1000:]
                        raise RuntimeError(detail)
                audio = output_path.read_bytes()
            self.send_bytes(200, audio, CONTENT_TYPES[audio_format])
        except subprocess.TimeoutExpired:
            self.send_json_error(504, "Speech generation timed out")
        except Exception as exc:
            self.send_json_error(500, f"Speech generation failed: {exc}")

    def stream_synthesis(self, text: str, voice: str, language: str, speed: float,
                         audio_format: str = "wav") -> None:
        """Synthesise with --split-output and forward each chunk as it lands.

        The CLI writes chunk_001, chunk_002 ... into a chapter directory
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
                     "--format", audio_format, "--lang", language, "--voice", voice,
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
                        for path in sorted(output_dir.rglob(f"chunk_*.{audio_format}"),
                                           key=chunk_sort_key):
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
                        raw = path.read_bytes()

                        if audio_format == "mp3":
                            # MP3 frames are self-describing, so chunks can be
                            # concatenated as-is with no header surgery.
                            if not raw:
                                sent_files.add(path.name)
                                continue
                            if not headers_sent:
                                self.begin_stream("audio/mpeg")
                                headers_sent = True
                            # Strip the Xing/Info header frame from every chunk,
                            # and the ID3 tag from all but the first, so the
                            # result is one continuous run of audio frames.
                            self.write_chunked(
                                strip_mp3_metadata(raw, drop_id3=bool(sent_files)))
                            sent_files.add(path.name)
                            last_progress = time.monotonic()
                            continue

                        try:
                            chunk_fmt, frames = parse_wav(raw)
                        except ValueError:
                            continue
                        if not frames:
                            sent_files.add(path.name)
                            continue

                        if not headers_sent:
                            fmt = chunk_fmt
                            self.begin_stream("audio/wav")
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
                        if not ready and not self.pending_chunks(
                                output_dir, sent_files, f"chunk_*.{audio_format}"):
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
    def pending_chunks(output_dir: Path, sent_files: set[str], pattern: str = "chunk_*.wav") -> bool:
        """True when the CLI left chunk files we have not forwarded yet."""
        if not output_dir.is_dir():
            return False
        return any(p.name not in sent_files for p in output_dir.rglob(pattern))

    def begin_stream(self, content_type: str) -> None:
        """Open a chunked streaming response."""
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Transfer-Encoding", "chunked")
        # The streamed response writes its own headers, so CORS is repeated
        # here rather than inherited from send_bytes.
        self.send_cors_headers()
        self.end_headers()

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kokoro TTS HTTP API.",
        epilog="Bind 0.0.0.0 to accept connections from other machines.",
    )
    parser.add_argument("--host", default=HOST, help=f"bind address (default {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"bind port (default {PORT})")
    args = parser.parse_args()

    try:
        token = expected_token()
    except RuntimeError as exc:
        print(f"Refusing to start: {exc}")
        raise SystemExit(1)

    print(f"Kokoro TTS API  ->  http://{args.host}:{args.port}/api")
    print(f"  docs    GET  /docs")
    print(f"  health  GET  /api/health")
    print(f"  voices  GET  /api/voices")
    print(f"  speak   POST /api/tts")
    print(f"  stream  POST /api/tts/stream")
    print(f"  auth    Authorization: Bearer <token>  ({len(token)} chars configured)")
    if not cli_path():
        print(f"  WARNING: Kokoro CLI '{KOKORO}' not found; synthesis will fail.")
    if args.host not in ("127.0.0.1", "localhost") and "*" in CORS_ORIGINS:
        print("  NOTE: reachable off-host with CORS open to any origin. "
              "Set KOKORO_CORS_ORIGINS to restrict browser callers.")
    print("\nCtrl+C to stop.")

    try:
        ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
