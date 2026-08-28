import { askAgent, gatewayReady } from '@/lib/gateway';

export const dynamic = 'force-dynamic';
export const maxDuration = 120;

export type SearchResult = { title: string; url: string; snippet: string };

/**
 * The gateway exposes search to the agent as a tool, not over HTTP, so we ask
 * the agent to search and return JSON, then parse whatever shape comes back.
 */
function parseResults(text: string): SearchResult[] {
  const candidates: string[] = [];
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenced) candidates.push(fenced[1]);
  const bare = text.match(/\[[\s\S]*\]/);
  if (bare) candidates.push(bare[0]);
  candidates.push(text);

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate.trim());
      if (Array.isArray(parsed) && parsed.length) {
        const rows = parsed
          .filter((r) => r && (r.url || r.link))
          .map((r) => ({
            title: String(r.title || r.name || r.url || 'Untitled').slice(0, 200),
            url: String(r.url || r.link),
            snippet: String(r.snippet || r.description || r.summary || '').slice(0, 400),
          }));
        if (rows.length) return rows;
      }
    } catch {
      // Try the next candidate shape.
    }
  }
  return [];
}

function searchPrompt(query: string) {
  return (
    'Use your web_search tool. Find sources about: ' +
    query +
    '\n\nReply with ONLY a JSON array, no prose and no code fence. Each item ' +
    'must be {"title": "...", "url": "https://...", "snippet": "one sentence"}. ' +
    'Return up to 10 real results with real URLs from the search tool. ' +
    'If the search tool is unavailable, reply with exactly: NO_SEARCH'
  );
}

// POST /api/search — { query } → { results }
export async function POST(request: Request) {
  if (!gatewayReady()) {
    return Response.json(
      {
        error:
          'Search is not configured. Set OPENCLAW_BASE_URL and OPENCLAW_TOKEN ' +
          'in .env, then restart the server.',
      },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => ({}));
  const query = typeof body.query === 'string' ? body.query.trim() : '';
  if (!query) return Response.json({ error: 'A search query is required' }, { status: 400 });

  try {
    const reply = await askAgent(searchPrompt(query));
    if (/^\s*NO_SEARCH\s*$/.test(reply)) {
      return Response.json(
        {
          error:
            'The assistant has no web search available. A search provider ' +
            'needs to be configured on the server.',
        },
        { status: 502 },
      );
    }
    const results = parseResults(reply);
    if (!results.length) {
      return Response.json(
        { error: 'No results could be read from the reply. Try a different wording.' },
        { status: 502 },
      );
    }
    return Response.json({ results });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Search failed.';
    return Response.json({ error: message }, { status: 502 });
  }
}
