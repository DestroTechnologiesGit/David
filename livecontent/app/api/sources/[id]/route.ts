import { prisma } from '@/lib/db';

// PATCH /api/sources/[id] — tick or untick a source.
export async function PATCH(request: Request, ctx: RouteContext<'/api/sources/[id]'>) {
  const { id } = await ctx.params;
  const body = await request.json().catch(() => ({}));
  const data: { on?: boolean } = {};
  if (typeof body.on === 'boolean') data.on = body.on;

  const source = await prisma.source.update({ where: { id }, data }).catch(() => null);
  if (!source) return Response.json({ error: 'Source not found' }, { status: 404 });
  return Response.json(source);
}

// DELETE /api/sources/[id]
export async function DELETE(_req: Request, ctx: RouteContext<'/api/sources/[id]'>) {
  const { id } = await ctx.params;
  const deleted = await prisma.source.delete({ where: { id } }).catch(() => null);
  if (!deleted) return Response.json({ error: 'Source not found' }, { status: 404 });
  return new Response(null, { status: 204 });
}
