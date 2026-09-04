# David Server Project — Setup Guide

Everything running on the VPS, how to install it, and how to run it locally.

Two independent web apps sit behind one Caddy reverse proxy:

| App | Path | What it is |
| --- | --- | --- |
| **Voice Studio** | `/kokoro/` | Text-to-speech with background music, document import, and live streaming |
| **LiveContent Studio** | `/studio` | Simplified NotebookLM-style chat UI |
| OpenClaw Control UI | `/` | The vendor's own admin console (unmodified) |

---

## Contents

- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [1. Kokoro TTS](#1-kokoro-tts)
- [2. OpenClaw Studio](#2-openclaw-studio)
- [3. Caddy reverse proxy](#3-caddy-reverse-proxy)
- [Running locally](#running-locally)
- [Configuration reference](#configuration-reference)
- [Verifying the install](#verifying-the-install)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)

---

> **Branding.** Both UIs are presented as **LiveContent** products — the Kokoro
> and OpenClaw names appear nowhere in the interfaces. The underlying software
> is unchanged; only the user-facing copy differs. API values such as
> `openclaw/default` are still required and are kept behind an *Advanced*
> section in the Studio settings.

## Repository layout

```
.
├── Caddyfile.openclaw          Caddy config for all three apps
├── Caddyfile.openclaw.bak      Previous version, kept for rollback
├── assets/companyLogo.jpeg     LiveContent logo (embedded into both UIs)
├── kokoro-frontend.html        Voice Studio browser UI (markup)
├── kokoro-app.css              Voice Studio styles
├── kokoro-app.js               Voice Studio behaviour
├── kokoro-web/
│   ├── server.py               Authenticated HTTP bridge to the Kokoro CLI
│   ├── .env.example            Config template — copy to .env
│   └── .env                    Local config (gitignored)
├── kokoro-tts/                 Kokoro TTS CLI source (upstream, vendored)
└── openclaw-ui/
    ├── index.html              LiveContent Studio UI (markup)
    ├── app.css                 LiveContent Studio styles
    ├── app.js                  LiveContent Studio behaviour
    ├── vendor/                 PDF.js build, used to read PDFs in the browser
    ├── package.json            Pins the PDF.js version vendor/ is built from
    ├── server.js               Private Node.js API; holds credentials and search logic
    ├── serve.py                Bioformer/document helper plus local dev server
    ├── studio-api.env.example Node service configuration template
    └── README.md               Studio-specific notes
```

Excluded from Git (see `.gitignore`):

- `kokoro-tts/kokoro-v1.0.onnx` — the TTS model (~330 MB)
- `kokoro-tts/voices-v1.0.bin` — the voice data
- `kokoro-web/.env` — contains host-specific paths
- `*.wav`, `*.mp3` — generated audio

Both HTML files are **fully self-contained**: no build step, no bundler, no
external requests. The logo and favicon are embedded as data URIs. Deploying
means copying the file.

---

## Prerequisites

- **Python 3.11 or 3.12** (Kokoro TTS does not support 3.13+)
- **Caddy** for the reverse proxy and TLS
- **OpenClaw** installed globally via npm, running as a gateway
- An **MP3 encoder** (`libmp3lame`) if you want MP3 output — usually present
  with `ffmpeg` or `libsndfile`

---

## 1. Kokoro TTS

### 1.1 Install the CLI

```bash
cd kokoro-tts
pip install -e .            # or: uv sync
```

### 1.2 Download the model files

These are excluded from Git and must be fetched onto the server:

```bash
cd kokoro-tts
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin
```

> The CLI looks for both files in the **current working directory**, so run it
> from wherever they live, or pass `--model` / `--voices`.

Verify:

```bash
kokoro-tts --help-voices      # should list 43 voices
```

### 1.3 Configure the bridge

```bash
cd kokoro-web
cp .env.example .env
$EDITOR .env                  # set the paths for this host
```

Every value has a working default, so `.env` only needs the ones that differ.
See the [configuration reference](#configuration-reference).

### 1.4 Run the bridge

```bash
python3 kokoro-web/server.py
```

It listens on `127.0.0.1:8890` and authenticates with the OpenClaw gateway
token, which it reads from `openclaw.json` — there is no separate password.

To run it as a service, create a systemd unit:

```ini
# /etc/systemd/system/kokoro-web.service
[Unit]
Description=Kokoro TTS web bridge
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/kokoro-tts
ExecStart=/usr/bin/python3 /home/ubuntu/kokoro-web/server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now kokoro-web
```

> `WorkingDirectory` matters: it must be the directory holding
> `kokoro-v1.0.onnx` and `voices-v1.0.bin`.

### 1.5 What the UI does

`kokoro-frontend.html` has two tabs:

**Generate** — waits for the whole narration, then returns a finished file.

- Output format: **WAV or MP3**
- Optional background music, mixed in the browser, trimmed to the narration
  length with a 2-second fade-out
- Up to **5,000 characters** (~950 words, ~6–7 min of speech)

**Stream** — starts playing as soon as the first sentences are ready.

- Output format: **WAV** (gapless) or **MP3** (smaller, ~50 ms gaps between parts)
- Up to **5,000 characters** (~950 words, ~6 to 7 min)
- No background music: mixing needs the finished file

Both tabs share: 43 voices across 6 languages, and document import from
**PDF, Word `.docx`, and `.txt`** — parsed entirely in the browser, so no
file is ever uploaded.

---

## 2. OpenClaw Studio

A simplified three-panel chat UI. It does **not** replace the built-in Control
UI, which stays at `/`.

**Add source** opens a dialog that starts a conversation from:

- a **document** — PDF, Word `.docx`, or `.txt`, by drag-and-drop or file
  picker. Text is extracted in the browser and seeded as context; files are
  never uploaded anywhere.
- **pasted text**
- a **research topic** — sent to the private Node.js API, which invokes the
  agent's `web_search` tool and normalises results without exposing that logic
  or the OpenClaw owner token to the browser.
- a **blank conversation**

### 2.1 Enable the chat endpoint

Disabled by default. Add to `~/.openclaw/openclaw.json`:

```json5
{
  gateway: {
    http: {
      endpoints: {
        chatCompletions: { enabled: true }
      }
    }
  }
}
```

Restart the gateway, then confirm:

```bash
curl -sS http://127.0.0.1:18789/v1/models \
  -H "Authorization: Bearer YOUR_TOKEN"
```

It should return JSON listing `openclaw/default`. If you get an HTML page
instead, the endpoint is still disabled — that HTML is the Control UI's
catch-all route.

### 2.2 Deploy the page

```bash
mkdir -p /home/ubuntu/openclaw-ui
cp openclaw-ui/index.html openclaw-ui/app.css openclaw-ui/app.js \
   openclaw-ui/library.html openclaw-ui/library.js /home/ubuntu/openclaw-ui/
# vendor/ holds the PDF.js build that reads PDFs in the browser.
cp -r openclaw-ui/vendor /home/ubuntu/openclaw-ui/

# Keep private backend code outside Caddy's static root.
mkdir -p /home/ubuntu/livecontent-studio-api
cp openclaw-ui/server.js openclaw-ui/studio-api.env.example \
   /home/ubuntu/livecontent-studio-api/
cp /home/ubuntu/livecontent-studio-api/studio-api.env.example \
   /home/ubuntu/livecontent-studio-api/studio-api.env
# Put a new `openssl rand -hex 32` value in STUDIO_ACCESS_TOKEN.
mkdir -p /home/ubuntu/.config/systemd/user
cp openclaw-ui/livecontent-studio-api.service \
   /home/ubuntu/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now livecontent-studio-api
```

Run `server.js` as the Node backend on loopback port 18881. The Python helper
remains on loopback port 18880 for Bioformer, OCR and Docling. `node_modules/`
is not deployed: the Node backend uses only built-in modules, and the two
PDF.js browser files are committed under `vendor/`.

### 2.3 Enable web search

Search is off until a provider is set. **DuckDuckGo needs no API key** and is
what this project uses:

```json5
{
  tools: {
    web: {
      search: { provider: "duckduckgo" }
    }
  }
}
```

> OpenClaw's docs call DuckDuckGo **experimental** — it scrapes DDG's HTML and
> can break on bot-challenge pages. For production, a keyed provider (Brave,
> Exa, Perplexity) is more reliable; see `docs/tools/web.md` in the openclaw
> package.

The **Sources** panel then has a search box: type a topic, review the results
with checkboxes, and select **Import**. Imported sources become a conversation,
and the assistant writes an overview you can ask follow-up questions about.

### 2.4 Configure in the browser

The settings dialog opens on first visit:

| Field | Value |
| --- | --- |
| Server address | `/studio-api` |
| Studio access key | your separate `STUDIO_ACCESS_TOKEN` |
| Assistant ID | `openclaw/studio` |
| Narration service | `/studio-api/tts` (blank to disable narration) |

Select **Test connection** before chatting. The restricted Studio key lives in
browser local storage. The owner-level gateway credential stays on the server.

---

## 3. Caddy reverse proxy

Copy `Caddyfile.openclaw` into place, adjusting the domain:

```caddy
51-81-81-208.sslip.io {
    handle_path /kokoro/* {
        reverse_proxy 127.0.0.1:8890
    }

    @studioAsset path /studio/app.css /studio/app.js /studio/library.html /studio/library.js /studio/vendor/*
    handle @studioAsset {
        uri strip_prefix /studio
        root * /home/ubuntu/openclaw-ui
        file_server
    }

    handle_path /studio/* {
        root * /home/ubuntu/openclaw-ui
        rewrite * /index.html
        file_server
    }

    handle_path /studio-api/* {
        reverse_proxy 127.0.0.1:18881 {
            flush_interval -1
        }
    }

    handle /v1/* {
        respond "Not found" 404
    }

    handle /tools/invoke {
        respond "Not found" 404
    }

    reverse_proxy 127.0.0.1:18789
}
```

Validate before reloading — a syntax error takes the whole site down:

```bash
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

**Why `/studio-api` exists.** Browser code must be downloadable and therefore
cannot protect proprietary search logic or an owner credential. This route
exposes only a constrained Node.js API. The raw OpenClaw gateway and the
Bioformer/Python endpoint remain on loopback and are not routed to Studio.

---

## Running locally

### Kokoro TTS

```bash
cd kokoro-web
cp .env.example .env          # point KOKORO_* at local paths
python3 server.py
```

Open <http://127.0.0.1:8890/>. The bridge serves the UI itself, so the paths
line up without Caddy.

### OpenClaw Studio

Opening `index.html` from disk **will not work** — `/studio-api` is a server
route. Start the private Node.js service and the Python dev/helper server:

```bash
cd openclaw-ui
STUDIO_ACCESS_TOKEN=local-development-key \
BIOFORMER_RANK_URL=http://127.0.0.1:8080/health-rank node server.js

# In another terminal
python3 serve.py              # http://127.0.0.1:8080
```

Then open <http://127.0.0.1:8080/> and enter `local-development-key`. The server
address already defaults to `/studio-api`.

Options: `--port 9000`, `--backend http://otherhost:18881`, `--timeout 900`.
Standard library only, no dependencies.

---

## Configuration reference

All Kokoro bridge settings, read from `kokoro-web/.env` or the real
environment. Real environment variables win, so systemd `Environment=` lines
override the file.

| Variable | Default | Purpose |
| --- | --- | --- |
| `KOKORO_HOST` | `127.0.0.1` | Bind address |
| `KOKORO_PORT` | `8890` | Bind port |
| `KOKORO_MAX_TEXT_LENGTH` | `5000` | Character cap, Generate tab |
| `KOKORO_MAX_STREAM_TEXT_LENGTH` | `5000` | Character cap, Stream tab |
| `KOKORO_FRONTEND` | `/home/ubuntu/kokoro-frontend.html` | UI file served on `GET /`; `kokoro-app.css` and `kokoro-app.js` are served from the same directory |
| `KOKORO_API_TOKEN` | _(unset)_ | Token callers send as `Authorization: Bearer`. Set this to run the API on any host; without it the token is read from `OPENCLAW_CONFIG` |
| `KOKORO_CORS_ORIGINS` | `*` | Origins allowed to call the API from a browser; a comma-separated list restricts it, empty disables CORS |
| `KOKORO_DEFAULT_VOICE` | `af_sarah` | Voice used when a request omits one |
| `KOKORO_DEFAULT_LANGUAGE` | `en-us` | Language used when a request omits one |
| `OPENCLAW_CONFIG` | `/home/ubuntu/.openclaw/openclaw.json` | Where the auth token is read from |
| `KOKORO_BIN` | `/home/ubuntu/.local/bin/kokoro-tts` | Kokoro CLI executable |
| `KOKORO_STREAM_CHUNK_TIMEOUT` | `180` | Seconds to wait per streaming chunk |
| `KOKORO_ENV_FILE` | `kokoro-web/.env` | Alternate location for the env file |

The character limits are also mirrored in `kokoro-app.js`
(`MAX_TEXT_LENGTH`, `MAX_STREAM_TEXT_LENGTH`) so the UI can warn before
sending. **Raise them together**, or the page will allow text the server rejects.

> **Deploying the UIs:** each page now loads a separate stylesheet and script,
> so copy them alongside the HTML or the page will render unstyled and inert.
> Voice Studio needs `kokoro-frontend.html`, `kokoro-app.css` and
> `kokoro-app.js` in the same directory; LiveContent Studio needs
> `index.html`, `app.css`, `app.js` and the `vendor/` directory in
> `/home/ubuntu/openclaw-ui`. Without `vendor/`, PDF import fails with
> "Could not load the PDF reader".

### API

The speech API can run standalone on any host — see
[kokoro-web/API.md](kokoro-web/API.md) for endpoints, auth, and examples.
Start it with `python3 server.py --host 0.0.0.0 --port 8890` and a
`KOKORO_API_TOKEN`.

Both endpoints authenticate with `X-Kokoro-Key: <gateway token>`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Serves the UI |
| `POST` | `/api/tts` | Synthesise and return a finished file |
| `POST` | `/api/tts/stream` | Synthesise and stream while generating |

Request body:

```json
{
  "text": "Hello world",
  "voice": "af_sarah",
  "language": "en-us",
  "speed": 1.0,
  "format": "wav"
}
```

`format` is `wav` or `mp3`. `speed` must be between 0.5 and 2.0.

---

## Verifying the install

```bash
# 1. Kokoro CLI sees the model
kokoro-tts --help-voices                     # 43 voices

# 2. Bridge is up
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8890/     # 200

# 3. Synthesis works
TOKEN=$(python3 -c "import json;print(json.load(open('/home/ubuntu/.openclaw/openclaw.json'))['gateway']['auth']['token'])")
curl -s -X POST http://127.0.0.1:8890/api/tts \
  -H "X-Kokoro-Key: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"text":"Setup test.","voice":"af_sarah","format":"wav"}' \
  -o /tmp/test.wav -w 'HTTP %{http_code}, %{size_download} bytes\n'

# 4. OpenClaw chat endpoint is enabled
curl -s http://127.0.0.1:18789/v1/models -H "Authorization: Bearer $TOKEN" | head -c 100

# 5. Restricted Studio API (use the separate value from studio-api.env)
STUDIO_TOKEN=YOUR_STUDIO_ACCESS_TOKEN
curl -s http://127.0.0.1:18881/models -H "Authorization: Bearer $STUDIO_TOKEN"

# 6. Public routes
curl -s -o /dev/null -w '%{http_code}\n' https://YOUR-DOMAIN/kokoro/
curl -s -o /dev/null -w '%{http_code}\n' https://YOUR-DOMAIN/studio
```

---

## Troubleshooting

**`Could not reach the private Studio API`**
Check `livecontent-studio-api.service`, then verify that Caddy routes
`/studio-api/*` to loopback port 18881. For local work, start `server.js` before
`serve.py`.

**`/v1/models` returns HTML instead of JSON**
`chatCompletions` is not enabled. The HTML is the Control UI catch-all. See
[2.1](#21-enable-the-chat-endpoint).

**`Unsupported audio format from server` / `did not return a WAV stream`**
A format mismatch between the CLI's output and what the bridge expects. Both
now handle 8/16/24/32-bit PCM, 32/64-bit float, and MP3 — if this reappears,
check what the CLI actually wrote: `file chunk_001.*`.

**`Text must contain 1-5000 characters`**
Over the limit for that tab. The Stream tab allows 5,000. Raise
`KOKORO_MAX_TEXT_LENGTH` *and* the matching constant in the HTML.

**Kokoro fails with a model error**
The CLI resolves `kokoro-v1.0.onnx` and `voices-v1.0.bin` relative to the
working directory. Check `WorkingDirectory` in the systemd unit.

**MP3 output fails, WAV works**
The MP3 encoder is missing. Install `ffmpeg` or a `libsndfile` build with
`libmp3lame`.

**Chat replies take minutes**
Not a UI bug. Check the gateway log (`/tmp/openclaw/openclaw-YYYY-MM-DD.log`)
for `Rate limit reached` — if the configured model is throttled, the gateway
retries down its fallback chain, and each attempt adds delay. Observed on this
project: `openai/gpt-5.5-pro` hitting a tokens-per-minute cap turned a two-word
answer into a 261-second wait. Fix by changing the default model, raising the
provider quota, or reordering the fallback chain. The send button becomes a red
Stop button so a slow reply stays cancellable.

**Dev server prints a `ConnectionResetError` traceback**
Fixed. Browsers open speculative keep-alive sockets and drop them without
sending a request; `serve.py` now treats that as routine instead of an error.
Genuine faults are still reported.

**Audio streaming requires PortAudio**
The CLI's `--stream` flag plays to a local speaker and is unusable on a
headless server. The bridge does not use it; browser streaming is implemented
in `server.py` via `--split-output`.

---

## Security notes

Worth reviewing before this is exposed to real users.

- **The gateway token is an operator credential.** OpenClaw's own docs state a
  valid token on `/v1/chat/completions` is equivalent to owner/operator access,
  not a narrow per-user scope, and that the endpoint should be kept to
  loopback or private ingress.
- **Studio no longer exposes that gateway token.** Node reads it on the host
  and allowlists only chat, translation, search, document conversion, voice
  discovery and narration.
  Caddy does not publish `/openclaw-api` or `/health-rank`.
- **The browser stores a separate restricted key.** `STUDIO_ACCESS_TOKEN` can
  use Studio features but is not accepted by OpenClaw itself. Use a long random
  value and do not reuse the owner token.
- **Server-side code is the protection boundary.** Minification/uglification is
  not encryption. Browser UI code remains visible by design; the clinical
  query strategy, provider invocation, Bioformer hand-off and credentials now
  remain in Node.js/Python processes bound to loopback.
