'use client';

import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { relativeTime } from '@/lib/format';
import type { Note } from '@/lib/types';
import styles from './studio.module.css';

type Props = {
  notes: Note[];
  onChanged: () => void;
};

export default function StudioPanel({ notes, onChanged }: Props) {
  const router = useRouter();

  return (
    <section className="panel" aria-label="Studio">
      <header className={styles.head}>
        <div>
          <h2 className={styles.title}>Studio</h2>
          <p className={styles.sub}>Saved work</p>
        </div>
      </header>

      <div className={styles.body}>
        <div className={styles.notesHead}>
          <h3>Notes</h3>
          <button className="link-btn" onClick={() => router.push('/notes')}>
            View all
          </button>
        </div>

        {!notes.length ? (
          <p className={styles.empty}>
            Nothing saved yet. Use Save Note under the chat to keep an answer.
          </p>
        ) : (
          <div>
            {notes.slice(0, 8).map((note) => (
              <div key={note.id} className={styles.note}>
                <button
                  type="button"
                  className={styles.noteOpen}
                  onClick={() => router.push(`/notes/${note.id}`)}
                >
                  <span className={styles.noteIcon}>
                    <svg viewBox="0 0 24 24" fill="currentColor">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zm-1 7V3.5L18.5 9zM8 13h8v2H8zm0 4h8v2H8z" />
                    </svg>
                  </span>
                  <span className={styles.noteText}>
                    <span className={styles.noteTitle}>{note.title}</span>
                    <span className={styles.noteMeta}>{relativeTime(note.updatedAt)}</span>
                  </span>
                </button>
                <button
                  type="button"
                  className={styles.noteDel}
                  title="Delete note"
                  aria-label={`Delete ${note.title}`}
                  onClick={async () => {
                    await api.deleteNote(note.id).catch(() => null);
                    onChanged();
                  }}
                >
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
