'use client';

import { use, useCallback, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import ChatPanel from '@/components/ChatPanel';
import SourcesPanel from '@/components/SourcesPanel';
import StudioPanel from '@/components/StudioPanel';
import { api } from '@/lib/api';
import type { Book } from '@/lib/types';
import styles from './book.module.css';

export default function BookPage({ params }: PageProps<'/books/[id]'>) {
  const { id } = use(params);
  const router = useRouter();

  const {
    data: book,
    error: loadError,
    mutate,
  } = useSWR<Book>(`/api/books/${id}`, () => api.getBook(id));
  const [error, setError] = useState('');
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Re-read the book after any change, so every panel reflects it.
  const load = useCallback(async () => {
    await mutate();
  }, [mutate]);

  /**
   * Send a message and stream the reply. The user's message is stored first so
   * a refresh mid-stream does not lose it; the assistant's reply is stored once
   * complete.
   */
  const send = useCallback(
    async (text: string, opts: { quiet?: boolean; display?: string } = {}) => {
      if (!book || streamingText !== null) return;
      setError('');
      try {
        await api.addMessage(book.id, {
          role: 'user',
          content: text,
          quiet: opts.quiet,
          display: opts.display,
        });
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not send that message.');
        return;
      }

      setStreamingText('');
      const controller = new AbortController();
      abortRef.current = controller;
      let acc = '';

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ bookId: book.id }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          throw new Error(detail?.error || `The assistant returned ${res.status}.`);
        }
        if (!res.body) throw new Error('This browser cannot read streaming responses.');

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // SSE frames are separated by a blank line.
          const frames = buffer.split(/\r?\n\r?\n/);
          buffer = frames.pop() ?? '';
          for (const frame of frames) {
            for (const line of frame.split(/\r?\n/)) {
              if (!line.startsWith('data:')) continue;
              const payload = line.slice(5).trim();
              if (!payload || payload === '[DONE]') continue;
              try {
                const json = JSON.parse(payload);
                const delta = json?.choices?.[0]?.delta?.content;
                if (typeof delta === 'string') {
                  acc += delta;
                  setStreamingText(acc);
                }
              } catch {
                // A partial frame; the next chunk completes it.
              }
            }
          }
        }

        if (acc.trim()) {
          await api.addMessage(book.id, { role: 'assistant', content: acc });
        }
      } catch (err) {
        // A deliberate stop keeps whatever streamed in.
        if (err instanceof Error && err.name === 'AbortError') {
          if (acc.trim()) {
            await api.addMessage(book.id, { role: 'assistant', content: acc }).catch(() => null);
          }
        } else {
          setError(err instanceof Error ? err.message : 'The assistant could not be reached.');
        }
      } finally {
        abortRef.current = null;
        setStreamingText(null);
        void load();
      }
    },
    [book, streamingText, load],
  );

  if (loadError) {
    return (
      <main className={styles.missing}>
        <p>That book could not be found.</p>
        <button className="btn" onClick={() => router.push('/')}>
          Back to library
        </button>
      </main>
    );
  }

  if (!book) return <main className={styles.missing}>Loading…</main>;

  return (
    <main className={styles.shell}>
      <SourcesPanel
        bookId={book.id}
        sources={book.sources}
        onChanged={load}
        onSummarise={(titles) =>
          send(
            `I have just added these sources: ${titles.map((t) => `"${t}"`).join(', ')}. ` +
              'Give a short summary of what they cover.',
            { quiet: true, display: `Added ${titles.length} source${titles.length === 1 ? '' : 's'}.` },
          )
        }
      />
      <ChatPanel
        book={book}
        onChanged={load}
        onSend={send}
        onStop={() => abortRef.current?.abort()}
        streaming={streamingText !== null}
        streamingText={streamingText}
        error={error}
      />
      <StudioPanel notes={book.notes} onChanged={load} />
    </main>
  );
}
