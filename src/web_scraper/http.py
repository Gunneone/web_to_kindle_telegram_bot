"""
Shared HTTP helpers: browser-like headers, timeouts, charset detection and a
browser-impersonation retry for sites that block plain HTTP clients.
"""

import codecs
import logging
import re
import threading
import time
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin

import requests
from requests.structures import CaseInsensitiveDict

from .errors import BlockedError, FetchError

logger = logging.getLogger(__name__)

USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36')
HTML_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}
# Ask image CDNs (Substack, Medium, ...) for formats Kindle understands instead of WebP/AVIF
IMAGE_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'image/jpeg,image/png,image/gif;q=0.9,image/*;q=0.5,*/*;q=0.1',
}
TIMEOUT = (10, 30)  # (connect, read) seconds
BLOCK_STATUSES = {401, 403, 429, 503}
RATE_LIMIT_RETRIES = 2  # Wikimedia and others answer bursts of image requests with 429
MAX_META_REFRESH_HOPS = 3
META_REFRESH = re.compile(r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]*content=["\']?\s*\d+\s*;\s*url=([^"\'>\s]+)', re.I)
MAX_IMAGE_BYTES = 10 * 1024 * 1024

_local = threading.local()


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    headers: CaseInsensitiveDict
    html: str

    @property
    def is_cloudflare(self) -> bool:
        return 'cloudflare' in self.headers.get('server', '').lower() or 'cf-ray' in self.headers


def _session() -> requests.Session:
    """One session per thread (requests.Session is not guaranteed to be thread-safe)."""
    session = getattr(_local, 'session', None)
    if session is None:
        session = requests.Session()
        session.headers.update(HTML_HEADERS)
        _local.session = session
    return session


def fetch(url: str) -> FetchResult:
    """
    Download an HTML page.

    Retries with browser TLS impersonation (curl_cffi) when the site answers with a
    bot-block status, as Medium and other Cloudflare-protected sites do, and follows
    <meta http-equiv="refresh"> redirect pages (open.substack.com share links use them).

    Raises:
        BlockedError: the site keeps refusing access
        FetchError: network error, timeout or another HTTP error
    """
    result = _fetch_once(url)
    for _ in range(MAX_META_REFRESH_HOPS):
        target = _meta_refresh_target(result)
        if not target:
            break
        logger.info(f"Following meta refresh redirect to {target}")
        result = _fetch_once(target)
    result.url = url
    return result


def _fetch_once(url: str) -> FetchResult:
    try:
        response = _get_with_backoff(url)
        result = _to_result(url, response.url, response.status_code, response.headers, response.content)
    except requests.Timeout as e:
        raise FetchError("The site took too long to respond.") from e
    except requests.RequestException as e:
        raise FetchError(f"Could not reach the site ({type(e).__name__}).") from e

    if result.status in BLOCK_STATUSES:
        logger.info(f"HTTP {result.status} for {url}, retrying with browser impersonation")
        impersonated = _fetch_impersonated(url)
        if impersonated is not None:
            result = impersonated

    if result.status in BLOCK_STATUSES:
        raise BlockedError("This site blocks automated access, so the article can't be fetched.", result)
    if result.status >= 400:
        raise FetchError(f"The site returned HTTP {result.status}.")
    return result


def fetch_bytes(url: str, max_bytes: int = MAX_IMAGE_BYTES) -> tuple[bytes, str] | None:
    """Download a binary resource (image). Returns (content, content_type) or None on any failure."""
    try:
        with _get_with_backoff(url, headers=IMAGE_HEADERS, stream=True) as response:
            if response.status_code in (401, 403):
                return _fetch_bytes_impersonated(url, max_bytes)
            if response.status_code != 200:
                logger.warning(f"Image download failed with HTTP {response.status_code}: {url}")
                return None
            if int(response.headers.get('content-length') or 0) > max_bytes:
                logger.warning(f"Image too large, skipping: {url}")
                return None
            chunks, total = [], 0
            for chunk in response.iter_content(64 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    logger.warning(f"Image too large, skipping: {url}")
                    return None
                chunks.append(chunk)
            return b''.join(chunks), response.headers.get('content-type', '')
    except requests.RequestException as e:
        logger.warning(f"Image download failed ({type(e).__name__}): {url}")
        return None


def _meta_refresh_target(result: FetchResult) -> str | None:
    """Redirect target of a small interstitial page that only contains a meta refresh."""
    if len(result.html) > 20000:
        return None
    match = META_REFRESH.search(result.html)
    return urljoin(result.final_url, unescape(match.group(1))) if match else None


def _get_with_backoff(url: str, **kwargs) -> requests.Response:
    """GET that waits and retries when the server rate-limits us (HTTP 429)."""
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        response = _session().get(url, timeout=TIMEOUT, **kwargs)
        if response.status_code != 429 or attempt == RATE_LIMIT_RETRIES:
            return response
        retry_after = response.headers.get('retry-after', '')
        delay = min(float(retry_after), 5.0) if retry_after.isdigit() else 1.0 + attempt
        response.close()
        logger.info(f"HTTP 429 for {url}, retrying in {delay:.0f}s")
        time.sleep(delay)
    return response


def decode_html(content: bytes, content_type: str = '') -> str:
    """
    Decode an HTML body: HTTP charset, then <meta charset>, then UTF-8, then cp1252.

    requests falls back to ISO-8859-1 when the header has no charset, which garbles UTF-8 pages.
    """
    if content.startswith(codecs.BOM_UTF8):
        return content[len(codecs.BOM_UTF8):].decode('utf-8', errors='replace')

    candidates = []
    header_match = re.search(r'charset=["\']?([\w.:-]+)', content_type or '', re.I)
    if header_match:
        candidates.append(header_match.group(1))
    meta_match = re.search(rb'<meta[^>]+charset=["\']?\s*([\w.:-]+)', content[:4096], re.I)
    if meta_match:
        candidates.append(meta_match.group(1).decode('ascii', errors='ignore'))
    candidates.append('utf-8')

    for encoding in candidates:
        try:
            return content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode('cp1252', errors='replace')


def _to_result(url, final_url, status, headers, content) -> FetchResult:
    headers = CaseInsensitiveDict(headers)
    return FetchResult(url=url, final_url=str(final_url), status=status, headers=headers,
                       html=decode_html(content, headers.get('content-type', '')))


def _fetch_impersonated(url: str) -> FetchResult | None:
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        logger.warning("curl_cffi is not installed, cannot retry with browser impersonation")
        return None
    try:
        response = cffi_requests.get(url, impersonate='chrome', timeout=TIMEOUT[1])
    except Exception as e:
        logger.warning(f"Impersonated request failed for {url}: {e}")
        return None
    return _to_result(url, response.url, response.status_code, dict(response.headers), response.content)


def _fetch_bytes_impersonated(url: str, max_bytes: int) -> tuple[bytes, str] | None:
    try:
        from curl_cffi import requests as cffi_requests
        response = cffi_requests.get(url, impersonate='chrome', timeout=TIMEOUT[1],
                                     headers={'Accept': IMAGE_HEADERS['Accept']})
    except Exception as e:
        logger.warning(f"Impersonated image download failed for {url}: {e}")
        return None
    if response.status_code != 200 or len(response.content) > max_bytes:
        return None
    return response.content, response.headers.get('content-type', '')
