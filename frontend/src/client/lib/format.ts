const LOCALES = { en: 'en-GB', de: 'de-DE' } as const;

export function formatDate(value: string | null, lang: 'en' | 'de'): string {
  if (!value) return '';
  return new Date(value).toLocaleDateString(LOCALES[lang], { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatSize(bytes: number | null, lang: 'en' | 'de'): string {
  if (bytes === null) return '';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  const mb = (bytes / (1024 * 1024)).toFixed(1);
  return `${lang === 'de' ? mb.replace('.', ',') : mb} MB`;
}

/** Where a path goes after signing in: only places on this site. */
export function safeNext(value: string | null): string {
  return value && value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') ? value : '/';
}
