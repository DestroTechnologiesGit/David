'use client';

import { useRef, useState } from 'react';
import { api } from '@/lib/api';
import { hostOf } from '@/lib/format';
import { extractFileText } from '@/lib/extract';
import type { SearchResult, Source } from '@/lib/types';
import styles from './sources.module.css';

type Props = {
  bookId: string;
  sources: Source[];
  onChanged: () => void;
  onSummarise: (added: string[]) => void;
};

export default function SourcesPanel({ bookId, sources, onChanged, onSummarise }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [status, setStatus] = useState<{ text: string; kind: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [dropping, setDropping] = useState(false);

  function say(text: string, kind = 'busy') {
    setStatus(text ? { text, kind } : null);
  }

  async function runSearch() {
    const q = query.trim();
    if (!q) return say('Enter something to search for.', 'error');
    setBusy(true);
    setResults(null);
    say(`Searching the web for "${q}"…`);
    try {
      const { results: found } = await api.search(q);
      setResults(found);
      setPicked(new Set(found.map((r) => r.url)));
      say('');
    } catch (err) {
      say(err instanceof Error ? err.message : 'Search failed.', 'error');
    } finally {
      setBusy(false);
    }
  }

  async function addToChat() {
    const chosen = (results ?? []).filter((r) => picked.has(r.url));
    if (!chosen.length) return;
    setBusy(true);
    try {
      const res = await api.addSources(bookId, chosen);
      setResults(null);
      setPicked(new Set());
      onChanged();
      say(
        res.added
          ? `Added ${res.added} source${res.added === 1 ? '' : 's'}` +
              (res.skipped ? ` (${res.skipped} already saved)` : '') + '.'
          : 'Those sources are already saved.',
        'ok',
      );
      if (res.added) onSummarise(chosen.slice(0, res.added).map((c) => c.title));
    } catch (err) {
      say(err instanceof Error ? err.message : 'Could not add those sources.', 'error');
    } finally {
      setBusy(false);
    }
  }

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    try {
      const docs = [];
      for (const file of Array.from(files)) {
        say(`Reading ${file.name}…`);
        docs.push({
          title: file.name,
          kind: 'Document',
          text: await extractFileText(file),
        });
      }
      const res = await api.addSources(bookId, docs);
      onChanged();
      say(`Added ${res.added} document${res.added === 1 ? '' : 's'}.`, 'ok');
      if (res.added) onSummarise(docs.map((d) => d.title));
    } catch (err) {
      say(err instanceof Error ? err.message : 'Could not read that file.', 'error');
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function toggle(source: Source) {
    await api.toggleSource(source.id, !source.on).catch(() => null);
    onChanged();
  }

  const onCount = sources.filter((s) => s.on).length;

  return (
    <section
      className="panel"
      aria-label="Sources"
      onDragOver={(e) => {
        e.preventDefault();
        setDropping(true);
      }}
      onDragLeave={() => setDropping(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDropping(false);
        void handleFiles(e.dataTransfer.files);
      }}
    >
      <header className={styles.head}>
        <h2 className={styles.title}>Find Sources</h2>
      </header>

      <div className={styles.body}>
        <div className={styles.search}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                void runSearch();
              }
            }}
            placeholder="What are you looking for?"
            aria-label="Search the web for sources"
          />
          <div className={styles.searchRow}>
            <span className={styles.scope}>
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm6.9 6h-2.9a15.6 15.6 0 0 0-1.3-3.4A8 8 0 0 1 18.9 8zM12 4c.7 1 1.3 2.4 1.7 4h-3.4C10.7 6.4 11.3 5 12 4zM4.3 14a8 8 0 0 1 0-4h3.3a17 17 0 0 0 0 4zm.8 2h2.9c.3 1.2.8 2.4 1.3 3.4A8 8 0 0 1 5.1 16zm2.9-8H5.1a8 8 0 0 1 4.2-3.4C8.8 5.6 8.3 6.8 8 8zM12 20c-.7-1-1.3-2.4-1.7-4h3.4c-.4 1.6-1 3-1.7 4zm2.1-6H9.9a15 15 0 0 1 0-4h4.2a15 15 0 0 1 0 4zm.6 5.4c.5-1 1-2.2 1.3-3.4h2.9a8 8 0 0 1-4.2 3.4zm1.7-5.4a17 17 0 0 0 0-4h3.3a8 8 0 0 1 0 4z" />
              </svg>
              Web
            </span>
            <button
              className={styles.go}
              onClick={runSearch}
              disabled={busy}
              title="Search"
              aria-label="Search"
            >
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
              </svg>
            </button>
          </div>
        </div>

        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.md"
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />

        {status && <p className={`status-line ${status.kind}`}>{status.text}</p>}

        {results && results.length > 0 && (
          <div className={styles.results}>
            <div className={styles.resultsHead}>
              <span>
                Found {results.length} source{results.length === 1 ? '' : 's'}
              </span>
              <button
                className="link-btn"
                onClick={() =>
                  setPicked(
                    picked.size === results.length
                      ? new Set()
                      : new Set(results.map((r) => r.url)),
                  )
                }
              >
                {picked.size === results.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>
            {results.map((r) => (
              <label key={r.url} className={styles.result}>
                <input
                  type="checkbox"
                  checked={picked.has(r.url)}
                  onChange={() => {
                    const next = new Set(picked);
                    if (next.has(r.url)) next.delete(r.url);
                    else next.add(r.url);
                    setPicked(next);
                  }}
                />
                <span className={styles.resultText}>
                  <span className={styles.resultTitle}>{r.title}</span>
                  <span className={styles.resultHost}>{hostOf(r.url)}</span>
                </span>
              </label>
            ))}
            <div className={styles.resultsFoot}>
              <button className="link-btn danger" onClick={() => setResults(null)}>
                Discard
              </button>
              <button className="btn" onClick={addToChat} disabled={busy || !picked.size}>
                Add to Chat
              </button>
            </div>
          </div>
        )}

        {sources.length > 0 && (
          <div className={styles.saved}>
            <div className={styles.savedHead}>
              <span>
                {onCount} of {sources.length} selected
              </span>
            </div>
            {sources.map((s) => (
              <label key={s.id} className={styles.source}>
                <input type="checkbox" checked={s.on} onChange={() => toggle(s)} />
                <span className={styles.sourceText}>
                  <span className={styles.sourceTitle}>{s.title}</span>
                  <span className={styles.sourceHost}>
                    {s.kind === 'Document' ? 'Document' : hostOf(s.url)}
                  </span>
                </span>
              </label>
            ))}
          </div>
        )}

        {dropping && <p className="status-line busy">Drop to add these documents.</p>}

        {!sources.length && !results && (
          <p className="empty">
            Saved sources will appear here. Search the web above, or drop a
            PDF, .docx or .txt onto this panel.
          </p>
        )}
      </div>
    </section>
  );
}
