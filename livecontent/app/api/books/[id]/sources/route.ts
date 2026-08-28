import { prisma } from '@/lib/db';

type Incoming = {
  title?: unknown;
  url?: unknown;
  snippet?: unknown;
  text?: unknown;
  kind?: unknown;
};

// POST /api/books/[id]/sources — add one or many sources to a book.
// Accepts a single object or an array, so a web import and a document upload
// use the same endpoint.
export async function POST(request: Request, ctx: RouteContext<'/api/books/[id]/sources'>) {
  const { id: bookId } = await ctx.params;
  const body = await request.json().catch(() => null);
  if (!body) return Response.json({ error: 'Invalid JSON body' }, { status: 400 });

  const book = await prisma.book.findUnique({ where: { id: bookId } });
  if (!book) return Response.json({ error: 'Book not found' }, { status: 404 });

  const incoming: Incoming[] = Array.isArray(body) ? body : [body];
  const rows = incoming
    .filter((r) => typeof r.title === 'string' && r.title.trim())
    .map((r) => ({
      bookId,
      title: String(r.title).trim(),
      url: typeof r.url === 'string' && r.url ? r.url : null,
      snippet: typeof r.snippet === 'string' && r.snippet ? r.snippet : null,
      text: typeof r.text === 'string' && r.text ? r.text : null,
      kind: typeof r.kind === 'string' && r.kind ? r.kind : 'Web',
    }));

  if (!rows.length) {
    return Response.json({ error: 'No usable sources supplied' }, { status: 400 });
  }

  // Re-importing the same URL should not duplicate a row. Guard against both
  // URLs already stored and repeats inside this one batch.
  const existing = await prisma.source.findMany({
    where: { bookId, url: { not: null } },
    select: { url: true },
  });
  const seen = new Set(existing.map((s) => s.url));
  const fresh = rows.filter((r) => {
    if (!r.url) return true;
    if (seen.has(r.url)) return false;
    seen.add(r.url);
    return true;
  });

  if (fresh.length) {
    await prisma.source.createMany({ data: fresh });
    await prisma.book.update({ where: { id: bookId }, data: { updatedAt: new Date() } });
  }

  const sources = await prisma.source.findMany({
    where: { bookId },
    orderBy: { createdAt: 'asc' },
  });
  return Response.json(
    { added: fresh.length, skipped: rows.length - fresh.length, sources },
    { status: 201 },
  );
}
