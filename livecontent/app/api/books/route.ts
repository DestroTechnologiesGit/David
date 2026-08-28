import { prisma } from '@/lib/db';

// GET /api/books — every book, newest activity first.
export async function GET() {
  const books = await prisma.book.findMany({
    orderBy: { updatedAt: 'desc' },
    include: {
      _count: { select: { sources: true, messages: true } },
    },
  });
  return Response.json(books);
}

// POST /api/books — create a book.
export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const title =
    typeof body.title === 'string' && body.title.trim()
      ? body.title.trim()
      : 'Untitled book';

  const book = await prisma.book.create({ data: { title } });
  return Response.json(book, { status: 201 });
}
