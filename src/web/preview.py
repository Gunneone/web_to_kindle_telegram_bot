"""
A look inside a book before it goes anywhere: the EPUB's chapters as one self-contained HTML page,
shown in a sandboxed frame. Stylesheets and images are inlined, so the page loads nothing else
and its own content security policy can forbid everything but inline styles and data: images.
"""

import base64
import mimetypes
import posixpath
import zipfile
from html import escape
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

# The page refuses scripts, connections and forms; it may only be framed by Eselsohr itself
CSP = ("default-src 'none'; img-src data:; style-src 'unsafe-inline'; frame-ancestors 'self'; "
       "base-uri 'none'; form-action 'none'")

DROP_TAGS = ('script', 'iframe', 'frame', 'object', 'embed', 'form', 'link', 'meta', 'base', 'noscript')
URL_ATTRIBUTES = ('href', 'src', 'xlink:href', 'action', 'formaction', 'poster')
MAX_IMAGE_BYTES = 8 * 1024 * 1024

# A Kindle page: e-ink paper, near-black ink, a book face, justified and hyphenated text with
# narrow margins. Kindle uses Bookerly; fonts can't load here, so the nearest system serifs stand in.
READER_CSS = """
:root { color-scheme: light; }
html { background: #f1f1ec; scrollbar-width: none; }
html::-webkit-scrollbar { display: none; }
body {
  margin: 0; padding: 16px 16px 20px; color: #161616; background: #f1f1ec;
  font: 14.5px/1.55 "Bookerly", "Literata", Charter, "Iowan Old Style", Georgia, serif;
  text-align: justify; hyphens: auto; -webkit-hyphens: auto; overflow-wrap: break-word;
  -webkit-text-size-adjust: 100%; text-rendering: optimizeLegibility;
}
h1, h2, h3, h4, h5, h6, figcaption, pre, table { text-align: left; hyphens: manual; }
h1 { font-size: 1.45em; line-height: 1.25; }
img, svg, video { max-width: 100% !important; height: auto !important; filter: grayscale(1); }
pre, code { white-space: pre-wrap; font-size: 0.85em; }
table { max-width: 100%; display: block; overflow-x: auto; }
a { color: inherit; }
hr.eselsohr-break { border: 0; border-top: 1px solid #c8c8c2; margin: 2em 0; }
"""


class PreviewError(Exception):
    """The file isn't an EPUB we can read."""


def _read(book: zipfile.ZipFile, name: str) -> bytes:
    try:
        return book.read(name)
    except KeyError as e:
        raise PreviewError(f'missing {name}') from e


def _resolve(base: str, ref: str) -> str | None:
    """A reference inside the EPUB, relative to the file `base`, as a zip entry name."""
    parts = urlparse(ref)
    if parts.scheme or parts.netloc or not parts.path:
        return None
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), unquote(parts.path))).lstrip('/')


def _spine(book: zipfile.ZipFile) -> tuple[list[str], dict[str, str]]:
    """The reading order (zip entry names) and the media type of every manifest entry."""
    container = BeautifulSoup(_read(book, 'META-INF/container.xml'), 'xml')
    rootfile = container.find('rootfile')
    if rootfile is None or not rootfile.get('full-path'):
        raise PreviewError('no package document')
    opf_path = rootfile['full-path']
    opf = BeautifulSoup(_read(book, opf_path), 'xml')
    manifest: dict[str, tuple[str, str, str]] = {}
    for item in opf.find_all('item'):
        name = _resolve(opf_path, item.get('href', ''))
        if name:
            manifest[item.get('id', '')] = (name, item.get('media-type', ''), item.get('properties', ''))
    order = []
    for ref in opf.find_all('itemref'):
        entry = manifest.get(ref.get('idref', ''))
        if entry and 'nav' not in entry[2].split() and entry[1] in ('application/xhtml+xml', 'text/html'):
            order.append(entry[0])
    if not order:
        raise PreviewError('empty spine')
    return order, {name: media for name, media, _ in manifest.values()}


def _data_uri(book: zipfile.ZipFile, name: str, types: dict[str, str]) -> str | None:
    try:
        info = book.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_IMAGE_BYTES:
        return None
    media = types.get(name) or mimetypes.guess_type(name)[0] or ''
    if not media.startswith('image/'):
        return None
    return f'data:{media};base64,{base64.b64encode(book.read(name)).decode()}'


def _clean(body, book: zipfile.ZipFile, doc: str, types: dict[str, str]) -> None:
    """Make one chapter's body safe and self-contained, in place."""
    for tag in body.find_all(DROP_TAGS):
        tag.decompose()
    for tag in body.find_all(True):
        for attribute in list(tag.attrs):
            value = tag.attrs[attribute]
            text = ' '.join(value) if isinstance(value, list) else str(value)
            lowered = attribute.lower()
            if lowered.startswith('on') or lowered == 'srcset':
                del tag.attrs[attribute]
            elif lowered in URL_ATTRIBUTES and text.strip().lower().startswith(('javascript:', 'vbscript:', 'data:text')):
                del tag.attrs[attribute]
        if tag.name in ('img', 'image', 'source'):
            attribute = 'src' if tag.name != 'image' else ('xlink:href' if tag.get('xlink:href') else 'href')
            ref = tag.get(attribute)
            name = _resolve(doc, ref) if ref else None
            uri = _data_uri(book, name, types) if name else None
            if uri:
                tag[attribute] = uri
            elif ref and not str(ref).startswith('data:image/'):
                del tag[attribute]  # a remote or missing image can't load in the preview anyway
        if tag.name == 'a' and tag.get('href'):
            href = str(tag['href'])
            if href.startswith('#'):
                continue
            if urlparse(href).scheme in ('http', 'https', 'mailto'):
                tag['target'] = '_blank'
                tag['rel'] = 'noopener noreferrer'
            else:
                del tag['href']  # links between chapters: the preview is one scrolling page


def word_count(epub_path: str) -> int:
    """How many words the book's chapters hold; 0 when the EPUB can't be read."""
    try:
        with zipfile.ZipFile(epub_path) as book:
            order, _ = _spine(book)
            text = ' '.join(BeautifulSoup(_read(book, doc), 'html.parser').get_text(' ') for doc in order)
    except (OSError, zipfile.BadZipFile, PreviewError):
        return 0
    return len(text.split())


def render(epub_path: str, title: str | None = None, lang: str = 'en') -> str:
    """The book as one HTML page. Raises PreviewError when the EPUB can't be read."""
    try:
        book = zipfile.ZipFile(epub_path)
    except (OSError, zipfile.BadZipFile) as e:
        raise PreviewError(str(e)) from e
    with book:
        order, types = _spine(book)
        styles: list[str] = []
        seen_styles: set[str] = set()
        chapters: list[str] = []
        for doc in order:
            soup = BeautifulSoup(_read(book, doc), 'html.parser')
            for link in soup.find_all('link'):
                rel = ' '.join(link.get('rel') or []).lower()
                name = _resolve(doc, link.get('href', ''))
                if 'stylesheet' in rel and name and name not in seen_styles:
                    seen_styles.add(name)
                    try:
                        styles.append(book.read(name).decode('utf-8', 'replace'))
                    except KeyError:
                        pass
            for style in soup.find_all('style'):
                styles.append(style.get_text())
            body = soup.find('body') or soup
            _clean(body, book, doc, types)
            chapters.append(body.decode_contents() if body.name == 'body' else str(body))

    # A style sheet can't break out of a <style> element unless it closes it
    css = '\n'.join(styles).replace('</', '<\\/')
    divider = '<hr class="eselsohr-break">'
    return (f'<!doctype html><html lang="{escape(lang, quote=True)}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(title or "Preview")}</title>'
            f'<style>{css}</style><style>{READER_CSS}</style></head>'
            f'<body>{divider.join(chapters)}</body></html>')
