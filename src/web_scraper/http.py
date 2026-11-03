"""
Shared HTTP helpers: browser-like headers, timeouts, charset detection and a
browser-impersonation retry for sites that block plain HTTP clients.

Every request goes through an SSRF guard: users (and the pages they send, via image URLs and
meta refreshes) choose what we fetch, so only http(s) URLs on public addresses are allowed.
"""

import codecs
import ipaddress
import logging
import re
import socket
import threading
import time
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlsplit
from urllib.request import getproxies_environment

import requests
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from requests.utils import requote_uri
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

from .errors import BlockedError, FetchError, UnsafeURLError

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
MAX_REDIRECTS = 10
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
DEFAULT_PORTS = {'http': 80, 'https': 443}
NAT64_PREFIX = ipaddress.ip_network('64:ff9b::/96')
# Characters that make URL parsers disagree about the host (http://evil.example\@127.0.0.1/)
AMBIGUOUS_NETLOC = re.compile(r'[\\\s\x00-\x1f\x7f]')
UNSAFE_ADDRESS_MESSAGE = "This link points to a private or local network address, so it can't be fetched."

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


def check_url(url: str) -> None:
    """
    SSRF guard: refuse URLs we must not fetch on a user's behalf.

    Only http(s) URLs whose host resolves exclusively to public, globally routable addresses
    pass. Loopback, private (RFC 1918, IPv6 ULA), link-local (cloud metadata at
    169.254.169.254), shared, multicast and reserved addresses are refused.

    Raises:
        UnsafeURLError: the scheme isn't http(s) or the host has a non-public address
        FetchError: the host name doesn't resolve
    """
    try:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        port = parts.port or DEFAULT_PORTS.get(scheme)
    except ValueError as e:  # e.g. a non-numeric port
        raise UnsafeURLError("The link is not a valid web address.") from e
    if scheme not in DEFAULT_PORTS:
        raise UnsafeURLError("Only http and https links can be fetched.")
    if not parts.hostname or AMBIGUOUS_NETLOC.search(parts.netloc):
        raise UnsafeURLError("The link is not a valid web address.")

    for address in _resolve(parts.hostname, port):
        if not is_public_address(address):
            logger.warning(f"Refusing to fetch {url}: {parts.hostname} resolves to non-public address {address}")
            raise UnsafeURLError(UNSAFE_ADDRESS_MESSAGE)


def is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for globally routable unicast addresses, judging IPv4 embedded in IPv6 by the IPv4 address."""
    if address.version == 6:
        if address.ipv4_mapped:
            address = address.ipv4_mapped
        elif address in NAT64_PREFIX:
            address = ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    return address.is_global and not (address.is_loopback or address.is_private or address.is_link_local
                                      or address.is_multicast or address.is_reserved or address.is_unspecified)


def _resolve(host: str, port: int) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return {ipaddress.ip_address(host)}
    except ValueError:
        pass  # a host name, or an IPv4 shorthand like 127.1 or 2130706433 that only the resolver understands
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as e:
        raise FetchError("Could not reach the site (its address could not be found).") from e
    addresses = {ipaddress.ip_address(info[4][0]) for info in infos}
    if not addresses:
        raise FetchError("Could not reach the site (its address could not be found).")
    return addresses


def _check_peer(ip: str, host: str) -> None:
    """Refuse a connection that ended up at a non-public address (DNS rebinding after check_url)."""
    address = ipaddress.ip_address(ip)
    if not is_public_address(address):
        logger.warning(f"Refusing connection to {host}: connected to non-public address {address}")
        raise UnsafeURLError(UNSAFE_ADDRESS_MESSAGE)


class _PublicPeerMixin:
    """urllib3 connection that verifies the address it actually connected to before sending anything."""

    def _new_conn(self):
        sock = super()._new_conn()
        try:
            _check_peer(sock.getpeername()[0], self.host)
        except UnsafeURLError:
            sock.close()
            raise
        return sock


class _PublicHTTPConnection(_PublicPeerMixin, HTTPConnection):
    pass


class _PublicHTTPSConnection(_PublicPeerMixin, HTTPSConnection):
    pass


class _PublicHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _PublicHTTPConnection


class _PublicHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PublicHTTPSConnection


class _PublicOnlyAdapter(HTTPAdapter):
    """
    Adapter whose direct connections only reach public addresses.

    Requests through a configured proxy use urllib3's proxy manager and are not affected: the
    proxy is the peer then, and check_url has already vetted the target.
    """

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {'http': _PublicHTTPConnectionPool,
                                                   'https': _PublicHTTPSConnectionPool}


def _session() -> requests.Session:
    """One session per thread (requests.Session is not guaranteed to be thread-safe)."""
    session = getattr(_local, 'session', None)
    if session is None:
        session = requests.Session()
        session.headers.update(HTML_HEADERS)
        adapter = _PublicOnlyAdapter()
        session.mount('http://', adapter)
        session.mount('https://', adapter)
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
        UnsafeURLError: the URL, a redirect or a meta refresh leads to a non-public address
        FetchError: network error, timeout or another HTTP error
    """
    result = _fetch_once(url)
    for _ in range(MAX_META_REFRESH_HOPS):
        target = _meta_refresh_target(result)
        if not target:
            break
        logger.info(f"Following meta refresh redirect to {target}")
        result = _fetch_once(target)  # checked by check_url like any other URL
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
    except FetchError as e:  # refused by check_url, or the host doesn't resolve
        logger.warning(f"Image download refused ({e}): {url}")
        return None


def _meta_refresh_target(result: FetchResult) -> str | None:
    """Redirect target of a small interstitial page that only contains a meta refresh."""
    if len(result.html) > 20000:
        return None
    match = META_REFRESH.search(result.html)
    return urljoin(result.final_url, unescape(match.group(1))) if match else None


def _get_with_backoff(url: str, **kwargs) -> requests.Response:
    """Checked GET (see _get_checked) that waits and retries when the server rate-limits us (HTTP 429)."""
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        response = _get_checked(url, **kwargs)
        if response.status_code != 429 or attempt == RATE_LIMIT_RETRIES:
            return response
        retry_after = response.headers.get('retry-after', '')
        delay = min(float(retry_after), 5.0) if retry_after.isdigit() else 1.0 + attempt
        response.close()
        logger.info(f"HTTP 429 for {url}, retrying in {delay:.0f}s")
        time.sleep(delay)
    return response


def _get_checked(url: str, **kwargs) -> requests.Response:
    """GET that follows redirects itself, running check_url on the URL and on every redirect target."""
    session = _session()
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        response = session.get(url, timeout=TIMEOUT, allow_redirects=False, **kwargs)
        target = session.get_redirect_target(response)
        if not target:
            return response
        response.close()
        url = urljoin(response.url, requote_uri(target))
    raise requests.TooManyRedirects(f"Exceeded {MAX_REDIRECTS} redirects.")


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


def _get_impersonated(url: str, **kwargs):
    """
    curl_cffi GET with Chrome's TLS fingerprint and the same SSRF checks as _get_checked.

    curl resolves host names itself, so on top of check_url for every hop the address curl
    connected to is verified before the response is used.
    """
    from curl_cffi import requests as cffi_requests
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        response = cffi_requests.get(url, impersonate='chrome', timeout=TIMEOUT[1], allow_redirects=False, **kwargs)
        behind_proxy = any(scheme != 'no' for scheme in getproxies_environment())  # the proxy is the peer then
        if response.primary_ip and not behind_proxy:
            _check_peer(response.primary_ip, urlsplit(url).hostname)
        location = response.headers.get('location')
        if response.status_code not in REDIRECT_STATUSES or not location:
            return response
        url = urljoin(response.url or url, location)
    raise FetchError("The site redirected too many times.")


def _fetch_impersonated(url: str) -> FetchResult | None:
    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        logger.warning("curl_cffi is not installed, cannot retry with browser impersonation")
        return None
    try:
        response = _get_impersonated(url)
    except UnsafeURLError:
        raise
    except Exception as e:
        logger.warning(f"Impersonated request failed for {url}: {e}")
        return None
    return _to_result(url, response.url, response.status_code, dict(response.headers), response.content)


def _fetch_bytes_impersonated(url: str, max_bytes: int) -> tuple[bytes, str] | None:
    try:
        response = _get_impersonated(url, headers={'Accept': IMAGE_HEADERS['Accept']})
    except Exception as e:
        logger.warning(f"Impersonated image download failed for {url}: {e}")
        return None
    if response.status_code != 200 or len(response.content) > max_bytes:
        return None
    return response.content, response.headers.get('content-type', '')
