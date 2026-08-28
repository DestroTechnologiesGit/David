import { prisma } from '@/lib/db';
import { callGateway, gatewayReady, withSources, type ChatMessage } from '@/lib/gateway';

// Long agent replies must not be cut short by a static render.
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

/**
 * POST /api/chat — stream a reply for a book.
 *
 * The browser never sees the gateway token: it posts the book id here, the
 * server loads that book's messages and ticked sources, calls the gateway,
 * and pipes the SSE stream straight back.
 */
export async function POST(request: Request) {
  if (!gatewayReady()) {
    return Response.json(
      {
        error:
          'The assistant is not configured. Set OPENCLAW_BASE_URL and ' +
          'OPENCLAW_TOKEN in .env, then restart the server.',
      },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => ({}));
  const bookId = typeof body.bookId === 'string' ? body.bookId : '';
  if (!bookId) return Response.json({ error: 'bookId is required' }, { status: 400 });

  const book = await prisma.book.findUnique({
    where: { id: bookId },
    include: {
      messages: { orderBy: { createdAt: 'asc' } },
      sources: { where: { on: true }, orderBy: { createdAt: 'asc' } },
    },
  });
  if (!book) return Response.json({ error: 'Book not found' }, { status: 404 });

  const history: ChatMessage[] = book.messages.map((m) => ({
    role: m.role as ChatMessage['role'],
    content: m.content,
  }));

  let upstream: Response;
  try {
    upstream = await callGateway(withSources(history, book.sources), {
      stream: true,
      user: `studio-${book.id}`,
      signal: request.signal,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Could not reach the assistant.';
    return Response.json({ error: message }, { status: 502 });
  }

  if (!upstream.body) {
    return Response.json({ error: 'The assistant returned no content.' }, { status: 502 });
  }

  // Pipe the SSE frames through untouched; the client parses them exactly as
  // it would have parsed the gateway's own response.
  return new Response(upstream.body, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-store, no-transform',
      Connection: 'keep-alive',
    },
  });
}
