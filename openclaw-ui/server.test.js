"use strict";

const assert = require("node:assert/strict");
const { after, before, describe, it } = require("node:test");
const {
    createServer,
    normalizeResults,
    parseResults,
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

    it("normalizes Caddy and direct API paths", () => {
        assert.equal(routePath("/studio-api/chat"), "/chat");
        assert.equal(routePath("/chat?x=1"), "/chat");
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
});

const describeNetwork = process.env.RUN_NETWORK_TESTS === "1" ? describe : describe.skip;

describeNetwork("private Studio API HTTP boundary", () => {
    let server;
    let base;

    before(async () => {
        server = createServer({ gatewayToken: "owner-secret", studioToken: "studio-secret" });
        await new Promise((resolve, reject) => {
            server.once("error", reject);
            server.listen(0, "127.0.0.1", resolve);
        });
        base = `http://127.0.0.1:${server.address().port}`;
    });

    after(() => {
        server.closeAllConnections();
        server.close();
    });

    it("rejects a missing restricted key", async () => {
        const response = await fetch(`${base}/studio-api/models`, {
            headers: { Connection: "close" },
        });
        assert.equal(response.status, 401);
    });

    it("does not expose arbitrary routes", async () => {
        const response = await fetch(`${base}/studio-api/admin`, {
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
