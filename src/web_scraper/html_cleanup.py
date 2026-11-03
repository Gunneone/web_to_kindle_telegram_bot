"""
HTML helpers shared by all scrapers: lazy-image promotion, page-chrome removal,
Kindle-safe sanitizing and the article header.
"""

import re
from html import escape
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .metadata import format_date

LAZY_SRC_ATTRS = ('data-src', 'data-lazy-src', 'data-original', 'data-lazy', 'data-url',
                  'data-hi-res-src', 'data-full-src', 'data-orig-file')
LAZY_SRCSET_ATTRS = ('data-srcset', 'data-lazy-srcset', 'srcset')
PLACEHOLDER_SRC = re.compile(r'^data:|placeholder|blank\.(gif|png)|spacer\.(gif|png)|transparent\.(gif|png)|\$\{|\{\{',
                             re.I)
CUSTOM_IMAGE_TAGS = ('amp-img', 'a-img')  # AMP and heise.de image components
MAX_IMAGE_WIDTH = 1600

CHROME_SELECTORS = [
    '[role=dialog]', '[aria-modal=true]', '.modal', 'nav',
    '.navbox', '.vertical-navbox', '.mw-editsection', '.mw-jump-link',
    '#comments', '.comments', '#comment-section', '.comment-section', '#disqus_thread', '.comments-area',
    '.sharedaddy', '.jp-relatedposts', '.share-buttons', '.social-share',
    '#onetrust-consent-sdk', '.cookie-banner', '#cookie-banner', '.cookie-notice',
]
REMOVE_TAGS = ['script', 'style', 'noscript', 'form', 'button', 'input', 'select', 'textarea', 'svg',
               'template', 'link', 'meta', 'canvas', 'dialog', 'object']
FALLBACK_SRC = 'data-fallback-src'
KEEP_ATTRS = {'id', 'href', 'src', 'alt', 'title', 'colspan', 'rowspan', 'lang', 'dir', 'start', 'reversed',
              FALLBACK_SRC}
HEADER_STYLE = {
    'author': 'color: #666; font-style: italic; margin: 10px 0;',
    'meta': 'color: #888; font-style: italic; margin: 5px 0;',
    'rule': 'border-top: 1px solid #ccc; margin: 20px 0;',
}


def promote_lazy_images(soup: BeautifulSoup) -> None:
    """
    Make lazy-loaded and responsive images visible to extractors: copy data-src/srcset into src,
    collapse <picture> into a plain <img>, and use <noscript> fallbacks for placeholder images.
    """
    for custom in soup.find_all(CUSTOM_IMAGE_TAGS):
        custom.name = 'img'

    for picture in soup.find_all('picture'):
        img = picture.find('img')
        src = _best_image_url(img) if img else None
        if not src:
            src = _best_source_url(picture.find_all('source'))
        if not src:
            continue
        if img is None:
            img = soup.new_tag('img')
        img['src'] = src
        for attr in LAZY_SRCSET_ATTRS:
            img.attrs.pop(attr, None)
        picture.replace_with(img.extract() if img.parent else img)

    for img in soup.find_all('img'):
        src = _best_image_url(img)
        original = img.get('src')
        if src and original and src != original and not _is_placeholder(original):
            img[FALLBACK_SRC] = original  # used if the larger srcset candidate can't be downloaded
        if src:
            img['src'] = src

    for noscript in soup.find_all('noscript'):
        fallback = noscript.find('img')
        if fallback is None:
            inner = BeautifulSoup(noscript.decode_contents(), 'html.parser')
            fallback = inner.find('img')
        if fallback is None:
            continue
        sibling = _neighbour_image(noscript)
        if sibling is not None and not _is_placeholder(sibling.get('src')):
            noscript.decompose()  # the visible image is already usable
            continue
        if sibling is not None:
            sibling.decompose()
        noscript.replace_with(fallback.extract() if fallback.parent else fallback)


def reveal_streamed_content(soup: BeautifulSoup) -> None:
    """
    React streaming SSR (Next.js, LessWrong) sends the article in <div hidden id="S:n"> chunks that
    JavaScript moves into place; un-hide them so extractors can see the text.
    """
    for chunk in soup.find_all('div', attrs={'hidden': True, 'id': re.compile(r'^S:\d+$')}):
        del chunk['hidden']


def remove_chrome(soup: BeautifulSoup) -> None:
    """Remove pop-ups, navigation, comment sections and other non-article page elements."""
    for selector in CHROME_SELECTORS:
        for element in soup.select(selector):
            if element.name not in ('html', 'body', 'article', 'main'):
                element.decompose()


def sanitize_for_kindle(html: str, base_url: str) -> str:
    """
    Turn extracted article HTML into something safe for an EPUB: absolute links, no scripts,
    forms, inline SVG icons, responsive-image sources or embedded frames.
    """
    soup = BeautifulSoup(html, 'lxml')
    root = soup.body or soup

    # Hidden duplicates (e.g. Wikipedia's hidden MathML next to the fallback image)
    for element in root.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
        element.decompose()

    for media in root.find_all(['iframe', 'embed', 'video', 'audio']):
        src = media.get('src') or next((s.get('src') for s in media.find_all('source') if s.get('src')), None)
        media.replace_with(_embed_link(soup, src, media.name, base_url) if src else '')

    for tag in root.find_all(REMOVE_TAGS + ['source']):
        tag.decompose()

    for img in root.find_all('img'):
        src = (img.get('src') or '').strip()
        if not src or src == '#' or _is_placeholder(src) and not src.startswith('data:'):
            img.decompose()
            continue
        if not src.startswith('data:'):
            img['src'] = urljoin(base_url, src)
            if img['src'].split('#')[0] == base_url.split('#')[0]:
                img.decompose()  # empty src that an extractor resolved to the page itself
                continue
        if img.get(FALLBACK_SRC):
            img[FALLBACK_SRC] = urljoin(base_url, img[FALLBACK_SRC])

    for link in root.find_all('a'):
        href = (link.get('href') or '').strip()
        if not href or href.lower().startswith('javascript:'):
            link.unwrap()
        elif not href.startswith('#'):
            link['href'] = urljoin(base_url, href)

    for tag in root.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in KEEP_ATTRS}

    return root.decode_contents()


def strip_leading_title(html: str, title: str | None) -> str:
    """Remove a heading at the top of the content that repeats the article title."""
    if not title:
        return html
    soup = BeautifulSoup(html, 'lxml')
    root = soup.body or soup
    wanted = _normalize_text(title)
    for heading in root.find_all(['h1', 'h2', 'h3'], limit=3):
        preceding_words = sum(len(el.split()) for el in heading.find_all_previous(string=True))
        if preceding_words > 30:
            break
        if _normalize_text(heading.get_text()) == wanted:
            heading.decompose()
            return root.decode_contents()
    return html


def build_header(title: str, author: str | None = None, publication: str | None = None,
                 published: str | None = None, subtitle: str | None = None) -> str:
    parts = [f'<h1>{escape(title)}</h1>']
    if subtitle:
        parts.append(f'<p><em>{escape(subtitle)}</em></p>')
    if author:
        parts.append(f'<h4 style="{HEADER_STYLE["author"]}">By {escape(author)}</h4>')
    if publication and publication != author:
        parts.append(f'<h5 style="{HEADER_STYLE["meta"]}">From: {escape(publication)}</h5>')
    if published:
        parts.append(f'<h5 style="{HEADER_STYLE["meta"]}">Published: {escape(format_date(published))}</h5>')
    parts.append(f'<hr style="{HEADER_STYLE["rule"]}"/>')
    return '\n'.join(parts) + '\n'


def count_words(html: str | None) -> int:
    if not html:
        return 0
    return len(BeautifulSoup(html, 'lxml').get_text(' ').split())


def best_srcset_url(srcset: str | None, max_width: int = MAX_IMAGE_WIDTH) -> str | None:
    """Pick the largest candidate no wider than max_width from a srcset attribute."""
    if not srcset:
        return None
    candidates = []
    for entry in re.split(r',\s+', srcset.strip()):
        bits = entry.strip().split()
        if not bits:
            continue
        match = re.fullmatch(r'(\d+(?:\.\d+)?)([wx])', bits[1]) if len(bits) > 1 else None
        width = 800.0
        if match:
            width = float(match.group(1)) * (1 if match.group(2) == 'w' else 800)
        candidates.append((width, bits[0]))
    if not candidates:
        return None
    fitting = [c for c in candidates if c[0] <= max_width]
    return (max(fitting) if fitting else min(candidates))[1]


def _best_image_url(img: Tag) -> str | None:
    for attr in LAZY_SRC_ATTRS:
        value = img.get(attr)
        if value and not _is_placeholder(value):
            return value
    for attr in LAZY_SRCSET_ATTRS:
        best = best_srcset_url(img.get(attr))
        if best and not _is_placeholder(best):
            return best
    src = img.get('src')
    return None if _is_placeholder(src) else src


def _best_source_url(sources: list[Tag]) -> str | None:
    """Prefer <source> candidates in formats Kindle supports natively."""
    ranked = sorted(sources, key=lambda s: (s.get('type') or '').lower() in ('image/webp', 'image/avif'))
    for source in ranked:
        best = best_srcset_url(source.get('srcset') or source.get('data-srcset'))
        if best:
            return best
    return None


def _neighbour_image(noscript: Tag) -> Tag | None:
    previous = noscript.find_previous_sibling()
    if previous is not None and previous.name == 'img':
        return previous
    if noscript.parent is not None:
        for img in noscript.parent.find_all('img', recursive=False):
            return img
    return None


def _is_placeholder(src: str | None) -> bool:
    return not src or bool(PLACEHOLDER_SRC.search(src))


def _embed_link(soup: BeautifulSoup, src: str, kind: str, base_url: str) -> Tag:
    url = urljoin(base_url, src)
    if url.startswith('//'):
        url = 'https:' + url
    host = (urlparse(url).hostname or url).removeprefix('www.')
    is_video = kind in ('video',) or any(v in host for v in ('youtube', 'youtu.be', 'vimeo'))
    label = 'Embedded video' if is_video else ('Embedded audio' if kind == 'audio' else 'Embedded content')
    paragraph = soup.new_tag('p')
    link = soup.new_tag('a', href=url)
    link.string = f"{label}: {host}"
    paragraph.append(link)
    return paragraph


def _normalize_text(text: str) -> str:
    return re.sub(r'[\W_]+', ' ', text.lower()).strip()
