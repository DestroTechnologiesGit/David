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

const API_PREFIX = "/studio-api";
const PORT = integerEnv("STUDIO_NODE_PORT", 18881);
const HOST = process.env.STUDIO_NODE_HOST || "127.0.0.1";
const GATEWAY = withoutTrailingSlash(process.env.OPENCLAW_GATEWAY || "http://127.0.0.1:18789");
const HEALTH_RANK_URL = process.env.BIOFORMER_RANK_URL || "http://127.0.0.1:18880/health-rank";
const CONVERT_URL = process.env.DOCUMENT_CONVERT_URL || "http://127.0.0.1:18880/convert";
const KOKORO_URL = process.env.KOKORO_URL || "http://127.0.0.1:8890/api";
const MAX_JSON_BYTES = integerEnv("STUDIO_MAX_JSON_BYTES", 2 * 1024 * 1024);
const MAX_DOCUMENT_BYTES = integerEnv("STUDIO_MAX_DOCUMENT_BYTES", 25 * 1024 * 1024);
const MAX_REQUESTS_PER_MINUTE = integerEnv("STUDIO_RATE_LIMIT", 120);
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

async function proxyResponse(upstream, res) {
    const headers = {
        "Content-Type": upstream.headers.get("content-type") || "application/octet-stream",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    };
    const disposition = upstream.headers.get("content-disposition");
    if (disposition) headers["Content-Disposition"] = disposition;
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

async function handleChat(req, res) {
    const body = await readJson(req);
    const model = String(body.model || "openclaw/studio");
    if (!ALLOWED_MODELS.has(model)) {
        return jsonResponse(res, 403, { error: "That assistant is not available through Studio." });
    }
    if (!validateMessages(body.messages)) {
        return jsonResponse(res, 400, { error: "A valid, bounded message list is required." });
    }
    const payload = {
        model,
        stream: body.stream !== false,
        user: String(body.user || `studio-${Date.now()}`).slice(0, 160),
        messages: body.messages,
    };
    const upstream = await fetchWithTimeout(`${GATEWAY}/v1/chat/completions`, {
        method: "POST",
        headers: gatewayHeaders({
            "Content-Type": "application/json",
            Accept: payload.stream ? "text/event-stream" : "application/json",
        }),
        body: JSON.stringify(payload),
        signal: requestAbortSignal(req, res),
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
            agentId: "studio",
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
            model: "openclaw/studio",
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
    await proxyResponse(response, res);
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
    const pathname = new URL(url, "http://localhost").pathname.replace(/\/$/, "") || "/";
    return pathname.startsWith(`${API_PREFIX}/`) ? pathname.slice(API_PREFIX.length) : pathname;
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
    if (!safeEqual(bearerToken(req), studioToken)) {
        res.setHeader("WWW-Authenticate", 'Bearer realm="LiveContent Studio"');
        return jsonResponse(res, 401, { error: "Invalid Studio access key." });
    }

    const route = routePath(req.url);
    if (req.method === "POST" && route === "/chat") return handleChat(req, res);
    if (req.method === "POST" && route === "/search") return handleSearch(req, res);
    if (req.method === "GET" && route === "/models") return handleModels(req, res);
    if (req.method === "GET" && route === "/voices") return handleVoices(req, res);
    if (req.method === "POST" && route === "/tts") return handleTts(req, res);
    if (req.method === "POST" && route === "/convert") return handleConvert(req, res);
    return jsonResponse(res, 404, { error: "Not found" });
}

let gatewayToken;
let studioToken;

function createServer(options = {}) {
    gatewayToken = options.gatewayToken || gatewayToken || readGatewayToken();
    studioToken = options.studioToken || studioToken || readStudioToken();
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
    parseResults,
    routePath,
    safeEqual,
    scopedSearchQuery,
    validateMessages,
};
