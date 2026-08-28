'use client';

import { useState } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { api } from '@/lib/api';
import { bookEmoji, relativeTime } from '@/lib/format';
import type { BookSummary } from '@/lib/types';
import styles from './library.module.css';

export default function LibraryPage() {
  const router = useRouter();
  const { data: books, error: loadError, mutate } = useSWR<BookSummary[]>(
    '/api/books',
    () => api.listBooks(),
  );
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  async function newBook() {
    setCreating(true);
    try {
      const book = await api.createBook();
      router.push(`/books/${book.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create a book.');
      setCreating(false);
    }
  }

  async function remove(book: BookSummary) {
    // Deleting takes the sources, chat and notes with it, so confirm first.
    if (!confirm(`Delete "${book.title}" and everything in it?`)) return;
    try {
      await api.deleteBook(book.id);
      void mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete that book.');
    }
  }

  return (
    <main className={styles.library}>
      <div className={styles.inner}>
        <header className={styles.head}>
          <div>
            <Image
              src="/logo.png"
              alt="LiveContent"
              width={320}
              height={110}
              priority
              className={styles.logo}
            />
            <h1 className={styles.title}>Your books</h1>
            <p className={styles.sub}>Choose a book to open, or start a new one.</p>
          </div>
          <button className="btn" onClick={newBook} disabled={creating}>
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
            </svg>
            {creating ? 'Creating…' : 'New Book'}
          </button>
        </header>

        {(error || loadError) && (
          <p className="status-line error">
            {error || 'Could not load your books.'}
          </p>
        )}

        {books === undefined ? (
          <p className={styles.loading}>Loading your books…</p>
        ) : books.length === 0 ? (
          <div className={styles.emptyState}>
            No books yet. Create one to start collecting sources.
          </div>
        ) : (
          <div className={styles.grid}>
            {books.map((book) => {
              const count = book._count?.sources ?? 0;
              const meta =
                (count ? `${count} source${count === 1 ? '' : 's'} · ` : '') +
                relativeTime(book.updatedAt);
              return (
                <div key={book.id} className={styles.card}>
                  <button
                    type="button"
                    className={styles.cardOpen}
                    onClick={() => router.push(`/books/${book.id}`)}
                  >
                    <span className={styles.emoji}>{bookEmoji(book.title)}</span>
                    <span className={styles.cardTitle}>{book.title}</span>
                    <span className={styles.cardMeta}>{meta}</span>
                  </button>
                  <button
                    type="button"
                    className={styles.del}
                    title="Delete book"
                    aria-label={`Delete ${book.title}`}
                    onClick={() => remove(book)}
                  >
                    <svg viewBox="0 0 24 24" fill="currentColor">
                      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                    </svg>
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
