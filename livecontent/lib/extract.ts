// Reading documents in the browser.
//
// Ported from the original Studio page: PDF and .docx are parsed here rather
// than uploaded, so file contents never leave the machine until the extracted
// text is saved as a source. No third-party parser is involved.

// Inflate a raw DEFLATE stream. .docx is a ZIP container and PDF text
// streams are usually FlateDecode, so both paths need this.
// Uses DecompressionStream where available, which is every current browser.
async function inflate(bytes: Uint8Array, format: 'deflate-raw' | 'deflate'): Promise<Uint8Array> {
    if (typeof DecompressionStream === 'undefined') {
        throw new Error('This browser cannot decompress the file. Try a recent Chrome, Edge, Firefox or Safari.');
    }
    const part = bytes.slice().buffer as ArrayBuffer;
    const stream = new Blob([part]).stream().pipeThrough(new DecompressionStream(format));
    return new Uint8Array(await new Response(stream).arrayBuffer());
}

// Read the entries of a ZIP archive (used for .docx).
type ZipEntry = { method: number; compressedSize: number; localOffset: number };
type Zip = { entries: Record<string, ZipEntry>; view: DataView; bytes: Uint8Array };

function readZipEntries(bytes: Uint8Array): Zip {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    // Locate the End Of Central Directory record, scanning back from the tail.
    let eocd = -1;
    for (let i = bytes.length - 22; i >= 0 && i >= bytes.length - 65557; i--) {
        if (view.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('Not a valid .docx file (no ZIP directory found).');

    const count = view.getUint16(eocd + 10, true);
    let offset = view.getUint32(eocd + 16, true);
    const entries: Record<string, ZipEntry> = {};

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

async function readZipFile(zip: Zip, name: string): Promise<Uint8Array | null> {
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
async function extractDocxText(arrayBuffer: ArrayBuffer): Promise<string> {
    const zip = readZipEntries(new Uint8Array(arrayBuffer));
    const documentXml = await readZipFile(zip, 'word/document.xml');
    if (!documentXml) throw new Error('No document body found. Old .doc files are not supported - save as .docx.');

    const xml = new TextDecoder('utf-8').decode(documentXml);
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    if (doc.querySelector('parsererror')) throw new Error('The .docx file appears to be corrupt.');

    const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
    const paragraphs: string[] = [];

    Array.from(doc.getElementsByTagNameNS(W, 'p')).forEach(p => {
        let line = '';
        // Walk the paragraph in document order so tabs and breaks land correctly.
        const walker = document.createTreeWalker(p, NodeFilter.SHOW_ELEMENT);
        let node: Node | null = walker.currentNode;
        while (node) {
            const elem = node as Element;
            if (elem.namespaceURI === W) {
                if (elem.localName === 't') line += elem.textContent;
                else if (elem.localName === 'tab') line += '\t';
                else if (elem.localName === 'br' || elem.localName === 'cr') line += '\n';
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
function decodePdfLiteral(raw: string): string {
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

function decodePdfHexString(hex: string): string {
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
function pdfContentToText(content: string): string {
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
async function extractPdfText(arrayBuffer: ArrayBuffer): Promise<string> {
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
        } catch {
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

/** Extract text from a file, choosing a parser by extension. */
export async function extractFileText(file: File): Promise<string> {
  const name = file.name.toLowerCase();
  let text = '';
  if (name.endsWith('.txt') || name.endsWith('.md')) {
    text = (await file.text()).trim();
  } else if (name.endsWith('.docx')) {
    text = await extractDocxText(await file.arrayBuffer());
  } else if (name.endsWith('.pdf')) {
    text = await extractPdfText(await file.arrayBuffer());
  } else if (name.endsWith('.doc')) {
    throw new Error('Legacy .doc is not supported. Save as .docx.');
  } else {
    throw new Error(`Unsupported file type: ${file.name}`);
  }
  if (!text) throw new Error(`No text could be read from ${file.name}.`);
  return text;
}
