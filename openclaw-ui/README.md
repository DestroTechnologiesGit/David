# LiveContent Studio — simplified frontend

A NotebookLM-style three-panel interface with a static browser UI and a
restricted Node.js backend. It is presented as a LiveContent product; the OpenClaw name does
not appear in the UI. It does **not** replace or modify the built-in
OpenClaw Control UI, which stays available at its own URL for admin work.

- **Sources** — the research surface. Search the web from the panel, tick the
  results you want and **Import** them; they are saved to the current
  notebook's source list. The first import into an empty notebook also names it
  and opens the chat with an overview of what the sources cover; later imports
  only add rows, so they never talk over a conversation in progress.
  **Add source** adds a document (PDF / `.docx` / `.txt`, drag-and-drop or file
  picker, parsed in the browser) or pasted text. Each row has a checkbox: only
  ticked sources are sent as context with the next question, so the answer can
  be re-grounded without retyping it
- **Notebooks** — conversations, listed under the sources. Each notebook owns
  its own source list; switching notebooks swaps the sources shown
- **Chat** — streaming replies through the private Node.js API
- **Notes** — saved answers, listed in the left panel under Sources.
  **View all** opens a full-screen page of every note, searchable, each showing
  which conversation it came from; selecting one jumps back to that conversation
- **Studio** — Audio Overview and translation of the latest assistant answer.
  Audio Overview starts in English and automatically translates its narration
  as soon as another language is selected. Completed translations can also be sent
  directly to Audio Overview. The same 164 language targets are offered for both
  tools: Kokoro provides high-quality,
  downloadable audio for its eight trained languages; Microsoft's online voices
  provide downloadable MP3/WAV audio for their supported languages; and an
  installed browser/device voice remains the playback fallback.

## Why a separate app

The OpenClaw Control UI ships as a prebuilt bundle inside the npm package
(`/usr/local/lib/node_modules/openclaw/dist/control-ui/`). It has no source in the
published package and no build script, so it cannot be edited in place — any change
is overwritten on `npm update`. The Node.js service talks to the gateway's
documented OpenAI-compatible HTTP API. The browser cannot reach the gateway
directly and never receives its owner-level credential.

## Testing locally

The page cannot be opened straight from disk because `/studio-api` is a
same-origin server route. Run the private Node service and the
Python model/document helper together:

```bash
# 1. Make sure the gateway is running.
openclaw gateway

# 2. Start the restricted API with a key different from the gateway token.
cd openclaw-ui
STUDIO_ACCESS_TOKEN=local-development-key \
BIOFORMER_RANK_URL=http://127.0.0.1:8080/health-rank node server.js

# 3. In another terminal, serve the UI plus Python helper routes.
cd openclaw-ui
python3 serve.py                    # http://127.0.0.1:8080
```

Then open <http://127.0.0.1:8080/> and fill in the settings dialog:

| Field | Value |
| --- | --- |
| Server address | `/studio-api` |
| Studio access key | `local-development-key` |
| Assistant ID | `openclaw/studio` |
| Narration service | `/studio-api/tts` |

Select **Test connection** first; it should list the available agent targets.

Python helper options: `--port 9000`, `--backend http://otherhost:18881`,
`--timeout 900`. The Node service has no runtime npm dependencies.

> Agent replies can take **minutes**. The send button turns into a red Stop
> button while one is in flight, so a slow reply is cancellable rather than
> looking frozen.
>
> If replies routinely take minutes, check the gateway log for
> `Rate limit reached` — the configured model may be throttled, and the gateway
> then retries down its fallback chain. That is a model/quota issue, not a UI one.

## Deploying

Install the CPU Bioformer runtime and download the model once:

```bash
uv venv --python 3.12 ~/.bioformer-venv
uv pip install --python ~/.bioformer-venv/bin/python -r requirements-health.txt
~/.bioformer-venv/bin/hf download bioformers/bioformer-8L \
  --local-dir ~/models/bioformer-8L
```

Run `serve.py` on loopback port 18880 with the Bioformer virtual environment and set
`BIOFORMER_MODEL=~/models/bioformer-8L` plus `BIOFORMER_LOCAL_ONLY=1`. The
model is warmed in the background when the service starts.

Bioformer-8L itself was trained from scratch on biomedical literature only:
33 million PubMed abstracts (as of 1 February 2021) and one million
down-sampled PMC full-text articles. Its 32,768-token cased WordPiece
vocabulary was built from that same Unicode corpus. Studio does not retrain or
add web text to the model; web results are merely encoded and ranked at request
time.

For scanned-PDF OCR, install `libgl1` on Debian/Ubuntu and install
`requirements-ocr.txt` into the Python environment configured by
`DOCLING_PYTHON`. Digital PDFs are still extracted in the browser; only a PDF
with no embedded text is sent to `/convert` for RapidOCR processing.

### 1. Enable the chat endpoint

Not enabled by default. Add to `~/.openclaw/openclaw.json`:

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
curl -sS http://127.0.0.1:18789/v1/models -H "Authorization: Bearer YOUR_TOKEN"
```

It should list `openclaw/default`.

Translation requests are routed separately to `openclaw/translator`; normal
chat continues to use `openclaw/studio`. Create that isolated agent once and
give its workspace translation-only bootstrap instructions:

```bash
openclaw agents add translator \
  --workspace ~/.openclaw/workspace-translator \
  --model madlad/madlad400-3b-mt \
  --non-interactive
```

The `madlad` provider is the local OpenAI-compatible service in
`../madlad-translation`. OpenClaw starts it on demand and stops it after five
idle minutes. The translator has no skills or external tools; the backend
preserves common code, URLs, and placeholders and returns
`NO_TRANSLATABLE_TEXT` for coordinate-only or machine-only input. The UI turns
that sentinel into a friendly status message.

> **Security.** OpenClaw's own docs state that a valid gateway token on this
> endpoint is equivalent to **owner/operator access**, not a narrow per-user
> scope, and that it should be kept to loopback / private ingress. Read
> `docs/gateway/openai-http-api.md` in the openclaw package before exposing it.

### 2. Start the private Node.js API

Create a restricted Studio key and install the included service:

```bash
mkdir -p /home/ubuntu/livecontent-studio-api
cp /path/to/project/openclaw-ui/server.js \
   /path/to/project/openclaw-ui/studio-api.env.example \
   /home/ubuntu/livecontent-studio-api/
cd /home/ubuntu/livecontent-studio-api
cp studio-api.env.example studio-api.env
# Replace STUDIO_ACCESS_TOKEN with output from: openssl rand -hex 32
mkdir -p /home/ubuntu/.config/systemd/user
cp /path/to/project/openclaw-ui/livecontent-studio-api.service \
   /home/ubuntu/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now livecontent-studio-api
```

The service reads the gateway owner token from `openclaw.json`; that token is
never returned to the browser. `STUDIO_ACCESS_TOKEN` is a separate restricted
key accepted only by the Node routes. The backend allowlists the `studio` and
`translator` agents, caps request sizes, rate-limits callers, privately invokes
web search, hands health results to Bioformer on loopback, forwards bounded
document conversion requests, and proxies Kokoro.
Keep this directory outside `/home/ubuntu/openclaw-ui`, which is Caddy's public
static root.

### 3. Serve the page and proxy the restricted API

Copy `index.html` to the server, then in the Caddyfile:

```caddy
51-81-81-208.sslip.io {
    handle_path /kokoro/* {
        reverse_proxy 127.0.0.1:8890
    }

    # Explicit public UI assets; private backend files are never served.
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

    # Restricted Studio operations; never expose the raw gateway API here.
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

Reload Caddy, then open `/studio`.

### 4. Configure in the browser

The settings dialog opens on first visit:

| Field | Value |
| --- | --- |
| Server address | `/studio-api` |
| Studio access key | the separate `STUDIO_ACCESS_TOKEN` value |
| Assistant ID | `openclaw/studio` |
| Narration service | `/studio-api/tts` (blank to disable narration) |

**Test connection** verifies the setup before you chat. Settings live in that
browser's local storage only.

## Notes and limits

- Conversations and notes are stored per browser (`localStorage`); they are not
  synced between devices and clearing site data removes them.
- The restricted Studio key is held in local storage. It can use Studio
  features but cannot call arbitrary OpenClaw gateway or administration routes.
- Audio Overview sends narration to the configured speech service, capped at
  5,000 characters. Selecting the online multilingual voice sends that narration
  text to Microsoft's speech service so Studio can return a downloadable file.
- Sources are attached to each request as a system message, not indexed. There
  is no retrieval layer, so very large documents are truncated (20,000
  characters per source) and many ticked sources at once can exceed the model's
  context window. Untick what a question does not need.
- Health/Clinical search and ranking logic is server-only. Results are
  semantically ranked with the
  Apache-2.0 `bioformers/bioformer-8L` biomedical language model. The ranker is
  CPU-capable and is used only to order evidence; OpenClaw still writes the
  response. Set `BIOFORMER_MODEL` to a local Hugging Face snapshot path and
  `BIOFORMER_LOCAL_ONLY=1` in production so requests never download models.
- Minification or obfuscation is not treated as a security control. UI code is
  necessarily visible to browsers; credentials and protected orchestration
  live only in `server.js` on the host.
- Sources live in `localStorage` alongside conversations, so the same per-browser
  limits apply.
- Web sources show their site's favicon, fetched from Google
  (`google.com/s2/favicons`). This is the only third-party request the page
  makes, and it tells Google which domains you have saved. Icons are sent
  `referrerpolicy="no-referrer"`, and a source whose icon fails to load falls
  back to a coloured letter tile. To keep the page fully self-contained, delete
  the `<img>` in `faviconTile()` and the one in `renderResults()`; the letter
  tiles remain.
