// Small presentation helpers shared across components.

/** "just now", "5m ago", "3d ago", then a date. */
export function relativeTime(value: string | number | Date) {
  const ts = new Date(value).getTime();
  if (!ts) return '';
  const secs = Math.round((Date.now() - ts) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function formatDate(value: string | number | Date) {
  return new Date(value).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/** The host, for showing a source's origin under its title. */
export function hostOf(url: string | null | undefined) {
  if (!url) return '';
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

/** A book's face, picked from the words its sources share. Stable per topic. */
const TOPIC_EMOJI: [RegExp, string][] = [
  [/solar|renewable|photovolt|panel/, '☀️'],
  [/energy|electric|power|battery|grid/, '⚡'],
  [/health|medic|clinic|patient|disease/, '🩺'],
  [/finance|tax|money|invest|bank|credit|cost|price/, '💰'],
  [/law|legal|policy|regulat|court/, '⚖️'],
  [/food|recipe|cook|nutrit|diet/, '🍽️'],
  [/travel|flight|hotel|tour|city|country/, '✈️'],
  [/video|youtube|stream|channel|creator/, '📺'],
  [/code|software|program|develop|api|data/, '💻'],
  [/science|research|study|physic|chem|biolog/, '🔬'],
  [/school|learn|educat|course|student/, '🎓'],
  [/car|vehicle|drive|auto|engine/, '🚗'],
  [/home|house|build|construct|roof/, '🏠'],
  [/climate|environment|carbon|green|weather/, '🌍'],
  [/market|business|company|startup|sales/, '📈'],
  [/sport|game|team|football|match/, '⚽'],
  [/music|song|audio|sound/, '🎵'],
];

export function bookEmoji(title: string, sourceTitles: string[] = []) {
  const hay = `${title} ${sourceTitles.join(' ')}`.toLowerCase();
  for (const [re, emoji] of TOPIC_EMOJI) if (re.test(hay)) return emoji;
  return '📓';
}

/** Strip markdown so notes and narration read as plain prose. */
export function toPlainText(md: string) {
  return md
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/^\s*>\s?/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
