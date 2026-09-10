/* LiveContent™ library — the book picker.
 *
 * A standalone page: opening a book navigates to its conversation URL rather
 * than revealing a hidden panel. The two pages share state only through
 * localStorage, so the small helpers below are duplicated from app.js by
 * design rather than imported.
 */
(async () => {
    "use strict";

    const CURRENT_USER_KEY = 'openclaw.studio.currentUser.v1';
    const USERS = Object.freeze({ david: 'David', shayan: 'Shayan' });
    const savedUser = String(localStorage.getItem(CURRENT_USER_KEY) || '').toLowerCase();
    const currentUser = USERS[savedUser] ? savedUser : '';
    const userStorageKey = key => key + '.user.' + (currentUser || 'signed-out');
    const PROFILE_DATA_KEYS = [
        'openclaw.studio.v1',
        'openclaw.studio.convos.v1',
        'openclaw.studio.notes.v1',
        'openclaw.studio.active.v1',
        'openclaw.studio.audio.v1',
        'openclaw.studio.translation.v1',
        'openclaw.studio.sourceScope.v1',
        'openclaw.studio.healthAdvancedEnabled.v1',
        'openclaw.studio.panels.v1',
    ];

    async function hydrateUserProfile() {
        if (!currentUser) return;
        try {
            const response = await fetch('/studio-api/user-data', {
                headers: { 'X-LiveContent-User': currentUser },
            });
            const payload = await response.json();
            if (!response.ok || !payload || !payload.data) return;
            PROFILE_DATA_KEYS.forEach(key => {
                if (Object.prototype.hasOwnProperty.call(payload.data, key)) {
                    localStorage.setItem(userStorageKey(key), JSON.stringify(payload.data[key]));
                }
            });
        } catch (_) { /* Keep using the local cache while the server is unavailable. */ }
    }

    await hydrateUserProfile();
    const CONVOS = userStorageKey('openclaw.studio.convos.v1');
    // Which book index.html should open. Set here, read there.
    const ACTIVE = userStorageKey('openclaw.studio.active.v1');
    const BASE = '/livecontent';

    // This page does not consume URL parameters or fragments. Remove them and
    // refuse to derive navigation destinations from address-bar input.
    const LIBRARY_PATH = BASE + '/library.html';
    if (location.pathname !== LIBRARY_PATH || location.search || location.hash) {
        history.replaceState(null, '', LIBRARY_PATH);
    }

    function readJSON(key, fallback) {
        try {
            const raw = localStorage.getItem(key);
            return raw ? JSON.parse(raw) : fallback;
        } catch (e) { return fallback; }
    }

    const databaseWrites = new Map();
    function persistUserData(key, value) {
        if (!currentUser) return;
        const suffix = '.user.' + currentUser;
        if (!key.endsWith(suffix)) return;
        const dataKey = key.slice(0, -suffix.length);
        if (!PROFILE_DATA_KEYS.includes(dataKey)) return;
        const previous = databaseWrites.get(dataKey) || Promise.resolve();
        const next = previous.catch(() => {}).then(() => fetch('/studio-api/user-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-LiveContent-User': currentUser,
            },
            body: JSON.stringify({ key: dataKey, value }),
        })).then(response => {
            if (!response.ok) throw new Error('User data could not be saved.');
        }).catch(() => { /* Keep the local copy when the database is unavailable. */ });
        databaseWrites.set(dataKey, next);
    }

    function writeJSON(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            persistUserData(key, value);
        } catch (e) {}
    }

    function migrateLegacyProfile(userId) {
        if (userId !== 'david') return;
        const marker = 'openclaw.studio.userMigration.david.v1';
        if (localStorage.getItem(marker)) return;
        PROFILE_DATA_KEYS.forEach(key => {
            const value = localStorage.getItem(key);
            const target = key + '.user.david';
            if (value !== null && localStorage.getItem(target) === null) {
                localStorage.setItem(target, value);
            }
        });
        localStorage.setItem(marker, '1');
    }

    function selectUser(userId) {
        if (!USERS[userId]) return;
        migrateLegacyProfile(userId);
        localStorage.setItem(CURRENT_USER_KEY, userId);
        location.reload();
    }

    function showLoginGate(allowCancel) {
        const gate = document.getElementById('loginGate');
        gate.hidden = false;
        document.body.classList.add('user-login-open');
        document.getElementById('btnLoginCancel').hidden = !allowCancel;
        const selected = gate.querySelector('[data-login-user="' + currentUser + '"]')
            || gate.querySelector('[data-login-user]');
        if (selected) selected.focus();
    }

    function hideLoginGate() {
        if (!currentUser) return;
        document.getElementById('loginGate').hidden = true;
        document.body.classList.remove('user-login-open');
    }

    function initializeUserLogin() {
        const name = USERS[currentUser] || 'Choose user';
        document.getElementById('currentUserName').textContent = name;
        document.getElementById('currentUserAvatar').textContent = currentUser
            ? name.charAt(0) : '?';
        document.getElementById('btnCurrentUser').addEventListener(
            'click', () => showLoginGate(true)
        );
        document.querySelectorAll('[data-login-user]').forEach(button => {
            button.addEventListener('click', () => selectUser(button.dataset.loginUser));
        });
        document.getElementById('btnLoginCancel').addEventListener('click', hideLoginGate);
        if (!currentUser) showLoginGate(false);
    }

    const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

    function slugPart(value) {
        return String(value || '')
            .normalize('NFKD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, 48) || 'note';
    }

    function migrateConvos(items) {
        const used = new Set();
        let changed = false;
        const migrated = (Array.isArray(items) ? items : []).map(raw => {
            const convo = raw && typeof raw === 'object' ? raw : {};
            if (!convo.id) { convo.id = uid(); changed = true; }
            if (!convo.title) { convo.title = 'Untitled book'; changed = true; }
            let slug = convo.slug ? slugPart(convo.slug) : '';
            if (!slug || used.has(slug)) {
                const base = slugPart(convo.title || 'conversation');
                const suffix = String(convo.id).slice(-6).toLowerCase();
                slug = base + '-' + suffix;
                let n = 2;
                while (used.has(slug)) slug = base + '-' + suffix + '-' + n++;
                changed = true;
            }
            convo.slug = slug;
            used.add(slug);
            if (!Array.isArray(convo.messages)) { convo.messages = []; changed = true; }
            if (!Array.isArray(convo.sources)) { convo.sources = []; changed = true; }
            if (!convo.at) { convo.at = Date.now(); changed = true; }
            return convo;
        });
        return { convos: migrated, changed };
    }

    const migration = migrateConvos(readJSON(CONVOS, []));
    let convos = migration.convos;
    if (migration.changed) writeJSON(CONVOS, convos);
    if (currentUser) {
        PROFILE_DATA_KEYS.forEach(key => {
            const scopedKey = userStorageKey(key);
            const raw = localStorage.getItem(scopedKey);
            if (raw === null) return;
            try { persistUserData(scopedKey, JSON.parse(raw)); } catch (_) {}
        });
    }

    function makeConvo(title) {
        const id = uid();
        const name = title || 'Untitled book';
        const base = slugPart(name);
        const suffix = id.slice(-6).toLowerCase();
        let slug = base + '-' + suffix;
        let n = 2;
        while (convos.some(convo => convo.slug === slug)) slug = base + '-' + suffix + '-' + n++;
        return { id, slug, title: name, messages: [], sources: [], at: Date.now() };
    }

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
            const meta = '/' + c.slug + ' · '
                       + (count ? count + ' source' + (count === 1 ? '' : 's') + ' · ' : '')
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

    // Store the choice and use the notebook's canonical, shareable URL.
    function openBook(id) {
        const book = convos.find(c => c.id === id || c.slug === id);
        if (!book) return;
        writeJSON(ACTIVE, book.id);
        location.href = BASE + '/conversations/' + encodeURIComponent(book.slug);
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
        const c = makeConvo('Untitled book');
        convos.unshift(c);
        writeJSON(CONVOS, convos);
        openBook(c.id);
    });

    initializeUserLogin();
    render();
})();
