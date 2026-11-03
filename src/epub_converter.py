import base64
import hashlib
import io
import logging
import os
import re
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from html import escape

from bs4 import BeautifulSoup
from ebooklib import epub
from PIL import Image, ImageOps, UnidentifiedImageError

from web_scraper import Article
from web_scraper.html_cleanup import FALLBACK_SRC
from web_scraper.http import fetch_bytes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

EPUBS_DIR = './output/epubs'  # one directory per conversion: <url hash>-<random>/<title slug>.epub
MAX_IMAGES = 300
MAX_IMAGE_WIDTH = 1600
DOWNLOAD_WORKERS = 8
# Formats Kindle's EPUB conversion handles natively; everything else (WebP, AVIF, ...) is converted
KINDLE_FORMATS = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'), 'GIF': ('gif', 'image/gif')}
STYLESHEET = """
img { max-width: 100%; height: auto; }
figure { margin: 1em 0; }
figcaption { font-size: 0.9em; font-style: italic; }
pre { white-space: pre-wrap; }
"""


def load_image(src: str) -> bytes | None:
    """Return the raw bytes of an image URL or data: URI."""
    if src.startswith('data:'):
        match = re.match(r'data:image/[\w.+-]+;base64,(.*)', src, re.S)
        if not match:
            return None
        try:
            return base64.b64decode(match.group(1))
        except ValueError:
            return None
    result = fetch_bytes(src)
    return result[0] if result else None


def to_kindle_image(data: bytes) -> tuple[bytes, str, str] | None:
    """
    Convert image bytes to a Kindle-friendly format and size.

    Returns (content, extension, media_type), or None for undecodable data and tracking pixels.
    """
    if b'<svg' in data[:1024].lower():
        return data, 'svg', 'image/svg+xml'
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width <= 2 or image.height <= 2:
                return None  # tracking pixel
            animated = getattr(image, 'is_animated', False)
            if image.format in KINDLE_FORMATS and (image.width <= MAX_IMAGE_WIDTH or animated):
                extension, media_type = KINDLE_FORMATS[image.format]
                return data, extension, media_type

            image = ImageOps.exif_transpose(image)
            if image.width > MAX_IMAGE_WIDTH:
                image.thumbnail((MAX_IMAGE_WIDTH, MAX_IMAGE_WIDTH * 10))
            has_alpha = image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info)
            output = io.BytesIO()
            if has_alpha:
                image.convert('RGBA').save(output, 'PNG', optimize=True)
                return output.getvalue(), 'png', 'image/png'
            image.convert('RGB').save(output, 'JPEG', quality=85, optimize=True)
            return output.getvalue(), 'jpg', 'image/jpeg'
    except (UnidentifiedImageError, OSError, ValueError) as e:
        logger.warning(f"Could not decode image: {e}")
        return None


def _prepare_image(src: str) -> tuple[bytes, str, str] | None:
    data = load_image(src)
    return to_kindle_image(data) if data else None


def process_images(html_content: str, book: epub.EpubBook, preserve_image_links: bool = False) -> str:
    """Download all images in parallel, embed them in the book and point the HTML at the embedded copies."""
    soup = BeautifulSoup(html_content, 'html.parser')
    images = [img for img in soup.find_all('img') if img.get('src')]
    unique_sources = list(dict.fromkeys(img['src'] for img in images))[:MAX_IMAGES]
    # Smaller original src of images whose larger srcset candidate was picked (e.g. Wikimedia originals are rate-limited)
    fallbacks = {img['src']: img[FALLBACK_SRC] for img in images if img.get(FALLBACK_SRC)}
    logger.debug(f"Found {len(images)} images ({len(unique_sources)} unique) in HTML content")

    def prepare(src: str):
        return _prepare_image(src) or (_prepare_image(fallbacks[src]) if src in fallbacks else None)

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
        prepared = dict(zip(unique_sources, executor.map(prepare, unique_sources)))

    embedded = {}  # src -> file name inside the EPUB
    for src, result in prepared.items():
        if result is None:
            continue
        content, extension, media_type = result
        file_name = f'Images/img_{len(embedded) + 1:03d}.{extension}'
        book.add_item(epub.EpubImage(uid=f'img_{len(embedded) + 1:03d}', file_name=file_name,
                                     media_type=media_type, content=content))
        embedded[src] = file_name

    failed = 0
    for img in images:
        img.attrs.pop(FALLBACK_SRC, None)
        file_name = embedded.get(img['src'])
        if file_name is None:
            # Never leave remote images in the book: keep the alt text instead
            failed += 1
            alt = (img.get('alt') or '').strip()
            img.replace_with(soup.new_string(f'[Image: {alt}]') if alt else '')
            continue
        img['src'] = file_name  # content.xhtml sits next to Images/, so the reference resolves exactly
        parent_link = img.find_parent('a')
        if not preserve_image_links and parent_link:
            parent_link.unwrap()  # a link can wrap several images (galleries), so keep all of its content

    logger.info(f"Embedded {len(embedded)} images, {failed} image references failed")
    return str(soup)


def safe_filename(title: str, max_length: int = 80) -> str:
    """'TCP/IP: a "guide"?' -> 'tcp-ip-a-guide'"""
    slug = re.sub(r'[^\w-]+', '-', title.lower(), flags=re.UNICODE).strip('-_')
    return re.sub(r'-{2,}', '-', slug)[:max_length].strip('-') or 'article'


def convert_to_epub(article: Article, preserve_image_links: bool = False) -> str:
    """
    Convert article content to EPUB format and save it.

    Args:
        article (Article): The extracted article
        preserve_image_links (bool): Keep links around images (for zooming on the Kindle)

    Returns:
        str: Path to the saved EPUB file

    Raises:
        RuntimeError: If the EPUB file could not be written
    """
    logger.debug("Starting EPUB conversion")
    title = article.Title or 'Untitled'
    language = article.Language or 'en'

    book = epub.EpubBook()
    book.set_identifier(f'urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, article.URL)}')
    book.set_title(title)
    book.set_language(language)
    if article.Author:
        book.add_author(article.Author)
    if article.Publication:
        book.add_metadata('DC', 'publisher', article.Publication)
        book.add_metadata('DC', 'description', f"Article from {article.Publication}")
    if article.Published_At:
        book.add_metadata('DC', 'date', article.Published_At)
    book.add_metadata('DC', 'source', article.URL)

    html_content = article.Content
    if article.Is_Preview:
        url = escape(article.URL, quote=True)
        html_content += (f'<hr/><p><em>This is a preview — the full post is for paid subscribers: '
                         f'<a href="{url}">{url}</a></em></p>')
    processed_content = process_images(html_content, book, preserve_image_links)

    style = epub.EpubItem(uid='style', file_name='style.css', media_type='text/css', content=STYLESHEET)
    book.add_item(style)
    content = epub.EpubHtml(title=title, file_name='content.xhtml', lang=language, content=processed_content)
    content.add_item(style)
    book.add_item(content)

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Basic spine without cover
    book.spine = [content]

    # The file name is what readers see (Telegram attachment, Kindle library), so it stays the readable slug.
    # The directory is new for every conversion: articles that share a title, or have none, never share a file.
    url_hash = hashlib.sha256(article.URL.encode()).hexdigest()[:10]
    book_dir = os.path.join(EPUBS_DIR, f"{url_hash}-{uuid.uuid4().hex[:12]}")
    os.makedirs(book_dir)  # no exist_ok: a reused directory would be a shared file, so fail instead
    epub_path = os.path.join(book_dir, f"{safe_filename(title)}.epub")
    temp_path = f"{epub_path}.tmp"

    # write_epub swallows IO errors and returns False, so check explicitly
    if not epub.write_epub(temp_path, book) or not os.path.exists(temp_path):
        shutil.rmtree(book_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to write EPUB file for '{title}'")
    os.replace(temp_path, epub_path)  # atomic, so a reader never sees a half-written file
    logger.info(f"EPUB saved to {epub_path}")
    return epub_path
