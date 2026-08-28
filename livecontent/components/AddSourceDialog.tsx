'use client';

import { useEffect, useRef, useState } from 'react';
import styles from './addsource.module.css';

type Props = {
  open: boolean;
  onClose: () => void;
  /** Research a topic: runs the same web search the panel runs. */
  onResearch: (topic: string) => void;
  /** Files chosen or dropped here are extracted by the panel. */
  onFiles: (files: FileList | null) => void;
  /** Text pasted in becomes a source directly. */
  onPaste: (text: string) => void;
  status: { text: string; kind: string } | null;
};

export default function AddSourceDialog({
  open,
  onClose,
  onResearch,
  onFiles,
  onPaste,
  status,
}: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [topic, setTopic] = useState('');
  const [pasting, setPasting] = useState(false);
  const [pasted, setPasted] = useState('');
  const [dropping, setDropping] = useState(false);

  // Drive the native dialog from the `open` prop so Escape and the backdrop
  // behave as the platform expects.
  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) dlg.showModal();
    if (!open && dlg.open) dlg.close();
  }, [open]);

  function submitTopic() {
    const value = topic.trim();
    if (!value) return;
    setTopic('');
    onResearch(value);
  }

  return (
    <dialog ref={ref} className={styles.dialog} onClose={onClose}>
      <button className={styles.close} onClick={onClose} title="Close" aria-label="Close">
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
        </svg>
      </button>

      <div className={styles.head}>
        <h2>Add a source</h2>
        <p>Find sources from a topic, a document, or pasted text.</p>
      </div>

      <div className={styles.body}>
        <div className={styles.search}>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                submitTopic();
              }
            }}
            placeholder="Ask the agent to research a topic…"
            aria-label="Research a topic"
          />
          <button className={styles.go} onClick={submitTopic} title="Research" aria-label="Research">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
            </svg>
          </button>
        </div>
        <p className={styles.hint}>
          The agent searches the web for this, then the results appear in the sidebar
          for you to pick which ones to keep.
        </p>

        {pasting ? (
          <div className={styles.paste}>
            <textarea
              value={pasted}
              onChange={(e) => setPasted(e.target.value)}
              placeholder="Paste the text to use as a source…"
              aria-label="Pasted text"
              autoFocus
            />
            <div className={styles.pasteActions}>
              <button
                className="link-btn"
                onClick={() => {
                  setPasting(false);
                  setPasted('');
                }}
              >
                Cancel
              </button>
              <button
                className="btn"
                disabled={!pasted.trim()}
                onClick={() => {
                  onPaste(pasted.trim());
                  setPasted('');
                  setPasting(false);
                }}
              >
                Add text
              </button>
            </div>
          </div>
        ) : (
          <div
            className={`${styles.drop} ${dropping ? styles.dropping : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDropping(true);
            }}
            onDragLeave={() => setDropping(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDropping(false);
              onFiles(e.dataTransfer.files);
            }}
          >
            <div className={styles.dropTitle}>or drop your files</div>
            <div className={styles.dropSub}>
              PDF, Word .docx, or plain text — read in your browser, never uploaded
            </div>
            <div className={styles.actions}>
              <button className={styles.srcBtn} onClick={() => fileRef.current?.click()}>
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z" />
                </svg>
                Upload files
              </button>
              <button className={styles.srcBtn} onClick={() => setPasting(true)}>
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 2h-4.18C14.4.84 13.3 0 12 0S9.6.84 9.18 2H5a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zm-7 0a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm7 18H5V4h2v3h10V4h2v16z" />
                </svg>
                Copied text
              </button>
            </div>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md"
              hidden
              onChange={(e) => {
                onFiles(e.target.files);
                if (fileRef.current) fileRef.current.value = '';
              }}
            />
          </div>
        )}

        {status && <p className={`status-line ${status.kind}`}>{status.text}</p>}
      </div>
    </dialog>
  );
}
