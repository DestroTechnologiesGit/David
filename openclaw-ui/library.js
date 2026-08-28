/* LiveContent™ library — the book picker.
 *
 * A standalone page: opening a book navigates to index.html rather than
 * revealing a hidden panel. The two pages share state only through
 * localStorage, so the small helpers below are duplicated from app.js by
 * design rather than imported.
 */
(() => {
    "use strict";

    const CONVOS = 'openclaw.studio.convos.v1';
    // Which book index.html should open. Set here, read there.
    const ACTIVE = 'openclaw.studio.active.v1';

    function readJSON(key, fallback) {
        try {
            const raw = localStorage.getItem(key);
            return raw ? JSON.parse(raw) : fallback;
        } catch (e) { return fallback; }
    }

    function writeJSON(key, value) {
        try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
    }

    let convos = readJSON(CONVOS, []);

    const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, ch => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
        ));
    }

    // Same table as app.js, so a book keeps one face across both pages.
    const TOPIC_EMOJI = [
        [/solar|renewable|photovolt|panel/, '☀️'],
        [/energy|electric|power|battery|grid/, '⚡'],
        [/health|medic|clinic|patient|disease/, '\u{1FA7A}'],
        [/finance|tax|money|invest|bank|credit|cost|price/, '\u{1F4B0}'],
        [/law|legal|policy|regulat|court/, '⚖️'],
        [/food|recipe|cook|nutrit|diet/, '\u{1F37D}️'],
        [/travel|flight|hotel|tour|city|country/, '✈️'],
        [/code|software|program|develop|api|data/, '\u{1F4BB}'],
        [/science|research|study|physic|chem|biolog/, '\u{1F52C}'],
        [/school|learn|educat|course|student/, '\u{1F393}'],
        [/car|vehicle|drive|auto|engine/, '\u{1F697}'],
        [/home|house|build|construct|roof/, '\u{1F3E0}'],
        [/climate|environment|carbon|green|weather/, '\u{1F30D}'],
        [/market|business|company|startup|sales/, '\u{1F4C8}'],
        [/sport|game|team|football|match/, '⚽'],
        [/music|song|audio|sound/, '\u{1F3B5}'],
    ];

    function notebookEmoji(c) {
        const hay = ((c.title || '') + ' '
            + (c.sources || []).map(s => s.title || '').join(' ')).toLowerCase();
        for (const [re, emoji] of TOPIC_EMOJI) if (re.test(hay)) return emoji;
        return '\u{1F4D3}';
    }

    function relativeTime(ts) {
        const secs = Math.round((Date.now() - ts) / 1000);
        if (secs < 60) return 'just now';
        const mins = Math.round(secs / 60);
        if (mins < 60) return mins + 'm ago';
        const hours = Math.round(mins / 60);
        if (hours < 24) return hours + 'h ago';
        const days = Math.round(hours / 24);
        if (days < 30) return days + 'd ago';
        return new Date(ts).toLocaleDateString(undefined,
            { month: 'short', day: 'numeric', year: 'numeric' });
    }

    const grid = document.getElementById('bookGrid');

    function render() {
        if (!convos.length) {
            grid.innerHTML = '<div class="library-empty">No books yet. '
                           + 'Create one to start collecting sources.</div>';
            return;
        }
        grid.innerHTML = convos.map(c => {
            const count = (c.sources || []).length;
            const meta = (count ? count + ' source' + (count === 1 ? '' : 's') + ' · ' : '')
                       + relativeTime(c.at || Date.now());
            return '<button type="button" class="book" data-id="' + c.id + '">'
                 + '<span class="book-del" data-del="' + c.id + '" role="button" '
                 + 'title="Delete book" aria-label="Delete book">'
                 + '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 '
                 + '10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 '
                 + '13.41 12z"/></svg></span>'
                 + '<span class="book-emoji">' + notebookEmoji(c) + '</span>'
                 + '<span class="book-title">' + escapeHtml(c.title || 'Untitled book') + '</span>'
                 + '<span class="book-meta">' + escapeHtml(meta) + '</span>'
                 + '</button>';
        }).join('');
    }

    // Hand the chosen book to index.html and go there. Relative, so this works
    // at the root and under a /studio prefix alike.
    function openBook(id) {
        writeJSON(ACTIVE, id);
        location.href = 'index.html';
    }

    grid.addEventListener('click', e => {
        const del = e.target.closest('[data-del]');
        if (del) {
            // Deleting is destructive, so confirm before dropping the book.
            const id = del.dataset.del;
            const book = convos.find(c => c.id === id);
            const label = book && book.title ? '"' + book.title + '"' : 'this book';
            if (!confirm('Delete ' + label + ' and everything in it?')) return;
            convos = convos.filter(c => c.id !== id);
            writeJSON(CONVOS, convos);
            render();
            return;
        }
        const card = e.target.closest('.book');
        if (card) openBook(card.dataset.id);
    });

    document.getElementById('btnNewBook').addEventListener('click', () => {
        const c = { id: uid(), title: 'Untitled book', messages: [], sources: [], at: Date.now() };
        convos.unshift(c);
        writeJSON(CONVOS, convos);
        openBook(c.id);
    });

    render();
})();
