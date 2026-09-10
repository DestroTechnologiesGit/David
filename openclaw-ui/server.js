#!/usr/bin/env node
"use strict";

/*
 * Private backend-for-frontend for LiveContent Studio.
 *
 * The browser receives only a restricted Studio access key. The OpenClaw
 * owner token, search prompt, provider calls and Bioformer hand-off remain on
 * the server. Bioformer continues to run in the Python helper because the
 * shipped model is a PyTorch/Transformers model; Node only orchestrates it.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { Readable } = require("node:stream");
const { StringDecoder } = require("node:string_decoder");

const API_PREFIX = "/studio-api";
const ALLOWED_API_ROUTES = new Set([
    "/chat", "/search", "/models", "/voices", "/tts", "/convert",
    "/share-note", "/shared-note", "/share-note-audio", "/shared-note-audio",
]);
const PORT = integerEnv("STUDIO_NODE_PORT", 18881);
const HOST = process.env.STUDIO_NODE_HOST || "127.0.0.1";
const GATEWAY = withoutTrailingSlash(process.env.OPENCLAW_GATEWAY || "http://127.0.0.1:18789");
const HEALTH_RANK_URL = process.env.BIOFORMER_RANK_URL || "http://127.0.0.1:18880/health-rank";
const CONVERT_URL = process.env.DOCUMENT_CONVERT_URL || "http://127.0.0.1:18880/convert";
const KOKORO_URL = process.env.KOKORO_URL || "http://127.0.0.1:8890/api";
const OLLAMA_CHAT_URL = process.env.OLLAMA_CHAT_URL || "http://127.0.0.1:11434/api/chat";
const STUDIO_CHAT_MODEL = process.env.STUDIO_CHAT_MODEL || "qwen3:1.7b";
const MAX_JSON_BYTES = integerEnv("STUDIO_MAX_JSON_BYTES", 2 * 1024 * 1024);
const MAX_DOCUMENT_BYTES = integerEnv("STUDIO_MAX_DOCUMENT_BYTES", 25 * 1024 * 1024);
const MAX_REQUESTS_PER_MINUTE = integerEnv("STUDIO_RATE_LIMIT", 120);
const CHAT_DEFAULT_TOKENS = integerEnv("STUDIO_CHAT_DEFAULT_TOKENS", 768);
const CHAT_MAX_TOKENS = integerEnv("STUDIO_CHAT_MAX_TOKENS", 3072);
const CHAT_CONTEXT_TOKENS = integerEnv("STUDIO_CHAT_CONTEXT_TOKENS", 8192);
const MAX_SHARED_AUDIO_BYTES = integerEnv("STUDIO_MAX_SHARED_AUDIO_BYTES", 64 * 1024 * 1024);
const DEFAULT_SHARED_NOTES_DIR = process.env.SHARED_NOTES_DIR
    || "/home/ubuntu/livecontent-shared-notes";
const SHARE_ID = /^[a-f0-9]{32}$/;
const SHARED_AUDIO_TYPES = new Set([
    "audio/aac", "audio/mp4", "audio/mpeg", "audio/ogg", "audio/wav",
    "audio/webm", "audio/x-wav",
]);
const CHAT_GUIDANCE = "Answer the user's latest request directly. Put the answer first. "
    + "Follow any explicit output format exactly and do not add unrequested sections. "
    + "Be concise unless the user asks for detail. Use supplied source context when relevant, "
    + "say when it is insufficient, and do not substitute an answer to an earlier question. "
    + "Return only user-visible answer text; never emit reply-routing tags.";
const ALLOWED_MODELS = new Set(
    (process.env.STUDIO_ALLOWED_MODELS || "openclaw/studio,openclaw/translator")
        .split(",").map(value => value.trim()).filter(Boolean)
);

function integerEnv(name, fallback) {
    const value = Number.parseInt(process.env[name] || "", 10);
    return Number.isSafeInteger(value) && value > 0 ? value : fallback;
}

function withoutTrailingSlash(value) {
    return String(value).replace(/\/+$/, "");
}

function readGatewayToken() {
    if (process.env.OPENCLAW_GATEWAY_TOKEN) return process.env.OPENCLAW_GATEWAY_TOKEN.trim();
    const configPath = process.env.OPENCLAW_CONFIG
        || path.join(process.env.HOME || "/home/ubuntu", ".openclaw", "openclaw.json");
    const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
    const token = config.gateway && config.gateway.auth && config.gateway.auth.token;
    if (!token || typeof token !== "string") {
        throw new Error(`No gateway.auth.token found in ${configPath}`);
    }
    return token;
}

function readStudioToken() {
    const token = String(process.env.STUDIO_ACCESS_TOKEN || "").trim();
    if (!token) {
        throw new Error("STUDIO_ACCESS_TOKEN is required; do not reuse the OpenClaw gateway token");
    }
    return token;
}

function safeEqual(left, right) {
    const a = Buffer.from(String(left));
    const b = Buffer.from(String(right));
    return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function bearerToken(req) {
    const match = /^Bearer\s+(.+)$/i.exec(req.headers.authorization || "");
    return match ? match[1].trim() : "";
}

function jsonResponse(res, status, value) {
    const body = Buffer.from(JSON.stringify(value));
    res.writeHead(status, {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": body.length,
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    });
    res.end(body);
}

function errorMessage(value, fallback) {
    if (!value) return fallback;
    if (typeof value === "string") return value.slice(0, 300);
    if (value.error && typeof value.error === "string") return value.error.slice(0, 300);
    if (value.error && typeof value.error.message === "string") return value.error.message.slice(0, 300);
    return fallback;
}

async function readBody(req, maxBytes) {
    const declared = Number.parseInt(req.headers["content-length"] || "0", 10);
    if (declared > maxBytes) throw Object.assign(new Error("Request is too large"), { status: 413 });
    const chunks = [];
    let size = 0;
    for await (const chunk of req) {
        size += chunk.length;
        if (size > maxBytes) throw Object.assign(new Error("Request is too large"), { status: 413 });
        chunks.push(chunk);
    }
    if (!chunks.length) throw Object.assign(new Error("A request body is required"), { status: 400 });
    return Buffer.concat(chunks);
}

async function readJson(req, maxBytes = MAX_JSON_BYTES) {
    try {
        const value = JSON.parse((await readBody(req, maxBytes)).toString("utf8"));
        if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("object required");
        return value;
    } catch (error) {
        if (error.status) throw error;
        throw Object.assign(new Error("Request body is not valid JSON"), { status: 400 });
    }
}

function gatewayHeaders(extra = {}) {
    return {
        Authorization: `Bearer ${gatewayToken}`,
        ...extra,
    };
}

function fetchWithTimeout(url, options = {}, timeoutMs = 600_000) {
    const signals = [AbortSignal.timeout(timeoutMs)];
    if (options.signal) signals.push(options.signal);
    // Keep the signal attached after response headers arrive so it also limits
    // and cancels a long-running SSE/audio response body.
    return fetch(url, { ...options, signal: AbortSignal.any(signals) });
}

function requestAbortSignal(req, res) {
    const controller = new AbortController();
    req.once("aborted", () => controller.abort());
    res.once("close", () => {
        if (!res.writableFinished) controller.abort();
    });
    return controller.signal;
}

async function proxyResponse(upstream, res, options = {}) {
    const headers = {
        "Content-Type": upstream.headers.get("content-type") || "application/octet-stream",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    };
    const disposition = upstream.headers.get("content-disposition");
    if (options.inline) headers["Content-Disposition"] = "inline";
    else if (disposition) headers["Content-Disposition"] = disposition;
    res.writeHead(upstream.status, headers);
    if (!upstream.body) return res.end();
    await new Promise((resolve, reject) => {
        const stream = Readable.fromWeb(upstream.body);
        stream.on("error", reject);
        res.on("close", resolve);
        res.on("finish", resolve);
        stream.pipe(res);
    });
}

function validateMessages(messages) {
    if (!Array.isArray(messages) || !messages.length || messages.length > 40) return false;
    return messages.every(message => message && ["system", "user", "assistant"].includes(message.role)
        && typeof message.content === "string" && message.content.length <= 100_000);
}

function requestedChatTokens(value) {
    const requested = Number.isSafeInteger(value) && value > 0
        ? value
        : CHAT_DEFAULT_TOKENS;
    return Math.min(requested, CHAT_MAX_TOKENS);
}

function normalizeSharedNote(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const title = String(value.title || "Untitled note").trim().slice(0, 200) || "Untitled note";
    const body = typeof value.body === "string" ? value.body.trim() : "";
    if (!body || body.length > 200_000) return null;
    const resourceType = value.resourceType === "audio" ? "audio" : "note";
    const audioMimeType = SHARED_AUDIO_TYPES.has(String(value.audioMimeType || "").toLowerCase())
        ? String(value.audioMimeType).toLowerCase() : "";
    if (resourceType === "audio" && !audioMimeType) return null;
    const normalized = {
        title,
        body,
        createdAt: Date.now(),
        resourceType,
    };
    if (resourceType === "audio" && audioMimeType) {
        normalized.hasAudio = true;
        normalized.audioMimeType = audioMimeType;
        normalized.audioLanguage = String(value.audioLanguage || "Narration").trim().slice(0, 80)
            || "Narration";
    }
    return normalized;
}

let sharedNotesDir = DEFAULT_SHARED_NOTES_DIR;

async function handleShareNote(req, res) {
    const note = normalizeSharedNote(await readJson(req, 256 * 1024));
    if (!note) {
        return jsonResponse(res, 400, { error: "A non-empty, bounded note is required." });
    }
    fs.mkdirSync(sharedNotesDir, { recursive: true, mode: 0o700 });
    for (let attempt = 0; attempt < 4; attempt++) {
        const id = crypto.randomBytes(16).toString("hex");
        const uploadToken = note.hasAudio ? crypto.randomBytes(24).toString("hex") : "";
        if (uploadToken) {
            note.audioUploadTokenHash = crypto.createHash("sha256").update(uploadToken).digest("hex");
        }
        try {
            fs.writeFileSync(path.join(sharedNotesDir, `${id}.json`), JSON.stringify(note), {
                encoding: "utf8",
                flag: "wx",
                mode: 0o600,
            });
            return jsonResponse(res, 201, uploadToken ? { id, uploadToken } : { id });
        } catch (error) {
            if (error.code !== "EEXIST") throw error;
        }
    }
    throw new Error("A unique note link could not be created.");
}

function sharedNotePath(id) {
    return path.join(sharedNotesDir, `${id}.json`);
}

function sharedAudioPath(id) {
    return path.join(sharedNotesDir, `${id}.audio`);
}

function readStoredSharedNote(id) {
    return JSON.parse(fs.readFileSync(sharedNotePath(id), "utf8"));
}

async function handleShareNoteAudio(req, res) {
    const id = String(req.headers["x-share-id"] || "");
    const uploadToken = String(req.headers["x-share-upload-token"] || "");
    const mimeType = String(req.headers["content-type"] || "").split(";", 1)[0].trim().toLowerCase();
    if (!SHARE_ID.test(id) || !/^[a-f0-9]{48}$/.test(uploadToken)) {
        return jsonResponse(res, 400, { error: "Invalid audio upload." });
    }
    if (!SHARED_AUDIO_TYPES.has(mimeType)) {
        return jsonResponse(res, 415, { error: "Unsupported shared audio format." });
    }
    try {
        const note = readStoredSharedNote(id);
        const suppliedHash = crypto.createHash("sha256").update(uploadToken).digest("hex");
        if (!note.hasAudio || note.audioMimeType !== mimeType
                || !note.audioUploadTokenHash || !safeEqual(suppliedHash, note.audioUploadTokenHash)) {
            return jsonResponse(res, 403, { error: "This audio upload is not authorized." });
        }
        const audio = await readBody(req, MAX_SHARED_AUDIO_BYTES);
        if (!audio.length) return jsonResponse(res, 400, { error: "Audio is required." });
        const audioPath = sharedAudioPath(id);
        fs.writeFileSync(audioPath, audio, { flag: "wx", mode: 0o600 });
        try {
            delete note.audioUploadTokenHash;
            fs.writeFileSync(sharedNotePath(id), JSON.stringify(note), { mode: 0o600 });
        } catch (error) {
            fs.unlinkSync(audioPath);
            throw error;
        }
        return jsonResponse(res, 201, { saved: true });
    } catch (error) {
        if (error.code === "ENOENT") return jsonResponse(res, 404, { error: "Shared note not found." });
        if (error.code === "EEXIST") return jsonResponse(res, 409, { error: "Shared audio already exists." });
        throw error;
    }
}

async function handleSharedNote(req, res) {
    const body = await readJson(req, 4 * 1024);
    const id = String(body.id || "");
    if (!SHARE_ID.test(id)) return jsonResponse(res, 400, { error: "Invalid shared note link." });
    try {
        const note = readStoredSharedNote(id);
        const normalized = normalizeSharedNote(note);
        if (!normalized) throw new Error("Invalid shared note data");
        // Preserve the original share time rather than the normalizer's new timestamp.
        normalized.createdAt = Number.isFinite(note.createdAt) ? note.createdAt : normalized.createdAt;
        return jsonResponse(res, 200, { note: normalized });
    } catch (error) {
        if (error.code === "ENOENT") return jsonResponse(res, 404, { error: "Shared note not found." });
        throw error;
    }
}

async function handleSharedNoteAudio(req, res) {
    const body = await readJson(req, 4 * 1024);
    const id = String(body.id || "");
    if (!SHARE_ID.test(id)) return jsonResponse(res, 400, { error: "Invalid shared note link." });
    try {
        const note = readStoredSharedNote(id);
        const normalized = normalizeSharedNote(note);
        if (!normalized || !normalized.hasAudio || note.audioUploadTokenHash) {
            return jsonResponse(res, 404, { error: "Shared audio not found." });
        }
        const audioPath = sharedAudioPath(id);
        const size = fs.statSync(audioPath).size;
        res.writeHead(200, {
            "Content-Type": normalized.audioMimeType,
            "Content-Length": size,
            "Content-Disposition": "inline",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        });
        await new Promise((resolve, reject) => {
            const stream = fs.createReadStream(audioPath);
            stream.on("error", reject);
            res.on("close", resolve);
            res.on("finish", resolve);
            stream.pipe(res);
        });
    } catch (error) {
        if (error.code === "ENOENT") return jsonResponse(res, 404, { error: "Shared audio not found." });
        throw error;
    }
}

function prepareChatMessages(messages, model) {
    const copied = messages.map(message => ({ role: message.role, content: message.content }));
    // The translation model has a strict machine-oriented prompt contract. The
    // direct-answer instruction is for interactive Studio chat only.
    if (model !== "openclaw/studio") return copied;
    if (copied[0] && copied[0].role === "system") {
        copied[0].content = `${CHAT_GUIDANCE}\n\n${copied[0].content}`;
    } else {
        copied.unshift({ role: "system", content: CHAT_GUIDANCE });
    }
    return copied;
}

function ollamaChatPayload(messages, stream, maxTokens) {
    return {
        model: STUDIO_CHAT_MODEL,
        stream,
        think: false,
        keep_alive: "30m",
        messages,
        options: {
            temperature: 0.2,
            num_ctx: CHAT_CONTEXT_TOKENS,
            num_predict: maxTokens,
        },
    };
}

function cleanAssistantOutput(value) {
    return String(value || "")
        .replace(/\[\[(?:\/?reply_to_current|reply_to:[^\]]+)\]\]/gi, "")
        .trim();
}

function completionJson(content, usage = {}) {
    return {
        id: `chatcmpl_studio_${Date.now()}`,
        object: "chat.completion",
        created: Math.floor(Date.now() / 1000),
        model: STUDIO_CHAT_MODEL,
        choices: [{ index: 0, message: { role: "assistant", content }, finish_reason: "stop" }],
        usage: {
            prompt_tokens: usage.prompt_tokens || 0,
            completion_tokens: usage.completion_tokens || 0,
            total_tokens: (usage.prompt_tokens || 0) + (usage.completion_tokens || 0),
        },
    };
}

async function handleOllamaChat(res, messages, stream, maxTokens, signal) {
    const upstream = await fetchWithTimeout(OLLAMA_CHAT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ollamaChatPayload(messages, stream, maxTokens)),
        signal,
    });
    if (!upstream.ok) {
        const failure = await upstream.json().catch(() => null);
        return jsonResponse(res, upstream.status, {
            error: errorMessage(failure, `Local chat model failed with HTTP ${upstream.status}.`),
        });
    }

    if (!stream) {
        const result = await upstream.json();
        return jsonResponse(res, 200, completionJson(cleanAssistantOutput(result.message && result.message.content), {
            prompt_tokens: result.prompt_eval_count,
            completion_tokens: result.eval_count,
        }));
    }

    res.writeHead(200, {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
        "X-Content-Type-Options": "nosniff",
    });
    if (!upstream.body) throw new Error("Local chat model returned no response stream.");

    let buffer = "";
    let finished = false;
    const decoder = new StringDecoder("utf8");
    const emitLine = line => {
        if (!line.trim()) return;
        const event = JSON.parse(line);
        if (event.error) throw new Error(event.error);
        const content = event.message && event.message.content;
        if (content) {
            res.write(`data: ${JSON.stringify({ choices: [{ index: 0, delta: { content } }] })}\n\n`);
        }
        if (event.done) finished = true;
    };

    for await (const chunk of upstream.body) {
        buffer += decoder.write(Buffer.from(chunk));
        let newline;
        while ((newline = buffer.indexOf("\n")) !== -1) {
            emitLine(buffer.slice(0, newline));
            buffer = buffer.slice(newline + 1);
        }
    }
    buffer += decoder.end();
    if (buffer) emitLine(buffer);
    if (!finished) throw new Error("Local chat model stream ended unexpectedly.");
    res.write(`data: ${JSON.stringify({ choices: [{ index: 0, delta: {}, finish_reason: "stop" }] })}\n\n`);
    res.end("data: [DONE]\n\n");
}

async function handleChat(req, res) {
    const body = await readJson(req);
    const model = String(body.model || "openclaw/studio");
    if (!ALLOWED_MODELS.has(model)) {
        return jsonResponse(res, 403, { error: "That assistant is not available through Studio." });
    }
    if (!validateMessages(body.messages)) {
        return jsonResponse(res, 400, { error: "A valid, bounded message list is required." });
    }
    const messages = prepareChatMessages(body.messages, model);
    const signal = requestAbortSignal(req, res);
    const maxTokens = requestedChatTokens(body.max_completion_tokens);
    if (model === "openclaw/studio") {
        return handleOllamaChat(res, messages, body.stream !== false, maxTokens, signal);
    }

    const payload = {
        model,
        stream: body.stream !== false,
        user: String(body.user || `studio-${Date.now()}`).slice(0, 160),
        messages,
    };
    const upstream = await fetchWithTimeout(`${GATEWAY}/v1/chat/completions`, {
        method: "POST",
        headers: gatewayHeaders({
            "Content-Type": "application/json",
            Accept: payload.stream ? "text/event-stream" : "application/json",
        }),
        body: JSON.stringify(payload),
        signal,
    });
    await proxyResponse(upstream, res);
}

function cleanSearchText(value) {
    return String(value || "")
        .replace(/<<<(?:END_)?EXTERNAL_UNTRUSTED_CONTENT[^>]*>>>/g, "")
        .replace(/^\s*Source:\s*Web Search\s*$/gmi, "")
        .replace(/^\s*---\s*$/gm, "")
        .trim();
}

function normalizeResults(results) {
    if (!Array.isArray(results)) return [];
    return results.filter(item => item && (item.url || item.link)).slice(0, 10).map(item => ({
        title: cleanSearchText(item.title || item.name || item.url || "Untitled").slice(0, 200),
        url: String(item.url || item.link).slice(0, 2048),
        snippet: cleanSearchText(item.snippet || item.description || item.summary || "").slice(0, 400),
    })).filter(item => /^https?:\/\//i.test(item.url));
}

function parseResults(text) {
    const source = String(text || "");
    const fenced = source.match(/```(?:json)?\s*([\s\S]*?)```/i);
    const bare = source.match(/\[[\s\S]*\]/);
    for (const candidate of [fenced && fenced[1], bare && bare[0], source]) {
        if (!candidate) continue;
        try {
            const results = normalizeResults(JSON.parse(candidate.trim()));
            if (results.length) return results;
        } catch (_) { /* try the next representation */ }
    }
    return [];
}

function scopedSearchQuery(query, scope) {
    if (scope !== "health") return query;
    return `${query} clinical evidence guideline authoritative medical source `
        + "(WHO OR CDC OR NIH OR PubMed OR Cochrane OR NHS)";
}

function searchPrompt(query, scope) {
    const health = scope === "health"
        ? "Prioritise current clinical guidance, systematic reviews, peer-reviewed research, "
          + "and official public-health sources such as WHO, CDC, NIH, PubMed, Cochrane and NHS. "
          + "Avoid promotional health content. "
        : "";
    return `Use your web_search tool. Find sources about: ${query}\n\n${health}`
        + "Reply with ONLY a JSON array, no prose and no code fence. Each item must be "
        + '{"title":"...","url":"https://...","snippet":"one sentence"}. '
        + "Return up to 10 real results with real URLs from the search tool. "
        + "If the search tool is unavailable, reply with exactly: NO_SEARCH";
}

async function invokeWebSearch(query, scope) {
    const response = await fetchWithTimeout(`${GATEWAY}/tools/invoke`, {
        method: "POST",
        headers: gatewayHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
            tool: "web_search",
            agentId: "studio-search",
            args: { query: scopedSearchQuery(query, scope), count: 10 },
        }),
    }, 120_000);
    const json = await response.json().catch(() => null);
    const details = json && json.result && json.result.details;
    const results = normalizeResults(details && details.results);
    if (!response.ok || !json || !json.ok || !results.length) {
        throw new Error(errorMessage(json, "Structured web search is unavailable."));
    }
    return results;
}

async function agentWebSearch(query, scope) {
    const response = await fetchWithTimeout(`${GATEWAY}/v1/chat/completions`, {
        method: "POST",
        headers: gatewayHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
            model: "openclaw/studio-search",
            stream: false,
            user: `studio-search-${Date.now()}`,
            max_tokens: 1536,
            messages: [{ role: "user", content: searchPrompt(query, scope) }],
        }),
    });
    const json = await response.json().catch(() => null);
    if (!response.ok) throw new Error(errorMessage(json, `Search failed with HTTP ${response.status}.`));
    const content = json && json.choices && json.choices[0] && json.choices[0].message
        && json.choices[0].message.content;
    if (/^\s*NO_SEARCH\s*$/.test(content || "")) {
        throw new Error("The assistant has no web search available on the server.");
    }
    const results = parseResults(content);
    if (!results.length) throw new Error("No search results could be read from the assistant reply.");
    return results;
}

async function rankHealthResults(query, results) {
    const response = await fetchWithTimeout(HEALTH_RANK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, results }),
    }, 120_000);
    const json = await response.json().catch(() => null);
    if (!response.ok) throw new Error(errorMessage(json, "Bioformer ranking is unavailable."));
    const ranked = normalizeResults(json && json.results);
    if (!ranked.length) throw new Error("Bioformer returned no ranked results.");
    return { model: String(json.model || "bioformers/bioformer-8L"), results: ranked };
}

async function handleSearch(req, res) {
    const body = await readJson(req, 16 * 1024);
    const query = String(body.query || "").trim().slice(0, 500);
    const scope = body.scope === "health" ? "health" : "web";
    if (!query) return jsonResponse(res, 400, { error: "A search query is required." });

    let results;
    try {
        results = await invokeWebSearch(query, scope);
    } catch (_) {
        results = await agentWebSearch(query, scope);
    }

    let ranking = null;
    if (scope === "health") {
        try {
            const ranked = await rankHealthResults(query, results);
            results = ranked.results;
            ranking = { applied: true, model: ranked.model };
        } catch (error) {
            // Search remains useful during model maintenance, but the response
            // makes it explicit that biomedical ranking was not applied.
            console.error(`Bioformer ranking failed: ${error.message}`);
            ranking = { applied: false, error: "Biomedical ranking is temporarily unavailable." };
        }
    }
    jsonResponse(res, 200, { results, ranking });
}

async function handleModels(_req, res) {
    const response = await fetchWithTimeout(`${GATEWAY}/v1/models`, {
        headers: gatewayHeaders(),
    }, 30_000);
    const json = await response.json().catch(() => null);
    if (!response.ok) return jsonResponse(res, response.status, { error: errorMessage(json, "Gateway unavailable.") });
    const available = new Set((json && json.data || []).map(item => item && item.id));
    const data = [...ALLOWED_MODELS].filter(model => available.has(model)).map(id => ({ id }));
    jsonResponse(res, 200, { data });
}

async function handleVoices(_req, res) {
    const response = await fetchWithTimeout(`${withoutTrailingSlash(KOKORO_URL)}/voices`, {}, 30_000);
    await proxyResponse(response, res);
}

async function handleTts(req, res) {
    const body = await readJson(req, 16 * 1024);
    const response = await fetchWithTimeout(`${withoutTrailingSlash(KOKORO_URL)}/tts`, {
        method: "POST",
        headers: gatewayHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(body),
        signal: requestAbortSignal(req, res),
    });
    await proxyResponse(response, res, { inline: true });
}

async function handleConvert(req, res) {
    const body = await readBody(req, MAX_DOCUMENT_BYTES);
    const filename = String(req.headers["x-filename"] || "document")
        .replace(/[\r\n]/g, "").slice(0, 255);
    const response = await fetchWithTimeout(CONVERT_URL, {
        method: "POST",
        headers: {
            "Content-Type": "application/octet-stream",
            "Content-Length": String(body.length),
            "X-Filename": filename,
        },
        body,
        signal: requestAbortSignal(req, res),
    }, 240_000);
    await proxyResponse(response, res);
}

function routePath(url) {
    const raw = String(url || "");
    const prefixed = raw.startsWith(`${API_PREFIX}/`) ? raw.slice(API_PREFIX.length) : raw;
    const route = prefixed.replace(/\/$/, "");
    return ALLOWED_API_ROUTES.has(route) && !raw.includes("?") && !raw.includes("#") ? route : null;
}

const rateBuckets = new Map();
let rateWindowMinute = -1;
function withinRateLimit(req) {
    const forwarded = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim();
    const key = forwarded || req.socket.remoteAddress || "unknown";
    const minute = Math.floor(Date.now() / 60_000);
    if (minute !== rateWindowMinute) {
        rateBuckets.clear();
        rateWindowMinute = minute;
    }
    const current = rateBuckets.get(key);
    if (!current || current.minute !== minute) {
        rateBuckets.set(key, { minute, count: 1 });
        return true;
    }
    current.count += 1;
    return current.count <= MAX_REQUESTS_PER_MINUTE;
}

async function handleRequest(req, res) {
    res.setHeader("Referrer-Policy", "same-origin");
    if (!withinRateLimit(req)) return jsonResponse(res, 429, { error: "Too many Studio requests. Try again shortly." });
    // The reverse-proxied Studio UI is public by design. The OpenClaw owner
    // credential remains server-side and is never exposed to browsers.

    const route = routePath(req.url);
    if (req.method === "POST" && route === "/chat") return handleChat(req, res);
    if (req.method === "POST" && route === "/search") return handleSearch(req, res);
    if (req.method === "GET" && route === "/models") return handleModels(req, res);
    if (req.method === "GET" && route === "/voices") return handleVoices(req, res);
    if (req.method === "POST" && route === "/tts") return handleTts(req, res);
    if (req.method === "POST" && route === "/convert") return handleConvert(req, res);
    if (req.method === "POST" && route === "/share-note") return handleShareNote(req, res);
    if (req.method === "POST" && route === "/shared-note") return handleSharedNote(req, res);
    if (req.method === "POST" && route === "/share-note-audio") return handleShareNoteAudio(req, res);
    if (req.method === "POST" && route === "/shared-note-audio") return handleSharedNoteAudio(req, res);
    return jsonResponse(res, 404, { error: "Not found" });
}

let gatewayToken;
let studioToken;

function createServer(options = {}) {
    gatewayToken = options.gatewayToken || gatewayToken || readGatewayToken();
    studioToken = options.studioToken || studioToken || readStudioToken();
    sharedNotesDir = options.sharedNotesDir || DEFAULT_SHARED_NOTES_DIR;
    return http.createServer((req, res) => {
        handleRequest(req, res).catch(error => {
            if (res.headersSent) return res.destroy();
            const status = error.status || (error.name === "AbortError" ? 504 : 502);
            jsonResponse(res, status, { error: status === 502
                ? "A private Studio service is unavailable."
                : error.message });
            if (status === 502) console.error(error.message);
        });
    });
}

if (require.main === module) {
    try {
        createServer().listen(PORT, HOST, () => {
            console.log(`LiveContent private API -> http://${HOST}:${PORT}${API_PREFIX}`);
            console.log(`Allowed assistants       -> ${[...ALLOWED_MODELS].join(", ")}`);
        });
    } catch (error) {
        console.error(`Cannot start LiveContent private API: ${error.message}`);
        process.exitCode = 1;
    }
}

module.exports = {
    cleanSearchText,
    createServer,
    normalizeResults,
    normalizeSharedNote,
    ollamaChatPayload,
    parseResults,
    prepareChatMessages,
    requestedChatTokens,
    routePath,
    safeEqual,
    scopedSearchQuery,
    validateMessages,
};
