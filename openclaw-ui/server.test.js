"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { after, before, describe, it } = require("node:test");
const {
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
} = require("./server");

describe("private Studio API helpers", () => {
    it("normalizes only bounded HTTP search results", () => {
        const results = normalizeResults([
            { name: "Example", link: "https://example.test/a", description: "Useful" },
            { title: "Unsafe", url: "javascript:alert(1)" },
        ]);
        assert.deepEqual(results, [{
            title: "Example", url: "https://example.test/a", snippet: "Useful",
        }]);
    });

    it("extracts JSON from a fenced assistant reply", () => {
        assert.equal(parseResults('```json\n[{"title":"A","url":"https://a.test"}]\n```')[0].title, "A");
    });

    it("keeps the clinical query expansion on the backend", () => {
        assert.equal(scopedSearchQuery("asthma", "web"), "asthma");
        assert.match(scopedSearchQuery("asthma", "health"), /PubMed/);
    });

    it("allows only exact Caddy and direct API paths", () => {
        assert.equal(routePath("/studio-api/chat"), "/chat");
        assert.equal(routePath("/models/"), "/models");
        assert.equal(routePath("/chat?x=1"), null);
        assert.equal(routePath("/studio-api/../models"), null);
        assert.equal(routePath("//example.test/models"), null);
        assert.equal(routePath("/admin"), null);
    });

    it("compares access keys without accepting unequal lengths", () => {
        assert.equal(safeEqual("secret", "secret"), true);
        assert.equal(safeEqual("secret", "other"), false);
    });

    it("accepts only bounded Studio chat message shapes", () => {
        assert.equal(validateMessages([{ role: "user", content: "hello" }]), true);
        assert.equal(validateMessages([{ role: "tool", content: "unsafe" }]), false);
        assert.equal(validateMessages([{ role: "user", content: "x".repeat(100_001) }]), false);
    });

    it("adds a direct-answer contract to Studio chat without mutating input", () => {
        const input = [{ role: "user", content: "What is 2 + 2?" }];
        const prepared = prepareChatMessages(input, "openclaw/studio");
        assert.equal(input.length, 1);
        assert.equal(prepared[0].role, "system");
        assert.match(prepared[0].content, /latest request directly/i);
        assert.deepEqual(prepared[1], input[0]);
    });

    it("does not alter the translator prompt contract", () => {
        const input = [{ role: "user", content: "Translate exactly" }];
        assert.deepEqual(prepareChatMessages(input, "openclaw/translator"), input);
    });

    it("uses bounded no-thinking settings for direct local chat", () => {
        const messages = [{ role: "user", content: "hello" }];
        const payload = ollamaChatPayload(messages, true, 123);
        assert.equal(payload.stream, true);
        assert.equal(payload.think, false);
        assert.equal(payload.options.num_predict, 123);
        assert.equal(payload.messages, messages);
    });

    it("uses a larger but bounded completion budget", () => {
        assert.equal(requestedChatTokens(undefined), 768);
        assert.equal(requestedChatTokens(3072), 3072);
        assert.equal(requestedChatTokens(100_000), 3072);
    });

    it("accepts only non-empty, bounded shared notes", () => {
        const note = normalizeSharedNote({ title: "  Example  ", body: "  Shared body  " });
        assert.equal(note.title, "Example");
        assert.equal(note.body, "Shared body");
        assert.equal(Number.isFinite(note.createdAt), true);
        assert.equal(normalizeSharedNote({ title: "Empty", body: "   " }), null);
        assert.equal(normalizeSharedNote({ title: "Large", body: "x".repeat(200_001) }), null);
        assert.equal(normalizeSharedNote({
            title: "Audio", body: "Transcript", resourceType: "audio", audioMimeType: "text/html",
        }), null);
        assert.deepEqual(
            normalizeSharedNote({
                title: "Audio", body: "Transcript", resourceType: "audio",
                audioMimeType: "audio/mpeg", audioLanguage: "English",
            }).hasAudio,
            true,
        );
    });

    it("allows only the exact shared-note API routes", () => {
        assert.equal(routePath("/studio-api/share-note"), "/share-note");
        assert.equal(routePath("/studio-api/shared-note"), "/shared-note");
        assert.equal(routePath("/studio-api/share-note-audio"), "/share-note-audio");
        assert.equal(routePath("/studio-api/shared-note-audio"), "/shared-note-audio");
        assert.equal(routePath("/studio-api/shared-note/extra"), null);
    });
});

const describeNetwork = process.env.RUN_NETWORK_TESTS === "1" ? describe : describe.skip;

describeNetwork("private Studio API HTTP boundary", () => {
    let server;
    let base;
    let sharedNotesDir;

    before(async () => {
        sharedNotesDir = fs.mkdtempSync(path.join(os.tmpdir(), "livecontent-share-test-"));
        server = createServer({
            gatewayToken: "owner-secret",
            studioToken: "studio-secret",
            sharedNotesDir,
        });
        await new Promise((resolve, reject) => {
            server.once("error", reject);
            server.listen(0, "127.0.0.1", resolve);
        });
        base = `http://127.0.0.1:${server.address().port}`;
    });

    after(() => {
        server.closeAllConnections();
        server.close();
        fs.rmSync(sharedNotesDir, { recursive: true, force: true });
    });

    it("creates and retrieves a public note without exposing its content in the URL", async () => {
        const created = await fetch(`${base}/studio-api/share-note`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Connection: "close" },
            body: JSON.stringify({ title: "Shared title", body: "Shared body" }),
        });
        assert.equal(created.status, 201);
        const { id } = await created.json();
        assert.match(id, /^[a-f0-9]{32}$/);

        const loaded = await fetch(`${base}/studio-api/shared-note`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Connection: "close" },
            body: JSON.stringify({ id }),
        });
        assert.equal(loaded.status, 200);
        assert.deepEqual((await loaded.json()).note.body, "Shared body");
    });

    it("uploads and retrieves audio using only one-time headers and POST bodies", async () => {
        const created = await fetch(`${base}/studio-api/share-note`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Connection: "close" },
            body: JSON.stringify({
                title: "Audio note",
                body: "Audio transcript",
                resourceType: "audio",
                audioMimeType: "audio/mpeg",
                audioLanguage: "English",
            }),
        });
        assert.equal(created.status, 201);
        const { id, uploadToken } = await created.json();
        assert.match(id, /^[a-f0-9]{32}$/);
        assert.match(uploadToken, /^[a-f0-9]{48}$/);

        const audio = Buffer.from("test-audio-bytes");
        const uploaded = await fetch(`${base}/studio-api/share-note-audio`, {
            method: "POST",
            headers: {
                "Content-Type": "audio/mpeg",
                "X-Share-Id": id,
                "X-Share-Upload-Token": uploadToken,
                Connection: "close",
            },
            body: audio,
        });
        assert.equal(uploaded.status, 201);

        const loaded = await fetch(`${base}/studio-api/shared-note`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Connection: "close" },
            body: JSON.stringify({ id }),
        });
        const metadata = (await loaded.json()).note;
        assert.equal(metadata.hasAudio, true);
        assert.equal(metadata.audioLanguage, "English");
        assert.equal(Object.hasOwn(metadata, "audioUploadTokenHash"), false);

        const downloaded = await fetch(`${base}/studio-api/shared-note-audio`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Connection: "close" },
            body: JSON.stringify({ id }),
        });
        assert.equal(downloaded.status, 200);
        assert.equal(downloaded.headers.get("content-disposition"), "inline");
        assert.deepEqual(Buffer.from(await downloaded.arrayBuffer()), audio);
    });

    it("does not expose arbitrary routes", async () => {
        const response = await fetch(`${base}/studio-api/admin`, {
            headers: { Authorization: "Bearer studio-secret", Connection: "close" },
        });
        assert.equal(response.status, 404);
    });

    it("rejects query-string variants of allowed routes", async () => {
        const response = await fetch(`${base}/studio-api/models?admin=true`, {
            headers: { Authorization: "Bearer studio-secret", Connection: "close" },
        });
        assert.equal(response.status, 404);
    });

    it("rejects arbitrary assistant IDs before contacting OpenClaw", async () => {
        const response = await fetch(`${base}/studio-api/chat`, {
            method: "POST",
            headers: {
                Authorization: "Bearer studio-secret",
                "Content-Type": "application/json",
                Connection: "close",
            },
            body: JSON.stringify({
                model: "openclaw/main",
                messages: [{ role: "user", content: "hello" }],
            }),
        });
        assert.equal(response.status, 403);
    });
});
