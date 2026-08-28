// Shapes the API returns, shared by every client component.

export type Source = {
  id: string;
  bookId: string;
  title: string;
  url: string | null;
  snippet: string | null;
  text: string | null;
  kind: string;
  on: boolean;
  createdAt: string;
};

export type Message = {
  id: string;
  bookId: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  quiet: boolean;
  overview: boolean;
  display: string | null;
  createdAt: string;
};

export type Note = {
  id: string;
  bookId: string | null;
  title: string;
  body: string;
  createdAt: string;
  updatedAt: string;
  book?: { id: string; title: string } | null;
};

export type BookSummary = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  _count?: { sources: number; messages: number };
};

export type Book = BookSummary & {
  sources: Source[];
  messages: Message[];
  notes: Note[];
};

export type SearchResult = { title: string; url: string; snippet: string };
