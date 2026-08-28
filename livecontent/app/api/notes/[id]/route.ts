import { prisma } from '@/lib/db';

// GET /api/notes/[id] — one note, for the editor view.
export async function GET(_req: Request, ctx: RouteContext<'/api/notes/[id]'>) {
  const { id } = await ctx.params;
  const note = await prisma.note.findUnique({
    where: { id },
    include: { book: { select: { id: true, title: true } } },
  });
  if (!note) return Response.json({ error: 'Note not found' }, { status: 404 });
  return Response.json(note);
}

// PATCH /api/notes/[id] — save edits from the note editor.
export async function PATCH(request: Request, ctx: RouteContext<'/api/notes/[id]'>) {
  const { id } = await ctx.params;
  const body = await request.json().catch(() => ({}));

  const data: { title?: string; body?: string } = {};
  if (typeof body.title === 'string' && body.title.trim()) data.title = body.title.trim();
  if (typeof body.body === 'string') data.body = body.body;
  if (!Object.keys(data).length) {
    return Response.json({ error: 'Nothing to update' }, { status: 400 });
  }

  const note = await prisma.note
    .update({ where: { id }, data, include: { book: { select: { id: true, title: true } } } })
    .catch(() => null);
  if (!note) return Response.json({ error: 'Note not found' }, { status: 404 });
  return Response.json(note);
}

// DELETE /api/notes/[id]
export async function DELETE(_req: Request, ctx: RouteContext<'/api/notes/[id]'>) {
  const { id } = await ctx.params;
  const deleted = await prisma.note.delete({ where: { id } }).catch(() => null);
  if (!deleted) return Response.json({ error: 'Note not found' }, { status: 404 });
  return new Response(null, { status: 204 });
}
