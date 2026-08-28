'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { formatDate, toPlainText } from '@/lib/format';
import { renderMarkdown } from '@/lib/markdown';
import type { Book } from '@/lib/types';
import styles from './chat.module.css';

type Props = {
  book: Book;
  onChanged: () => void;
  streamingText: string | null;
  onSend: (text: string, opts?: { quiet?: boolean; display?: string }) => void;
  onStop: () => void;
  streaming: boolean;
  error: string;
};

export default function ChatPanel({
  book,
  onChanged,
  streamingText,
  onSend,
  onStop,
  streaming,
  error,
}: Props) {
  const router = useRouter();
  const [draft, setDraft] = useState('');
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState(book.title);
  const [noteFlash, setNoteFlash] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Follow the conversation as it grows.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [book.messages.length, streamingText]);

  const overview = book.messages.find((m) => m.overview && m.role === 'assistant');
  const transcript = book.messages.filter((m) => !m.quiet && m !== overview);
  const sourceCount = book.sources.length;

  async function commitRename() {
    const next = titleDraft.trim();
    setRenaming(false);
    // An empty title would leave the header blank, so keep the old one.
    if (!next || next === book.title) {
      setTitleDraft(book.title);
      return;
    }
    await api.renameBook(book.id, next).catch(() => null);
    onChanged();
  }

  async function saveNote() {
    const last = [...book.messages].reverse().find((m) => m.role === 'assistant');
    if (!last) {
      setNoteFlash('Nothing to save yet');
      setTimeout(() => setNoteFlash(''), 1500);
      return;
    }
    await api.createNote({
      title: book.title,
      body: toPlainText(last.content),
      bookId: book.id,
    });
    onChanged();
    setNoteFlash('Saved to Notes');
    setTimeout(() => setNoteFlash(''), 1500);
  }

  function submit() {
    const text = draft.trim();
    if (!text || streaming) return;
    setDraft('');
    onSend(text);
  }

  return (
    <section className="panel" aria-label="Chat">
      <header className={styles.head}>
        <div className={styles.headText}>
          {renaming ? (
            <input
              className={styles.titleInput}
              value={titleDraft}
              autoFocus
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={commitRename}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void commitRename();
                } else if (e.key === 'Escape') {
                  e.preventDefault();
                  setTitleDraft(book.title);
                  setRenaming(false);
                }
              }}
              aria-label="Book title"
            />
          ) : (
            <h1
              className={styles.title}
              title="Click to rename"
              onClick={() => {
                setTitleDraft(book.title);
                setRenaming(true);
              }}
            >
              {book.title}
            </h1>
          )}
          <p className={styles.sub}>
            {sourceCount ? `${sourceCount} source${sourceCount === 1 ? '' : 's'} · ` : ''}
            {formatDate(book.updatedAt)}
          </p>
        </div>
        <div className={styles.headActions}>
          <button
            className="icon-btn"
            title="All notes"
            aria-label="All notes"
            onClick={() => router.push('/notes')}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z" />
            </svg>
          </button>
          <button
            className="icon-btn"
            title="All books"
            aria-label="All books"
            onClick={() => router.push('/')}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M4 4h4v16H4zm6 0h3v16h-3zm5.2.6 3.9-1 3.9 14.6-3.9 1z" />
            </svg>
          </button>
          <button
            className="icon-btn"
            title="Rename"
            aria-label="Rename"
            onClick={() => {
              setTitleDraft(book.title);
              setRenaming(true);
            }}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" />
            </svg>
          </button>
          <button
            className="icon-btn"
            title="Clear conversation"
            aria-label="Clear conversation"
            onClick={async () => {
              if (!confirm('Clear this conversation? Sources and notes are kept.')) return;
              await api.clearMessages(book.id);
              onChanged();
            }}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
            </svg>
          </button>
        </div>
      </header>

      <div className={styles.scroll} ref={scrollRef}>
        {overview && (
          <div className={styles.overview}>
            <div
              className={styles.overviewBody}
              dangerouslySetInnerHTML={{ __html: renderMarkdown(overview.content) }}
            />
          </div>
        )}

        {!overview && !transcript.length && !streamingText && (
          <div className={styles.guide}>
            <strong>Start here.</strong> Search the web on the left, or drop a
            document onto that panel, then ask a question. Save any answer to
            Notes on the right.
          </div>
        )}

        {transcript.map((m) => (
          <div key={m.id} className={`${styles.msg} ${styles[m.role] ?? ''}`}>
            <div className={styles.bubble}>
              {m.role === 'assistant' ? (
                <span dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
              ) : (
                m.display || m.content
              )}
            </div>
          </div>
        ))}

        {streamingText !== null && (
          <div className={`${styles.msg} ${styles.assistant}`}>
            <div className={styles.bubble}>
              {streamingText ? (
                <span dangerouslySetInnerHTML={{ __html: renderMarkdown(streamingText) }} />
              ) : (
                <span className={styles.waiting}>Waiting for the assistant…</span>
              )}
            </div>
          </div>
        )}

        {error && <p className="status-line error">{error}</p>}
      </div>

      <div className={styles.composerWrap}>
        <div className={styles.chips}>
          <button className={styles.chip} onClick={() => onSend('Summarise what we have discussed so far.')}>
            Summarise
          </button>
          <button className={styles.chip} onClick={() => onSend('Explain that in simpler terms.')}>
            Explain simply
          </button>
          <button className={styles.saveNote} onClick={saveNote}>
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z" />
            </svg>
            {noteFlash || 'Save Note'}
          </button>
        </div>
        <div className={styles.composer}>
          <textarea
            rows={1}
            value={draft}
            placeholder="Ask a question…"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            aria-label="Ask a question"
          />
          <button
            className={styles.send}
            onClick={streaming ? onStop : submit}
            title={streaming ? 'Stop' : 'Send'}
            aria-label={streaming ? 'Stop' : 'Send'}
          >
            {streaming ? (
              <svg viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            )}
          </button>
        </div>
        <p className={styles.disclaimer}>
          LiveContent can make mistakes. Check important information.
        </p>
      </div>
    </section>
  );
}
