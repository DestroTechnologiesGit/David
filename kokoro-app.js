// UI Elements
const apiToken = document.getElementById('apiToken');
const languageSelect = document.getElementById('languageSelect');
const voiceSelect = document.getElementById('voiceSelect');
const textInput = document.getElementById('textInput');
const musicFile = document.getElementById('musicFile');
const formatSelect = document.getElementById('formatSelect');
const streamFormatSelect = document.getElementById('streamFormatSelect');
const speedSelect = document.getElementById('speedSelect');
const speedValue = document.getElementById('speedValue');
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

function updateSpeedValue() {
    const speed = parseFloat(speedSelect.value) || 1;
    speedValue.textContent = speed.toFixed(2) + '\u00d7';
}

speedSelect.addEventListener('input', updateSpeedValue);
updateSpeedValue();

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
async function generateTTS(text, voice, language, token, format, speed) {
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
            speed: speed,
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
async function streamTTS(text, voice, language, token, onProgress, format, speed) {
    const wanted = format || 'wav';
    const response = await fetch(apiUrl('/api/tts/stream'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Kokoro-Key': token,
        },
        body: JSON.stringify({ text, voice, language, speed, format: wanted })
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
    // The <select> yields a string; the API expects a number.
    const speed = parseFloat(speedSelect.value) || 1.0;

    // Validation
    if (!text) {
        showStatus('Please enter text to narrate', 'error');
        return;
    }

    if (!token) {
        showStatus('Please enter the API access token', 'error');
        openTokenDialog();
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
            }, streamFormat, speed);

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
        const voiceBlob = await generateTTS(text, voice, language, token, outputFormat, speed);

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
        if (/\b401\b|invalid api access token/i.test(error.message)) {
            apiToken.value = '';
            writeStoredToken('');
            openTokenDialog();
        }
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
// The token is a one-time setup value, kept out of the everyday form. The
// hidden input remains the single source of truth that generation reads from.
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

    // A stored token fills the field silently; otherwise ask for one.
    const saved = readStoredToken();
    if (saved) {
        apiToken.value = saved;
    } else {
        openTokenDialog();
    }
}
