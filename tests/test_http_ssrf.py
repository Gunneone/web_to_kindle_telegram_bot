"""
Tests for the SSRF guard in web_scraper.http.

DNS is faked with a patched socket.getaddrinfo and HTTP with a fake requests adapter, so no
network access is needed. The DNS rebinding test opens a listening socket on 127.0.0.1.
"""

import io
import ipaddress
import os
import socket
import sys
import threading

import pytest
import requests
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from web_scraper import FetchError, UnsafeURLError  # noqa: E402
from web_scraper import http  # noqa: E402

PUBLIC_V4 = '93.184.215.14'
PUBLIC_V6 = '2606:4700:4700::1111'
ARTICLE = b'<html><body><article><p>Public article</p></article></body></html>'


def addrinfo(*ips, port=80):
    return [(socket.AF_INET6 if ':' in ip else socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))
            for ip in ips]


@pytest.fixture
def fake_dns(monkeypatch):
    """Map host names to addresses; unknown names fail to resolve like NXDOMAIN."""
    records = {}

    def getaddrinfo(host, port, *args, **kwargs):
        if host not in records:
            raise socket.gaierror(socket.EAI_NONAME, 'Name or service not known')
        return addrinfo(*records[host], port=port or 80)

    monkeypatch.setattr(socket, 'getaddrinfo', getaddrinfo)
    return records


class FakeAdapter(BaseAdapter):
    """Serves canned responses by URL and records every request that reached it."""

    def __init__(self, routes):
        super().__init__()
        self.routes = routes
        self.requested = []

    def send(self, request, **kwargs):
        self.requested.append(request.url)
        status, headers, body = self.routes[request.url]
        response = requests.Response()
        response.status_code = status
        response.headers = CaseInsensitiveDict(headers)
        response.raw = io.BytesIO(body)
        response.url = request.url
        response.request = request
        return response

    def close(self):
        pass


@pytest.fixture
def fake_web(monkeypatch):
    """Route the scraper's requests session to a FakeAdapter; returns a function to install routes."""
    def install(routes):
        adapter = FakeAdapter(routes)
        session = requests.Session()
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        monkeypatch.setattr(http, '_session', lambda: session)
        return adapter
    return install


# --- check_url ------------------------------------------------------------------------------

@pytest.mark.parametrize('url', [
    'http://127.0.0.1/',
    'http://127.0.0.1:8080/admin',
    'https://10.0.0.1/',
    'http://172.16.5.4/',
    'http://192.168.1.1/router',
    'http://169.254.169.254/latest/meta-data/',  # cloud metadata
    'http://0.0.0.0:8000/',
    'http://100.64.0.1/',  # carrier-grade NAT
    'http://224.0.0.1/',  # multicast
    'http://255.255.255.255/',
    'http://192.0.2.10/',  # documentation range
    'http://[::1]/',
    'http://[::]/',
    'http://[fe80::1]/',  # link-local
    'http://[fd00::1]/',  # unique local
    'http://[fd00:ec2::254]/',  # AWS metadata over IPv6
    'http://[::ffff:127.0.0.1]/',  # IPv4-mapped loopback
    'http://[::ffff:169.254.169.254]/',
    'http://[64:ff9b::a9fe:a9fe]/',  # NAT64 of 169.254.169.254
    'http://[ff02::1]/',
    'http://user:pass@127.0.0.1/',
])
def test_blocks_non_public_ip_literals(url, fake_dns):
    with pytest.raises(UnsafeURLError):
        http.check_url(url)


@pytest.mark.parametrize('url', ['http://127.1/', 'http://2130706433/', 'http://0x7f000001/', 'http://0/'])
def test_blocks_ipv4_shorthands_the_resolver_understands(url):
    # Real getaddrinfo: these never touch the network, it parses them as IPv4 numbers
    with pytest.raises(UnsafeURLError):
        http.check_url(url)


@pytest.mark.parametrize('url', [
    'file:///etc/passwd',
    'ftp://example.com/file',
    'gopher://127.0.0.1:6379/_INFO',
    'dict://127.0.0.1:11211/',
    'javascript:alert(1)',
    'data:text/html,hello',
    '//example.com/article',
    'example.com/article',
])
def test_blocks_other_schemes(url, fake_dns):
    fake_dns['example.com'] = [PUBLIC_V4]
    with pytest.raises(UnsafeURLError):
        http.check_url(url)


@pytest.mark.parametrize('url', ['http://example.com\\@127.0.0.1/', 'http://exa mple.com/', 'http://example.com:http/',
                                 'http:///path-without-host'])
def test_blocks_malformed_authority(url, fake_dns):
    fake_dns['example.com'] = [PUBLIC_V4]
    with pytest.raises(UnsafeURLError):
        http.check_url(url)


def test_blocks_hostname_resolving_to_private_address(fake_dns):
    fake_dns['intranet.example.com'] = ['10.1.2.3']
    with pytest.raises(UnsafeURLError):
        http.check_url('https://intranet.example.com/wiki')


def test_blocks_hostname_with_any_private_address(fake_dns):
    fake_dns['mixed.example.com'] = [PUBLIC_V4, '127.0.0.1']
    with pytest.raises(UnsafeURLError):
        http.check_url('https://mixed.example.com/')


def test_blocks_localhost_name(fake_dns):
    fake_dns['localhost'] = ['127.0.0.1', '::1']
    with pytest.raises(UnsafeURLError):
        http.check_url('http://localhost:5000/')


def test_unresolvable_host_is_a_fetch_error(fake_dns):
    with pytest.raises(FetchError) as excinfo:
        http.check_url('https://no-such-host.example/')
    assert not isinstance(excinfo.value, UnsafeURLError)


@pytest.mark.parametrize('url', [
    'https://example.com/article',
    'http://example.com:8080/p/post?utm_source=x#section',
    'HTTPS://EXAMPLE.COM/',
    f'https://{PUBLIC_V4}/',
    f'https://[{PUBLIC_V6}]/',
    'https://[::ffff:93.184.215.14]/',
])
def test_public_urls_pass(url, fake_dns):
    fake_dns['example.com'] = [PUBLIC_V4, PUBLIC_V6]
    http.check_url(url)  # no exception


@pytest.mark.parametrize('ip', [PUBLIC_V4, PUBLIC_V6, '1.1.1.1', '64:ff9b::808:808'])
def test_public_addresses(ip):
    assert http.is_public_address(ipaddress.ip_address(ip))


# --- fetch / fetch_bytes ---------------------------------------------------------------------

def test_fetch_public_url_follows_public_redirects(fake_dns, fake_web):
    fake_dns['example.com'] = [PUBLIC_V4]
    fake_dns['www.example.com'] = [PUBLIC_V4]
    web = fake_web({
        'http://example.com/post': (301, {'Location': 'https://www.example.com/post'}, b''),
        'https://www.example.com/post': (302, {'Location': '/p/post'}, b''),
        'https://www.example.com/p/post': (200, {'Content-Type': 'text/html; charset=utf-8'}, ARTICLE),
    })
    result = http.fetch('http://example.com/post')
    assert result.status == 200
    assert result.url == 'http://example.com/post'
    assert result.final_url == 'https://www.example.com/p/post'
    assert 'Public article' in result.html
    assert len(web.requested) == 3


def test_fetch_refuses_redirect_to_private_address(fake_dns, fake_web):
    fake_dns['example.com'] = [PUBLIC_V4]
    web = fake_web({
        'https://example.com/go': (302, {'Location': 'http://169.254.169.254/latest/meta-data/'}, b''),
    })
    with pytest.raises(UnsafeURLError):
        http.fetch('https://example.com/go')
    assert web.requested == ['https://example.com/go']  # the metadata endpoint was never requested


def test_fetch_refuses_redirect_to_host_resolving_privately(fake_dns, fake_web):
    fake_dns['example.com'] = [PUBLIC_V4]
    fake_dns['internal.example.com'] = ['192.168.0.10']
    web = fake_web({'https://example.com/go': (307, {'Location': 'https://internal.example.com/'}, b'')})
    with pytest.raises(UnsafeURLError):
        http.fetch('https://example.com/go')
    assert web.requested == ['https://example.com/go']


def test_fetch_refuses_redirect_to_other_scheme(fake_dns, fake_web):
    fake_dns['example.com'] = [PUBLIC_V4]
    fake_web({'https://example.com/go': (302, {'Location': 'file:///etc/passwd'}, b'')})
    with pytest.raises(UnsafeURLError):
        http.fetch('https://example.com/go')


def test_fetch_refuses_meta_refresh_to_private_address(fake_dns, fake_web):
    fake_dns['example.com'] = [PUBLIC_V4]
    web = fake_web({'https://example.com/share': (
        200, {'Content-Type': 'text/html'},
        b'<html><head><meta http-equiv="refresh" content="0;url=http://127.0.0.1:6379/"></head></html>')})
    with pytest.raises(UnsafeURLError):
        http.fetch('https://example.com/share')
    assert web.requested == ['https://example.com/share']


def test_fetch_refuses_private_url_without_requesting_it(fake_dns, fake_web):
    fake_dns['localhost.'] = ['127.0.0.1']
    web = fake_web({})
    with pytest.raises(UnsafeURLError):
        http.fetch('http://localhost.:8080/')
    assert web.requested == []


def test_too_many_redirects_is_a_fetch_error(fake_dns, fake_web):
    fake_dns['example.com'] = [PUBLIC_V4]
    fake_web({'https://example.com/loop': (302, {'Location': '/loop'}, b'')})
    with pytest.raises(FetchError):
        http.fetch('https://example.com/loop')


def test_fetch_bytes_returns_none_for_private_image(fake_web):
    web = fake_web({})
    assert http.fetch_bytes('http://169.254.169.254/latest/meta-data/iam/') is None
    assert web.requested == []


def test_fetch_bytes_returns_none_for_image_redirecting_to_private_address(fake_dns, fake_web):
    fake_dns['cdn.example.com'] = [PUBLIC_V4]
    web = fake_web({'https://cdn.example.com/a.png': (302, {'Location': 'http://10.0.0.5/secret.png'}, b'')})
    assert http.fetch_bytes('https://cdn.example.com/a.png') is None
    assert web.requested == ['https://cdn.example.com/a.png']


def test_fetch_bytes_public_image(fake_dns, fake_web):
    fake_dns['cdn.example.com'] = [PUBLIC_V4]
    fake_web({'https://cdn.example.com/a.png': (200, {'Content-Type': 'image/png'}, b'\x89PNG data')})
    assert http.fetch_bytes('https://cdn.example.com/a.png') == (b'\x89PNG data', 'image/png')


# --- browser impersonation (curl_cffi) -------------------------------------------------------

class FakeCurlResponse:
    def __init__(self, url, status, headers=None, content=b'', primary_ip=PUBLIC_V4):
        self.url = url
        self.status_code = status
        self.headers = CaseInsensitiveDict(headers or {})
        self.content = content
        self.primary_ip = primary_ip


@pytest.fixture
def fake_curl(monkeypatch):
    from curl_cffi import requests as cffi_requests
    calls = []

    def install(responses):
        def get(url, **kwargs):
            calls.append(url)
            assert kwargs.get('allow_redirects') is False
            return responses[url]
        monkeypatch.setattr(cffi_requests, 'get', get)
        return calls
    return install


def test_impersonated_fetch_refuses_redirect_to_private_address(fake_dns, fake_curl):
    fake_dns['example.com'] = [PUBLIC_V4]
    calls = fake_curl({'https://example.com/a': FakeCurlResponse(
        'https://example.com/a', 302, {'Location': 'http://[::1]:9000/'})})
    with pytest.raises(UnsafeURLError):
        http._fetch_impersonated('https://example.com/a')
    assert calls == ['https://example.com/a']


def test_impersonated_fetch_refuses_response_from_private_peer(fake_dns, fake_curl, monkeypatch):
    for name in ('http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
        monkeypatch.delenv(name, raising=False)
    fake_dns['example.com'] = [PUBLIC_V4]
    fake_curl({'https://example.com/a': FakeCurlResponse('https://example.com/a', 200, content=b'secret',
                                                          primary_ip='10.0.0.7')})
    with pytest.raises(UnsafeURLError):
        http._fetch_impersonated('https://example.com/a')


def test_impersonated_fetch_follows_public_redirect(fake_dns, fake_curl):
    fake_dns['example.com'] = [PUBLIC_V4]
    fake_curl({
        'https://example.com/a': FakeCurlResponse('https://example.com/a', 301, {'Location': '/b'}),
        'https://example.com/b': FakeCurlResponse('https://example.com/b', 200, {'Content-Type': 'text/html'},
                                                  ARTICLE),
    })
    result = http._fetch_impersonated('https://example.com/a')
    assert result.final_url == 'https://example.com/b'
    assert 'Public article' in result.html


def test_impersonated_image_to_private_address_returns_none(fake_curl):
    calls = fake_curl({})
    assert http._fetch_bytes_impersonated('http://192.168.1.1/a.png', http.MAX_IMAGE_BYTES) is None
    assert calls == []


# --- DNS rebinding ---------------------------------------------------------------------------

def test_connection_to_private_peer_is_refused_after_dns_rebinding(monkeypatch):
    """check_url sees a public address, but the connection lands on 127.0.0.1: nothing may be sent."""
    for name in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy',
                 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY'):
        monkeypatch.delenv(name, raising=False)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    received = []

    def serve():
        listener.settimeout(5)
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        conn.settimeout(1)
        try:
            received.append(conn.recv(1024))
        except OSError:
            pass
        finally:
            conn.close()

    server = threading.Thread(target=serve, daemon=True)
    server.start()

    lookups = []
    real_getaddrinfo = socket.getaddrinfo

    def rebinding_getaddrinfo(host, *args, **kwargs):
        if host != 'rebind.example.com':
            return real_getaddrinfo(host, *args, **kwargs)
        lookups.append(host)
        # First answer (seen by check_url) is public, later ones (seen by urllib3) point at loopback
        return addrinfo(PUBLIC_V4 if len(lookups) == 1 else '127.0.0.1', port=port)

    monkeypatch.setattr(socket, 'getaddrinfo', rebinding_getaddrinfo)
    monkeypatch.setattr(http, '_local', threading.local())  # fresh session with the guarded adapter
    http._session().trust_env = False  # never route this through a system proxy

    try:
        with pytest.raises(UnsafeURLError):
            http.fetch(f'http://rebind.example.com:{port}/')
    finally:
        listener.close()
        server.join(timeout=5)
    assert len(lookups) == 2
    assert received in ([], [b''])  # connected, but no request bytes were sent
