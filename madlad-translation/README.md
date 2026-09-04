# LiveContent MADLAD Translation Service

Local OpenAI-compatible translation backend for the OpenClaw `translator`
agent. It uses the Apache-2.0 MADLAD-400 3B MT model through CTranslate2 INT8.

The service accepts `/v1/chat/completions` requests, extracts the target ISO
language code and `SOURCE_TEXT` block, preserves common code/URL/placeholder
content, and returns only the translation. Numeric/vector-only input returns
`NO_TRANSLATABLE_TEXT`.

Streaming requests start their SSE response immediately and emit translated
segments as they complete. The CPU-friendly defaults use greedy decoding and
48-token source segments; `MADLAD_BEAM_SIZE` and
`MADLAD_STREAM_SOURCE_TOKENS` can be adjusted when quality or throughput is
more important than interactive latency.

Run locally:

```bash
uv sync --no-dev --python ~/.local/bin/python3.12
uv run uvicorn server:app --host 127.0.0.1 --port 11555
```

OpenClaw starts this service on demand through the provider's `localService`
configuration, so a separate system service is not required.
