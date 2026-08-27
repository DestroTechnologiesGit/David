# LiveContent Studio — simplified frontend

A NotebookLM-style three-panel interface, built as a single self-contained
HTML file. It is presented as a LiveContent product; the OpenClaw name does
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
- **Chat** — streaming replies from the gateway
- **Notes** — saved answers, listed in the left panel under Sources.
  **View all** opens a full-screen page of every note, searchable, each showing
  which conversation it came from; selecting one jumps back to that conversation
- **Studio** — Audio Overview, wired to the narration service

## Why a separate app

The OpenClaw Control UI ships as a prebuilt bundle inside the npm package
(`/usr/local/lib/node_modules/openclaw/dist/control-ui/`). It has no source in the
published package and no build script, so it cannot be edited in place — any change
is overwritten on `npm update`. This app talks to the gateway's documented
OpenAI-compatible HTTP API instead, so gateway upgrades cannot break it.

## Testing locally

The page cannot be opened straight from disk. Two things prevent it:

- `/openclaw-api` is a **Caddy route**, so it only exists where Caddy runs.
- The gateway sends **no CORS headers**, so a browser refuses to call it from
  any other origin (`file://`, a different port, etc.).

`serve.py` solves both: it serves the page and proxies `/openclaw-api/*` to the
gateway from the same origin, exactly as Caddy does in production.

```bash
# 1. Make sure the chat endpoint is enabled (see step 1 below) and the
#    gateway is running:
openclaw gateway

# 2. In another terminal:
cd openclaw-ui
python3 serve.py                    # http://127.0.0.1:8080
```

Then open <http://127.0.0.1:8080/> and fill in the settings dialog:

| Field | Value |
| --- | --- |
| Gateway base URL | `/openclaw-api` |
| Gateway token | your `gateway.auth.token` |
| Agent target | `openclaw/default` |

Select **Test connection** first; it should list the available agent targets.

Options: `--port 9000`, `--gateway http://otherhost:18789`, `--timeout 900`.
No dependencies beyond the Python standard library.

> Agent replies can take **minutes**. The send button turns into a red Stop
> button while one is in flight, so a slow reply is cancellable rather than
> looking frozen.
>
> If replies routinely take minutes, check the gateway log for
> `Rate limit reached` — the configured model may be throttled, and the gateway
> then retries down its fallback chain. That is a model/quota issue, not a UI one.

## Deploying

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

> **Security.** OpenClaw's own docs state that a valid gateway token on this
> endpoint is equivalent to **owner/operator access**, not a narrow per-user
> scope, and that it should be kept to loopback / private ingress. Read
> `docs/gateway/openai-http-api.md` in the openclaw package before exposing it.

### 2. Serve the page and proxy the API

Copy `index.html` to the server, then in the Caddyfile:

```caddy
51-81-81-208.sslip.io {
    handle_path /kokoro/* {
        reverse_proxy 127.0.0.1:8890
    }

    # The simplified UI
    handle /studio* {
        root * /home/ubuntu/openclaw-ui
        rewrite * /index.html
        file_server
    }

    # Gateway API for the UI (same origin, so no CORS)
    handle_path /openclaw-api/* {
        reverse_proxy 127.0.0.1:18789
    }

    reverse_proxy 127.0.0.1:18789
}
```

Reload Caddy, then open `/studio`.

### 3. Configure in the browser

The settings dialog opens on first visit:

| Field | Value |
| --- | --- |
| Gateway base URL | `/openclaw-api` |
| Gateway token | your `gateway.auth.token` |
| Agent target | `openclaw/default` |
| Kokoro endpoint | `/kokoro/api/tts` (blank to disable narration) |

**Test connection** verifies the setup before you chat. Settings live in that
browser's local storage only.

## Notes and limits

- Conversations and notes are stored per browser (`localStorage`); they are not
  synced between devices and clearing site data removes them.
- The gateway token is held in local storage. On a shared machine, treat the
  browser profile as holding an operator credential.
- Audio Overview sends the latest answer to Kokoro, capped at 5,000 characters
  to match the bridge's limit.
- Sources are attached to each request as a system message, not indexed. There
  is no retrieval layer, so very large documents are truncated (20,000
  characters per source) and many ticked sources at once can exceed the model's
  context window. Untick what a question does not need.
- Sources live in `localStorage` alongside conversations, so the same per-browser
  limits apply.
