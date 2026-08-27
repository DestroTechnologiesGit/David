# David Server Project

This repository contains the project files configured on the VPS:

- `kokoro-frontend.html` - browser UI for text to speech.
- `kokoro-web/server.py` - authenticated local HTTP bridge for Kokoro TTS.
- `Caddyfile.openclaw` - Caddy reverse proxy configuration for OpenClaw and Kokoro.
- `kokoro-tts/` - Kokoro TTS CLI source.

Large local model artifacts are intentionally excluded from Git:

- `kokoro-tts/kokoro-v1.0.onnx`
- `kokoro-tts/voices-v1.0.bin`

Download or restore those files on the server before running Kokoro TTS.
