// Minimal, safe markdown: escape first, then apply a small set of patterns.
// Ported from the original page. Because escaping happens before any pattern
// runs, model output can never inject markup.

function escapeHtml(s: string) {
  return s.replace(
    /[&<>"']/g,
    (ch) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch] as string,
  );
}

// Placeholder for extracted code blocks. Uses characters that cannot appear
// in escaped output, so it can never collide with real content.
const MARK_OPEN = 'CODE';
const MARK_CLOSE = '';

export function renderMarkdown(text: string): string {
  let html = escapeHtml(text);

  // Fenced code is pulled out first so its contents are not reformatted.
  const blocks: string[] = [];
  html = html.replace(/```([\s\S]*?)```/g, (_m, code: string) => {
    blocks.push(`<pre><code>${code.replace(/^\n/, '')}</code></pre>`);
    return `${MARK_OPEN}${blocks.length - 1}${MARK_CLOSE}`;
  });

  html = html
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^\s{0,3}###\s+(.*)$/gm, '<h3>$1</h3>')
    .replace(/^\s{0,3}##\s+(.*)$/gm, '<h2>$1</h2>')
    .replace(/^\s{0,3}#\s+(.*)$/gm, '<h1>$1</h1>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, '<ul>$1</ul>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>');

  html = `<p>${html}</p>`
    .replace(/<p>\s*<\/p>/g, '')
    .replace(/<p>(<(?:h[1-3]|ul|pre))/g, '$1')
    .replace(/(<\/(?:h[1-3]|ul|pre)>)<\/p>/g, '$1');

  // Put the code blocks back.
  return html.replace(
    new RegExp(`${MARK_OPEN}(\\d+)${MARK_CLOSE}`, 'g'),
    (_m, i: string) => blocks[Number(i)],
  );
}
