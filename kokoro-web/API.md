# Kokoro TTS API

An HTTP API around the Kokoro TTS CLI. Send text, get audio back.

## Running it

The server needs two things: the `kokoro-tts` CLI on the machine, and a token.

```bash
export KOKORO_API_TOKEN=$(openssl rand -hex 24)   # any string you choose
export KOKORO_BIN=/path/to/kokoro-tts             # or leave it on $PATH

python3 server.py --host 0.0.0.0 --port 8890
```

`--host 0.0.0.0` accepts connections from other machines. The default
`127.0.0.1` keeps it local. Every option can also come from the environment or
a `.env` file beside `server.py` — see `.env.example`.

On start it prints the endpoints, confirms a token is set, and warns if the
CLI is missing.

> The CLI needs its model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`) in its
> working directory. `GET /api/health` reports whether the CLI was found, but
> not whether the models are in place — a missing model shows up as a failed
> synthesis.

## Authentication

Every synthesis request needs the token:

```
Authorization: Bearer <token>
```

`X-Kokoro-Key: <token>` also works, for the browser UI. Requests without a
valid token get `401`. The metadata endpoints (`/api`, `/api/health`,
`/api/voices`) are open, so a client can discover the service before
authenticating.

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/docs` | no | This reference (add `?raw=1` for Markdown) |
| GET | `/api` | no | Endpoint list, parameters, limits |
| GET | `/api/health` | no | Liveness, and whether the CLI resolved |
| GET | `/api/voices` | no | Voices grouped by language |
| POST | `/api/tts` | yes | Synthesize; returns a complete audio file |
| POST | `/api/tts/stream` | yes | Synthesize; streams audio as it is produced |

### POST /api/tts

```json
{
  "text": "Hello world",
  "voice": "af_sarah",
  "language": "en-us",
  "speed": 1.0,
  "format": "wav"
}
```

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `text` | yes | — | 1–5,000 characters (10,000 when streaming) |
| `voice` | no | `af_sarah` | See `/api/voices` |
| `language` | no | `en-us` | Must match the voice's language |
| `speed` | no | `1.0` | 0.5–2.0 |
| `format` | no | `wav` | `wav` or `mp3` |

Responds `200` with `audio/wav` or `audio/mpeg` as the body.

```bash
curl -X POST http://your-host:8890/api/tts \
  -H "Authorization: Bearer $KOKORO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","voice":"af_sarah"}' \
  -o hello.wav
```

### POST /api/tts/stream

Same request shape, but audio arrives chunked as it is generated, so playback
can start before synthesis finishes. Allows 10,000 characters. Chunks are
joined into one continuous file, so the response is still a single valid audio
file if you save it.

```bash
curl -X POST http://your-host:8890/api/tts/stream \
  -H "Authorization: Bearer $KOKORO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"A longer passage..."}' \
  -o long.wav
```

MP3 chunks do not join seamlessly — expect small gaps between segments. Use
`wav` when gapless output matters.

### GET /api/voices

```json
{
  "languages": ["cmn", "en-gb", "en-us", "es", "fr-fr", "hi", "it", "ja"],
  "voices": { "es": ["ef_dora", "em_alex", "em_santa"], "...": [] },
  "default_voice": "af_sarah",
  "default_language": "en-us"
}
```

Pair a voice with its own language — `ef_dora` with `es`, `hf_alpha` with `hi`.
A mismatched pair produces bad pronunciation rather than an error.

## Errors

Errors are JSON: `{"error": "..."}`.

| Status | Meaning |
| --- | --- |
| 400 | Bad request — empty text, over the limit, bad speed or format |
| 401 | Missing or wrong token |
| 404 | Unknown path |
| 500 | Synthesis failed (CLI missing, model missing, or it errored) |
| 504 | Synthesis timed out |

## Calling from a browser

CORS is open (`*`) by default, so a page on another origin can call the API.
To restrict it:

```bash
export KOKORO_CORS_ORIGINS=https://app.example.com,https://admin.example.com
```

Setting it empty disables CORS entirely, leaving the API same-origin only.

Note that calling from a browser means the token is in client-side code, where
any visitor can read it. Prefer calling from your own backend and keeping the
token there.

## Example client

```python
import requests

def speak(text, out="out.wav", voice="af_sarah", language="en-us"):
    r = requests.post(
        "http://your-host:8890/api/tts",
        headers={"Authorization": "Bearer " + TOKEN},
        json={"text": text, "voice": voice, "language": language, "format": "wav"},
        timeout=300,
    )
    r.raise_for_status()
    with open(out, "wb") as f:
        f.write(r.content)
    return out
```

Synthesis is serialised by a lock, so concurrent callers queue rather than
compete for the CPU. Long documents can take minutes — set a generous client
timeout, or use the streaming endpoint.

## Deploying behind a reverse proxy

Bind to `127.0.0.1` and let the proxy terminate TLS:

```
# Caddy
handle_path /kokoro/* {
    reverse_proxy 127.0.0.1:8890
}
```

Routes are matched from the `/api` or `/docs` part onward, so they work
whether or not the proxy strips its mount prefix — `/kokoro/docs` and `/docs`
both resolve. Disable proxy response buffering for `/api/tts/stream`, or
streaming will be buffered into a single delayed response.
