import { prisma } from '@/lib/db';

// GET /api/books/[id] — one book with everything it holds.
export async function GET(_req: Request, ctx: RouteContext<'/api/books/[id]'>) {
  const { id } = await ctx.params;
  const book = await prisma.book.findUnique({
    where: { id },
    include: {
      sources: { orderBy: { createdAt: 'asc' } },
      messages: { orderBy: { createdAt: 'asc' } },
      notes: { orderBy: { createdAt: 'desc' } },
    },
  });
  if (!book) return Response.json({ error: 'Book not found' }, { status: 404 });
  return Response.json(book);
}

// PATCH /api/books/[id] — rename.
export async function PATCH(request: Request, ctx: RouteContext<'/api/books/[id]'>) {
  const { id } = await ctx.params;
  const body = await request.json().catch(() => ({}));

  const title = typeof body.title === 'string' ? body.title.trim() : '';
  // An empty title would leave the header blank, so it is rejected.
  if (!title) {
    return Response.json({ error: 'A title is required' }, { status: 400 });
  }

  const book = await prisma.book
    .update({ where: { id }, data: { title } })
    .catch(() => null);
  if (!book) return Response.json({ error: 'Book not found' }, { status: 404 });
  return Response.json(book);
}

// DELETE /api/books/[id] — remove the book and everything in it.
export async function DELETE(_req: Request, ctx: RouteContext<'/api/books/[id]'>) {
  const { id } = await ctx.params;
  const deleted = await prisma.book.delete({ where: { id } }).catch(() => null);
  if (!deleted) return Response.json({ error: 'Book not found' }, { status: 404 });
  return new Response(null, { status: 204 });
}
