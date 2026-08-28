'use client';

import { use, useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { relativeTime } from '@/lib/format';
import type { Note } from '@/lib/types';
import styles from './note.module.css';

export default function NotePage({ params }: PageProps<'/notes/[id]'>) {
  const { id } = use(params);
  const router = useRouter();

  const [note, setNote] = useState<Note | null>(null);
  const [missing, setMissing] = useState(false);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [saved, setSaved] = useState(true);
  const [status, setStatus] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api
      .getNote(id)
      .then((n) => {
        setNote(n);
        setTitle(n.title);
        setBody(n.body);
      })
      .catch(() => setMissing(true));
  }, [id]);

  const save = useCallback(
    async (patch: { title?: string; body?: string }) => {
      try {
        const updated = await api.updateNote(id, patch);
        setNote(updated);
        setSaved(true);
        setStatus(`Saved ${relativeTime(updated.updatedAt)}`);
      } catch (err) {
        setStatus(err instanceof Error ? err.message : 'Could not save.');
      }
    },
    [id],
  );

  // Autosave shortly after typing stops, so edits are not lost on navigation.
  function edit(next: { title?: string; body?: string }) {
    if (next.title !== undefined) setTitle(next.title);
    if (next.body !== undefined) setBody(next.body);
    setSaved(false);
    setStatus('Editing…');
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const patch: { title?: string; body?: string } = {};
      if (next.title !== undefined && next.title.trim()) patch.title = next.title;
      if (next.body !== undefined) patch.body = next.body;
      if (Object.keys(patch).length) void save(patch);
    }, 700);
  }

  // A pending edit must not be dropped when leaving the page.
  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  if (missing) {
    return (
      <main className={styles.missing}>
        <p>That note could not be found.</p>
        <button className="btn" onClick={() => router.push('/notes')}>
          All notes
        </button>
      </main>
    );
  }

  if (!note) return <main className={styles.missing}>Loading…</main>;

  return (
    <main className={styles.page}>
      <div className={styles.sheet}>
        <header className={styles.head}>
          <nav className={styles.crumbs}>
            <button className="link-btn" onClick={() => router.push('/notes')}>
              Notes
            </button>
            {note.book && (
              <>
                <span aria-hidden="true">›</span>
                <button className="link-btn" onClick={() => router.push(`/books/${note.book!.id}`)}>
                  {note.book.title}
                </button>
              </>
            )}
          </nav>
          <button
            className="icon-btn"
            title="Delete note"
            aria-label="Delete note"
            onClick={async () => {
              if (!confirm('Delete this note?')) return;
              await api.deleteNote(id).catch(() => null);
              router.push('/notes');
            }}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
            </svg>
          </button>
        </header>

        <input
          className={styles.title}
          value={title}
          onChange={(e) => edit({ title: e.target.value })}
          onBlur={() => {
            if (title.trim() && title !== note.title) void save({ title });
          }}
          placeholder="Note title"
          aria-label="Note title"
        />

        <textarea
          className={styles.body}
          value={body}
          onChange={(e) => edit({ body: e.target.value })}
          onBlur={() => {
            if (body !== note.body) void save({ body });
          }}
          placeholder="Write your note…"
          aria-label="Note body"
        />

        <footer className={styles.foot}>
          <span className={styles.status}>
            {saved ? status || `Saved ${relativeTime(note.updatedAt)}` : status}
          </span>
          <button
            className="btn secondary"
            onClick={() => void save({ title, body })}
            disabled={saved}
          >
            Save now
          </button>
        </footer>
      </div>
    </main>
  );
}
