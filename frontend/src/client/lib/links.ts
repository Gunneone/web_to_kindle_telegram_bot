/** As many links as the bot takes from one message, and the server runs for one account at a time. */
export const MAX_LINKS = 10;

const URL_PATTERN = /https?:\/\/[^\s<>"'«»“”‘’]+/gi;
const TRAILING = /[.,;:!?)\]}>]+$/;

/** A link copied out of a sentence often brings the full stop or the closing bracket along. */
function trim(url: string): string {
  let result = url;
  for (;;) {
    const match = result.match(TRAILING);
    if (!match) return result;
    // Keep a closing bracket that belongs to the link, as in .../wiki/Ear_(anatomy)
    const end = match[0];
    if (end === ')' && (result.match(/\(/g)?.length ?? 0) >= (result.match(/\)/g)?.length ?? 0)) return result;
    result = result.slice(0, -1);
  }
}

/**
 * The links in whatever was pasted or shared: one link, several, or a sentence with links in it.
 * Text without any http(s) link comes back as it is, so `example.com/post` still reaches the server,
 * which knows how to complete it.
 */
export function extractLinks(text: string): string[] {
  const found = [...text.matchAll(URL_PATTERN)].map((match) => trim(match[0]));
  if (found.length === 0) {
    const plain = text.trim();
    return plain ? [plain] : [];
  }
  return [...new Set(found)];
}

/**
 * A link handed to the start page by the bookmarklet (`?url=`) or the phone's share sheet, which
 * sends `title`, `text` and `url`; many apps put the link into `text`.
 */
export function sharedLink(params: URLSearchParams): string {
  const url = params.get('url')?.trim();
  if (url) return url;
  const text = params.get('text') ?? '';
  return extractLinks(text).find((link) => /^https?:\/\//i.test(link)) ?? '';
}

/** A bookmark that opens Eselsohr with the page being read, in a new tab. */
export function bookmarklet(origin: string): string {
  const target = JSON.stringify(`${origin}/?url=`);
  return `javascript:(function(){var u=${target}+encodeURIComponent(location.href);if(!window.open(u,'_blank'))location.href=u;})();`;
}
