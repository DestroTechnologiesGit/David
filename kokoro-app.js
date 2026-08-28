// UI Elements
const apiToken = document.getElementById('apiToken');
const languageSelect = document.getElementById('languageSelect');
const voiceSelect = document.getElementById('voiceSelect');
const textInput = document.getElementById('textInput');
const musicFile = document.getElementById('musicFile');
const formatSelect = document.getElementById('formatSelect');
const streamFormatSelect = document.getElementById('streamFormatSelect');
const documentFile = document.getElementById('documentFile');
const documentInfo = document.getElementById('documentInfo');
const charCount = document.getElementById('charCount');
const tabGenerate = document.getElementById('tabGenerate');
const tabStream = document.getElementById('tabStream');
const panelGenerate = document.getElementById('panelGenerate');
const panelStream = document.getElementById('panelStream');
const voiceVolume = document.getElementById('voiceVolume');
const musicVolume = document.getElementById('musicVolume');
const voiceVolumeValue = document.getElementById('voiceVolumeValue');
const musicVolumeValue = document.getElementById('musicVolumeValue');
const generateBtn = document.getElementById('generateBtn');
const modeNote = document.getElementById('modeNote');
const generateLabel = generateBtn.querySelector('.btn-label') || generateBtn;
const progressBar = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');
const status = document.getElementById('status');
const audioPreview = document.getElementById('audioPreview');
const audioPlayer = document.getElementById('audioPlayer');
const downloadBtn = document.getElementById('downloadBtn');

let finalAudioBlob = null;
let finalAudioExt = 'wav';

// Seconds of music fade-out at the end of the narration.
const MUSIC_FADE_OUT_SECONDS = 2;

// The server caps a single request; mirror both limits here for feedback.
const MAX_TEXT_LENGTH = 5000;          // Generate tab
const MAX_STREAM_TEXT_LENGTH = 10000;  // Stream tab

// The active tab decides which limit applies.
function currentMaxLength() {
    return activeMode === 'stream' ? MAX_STREAM_TEXT_LENGTH : MAX_TEXT_LENGTH;
}

// ---- Document import (PDF / Word .docx / .txt) ----------------------
// All parsing happens in the browser; no file is uploaded anywhere.

// Inflate a raw DEFLATE stream. .docx is a ZIP container and PDF text
// streams are usually FlateDecode, so both paths need this.
// Uses DecompressionStream where available, which is every current browser.
async function inflate(bytes, format) {
    if (typeof DecompressionStream === 'undefined') {
        throw new Error('This browser cannot decompress the file. Try a recent Chrome, Edge, Firefox or Safari.');
    }
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream(format));
    return new Uint8Array(await new Response(stream).arrayBuffer());
}

// Read the entries of a ZIP archive (used for .docx).
function readZipEntries(bytes) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    // Locate the End Of Central Directory record, scanning back from the tail.
    let eocd = -1;
    for (let i = bytes.length - 22; i >= 0 && i >= bytes.length - 65557; i--) {
        if (view.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('Not a valid .docx file (no ZIP directory found).');

    const count = view.getUint16(eocd + 10, true);
    let offset = view.getUint32(eocd + 16, true);
    const entries = {};

    for (let i = 0; i < count; i++) {
        if (view.getUint32(offset, true) !== 0x02014b50) break;
        const method = view.getUint16(offset + 10, true);
        const compressedSize = view.getUint32(offset + 20, true);
        const nameLength = view.getUint16(offset + 28, true);
        const extraLength = view.getUint16(offset + 30, true);
        const commentLength = view.getUint16(offset + 32, true);
        const localOffset = view.getUint32(offset + 42, true);
        const name = new TextDecoder().decode(bytes.subarray(offset + 46, offset + 46 + nameLength));

        entries[name] = { method, compressedSize, localOffset };
        offset += 46 + nameLength + extraLength + commentLength;
    }
    return { entries, view, bytes };
}

async function readZipFile(zip, name) {
    const entry = zip.entries[name];
    if (!entry) return null;
    // Skip the local file header to reach the data.
    const h = entry.localOffset;
    const nameLength = zip.view.getUint16(h + 26, true);
    const extraLength = zip.view.getUint16(h + 28, true);
    const start = h + 30 + nameLength + extraLength;
    const data = zip.bytes.subarray(start, start + entry.compressedSize);
    if (entry.method === 0) return data;            // stored
    if (entry.method === 8) return inflate(data, 'deflate-raw');
    throw new Error('Unsupported compression in .docx file.');
}

// Extract text from a Word .docx, preserving paragraph and line breaks.
async function extractDocxText(arrayBuffer) {
    const zip = readZipEntries(new Uint8Array(arrayBuffer));
    const documentXml = await readZipFile(zip, 'word/document.xml');
    if (!documentXml) throw new Error('No document body found. Old .doc files are not supported - save as .docx.');

    const xml = new TextDecoder('utf-8').decode(documentXml);
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    if (doc.querySelector('parsererror')) throw new Error('The .docx file appears to be corrupt.');

    const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
    const paragraphs = [];

    Array.from(doc.getElementsByTagNameNS(W, 'p')).forEach(p => {
        let line = '';
        // Walk the paragraph in document order so tabs and breaks land correctly.
        const walker = document.createTreeWalker(p, NodeFilter.SHOW_ELEMENT);
        let node = walker.currentNode;
        while (node) {
            if (node.namespaceURI === W) {
                if (node.localName === 't') line += node.textContent;
                else if (node.localName === 'tab') line += '\t';
                else if (node.localName === 'br' || node.localName === 'cr') line += '\n';
            }
            node = walker.nextNode();
        }
        paragraphs.push(line);
    });

    // Blank line between paragraphs preserves the document's visual spacing.
    return paragraphs.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

// ---- PDF ------------------------------------------------------------

// Decode a PDF literal string: (Hello \(world\)) with escapes.
function decodePdfLiteral(raw) {
    let out = '';
    for (let i = 0; i < raw.length; i++) {
        const c = raw[i];
        if (c !== '\\') { out += c; continue; }
        const next = raw[++i];
        if (next === undefined) break;
        if (next === 'n') out += '\n';
        else if (next === 'r') out += '\r';
        else if (next === 't') out += '\t';
        else if (next === 'b' || next === 'f') out += ' ';
        else if (next >= '0' && next <= '7') {
            let oct = next;
            while (oct.length < 3 && raw[i + 1] >= '0' && raw[i + 1] <= '7') oct += raw[++i];
            out += String.fromCharCode(parseInt(oct, 8));
        } else if (next === '\n') { /* line continuation */ }
        else out += next;
    }
    return out;
}

function decodePdfHexString(hex) {
    const clean = hex.replace(/[^0-9A-Fa-f]/g, '');
    let out = '';
    // Heuristic: 4-hex-digit groups are usually UTF-16BE text.
    const utf16 = clean.length >= 4 && clean.length % 4 === 0 && /^(00|d[89ab])/i.test(clean);
    const step = utf16 ? 4 : 2;
    for (let i = 0; i + step <= clean.length; i += step) {
        const code = parseInt(clean.substr(i, step), 16);
        if (code > 0) out += String.fromCharCode(code);
    }
    return out;
}

// Turn one content stream into text, using layout operators as break hints.
function pdfContentToText(content) {
    let text = '';
    // Match strings, kerning numbers inside TJ arrays, and layout operators.
    const token = /\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]*>|-?\d+(?:\.\d+)?|\bT[Jj]\b|\bT[dD]\b|\bT\*\b|\bET\b|\[|\]/g;
    let match;
    let pendingBreak = false;
    let inArray = false;

    const flushBreak = () => {
        if (pendingBreak) {
            if (text && !text.endsWith('\n')) text += '\n';
            pendingBreak = false;
        }
    };

    while ((match = token.exec(content)) !== null) {
        const t = match[0];
        if (t === '[') {
            inArray = true;
        } else if (t === ']') {
            inArray = false;
        } else if (t.startsWith('(')) {
            flushBreak();
            text += decodePdfLiteral(t.slice(1, -1));
        } else if (t.startsWith('<')) {
            flushBreak();
            text += decodePdfHexString(t.slice(1, -1));
        } else if (t === 'Td' || t === 'TD' || t === 'T*' || t === 'ET') {
            // A text-positioning operator starts a new visual line.
            pendingBreak = true;
        } else if (inArray) {
            // Inside a TJ array a large negative kern is inter-word space.
            const kern = parseFloat(t);
            if (kern <= -100 && text && !/\s$/.test(text)) text += ' ';
        }
    }
    return text;
}

// Extract text from a PDF by inflating its FlateDecode content streams.
async function extractPdfText(arrayBuffer) {
    const bytes = new Uint8Array(arrayBuffer);
    // latin1 keeps byte values intact while letting us regex the structure.
    const raw = new TextDecoder('latin1').decode(bytes);

    if (!raw.startsWith('%PDF')) throw new Error('Not a valid PDF file.');
    if (/\/Encrypt\b/.test(raw)) throw new Error('This PDF is password protected or encrypted.');

    const pieces = [];
    // Walk every stream object and inflate the ones that are Flate-compressed.
    // The lookbehind avoids matching the trailing "stream" of "endstream".
    const streamRe = /(?:^|[^d])stream\r?\n/g;
    let m;
    while ((m = streamRe.exec(raw)) !== null) {
        const start = m.index + m[0].length;
        const end = raw.indexOf('endstream', start);
        if (end < 0) continue;
        streamRe.lastIndex = end;

        // Inspect the dictionary just before this stream.
        const dict = raw.slice(Math.max(0, m.index - 800), m.index);
        if (!/\/FlateDecode/.test(dict)) continue;
        // Skip image and font payloads; we only want page content.
        if (/\/Subtype\s*\/Image|\/FontFile|\/XObject\s*\/Image/.test(dict)) continue;

        // Prefer the declared /Length; otherwise trim the EOL that pads
        // the gap before "endstream", which would otherwise be junk bytes.
        let stop = end;
        const lengthMatch = /\/Length\s+(\d+)/.exec(dict);
        if (lengthMatch) {
            const declared = start + parseInt(lengthMatch[1], 10);
            if (declared <= end) stop = declared;
        } else {
            while (stop > start && (raw.charCodeAt(stop - 1) === 10 || raw.charCodeAt(stop - 1) === 13)) stop--;
        }

        try {
            const slice = bytes.subarray(start, stop);
            const inflated = await inflate(slice, 'deflate');
            const content = new TextDecoder('latin1').decode(inflated);
            // Only content streams carry text-showing operators.
            if (/\bTJ\b|\bTj\b/.test(content)) pieces.push(pdfContentToText(content));
        } catch (e) {
            // A stream we cannot inflate is skipped rather than failing the import.
        }
    }

    if (!pieces.length) {
        throw new Error('No extractable text found. This PDF may be a scanned image, which needs OCR.');
    }

    return pieces.join('\n\n')
        .replace(/[ \t]+\n/g, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

// Show character count and warn when past the server limit.
function updateCharCount() {
    const value = textInput.value.trim();
    const length = value.length;
    const max = currentMaxLength();
    // Show the word count too: the limit is in characters, and people
    // routinely read "5,000" as words.
    const words = value ? value.split(/\s+/).length : 0;
    charCount.textContent =
        `${length.toLocaleString()} / ${max.toLocaleString()} characters`
        + ` (${words.toLocaleString()} ${words === 1 ? 'word' : 'words'})`;
    charCount.className = 'card-meta' + (length > max ? ' over-limit' : '');
}

// Handle a chosen document: extract its text into the textarea.
async function importDocument(file) {
    const name = file.name.toLowerCase();
    documentInfo.className = 'file-note';
    documentInfo.textContent = `Reading ${file.name}...`;

    try {
        let text;
        if (name.endsWith('.txt')) {
            text = (await file.text()).trim();
        } else if (name.endsWith('.docx')) {
            text = await extractDocxText(await file.arrayBuffer());
        } else if (name.endsWith('.pdf')) {
            text = await extractPdfText(await file.arrayBuffer());
        } else if (name.endsWith('.doc')) {
            throw new Error('Legacy .doc files are not supported. Open it in Word and save as .docx.');
        } else {
            throw new Error('Unsupported file type. Use PDF, .docx or .txt.');
        }

        if (!text) throw new Error('No text could be read from this file.');

        textInput.value = text;
        updateCharCount();

        const length = text.length;
        const max = currentMaxLength();
        if (length > max) {
            documentInfo.className = 'file-note over-limit';
            documentInfo.textContent =
                `Imported ${file.name} - ${length.toLocaleString()} characters, which is over the ` +
                `${max.toLocaleString()} character limit. Trim the text before generating.`;
        } else {
            documentInfo.textContent = `Imported ${file.name} - ${length.toLocaleString()} characters.`;
        }
    } catch (error) {
        documentInfo.className = 'file-note error';
        documentInfo.textContent = error.message;
    }
}

documentFile.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) importDocument(file);
});

// Keep every stated limit in step with the constants above.
document.querySelectorAll('.limit-generate').forEach(el => {
    el.textContent = MAX_TEXT_LENGTH.toLocaleString();
});
document.querySelectorAll('.limit-stream').forEach(el => {
    el.textContent = MAX_STREAM_TEXT_LENGTH.toLocaleString();
});

// Which tab is active decides how audio is produced.
let activeMode = 'generate';

// Built from the constants above so a changed limit shows everywhere, and
// re-read on each switch rather than baked into the markup.
function modeNoteHtml(streaming) {
    const gen = MAX_TEXT_LENGTH.toLocaleString();
    const str = MAX_STREAM_TEXT_LENGTH.toLocaleString();
    if (streaming) {
        return '<strong>Stream</strong> starts playing as soon as the first few words '
            + 'are ready, instead of waiting for the whole narration. Best for long '
            + 'text and quick previews. Up to <strong>' + str + ' characters</strong> '
            + '&mdash; about <strong>13 minutes</strong> of speech. Playback is live, '
            + 'so leaving the page stops it; the finished audio still appears below.';
    }
    return '<strong>Generate</strong> waits for the whole narration, then gives you a '
        + 'finished file. Slower to start, but you can mix in background music and '
        + 'download the result. Up to <strong>' + gen + ' characters</strong> &mdash; '
        + 'about <strong>6 to 7 minutes</strong> of speech. The Stream tab allows '
        + '<strong>' + str + '</strong>.';
}

function selectMode(mode) {
    activeMode = mode;
    const streaming = mode === 'stream';

    tabGenerate.classList.toggle('active', !streaming);
    tabStream.classList.toggle('active', streaming);
    tabGenerate.setAttribute('aria-selected', String(!streaming));
    tabStream.setAttribute('aria-selected', String(streaming));

    panelGenerate.hidden = streaming;
    panelStream.hidden = !streaming;
    panelGenerate.classList.toggle('active', !streaming);
    panelStream.classList.toggle('active', streaming);

    // The button holds an icon beside its label, so only the label is
    // rewritten here.
    generateLabel.textContent = streaming ? 'Start Streaming' : 'Generate Speech';

    // One note describes the active mode, so it has to follow the tabs.
    if (modeNote) modeNote.innerHTML = modeNoteHtml(streaming);

    // The limit differs per tab, so the counter has to be re-evaluated.
    updateCharCount();
}

tabGenerate.addEventListener('click', () => selectMode('generate'));
tabStream.addEventListener('click', () => selectMode('stream'));

// Left/right arrows move between tabs, as expected for a tablist.
[tabGenerate, tabStream].forEach(tab => {
    tab.addEventListener('keydown', (e) => {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        e.preventDefault();
        const next = activeMode === 'generate' ? 'stream' : 'generate';
        selectMode(next);
        (next === 'stream' ? tabStream : tabGenerate).focus();
    });
});

selectMode('generate');

textInput.addEventListener('input', updateCharCount);
updateCharCount();

// Filter voices based on selected language
function filterVoicesByLanguage(selectedLang) {
    let firstVisibleOption = null;

    // Hide whole groups too, so empty group labels don't linger.
    voiceSelect.querySelectorAll('optgroup').forEach(group => {
        const matches = group.getAttribute('data-lang') === selectedLang;
        group.hidden = !matches;
        group.disabled = !matches;
    });

    voiceSelect.querySelectorAll('option').forEach(option => {
        const matches = option.getAttribute('data-lang') === selectedLang;
        option.hidden = !matches;
        option.disabled = !matches;
        if (matches && !firstVisibleOption) {
            firstVisibleOption = option;
        }
    });

    // Select the first visible voice
    if (firstVisibleOption) {
        voiceSelect.value = firstVisibleOption.value;
    }
}

// Initialize with default language
filterVoicesByLanguage('en-us');

// Language change handler
languageSelect.addEventListener('change', (e) => {
    filterVoicesByLanguage(e.target.value);
});

// Update volume display
voiceVolume.addEventListener('input', (e) => {
    voiceVolumeValue.textContent = e.target.value + '%';
});

musicVolume.addEventListener('input', (e) => {
    musicVolumeValue.textContent = e.target.value + '%';
});

// Show status message
function showStatus(message, type = 'info') {
    status.textContent = message;
    status.className = 'status ' + type;
    status.style.display = 'block';
}

// Update progress
function updateProgress(percent) {
    progressBar.style.display = 'block';
    progressFill.style.width = percent + '%';
}

// Where the speech API lives. Served from the API host, this stays relative
// and "just works". Set a full origin (via the field in the dialog) to point
// the page at an API on another host, or to run it from a file:// path.
function apiBase() {
    try {
        const saved = (localStorage.getItem(BASE_KEY) || '').trim();
        if (saved) return saved.replace(/\/+$/, '');
    } catch (e) {
        /* Storage unavailable; fall through to the default. */
    }
    // file:// has no server to be relative to, so a base must be set.
    if (location.protocol === 'file:') return '';
    // Served under /kokoro by the reverse proxy, or at the root standalone.
    return location.pathname.startsWith('/kokoro') ? '/kokoro' : '';
}

function apiUrl(path) {
    const base = apiBase();
    if (!base && location.protocol === 'file:') {
        throw new Error(
            'No API address set. Open the token dialog and enter the address '
            + 'of your speech server, for example http://localhost:8890');
    }
    return base + path;
}

// Generate TTS audio from the speech API
async function generateTTS(text, voice, language, token, format) {
    const response = await fetch(apiUrl('/api/tts'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Kokoro-Key': token,
        },
        body: JSON.stringify({
            text: text,
            voice: voice,
            language: language,
            speed: 1.0,
            format: format || 'wav'
        })
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`TTS API request failed: ${response.status} - ${errorText}`);
    }

    return await response.blob();
}

// Read a WAV header by walking its RIFF chunks. Returns null when more
// bytes are needed. `dataStart` is the offset of the audio itself.
function parseWavHeader(bytes) {
    if (bytes.length < 12) return null;
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const tag = (off) => String.fromCharCode(
        dv.getUint8(off), dv.getUint8(off + 1), dv.getUint8(off + 2), dv.getUint8(off + 3));

    if (tag(0) !== 'RIFF' || tag(8) !== 'WAVE') {
        throw new Error('The server did not return a WAV stream.');
    }

    let fmt = null;
    let offset = 12;
    while (offset + 8 <= bytes.length) {
        const id = tag(offset);
        const size = dv.getUint32(offset + 4, true);
        const body = offset + 8;

        if (id === 'fmt ') {
            if (body + 16 > bytes.length) return null;
            const formatTag = dv.getUint16(body, true);
            fmt = {
                channels: dv.getUint16(body + 2, true),
                sampleRate: dv.getUint32(body + 4, true),
                bits: dv.getUint16(body + 14, true),
                // 1 = PCM, 3 = IEEE float, 0xFFFE = extensible (subformat
                // in the extension block decides which).
                float: formatTag === 3,
            };
            if (formatTag === 0xFFFE && body + 26 <= bytes.length) {
                fmt.float = dv.getUint16(body + 24, true) === 3;
            }
        } else if (id === 'data') {
            if (!fmt) throw new Error('The WAV stream has no format header.');
            if (!fmt.channels || !fmt.sampleRate || !fmt.bits) {
                throw new Error('The WAV stream has an invalid format header.');
            }
            if (![8, 16, 24, 32, 64].includes(fmt.bits)) {
                throw new Error(`Unsupported audio format from server (${fmt.bits}-bit).`);
            }
            return { header: fmt, dataStart: body };
        }

        // Chunks are word-aligned, so an odd size carries a pad byte.
        offset = body + size + (size & 1);
        // A streaming `data` size can be a placeholder; guard the walk.
        if (size < 0 || offset < body) throw new Error('Malformed WAV stream.');
    }
    return null;   // header not complete yet
}

// Play a compressed stream (MP3) while it downloads, using MediaSource.
// Falls back to buffering the whole response if MSE is unavailable.
async function streamCompressed(response, onProgress) {
    const chunks = [];
    const collect = async () => {
        const reader = response.body.getReader();
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            chunks.push(value);
        }
    };

    const supported = typeof MediaSource !== 'undefined' &&
        MediaSource.isTypeSupported('audio/mpeg');

    if (!supported) {
        // No live playback, but the audio still arrives and plays after.
        await collect();
        const blob = new Blob(chunks, { type: 'audio/mpeg' });
        onProgress && onProgress('complete');
        return { blob, duration: 0, stop: () => {} };
    }

    const media = new MediaSource();
    const audio = new Audio();
    audio.src = URL.createObjectURL(media);

    await new Promise(resolve => media.addEventListener('sourceopen', resolve, { once: true }));
    const buffer = media.addSourceBuffer('audio/mpeg');

    const queue = [];
    let ended = false;
    const pump = () => {
        if (buffer.updating || !queue.length) return;
        buffer.appendBuffer(queue.shift());
    };
    buffer.addEventListener('updateend', () => {
        pump();
        if (ended && !buffer.updating && !queue.length && media.readyState === 'open') {
            media.endOfStream();
        }
    });

    let started = false;
    const reader = response.body.getReader();
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        chunks.push(value);
        queue.push(value);
        pump();
        if (!started) {
            started = true;
            // Autoplay can be blocked; the preview player below still works.
            audio.play().catch(() => {});
            onProgress && onProgress('playing');
        }
    }

    ended = true;
    pump();
    if (!buffer.updating && !queue.length && media.readyState === 'open') {
        try { media.endOfStream(); } catch (e) { /* already ended */ }
    }
    onProgress && onProgress('complete');

    const blob = new Blob(chunks, { type: 'audio/mpeg' });
    return {
        blob,
        duration: isFinite(audio.duration) ? audio.duration : 0,
        stop: () => { try { audio.pause(); } catch (e) {} },
    };
}

// Stream speech and play it while the server is still generating.
// The response is one long WAV whose header declares a placeholder
// length, so MediaSource is fed the bytes as they arrive.
async function streamTTS(text, voice, language, token, onProgress, format) {
    const wanted = format || 'wav';
    const response = await fetch(apiUrl('/api/tts/stream'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Kokoro-Key': token,
        },
        body: JSON.stringify({ text, voice, language, speed: 1.0, format: wanted })
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`TTS API request failed: ${response.status} - ${errorText}`);
    }
    if (!response.body) throw new Error('This browser cannot read streaming responses.');

    // MP3 arrives as self-describing frames: hand them to MediaSource
    // and let the browser decode, rather than parsing PCM by hand.
    const contentType = (response.headers.get('Content-Type') || '').toLowerCase();
    if (contentType.includes('mpeg') || contentType.includes('mp3')) {
        return streamCompressed(response, onProgress);
    }

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const reader = response.body.getReader();

    let header = null;          // parsed from the RIFF chunks up front
    let leftover = new Uint8Array(0);
    let playHead = audioContext.currentTime;
    let started = false;
    let totalSamples = 0;
    const sources = [];

    const concat = (a, b) => {
        const out = new Uint8Array(a.length + b.length);
        out.set(a, 0); out.set(b, a.length);
        return out;
    };

    // Queue one block of PCM for playback directly after whatever is queued.
    const schedule = (pcm) => {
        const bytesPerSample = header.bits / 8;
        const samples = pcm.length / bytesPerSample / header.channels;
        if (samples < 1) return;
        const buffer = audioContext.createBuffer(header.channels, samples, header.sampleRate);
        const view = new DataView(pcm.buffer, pcm.byteOffset, pcm.byteLength);
        const stride = header.channels * bytesPerSample;
        for (let ch = 0; ch < header.channels; ch++) {
            const target = buffer.getChannelData(ch);
            const chOffset = ch * bytesPerSample;
            for (let i = 0; i < samples; i++) {
                const at = i * stride + chOffset;
                // The engine writes 32-bit float; other tools write 16-bit PCM.
                if (header.float) {
                    target[i] = header.bits === 64
                        ? view.getFloat64(at, true)
                        : view.getFloat32(at, true);
                } else if (header.bits === 16) {
                    target[i] = view.getInt16(at, true) / 32768;
                } else if (header.bits === 32) {
                    target[i] = view.getInt32(at, true) / 2147483648;
                } else if (header.bits === 24) {
                    const b0 = view.getUint8(at), b1 = view.getUint8(at + 1);
                    const b2 = view.getInt8(at + 2);
                    target[i] = ((b2 << 16) | (b1 << 8) | b0) / 8388608;
                } else if (header.bits === 8) {
                    // 8-bit WAV is unsigned, centred on 128.
                    target[i] = (view.getUint8(at) - 128) / 128;
                }
            }
        }
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        // Never schedule in the past, or chunks overlap after a stall.
        playHead = Math.max(playHead, audioContext.currentTime);
        source.start(playHead);
        playHead += buffer.duration;
        totalSamples += samples;
        sources.push(source);
        if (!started) { started = true; onProgress && onProgress('playing'); }
    };

    const chunks = [];
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        chunks.push(value);
        leftover = concat(leftover, value);

        if (!header) {
            // Walk the RIFF chunks rather than assuming a 44-byte header:
            // float WAVs carry a `fact` chunk, and encoders may add
            // `LIST`, so `data` is not always at a fixed offset.
            const parsed = parseWavHeader(leftover);
            if (!parsed) continue;      // need more bytes
            header = parsed.header;
            leftover = leftover.subarray(parsed.dataStart);
        }

        // Only whole frames can be turned into samples.
        const frameBytes = (header.bits / 8) * header.channels;
        const usable = leftover.length - (leftover.length % frameBytes);
        if (usable > 0) {
            schedule(leftover.slice(0, usable));
            leftover = leftover.subarray(usable);
        }
    }

    if (!header) throw new Error('The server returned no audio.');
    onProgress && onProgress('complete');

    // Hand back the full audio too, so preview and download still work.
    let total = 0;
    chunks.forEach(c => total += c.length);
    const full = new Uint8Array(total);
    let at = 0;
    chunks.forEach(c => { full.set(c, at); at += c.length; });
    // Rewrite the placeholder sizes with the real byte counts. The data
    // chunk is not always at offset 36, so use the parsed position.
    const parsed = parseWavHeader(full);
    if (parsed) {
        const dataStart = parsed.dataStart;
        const dataBytes = full.length - dataStart;
        const view = new DataView(full.buffer, full.byteOffset, full.byteLength);
        view.setUint32(4, full.length - 8, true);
        view.setUint32(dataStart - 4, dataBytes, true);
    }

    return {
        blob: new Blob([full], { type: 'audio/wav' }),
        duration: totalSamples / header.sampleRate,
        stop: () => sources.forEach(s => { try { s.stop(); } catch (e) {} }),
    };
}

// Mix audio files using Web Audio API
async function mixAudio(voiceBlob, musicBlob, voiceVol, musicVol) {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();

    // Load voice audio
    const voiceArrayBuffer = await voiceBlob.arrayBuffer();
    const voiceAudioBuffer = await audioContext.decodeAudioData(voiceArrayBuffer);

    // Load music audio
    const musicArrayBuffer = await musicBlob.arrayBuffer();
    const musicAudioBuffer = await audioContext.decodeAudioData(musicArrayBuffer);

    // Output runs exactly as long as the narration: background music is
    // trimmed to the voice and stops when the voice stops.
    const outputLength = voiceAudioBuffer.length;
    const outputBuffer = audioContext.createBuffer(
        2, // stereo
        outputLength,
        audioContext.sampleRate
    );

    // Fade the music out over the final moments so the trim isn't an abrupt cut.
    const fadeSamples = Math.min(
        Math.floor(MUSIC_FADE_OUT_SECONDS * voiceAudioBuffer.sampleRate),
        outputLength
    );
    const fadeStart = outputLength - fadeSamples;

    // Mix the audio
    for (let channel = 0; channel < 2; channel++) {
        const outputData = outputBuffer.getChannelData(channel);
        const voiceData = voiceAudioBuffer.getChannelData(Math.min(channel, voiceAudioBuffer.numberOfChannels - 1));
        const musicData = musicAudioBuffer.getChannelData(Math.min(channel, musicAudioBuffer.numberOfChannels - 1));

        for (let i = 0; i < outputLength; i++) {
            const voiceSample = voiceData[i] * voiceVol;
            let musicSample = i < musicData.length ? musicData[i] * musicVol : 0;
            if (fadeSamples > 0 && i >= fadeStart) {
                musicSample *= (outputLength - i) / fadeSamples;
            }
            outputData[i] = voiceSample + musicSample;
        }
    }

    return outputBuffer;
}

// Convert AudioBuffer to WAV Blob
function audioBufferToWav(buffer) {
    const length = buffer.length * buffer.numberOfChannels * 2;
    const arrayBuffer = new ArrayBuffer(44 + length);
    const view = new DataView(arrayBuffer);
    const channels = buffer.numberOfChannels;
    const sampleRate = buffer.sampleRate;

    // Write WAV header
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + length, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, channels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * channels * 2, true);
    view.setUint16(32, channels * 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, length, true);

    // Write audio data
    const offset = 44;
    const channelData = [];
    for (let i = 0; i < channels; i++) {
        channelData.push(buffer.getChannelData(i));
    }

    let index = 0;
    for (let i = 0; i < buffer.length; i++) {
        for (let channel = 0; channel < channels; channel++) {
            const sample = Math.max(-1, Math.min(1, channelData[channel][i]));
            view.setInt16(offset + index, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
            index += 2;
        }
    }

    return new Blob([arrayBuffer], { type: 'audio/wav' });
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}

// Main generation function
generateBtn.addEventListener('click', async () => {
    const text = textInput.value.trim();
    const token = apiToken.value.trim();
    const voice = voiceSelect.value;
    const language = languageSelect.value;
    // Music only applies to the Generate tab; streaming has no mixing step.
    const music = activeMode === 'stream' ? null : musicFile.files[0];
    const outputFormat = formatSelect.value;

    // Validation
    if (!text) {
        showStatus('Please enter text to narrate', 'error');
        return;
    }

    if (!token) {
        showStatus('Please enter the API access token', 'error');
        return;
    }

    try {
        generateBtn.disabled = true;
        audioPreview.style.display = 'none';
        updateProgress(0);

        // Streaming path: playback begins before generation finishes,
        // so there is no mixing step and no intermediate blob to wait for.
        if (activeMode === 'stream') {
            showStatus('Connecting...', 'info');
            updateProgress(20);

            const streamFormat = streamFormatSelect.value;
            const result = await streamTTS(text, voice, language, token, (phase) => {
                if (phase === 'playing') {
                    showStatus('Playing while the rest is generated...', 'info');
                    updateProgress(60);
                }
            }, streamFormat);

            finalAudioBlob = result.blob;
            finalAudioExt = streamFormat;
            updateProgress(100);
            showStatus(result.duration
                ? `Finished streaming ${result.duration.toFixed(1)} seconds of audio.`
                : 'Finished streaming.', 'success');

            // Offer the finished audio for replay and download.
            audioPlayer.src = URL.createObjectURL(finalAudioBlob);
            audioPreview.style.display = 'block';
            return;
        }

        // Step 1: Generate TTS
        showStatus('Generating speech...', 'info');
        updateProgress(25);
        const voiceBlob = await generateTTS(text, voice, language, token, outputFormat);

        // Step 2: Load music
        showStatus('Loading background music...', 'info');
        updateProgress(50);

        // Step 3: Mix audio
        showStatus('Mixing voice and music...', 'info');
        updateProgress(75);

        const voiceVol = voiceVolume.value / 100;
        const musicVol = musicVolume.value / 100;

        if (music) {
            // Mixing decodes both inputs and re-encodes as WAV, so the
            // result is WAV even when MP3 was requested.
            const mixedBuffer = await mixAudio(voiceBlob, music, voiceVol, musicVol);
            finalAudioBlob = audioBufferToWav(mixedBuffer);
            finalAudioExt = 'wav';
        } else {
            finalAudioBlob = voiceBlob;
            finalAudioExt = outputFormat;
        }

        // Step 4: Convert to WAV
        showStatus('Creating final audio file...', 'info');
        updateProgress(90);

        // Step 5: Display result
        updateProgress(100);
        showStatus(music && outputFormat === 'mp3'
            ? 'Audio generated. Mixed with music, so it is saved as WAV.'
            : `Audio generated successfully (${finalAudioExt.toUpperCase()}).`, 'success');

        const audioUrl = URL.createObjectURL(finalAudioBlob);
        audioPlayer.src = audioUrl;
        audioPreview.style.display = 'block';

    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
        console.error(error);
    } finally {
        generateBtn.disabled = false;
    }
});

// Download function
downloadBtn.addEventListener('click', () => {
    if (finalAudioBlob) {
        const url = URL.createObjectURL(finalAudioBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'narration.' + finalAudioExt;
        a.click();
        URL.revokeObjectURL(url);
    }
});

// ---------- Access token dialog ----------
// The token is asked for on open rather than left as an empty field the user
// has to notice. It is stored only if they opt in, and the sidebar input stays
// the single source of truth that generation reads from.
const TOKEN_KEY = 'kokoro.token.v1';
const BASE_KEY = 'kokoro.apibase.v1';
const tokenDialog = document.getElementById('tokenDialog');
const tokenForm = document.getElementById('tokenForm');
const tokenInput = document.getElementById('tokenInput');
const tokenRemember = document.getElementById('tokenRemember');
const tokenError = document.getElementById('tokenError');
const tokenCancel = document.getElementById('tokenCancel');
const baseInput = document.getElementById('baseInput');

function readStoredToken() {
    // Storage can throw in private modes, so a failure just means "no token".
    try {
        return localStorage.getItem(TOKEN_KEY) || '';
    } catch (e) {
        return '';
    }
}

function writeStoredToken(value) {
    try {
        if (value) localStorage.setItem(TOKEN_KEY, value);
        else localStorage.removeItem(TOKEN_KEY);
    } catch (e) {
        /* Not fatal: the token still works for this session. */
    }
}

function openTokenDialog() {
    if (!tokenDialog || typeof tokenDialog.showModal !== 'function') return;
    if (tokenDialog.open) return;
    tokenError.hidden = true;
    tokenInput.value = apiToken.value.trim();
    if (baseInput) baseInput.value = apiBase();
    tokenDialog.showModal();
    // From a file:// page the address matters most, so start there.
    if (baseInput && location.protocol === 'file:' && !baseInput.value) {
        baseInput.focus();
    } else {
        tokenInput.focus();
    }
}

if (tokenDialog && tokenForm) {
    tokenForm.addEventListener('submit', (e) => {
        // Keep the dialog open when the field is empty instead of saving nothing.
        const value = tokenInput.value.trim();
        if (!value) {
            e.preventDefault();
            tokenError.textContent = 'Enter a token, or cancel to add it later.';
            tokenError.hidden = false;
            tokenInput.focus();
            return;
        }
        apiToken.value = value;
        writeStoredToken(tokenRemember.checked ? value : '');
        if (baseInput) {
            const base = baseInput.value.trim().replace(/\/+$/, '');
            try {
                if (base) localStorage.setItem(BASE_KEY, base);
                else localStorage.removeItem(BASE_KEY);
            } catch (e) {
                /* Not fatal; the address just will not persist. */
            }
        }
        tokenDialog.close();
    });

    tokenCancel.addEventListener('click', () => tokenDialog.close());

    // Re-open from the sidebar field so the token can be changed later.
    apiToken.addEventListener('focus', () => {
        if (!apiToken.value.trim()) openTokenDialog();
    });

    // Editing the sidebar field directly must not leave a stale stored token.
    apiToken.addEventListener('change', () => {
        if (readStoredToken()) writeStoredToken(apiToken.value.trim());
    });

    // A stored token fills the field silently; otherwise ask for one.
    const saved = readStoredToken();
    if (saved) {
        apiToken.value = saved;
    } else {
        openTokenDialog();
    }
}
