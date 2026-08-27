# OpenClaw Studio — simplified frontend

A NotebookLM-style three-panel interface for the OpenClaw gateway, built as a
single self-contained HTML file. It does **not** replace or modify the built-in
OpenClaw Control UI, which stays available at its own URL for admin work.

- **Sources** — conversations, stored in the browser
- **Chat** — streaming replies from the gateway
- **Studio** — Notes and an Audio Overview button wired to the Kokoro TTS bridge

## Why a separate app

The OpenClaw Control UI ships as a prebuilt bundle inside the npm package
(`/usr/local/lib/node_modules/openclaw/dist/control-ui/`). It has no source in the
published package and no build script, so it cannot be edited in place — any change
is overwritten on `npm update`. This app talks to the gateway's documented
OpenAI-compatible HTTP API instead, so gateway upgrades cannot break it.

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
- Sources are conversations, not uploaded documents. Document ingestion would
  need a retrieval layer that OpenClaw's chat endpoint does not itself provide.
