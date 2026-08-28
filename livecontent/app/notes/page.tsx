'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { relativeTime } from '@/lib/format';
import type { Note } from '@/lib/types';
import styles from './notes.module.css';

export default function NotesPage() {
  const router = useRouter();
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    setNotes(await api.listNotes().catch(() => []));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const q = filter.trim().toLowerCase();
  const shown = (notes ?? []).filter(
    (n) =>
      !q ||
      n.title.toLowerCase().includes(q) ||
      n.body.toLowerCase().includes(q) ||
      (n.book?.title ?? '').toLowerCase().includes(q),
  );

  return (
    <main className={styles.page}>
      <header className={styles.head}>
        <div>
          <h1>All notes</h1>
          <p>
            {!notes
              ? 'Loading…'
              : !notes.length
                ? 'No notes yet'
                : q
                  ? `${shown.length} of ${notes.length} notes`
                  : `${notes.length} note${notes.length === 1 ? '' : 's'}`}
          </p>
        </div>
        <div className={styles.actions}>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search notes"
            aria-label="Search notes"
          />
          <button className="icon-btn" title="Close" aria-label="Close" onClick={() => router.push('/')}>
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
            </svg>
          </button>
        </div>
      </header>

      {notes && !shown.length ? (
        <p className="empty">{q ? 'No notes match that search.' : 'No notes yet.'}</p>
      ) : (
        <div className={styles.grid}>
          {shown.map((note) => (
            <button
              key={note.id}
              type="button"
              className={styles.card}
              onClick={() => router.push(`/notes/${note.id}`)}
            >
              <span className={styles.cardTitle}>{note.title}</span>
              <span className={styles.cardBody}>{note.body.slice(0, 220)}</span>
              <span className={styles.cardMeta}>
                {note.book?.title ? `${note.book.title} · ` : ''}
                {relativeTime(note.updatedAt)}
              </span>
            </button>
          ))}
        </div>
      )}
    </main>
  );
}
