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
├── kokoro-frontend.html        Voice Studio browser UI (self-contained)
├── kokoro-web/
│   ├── server.py               Authenticated HTTP bridge to the Kokoro CLI
│   ├── .env.example            Config template — copy to .env
│   └── .env                    Local config (gitignored)
├── kokoro-tts/                 Kokoro TTS CLI source (upstream, vendored)
└── openclaw-ui/
    ├── index.html              LiveContent Studio UI (self-contained)
    ├── serve.py                Local dev server (not used in production)
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
- Up to **10,000 characters** (~1,950 words, ~13 min)
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
- a **research topic** — handed to the agent, which uses its `web_search` tool.
  There is no separate search backend; the gateway exposes search to agents as
  a tool, not over HTTP, so the UI asks the agent and parses the JSON it
  returns.
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
cp openclaw-ui/index.html /home/ubuntu/openclaw-ui/
```

`serve.py` is for local development only and is not needed on the server.

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
| Gateway base URL | `/openclaw-api` |
| Gateway token | your `gateway.auth.token` |
| Agent target | `openclaw/default` |
| Kokoro endpoint | `/kokoro/api/tts` (blank to disable narration) |

Select **Test connection** before chatting. Settings live in that browser's
local storage only, never on the server.

---

## 3. Caddy reverse proxy

Copy `Caddyfile.openclaw` into place, adjusting the domain:

```caddy
51-81-81-208.sslip.io {
    handle_path /kokoro/* {
        reverse_proxy 127.0.0.1:8890
    }

    handle /studio* {
        root * /home/ubuntu/openclaw-ui
        rewrite * /index.html
        file_server
    }

    handle_path /openclaw-api/* {
        reverse_proxy 127.0.0.1:18789
    }

    reverse_proxy 127.0.0.1:18789
}
```

Validate before reloading — a syntax error takes the whole site down:

```bash
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

**Why `/openclaw-api` exists.** The gateway sends no CORS headers, so a browser
can only call it from the same origin. Routing the API under the same domain
as the page satisfies that. Pointing the UI straight at `:18789` will be
blocked by the browser.

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

Opening `index.html` from disk **will not work** — `/openclaw-api` is a Caddy
route, and the gateway sends no CORS headers. Use the dev server, which
mirrors what Caddy does:

```bash
cd openclaw-ui
python3 serve.py              # http://127.0.0.1:8080
```

Then open <http://127.0.0.1:8080/> and paste your gateway token. The base URL
already defaults to `/openclaw-api`.

Options: `--port 9000`, `--gateway http://otherhost:18789`, `--timeout 900`.
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
| `KOKORO_MAX_STREAM_TEXT_LENGTH` | `10000` | Character cap, Stream tab |
| `KOKORO_FRONTEND` | `/home/ubuntu/kokoro-frontend.html` | UI file served on `GET /` |
| `OPENCLAW_CONFIG` | `/home/ubuntu/.openclaw/openclaw.json` | Where the auth token is read from |
| `KOKORO_BIN` | `/home/ubuntu/.local/bin/kokoro-tts` | Kokoro CLI executable |
| `KOKORO_STREAM_CHUNK_TIMEOUT` | `180` | Seconds to wait per streaming chunk |
| `KOKORO_ENV_FILE` | `kokoro-web/.env` | Alternate location for the env file |

The character limits are also mirrored in `kokoro-frontend.html`
(`MAX_TEXT_LENGTH`, `MAX_STREAM_TEXT_LENGTH`) so the UI can warn before
sending. **Raise them together**, or the page will allow text the server rejects.

### API

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

# 5. Public routes
curl -s -o /dev/null -w '%{http_code}\n' https://YOUR-DOMAIN/kokoro/
curl -s -o /dev/null -w '%{http_code}\n' https://YOUR-DOMAIN/studio
```

---

## Troubleshooting

**`Could not reach the gateway at /openclaw-api/...`**
Either the Caddy route is missing, or you opened `index.html` from disk. Use
`serve.py` locally; check `handle_path /openclaw-api/*` in the Caddyfile on the
server.

**`/v1/models` returns HTML instead of JSON**
`chatCompletions` is not enabled. The HTML is the Control UI catch-all. See
[2.1](#21-enable-the-chat-endpoint).

**`Unsupported audio format from server` / `did not return a WAV stream`**
A format mismatch between the CLI's output and what the bridge expects. Both
now handle 8/16/24/32-bit PCM, 32/64-bit float, and MP3 — if this reappears,
check what the CLI actually wrote: `file chunk_001.*`.

**`Text must contain 1-5000 characters`**
Over the limit for that tab. The Stream tab allows 10,000. Raise
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
- **The current Caddy config exposes the gateway publicly** at
  `51-81-81-208.sslip.io`, including `/openclaw-api`. Anyone with the token has
  operator-level access over the internet.
- **The same token authenticates Kokoro**, so a user given TTS access
  necessarily holds gateway access too.
- **Tokens are stored in browser local storage.** On a shared machine, treat
  the browser profile as holding a credential.

Reducing exposure would mean an IP allowlist on `/openclaw-api`, putting the
gateway behind Tailscale or a VPN, or adding a separate auth layer in front of
Caddy. None of these are configured today.
