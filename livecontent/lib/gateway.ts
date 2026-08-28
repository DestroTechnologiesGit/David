// Talking to the OpenClaw gateway.
//
// Everything here runs on the server: the token is read from the environment
// and never reaches the browser, unlike the original page which sent it from
// client-side code.

export type ChatMessage = {
  role: 'system' | 'user' | 'assistant';
  content: string;
};

export function gatewayConfig() {
  const base = (process.env.OPENCLAW_BASE_URL ?? '').replace(/\/+$/, '');
  const token = process.env.OPENCLAW_TOKEN ?? '';
  const model = process.env.OPENCLAW_MODEL || 'openclaw/default';
  return { base, token, model };
}

export function gatewayReady() {
  const { base, token } = gatewayConfig();
  return Boolean(base && token);
}

/** POST to the gateway's chat endpoint. `stream` picks SSE or a single reply. */
export async function callGateway(
  messages: ChatMessage[],
  opts: { stream?: boolean; user?: string; signal?: AbortSignal } = {},
) {
  const { base, token, model } = gatewayConfig();
  if (!base || !token) {
    throw new Error(
      'The speech gateway is not configured. Set OPENCLAW_BASE_URL and ' +
        'OPENCLAW_TOKEN in .env, then restart the server.',
    );
  }

  const res = await fetch(`${base}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    signal: opts.signal,
    body: JSON.stringify({
      model,
      stream: opts.stream ?? false,
      // A stable `user` keeps one gateway session per book.
      ...(opts.user ? { user: opts.user } : {}),
      messages,
    }),
  });

  if (!res.ok) {
    const detail = (await res.text()).slice(0, 300);
    throw new Error(`Gateway returned ${res.status}. ${detail}`);
  }
  return res;
}

/** One-shot call that returns the whole reply as a string. */
export async function askAgent(prompt: string): Promise<string> {
  const res = await callGateway([{ role: 'user', content: prompt }]);
  const json = await res.json();
  const content = json?.choices?.[0]?.message?.content;
  if (!content) throw new Error('The assistant returned an empty reply.');
  return content as string;
}

/**
 * Ticked sources ride along as a system message, so an answer is grounded in
 * what the user selected. Rebuilt per request, as the selection can change.
 */
export function withSources(
  messages: ChatMessage[],
  sources: { title: string; url: string | null; snippet: string | null; text: string | null }[],
): ChatMessage[] {
  if (!sources.length) return messages;

  const list = sources
    .map((s, i) => {
      const head = `${i + 1}. ${s.title}${s.url ? ` — ${s.url}` : ''}`;
      const body = s.text
        ? `\n${s.text.slice(0, 20000)}`
        : s.snippet
          ? `\n${s.snippet}`
          : '';
      return head + body;
    })
    .join('\n\n');

  return [
    {
      role: 'system',
      content:
        'Answer using these sources the user has selected. Cite them by title ' +
        'where relevant. If they do not cover the question, say so rather than ' +
        `guessing.\n\n${list}`,
    },
    ...messages,
  ];
}
