import { prisma } from '@/lib/db';

// POST /api/books/[id]/messages — append a chat message.
export async function POST(request: Request, ctx: RouteContext<'/api/books/[id]/messages'>) {
  const { id: bookId } = await ctx.params;
  const body = await request.json().catch(() => ({}));

  const role = body.role === 'assistant' || body.role === 'system' ? body.role : 'user';
  const content = typeof body.content === 'string' ? body.content : '';
  if (!content.trim()) {
    return Response.json({ error: 'Message content is required' }, { status: 400 });
  }

  const book = await prisma.book.findUnique({ where: { id: bookId } });
  if (!book) return Response.json({ error: 'Book not found' }, { status: 404 });

  const message = await prisma.message.create({
    data: {
      bookId,
      role,
      content,
      quiet: body.quiet === true,
      overview: body.overview === true,
      display: typeof body.display === 'string' ? body.display : null,
    },
  });
  await prisma.book.update({ where: { id: bookId }, data: { updatedAt: new Date() } });
  return Response.json(message, { status: 201 });
}

// DELETE /api/books/[id]/messages — clear the conversation, keeping sources.
export async function DELETE(_req: Request, ctx: RouteContext<'/api/books/[id]/messages'>) {
  const { id: bookId } = await ctx.params;
  await prisma.message.deleteMany({ where: { bookId } });
  return new Response(null, { status: 204 });
}
