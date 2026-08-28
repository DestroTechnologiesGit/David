import { prisma } from '@/lib/db';

// GET /api/notes — every note, newest first, with its book's title.
export async function GET() {
  const notes = await prisma.note.findMany({
    orderBy: { createdAt: 'desc' },
    include: { book: { select: { id: true, title: true } } },
  });
  return Response.json(notes);
}

// POST /api/notes — save a note.
export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const title = typeof body.title === 'string' && body.title.trim()
    ? body.title.trim()
    : 'Untitled note';
  const bodyText = typeof body.body === 'string' ? body.body : '';
  if (!bodyText.trim()) {
    return Response.json({ error: 'Note body is required' }, { status: 400 });
  }

  const note = await prisma.note.create({
    data: {
      title,
      body: bodyText,
      bookId: typeof body.bookId === 'string' ? body.bookId : null,
    },
    include: { book: { select: { id: true, title: true } } },
  });
  return Response.json(note, { status: 201 });
}
