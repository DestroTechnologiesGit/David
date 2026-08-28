// Thin client for the app's own API routes. Every call goes to /api/*, so the
// gateway token stays on the server.

import type { Book, BookSummary, Message, Note, SearchResult, Source } from './types';

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(data?.error || `Request failed with ${res.status}`);
  }
  return data as T;
}

export const api = {
  // ---- books ----
  listBooks: () => req<BookSummary[]>('/api/books'),
  getBook: (id: string) => req<Book>(`/api/books/${id}`),
  createBook: (title?: string) =>
    req<BookSummary>('/api/books', { method: 'POST', body: JSON.stringify({ title }) }),
  renameBook: (id: string, title: string) =>
    req<BookSummary>(`/api/books/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
  deleteBook: (id: string) => req<void>(`/api/books/${id}`, { method: 'DELETE' }),

  // ---- sources ----
  addSources: (
    bookId: string,
    sources: Partial<Pick<Source, 'title' | 'url' | 'snippet' | 'text' | 'kind'>>[],
  ) =>
    req<{ added: number; skipped: number; sources: Source[] }>(
      `/api/books/${bookId}/sources`,
      { method: 'POST', body: JSON.stringify(sources) },
    ),
  toggleSource: (id: string, on: boolean) =>
    req<Source>(`/api/sources/${id}`, { method: 'PATCH', body: JSON.stringify({ on }) }),
  deleteSource: (id: string) => req<void>(`/api/sources/${id}`, { method: 'DELETE' }),

  // ---- messages ----
  addMessage: (
    bookId: string,
    message: { role: string; content: string; quiet?: boolean; overview?: boolean; display?: string },
  ) =>
    req<Message>(`/api/books/${bookId}/messages`, {
      method: 'POST',
      body: JSON.stringify(message),
    }),
  clearMessages: (bookId: string) =>
    req<void>(`/api/books/${bookId}/messages`, { method: 'DELETE' }),

  // ---- notes ----
  listNotes: () => req<Note[]>('/api/notes'),
  getNote: (id: string) => req<Note>(`/api/notes/${id}`),
  createNote: (note: { title: string; body: string; bookId?: string | null }) =>
    req<Note>('/api/notes', { method: 'POST', body: JSON.stringify(note) }),
  updateNote: (id: string, patch: { title?: string; body?: string }) =>
    req<Note>(`/api/notes/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  deleteNote: (id: string) => req<void>(`/api/notes/${id}`, { method: 'DELETE' }),

  // ---- agent ----
  search: (query: string) =>
    req<{ results: SearchResult[] }>('/api/search', {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),
};
