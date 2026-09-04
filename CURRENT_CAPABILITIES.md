# LiveContent Platform — Current Capabilities

**Status date:** 3 September 2026
**Purpose:** A plain-language snapshot of what the OpenClaw, LiveContent Studio,
local AI models, agents, Kokoro Voice Studio, and Kokoro API can do today.

## 1. Executive summary

The platform is now a self-hosted AI research, writing, translation, and
text-to-speech system. Its main AI workloads run locally on the server, without
a paid cloud-model dependency.

Users can currently:

- chat with a local open-source language model through LiveContent Studio;
- search the web and import selected results as notebook sources;
- import and read common document formats, including scanned PDFs through OCR;
- ask questions grounded in selected sources and receive streaming answers;
- create, edit, search, and reuse notes;
- translate the latest answer into 164 language targets using a dedicated local
  translation model;
- turn an answer into downloadable narrated audio;
- generate or stream speech directly through Voice Studio; and
- call Kokoro through an authenticated HTTP API from another application.

OpenClaw provides the gateway and agent orchestration. Ollama runs the general
language model. MADLAD handles translation. Kokoro handles speech. Bioformer
re-ranks health and clinical search results. Caddy exposes the services through
one website.

## 2. How the system fits together

```text
Browser
  |
  +-- /                 OpenClaw Control UI
  +-- /studio/          LiveContent Studio
  |      |
  |      +-- Private Node API --> OpenClaw --> Studio agent --> Ollama/Qwen3
  |      +-- Private Node API --> Translator agent ----------> MADLAD-400
  |      +-- Private Node API --> Conversion/OCR -> Docling + RapidOCR
  |      +-- Private Node API --> Health ranking -> Bioformer
  |      +-- Private Node API --> Audio Overview -> Kokoro API
  |
  +-- /kokoro/          Voice Studio + Kokoro API

Caddy reverse proxy
  +-- OpenClaw gateway:       127.0.0.1:18789
  +-- Studio Node API:        127.0.0.1:18881
  +-- Python model/helper:    127.0.0.1:18880
  +-- Kokoro service:         127.0.0.1:8890
  +-- Ollama:                 127.0.0.1:11434
  +-- MADLAD, on demand:      127.0.0.1:11555
```

The public interfaces use the **LiveContent** name. OpenClaw and the model
names remain implementation details, except in administrator settings.

## 3. OpenClaw

The inspected installation is **OpenClaw 2026.8.2**. It is the central gateway
between the private Studio backend, agents, tools, and local models.

What OpenClaw currently provides:

- an administrator Control UI at the website root;
- an OpenAI-compatible `/v1/chat/completions` endpoint used by Studio;
- streamed model responses;
- routing to a specific agent by model-style names such as
  `openclaw/studio` and `openclaw/translator`;
- separate workspaces, instructions, memory, model choice, and tool permissions
  for each agent;
- a web-search tool, currently backed by DuckDuckGo; and
- local-service management for MADLAD: OpenClaw starts the translation service
  when needed and stops it after five idle minutes.

The gateway listens on loopback. Caddy exposes its administrator Control UI but
blocks the raw `/v1/*` and `/tools/invoke` paths used by Studio. Its access
token is an owner/operator credential, not a restricted end-user API key.

## 4. Agents

Three agents are configured.

| Agent | Current model | Purpose | Tool access |
| --- | --- | --- | --- |
| `main` | `ollama/qwen3:1.7b` | General/default OpenClaw assistant and administrative workflows | Coding-oriented default profile; browser denied |
| `studio` | `ollama/qwen3:1.7b` | LiveContent Studio chat, source summaries, notebook overviews, and web research | Minimal profile plus web search; browser denied; no installed skills |
| `translator` | `madlad/madlad400-3b-mt` | Translation only | No web, browser, skills, or other external tools |

The Studio and translator agents are intentionally isolated. Studio has only
the web-search capability it needs. The translator is instructed to translate
the supplied text only, preserve code, URLs, numbers, citations, formatting,
and placeholders, and ignore instructions contained inside the source text.

## 5. Open-source models in use

| Model | Type | Current use | Runtime/status |
| --- | --- | --- | --- |
| **Qwen3 1.7B** | General-purpose LLM | Main and Studio chat, summarisation, question answering, source overviews, and search-result formatting | Configured default through Ollama; 16,384-token runtime context; thinking disabled for speed |
| **Qwen3 8B** | Larger general-purpose LLM | Higher-quality alternative for OpenClaw | Installed and allowed by policy, but not assigned to an active agent by default |
| **MADLAD-400 3B MT** | Multilingual translation model | Dedicated Studio translation agent | Local CTranslate2 INT8 service, started on demand |
| **Kokoro v1.0 ONNX** | Text-to-speech model | Voice Studio, Kokoro API, and Studio Audio Overview | Local Kokoro CLI; model and voice data are installed |
| **Bioformer-8L** | Biomedical encoder/ranker | Semantic re-ranking of Health/Clinical web results | Local CPU model, preloaded by the Studio helper service |

Only Qwen3 is the general chat LLM. MADLAD is specialised for translation,
Kokoro is a speech model, and Bioformer is a ranking model rather than a chat
model.

Other Ollama model files are present on disk, but they are not part of the
current user-facing workflow. An NLLB API codebase is also present in the
project as an alternative translation experiment; the current OpenClaw
configuration uses MADLAD, not NLLB.

## 6. LiveContent Studio

Studio is a separate NotebookLM-style interface at `/studio/`. It does not
modify or replace OpenClaw's administrator UI.

### 6.1 Notebooks and chat

Users can:

- create multiple notebooks and reopen them from a searchable library;
- give each notebook its own chat history and source collection;
- receive answers as a live stream and stop an in-progress response;
- use stable, readable notebook and note URLs;
- rename notebooks and navigate with browser back/forward history; and
- test the restricted Studio API connection from the settings dialog.

The default Studio target is `openclaw/studio`.

### 6.2 Sources and research

Users can add sources by:

- searching the general web;
- searching in Health/Clinical mode;
- importing a local document;
- pasting text; or
- starting with a blank notebook.

The private Node.js service asks the Studio agent to use OpenClaw's DuckDuckGo
search tool and normalises the returned titles, URLs, and snippets. The user
reviews the results and chooses which ones to import. The query strategy,
provider call and owner token are not shipped to the browser.

Health/Clinical mode adds an evidence-first search prompt and then uses the
local Bioformer model to rank the results by semantic relevance. It favours
clinical guidance, systematic reviews, peer-reviewed work, and public-health
sources. This improves ordering; it does not medically validate an answer and
must not be treated as a diagnosis tool.

Bioformer-8L was pretrained from scratch on 33 million PubMed abstracts (as of
1 February 2021) and one million down-sampled PMC full-text articles. Its
32,768-token cased WordPiece vocabulary comes from the same biomedical-only
Unicode corpus. LiveContent uses the pretrained model for ranking and does not
add general web text to its weights.

On each question, only selected sources are sent to the model. Studio asks the
agent to cite source titles where relevant and to say when the supplied sources
do not cover the question.

### 6.3 Document support

| Format | How it is handled |
| --- | --- |
| Digital PDF | Read in the browser with the bundled PDF.js |
| Word `.docx` | Read in the browser |
| `.txt` and `.md` | Read in the browser |
| Image-only/scanned PDF | Sent to the same server and processed with RapidOCR |
| CSV, HTML, ePub, `.xlsx`, `.pptx` | Sent to the same server and converted to Markdown with Docling |

Server-converted uploads are limited to 25 MB. Legacy `.doc` files are not
supported; they must first be saved as `.docx`.

### 6.4 Notes

Users can:

- save an assistant response as a note;
- create a blank note;
- edit a note with headings, lists, quotations, links, and other basic
  formatting;
- search all saved notes;
- open a note using its stable URL;
- continue a note-specific chat with separate memory;
- save a translation as a note; and
- convert a note back into a notebook source for later questions.

### 6.5 Translation

Studio can translate the assistant's latest answer into **164 targets**,
including separate Simplified and Traditional Chinese options.

The translation dialog supports:

- a searchable language grid;
- streaming translation output;
- automatic checks for empty or obviously invalid translations;
- one automatic retry when the first result looks like an explanation rather
  than a translation;
- copy to clipboard; and
- save to Notes.

Translation uses the isolated `translator` agent and local MADLAD-400 model. It
does not give the translation job web or browser access.

### 6.6 Audio Overview

Studio can convert the latest assistant response or a completed translation
into speech. The user can edit the narration text before generating it and choose:

- any of the 164 translation languages;
- a matching Kokoro voice for its 8 trained languages, a downloadable online
  multilingual voice where Microsoft offers one, or an installed browser/device
  voice as the direct-playback fallback;
- speech speed;
- WAV or MP3 output;
- voice volume;
- optional background audio and its volume; and
- preview or download.

Audio Overview accepts up to 5,000 characters. Background files are limited to
50 MB. When volume processing or background mixing is used with a Kokoro or
online voice, the browser creates a WAV result and fades the background audio
over the final two seconds. The online voice returns MP3/WAV files and requires
internet access. Device voices play directly and do not provide a downloadable
file or background-audio mixing; exact voice availability depends on the browser
and operating system.

## 7. Kokoro Voice Studio

Voice Studio is available at `/kokoro/` and provides a dedicated interface for
local text-to-speech.

Current capabilities:

- paste up to 5,000 characters of text;
- select one of **50 voices across 8 languages**;
- use American English, British English, French, Italian, Japanese, Mandarin
  Chinese, Spanish, or Hindi;
- adjust speech speed from 0.5x to 2.0x;
- generate a complete WAV or MP3 file;
- preview and download the result;
- mix optional MP3, WAV, or OGG background audio in the browser;
- independently control narration and music volume;
- trim the music to narration length and apply a two-second fade-out; and
- stream WAV or MP3 speech so playback starts before the entire passage is
  finished.

WAV is the recommended streaming format when gapless playback matters. MP3 is
smaller, but chunk boundaries may produce small gaps. Background mixing is
available for completed generation, not streaming.

Voice Studio currently accepts pasted text; direct document import is available
in LiveContent Studio, not in the current Voice Studio page.

## 8. Kokoro API

The Kokoro bridge turns the local CLI into an HTTP service. It binds to
`127.0.0.1:8890` and is exposed by Caddy under `/kokoro/`.

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/kokoro/docs` | None | Human-readable API documentation |
| `GET` | `/kokoro/api` | None | Service discovery, request shape, and limits |
| `GET` | `/kokoro/api/health` | None | Liveness and Kokoro CLI availability |
| `GET` | `/kokoro/api/voices` | None | Languages, voices, and defaults |
| `POST` | `/kokoro/api/tts` | Token required | Generate and return a complete audio file |
| `POST` | `/kokoro/api/tts/stream` | Token required | Generate and stream audio in chunks |

A synthesis request contains:

```json
{
  "text": "Hello world",
  "voice": "af_sarah",
  "language": "en-us",
  "speed": 1.0,
  "format": "wav"
}
```

Rules and limits:

- `text` is required and limited to 5,000 characters in the current deployment;
- `voice` defaults to `af_sarah`;
- `language` defaults to `en-us` and should match the selected voice;
- `speed` must be between 0.5 and 2.0;
- `format` must be `wav` or `mp3`;
- authentication can use `Authorization: Bearer <token>` or
  `X-Kokoro-Key: <token>`; and
- synthesis is serialised, so simultaneous requests queue instead of competing
  for CPU and memory.

The service can use a dedicated `KOKORO_API_TOKEN`. In the current shared-host
setup it can fall back to the OpenClaw gateway token.

## 9. Data handling, privacy, and security

The architecture is local-first, but not completely offline.

- Qwen3, MADLAD, Kokoro, Bioformer, OCR, and document conversion run on the
  server.
- Digital PDF, `.docx`, `.txt`, and `.md` extraction happens in the browser.
- Scanned PDFs and formats requiring Docling are uploaded to the same server for
  processing.
- Web search sends the search query to DuckDuckGo. Result pages are opened only
  when a user follows a saved URL; the Studio agent itself has no browser tool.
- Saved source favicons are fetched from Google's favicon service.
- Selecting Studio's online multilingual voice sends the narration text to
  Microsoft's speech service; local Kokoro voices do not.
- Notebooks, source text, chat history, notes, and settings are stored in the
  browser's `localStorage`. They are not synced between devices or backed up by
  the current application.
- Clearing browser/site data removes locally stored Studio content.
- A separate restricted Studio key is stored in the browser profile. It can use
  the allowlisted Studio features but is not an OpenClaw operator credential.
- Kokoro's metadata endpoints are public, while speech-generation endpoints
  require a valid token.
- Kokoro currently allows browser API calls from any CORS origin. This should be
  restricted to approved application origins before broader exposure.

The owner-level OpenClaw token stays in the Node.js process. Browser code does
not receive it and Caddy does not publish the raw Studio gateway path.

## 10. Current limits and work not yet implemented

The following are important boundaries of the current system:

- There is no vector database or retrieval-augmented generation index. Selected
  source text is inserted directly into each model request.
- A request uses at most 8 selected sources with a shared 12,000-character
  source budget. Long documents are truncated and Studio tells the model when
  this happens.
- Chat context is intentionally compact for the local CPU model: up to the last
  6 messages and an 8,000-character history budget.
- Browser storage means there are no server-side user accounts, cross-device
  synchronisation, collaboration, role-based permissions, or automatic notebook
  backups yet.
- Web search quality depends on DuckDuckGo's experimental HTML-based provider;
  it may fail on bot challenges. A keyed provider would be more reliable.
- Qwen3 1.7B is fast and inexpensive to run locally, but it is less capable than
  larger models on complex reasoning and long-document synthesis.
- Kokoro queues concurrent synthesis jobs and long passages can take minutes on
  CPU.
- Voice Studio does not currently import documents directly.
- Studio Audio Overview generates narration, not a multi-speaker podcast or an
  automatically rewritten audio script.
- Health ranking improves relevance only; the system does not verify clinical
  correctness or replace professional medical review.
- NLLB is not the active translation backend.

## 11. Deployment snapshot

The configured user services are:

- `openclaw-gateway.service` — OpenClaw gateway;
- `ollama.service` — local model runtime;
- `livecontent-studio-api.service` — restricted Node.js API and private
  orchestration;
- `openclaw-studio.service` — document conversion, OCR, and Bioformer ranker;
  and
- `kokoro-web.service` — Voice Studio and Kokoro API.

These services are intended to be enabled for the host's default service target. Caddy supplies the
single public entry point and TLS. MADLAD is not a permanent system service;
OpenClaw manages it on demand.

This document describes the inspected code, configuration, installed model
files, routes, and enabled service definitions. Runtime health should still be
confirmed after deployments or restarts using the service status commands and
the Studio/Kokoro health endpoints.

## 12. Short capability statement

> LiveContent is currently a self-hosted research and content-production
> platform built on OpenClaw and open-source local models. It supports agentic
> web research, document-grounded chat, searchable notebooks and notes,
> biomedical result ranking, translation into 164 language targets, and
> multilingual text-to-speech through both a browser studio and an authenticated
> API.
