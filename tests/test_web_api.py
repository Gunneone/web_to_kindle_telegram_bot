#!/usr/bin/env python3
"""
Offline tests for the web app's API: signing in (email code, Google, Telegram), the account,
the book flow, ownership and the security rules. Scraping, EPUB building and mail are fakes; the
identity providers are a fake that signs ID tokens with a throwaway key.
"""

import logging
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

SRC = Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for scratch_db, however the tests are started

_DIR = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_DIR, 'users.db')}"

from core import accounts, db  # noqa: E402
from scratch_db import use_scratch_database  # noqa: E402
from web import auth_oidc, config, jobs  # noqa: E402
from web.app import create_app  # noqa: E402
from email_sender import EmailError  # noqa: E402
from web_scraper import Article, BlockedError  # noqa: E402

logging.getLogger('core.pipeline').setLevel(logging.CRITICAL)
logging.getLogger('web').setLevel(logging.CRITICAL)
logging.getLogger('httpx').setLevel(logging.WARNING)

ORIGIN = 'http://localhost:5173'
INLINE = "document.documentElement.setAttribute('data-theme','light')"


def make_dist() -> Path:
    dist = Path(tempfile.mkdtemp())
    (dist / 'assets').mkdir()
    (dist / 'assets' / 'app-abc.js').write_text('console.log(1)')
    (dist / 'favicon.svg').write_text('<svg/>')
    (dist / 'index.html').write_text(f'<!doctype html><script>{INLINE}</script><div id="root"></div>')
    return dist


def settings(**overrides) -> config.Settings:
    values = dict(public_url=ORIGIN, session_secret='test-secret', google=None, telegram=None,
                  dist_dir=make_dist(), mail='log', g1_ds_url='https://gunne.one/ds/v1')
    values.update(overrides)
    return config.Settings(**values)


PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8'
                    'cfc0f01f0005000201a0e1b2d90000000049454e44ae426082')


def make_epub(path: str) -> None:
    """A small EPUB laid out like the converter's, with a few things a preview must not pass on."""
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip')
        z.writestr('META-INF/container.xml',
                   '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
                   'version="1.0"><rootfiles><rootfile full-path="EPUB/content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr('EPUB/content.opf',
                   '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
                   '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
                   '<item id="style" href="style.css" media-type="text/css"/>'
                   '<item id="img" href="Images/img_001.png" media-type="image/png"/>'
                   '<item id="content" href="content.xhtml" media-type="application/xhtml+xml"/>'
                   '</manifest><spine><itemref idref="nav"/><itemref idref="content"/></spine></package>')
        z.writestr('EPUB/style.css', 'h1 { font-size: 1.4em; } /* </style><script>alert(1)</script> */')
        z.writestr('EPUB/nav.xhtml', '<html><body><nav>Table of contents</nav></body></html>')
        z.writestr('EPUB/content.xhtml',
                   '<html><head><link rel="stylesheet" href="style.css"/></head><body>'
                   '<h1>A Post</h1><p onclick="steal()">one two three</p>'
                   '<img src="Images/img_001.png" alt="dot"/><img src="https://tracker.example/pixel.gif"/>'
                   '<script>steal()</script><a href="javascript:steal()">bad</a>'
                   '<a href="https://e.com/source">source</a></body></html>')
        z.writestr('EPUB/Images/img_001.png', PNG)


@use_scratch_database
class ApiCase(unittest.TestCase):
    def setUp(self):
        with db.Session() as session:
            for model in (db.Identity, db.Article, db.User):
                session.query(model).delete()
            session.commit()
        jobs.LIVE.clear()  # article ids restart in every scratch database
        self.article = Article('https://e.com/post', 'A Post', 'Ann', '2026-11-01', '<p>one two three</p>')
        self.scrape_error = None
        self.mail_error = None
        self.mailed, self.codes, self.test_books = [], [], []
        self.epubs = 0
        self.real_epub = False
        patches = [
            patch('core.pipeline.get_website_content', self.fake_scrape),
            patch('core.pipeline.convert_to_epub', self.fake_epub),
            patch('core.pipeline.send_email', self.fake_mail),
            patch('web.auth_email.send_code', lambda s, email, code, token, lang: self.codes.append((email, code, token))),
            patch('web.routes_api.pipeline.email_article', self.fake_test_book),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def fake_mail(self, address, path):
        if self.mail_error:
            raise self.mail_error
        self.mailed.append((address, path))

    async def fake_test_book(self, article, address):
        self.test_books.append((article.Title, address))

    def fake_scrape(self, url):
        if self.scrape_error:
            raise self.scrape_error
        return self.article

    def fake_epub(self, article, image_links=False):
        self.epubs += 1
        path = os.path.join(_DIR, f'book-{time.monotonic_ns()}-{self.epubs}.epub')
        if self.real_epub:
            make_epub(path)
        else:
            Path(path).write_bytes(b'PK-fake-epub')
        return path

    def client(self, **overrides) -> TestClient:
        c = TestClient(create_app(settings(**overrides)), base_url=ORIGIN)
        c.__enter__()
        self.addCleanup(c.__exit__, None, None, None)
        return c

    def sign_in(self, client: TestClient, email='ann@example.com') -> dict:
        self.assertEqual(client.post('/api/auth/email/start', json={'email': email}).status_code, 204)
        _, code, _ = self.codes[-1]
        response = client.post('/api/auth/email/verify', json={'email': email, 'code': code})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['user']

    def wait_for(self, client, book_id, done=lambda b: b['status'] != 'processing'):
        for _ in range(100):
            book = client.get(f'/api/books/{book_id}').json()['book']
            if done(book):
                return book
            time.sleep(0.05)
        self.fail(f'book {book_id} never finished: {book}')


class SessionTest(ApiCase):
    def test_anonymous_session(self):
        body = self.client().get('/api/session').json()
        self.assertEqual(body, {'user': None, 'providers': {'google': False, 'telegram': False, 'email': True},
                                'feedback': False})

    def test_the_account_endpoints_need_a_sign_in(self):
        c = self.client()
        for method, path in (('get', '/api/books'), ('patch', '/api/me'), ('delete', '/api/me'),
                             ('post', '/api/books'), ('get', '/api/books/1/epub')):
            self.assertEqual(getattr(c, method)(path).status_code, 401, path)

    def test_email_code_sign_in_and_out(self):
        c = self.client()
        user = self.sign_in(c)
        self.assertEqual(user['email'], 'ann@example.com')
        self.assertEqual(user['name'], 'ann')
        self.assertEqual(c.get('/api/session').json()['user']['email'], 'ann@example.com')
        self.assertEqual(c.post('/api/auth/signout').status_code, 204)
        self.assertIsNone(c.get('/api/session').json()['user'])

    def test_wrong_code_then_right_code(self):
        c = self.client()
        c.post('/api/auth/email/start', json={'email': 'ann@example.com'})
        _, code, _ = self.codes[-1]
        wrong = '000000' if code != '000000' else '111111'
        r = c.post('/api/auth/email/verify', json={'email': 'ann@example.com', 'code': wrong})
        self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'WRONG_CODE'))
        self.assertEqual(c.post('/api/auth/email/verify', json={'email': 'ann@example.com', 'code': code}).status_code, 200)

    def test_a_code_works_once(self):
        c = self.client()
        self.sign_in(c)
        email, code, _ = self.codes[-1]
        r = c.post('/api/auth/email/verify', json={'email': email, 'code': code})
        self.assertEqual(r.json()['error']['code'], 'EXPIRED')

    def test_five_wrong_codes_burn_the_code(self):
        c = self.client()
        c.post('/api/auth/email/start', json={'email': 'ann@example.com'})
        _, code, _ = self.codes[-1]
        wrong = '000000' if code != '000000' else '111111'
        results = [c.post('/api/auth/email/verify', json={'email': 'ann@example.com', 'code': wrong}).json()['error']['code']
                   for _ in range(5)]
        self.assertEqual(results[-1], 'TOO_MANY_ATTEMPTS')
        r = c.post('/api/auth/email/verify', json={'email': 'ann@example.com', 'code': code})
        self.assertEqual(r.status_code, 400)

    def test_link_token_signs_in_once(self):
        c = self.client()
        c.post('/api/auth/email/start', json={'email': 'Ann@Example.com '})
        email, _, token = self.codes[-1]
        self.assertEqual(email, 'ann@example.com')
        self.assertEqual(c.post('/api/auth/email/verify', json={'token': token}).status_code, 200)
        self.assertEqual(c.post('/api/auth/email/verify', json={'token': token}).json()['error']['code'], 'EXPIRED')

    def test_new_code_replaces_the_old_one(self):
        c = self.client()
        c.post('/api/auth/email/start', json={'email': 'ann@example.com'})
        c.post('/api/auth/email/start', json={'email': 'ann@example.com'})
        (_, old, _), (_, new, _) = self.codes[-2:]
        if old != new:
            r = c.post('/api/auth/email/verify', json={'email': 'ann@example.com', 'code': old})
            self.assertEqual(r.status_code, 400)

    def test_mail_limits(self):
        c = self.client()
        statuses = [c.post('/api/auth/email/start', json={'email': 'ann@example.com'}).status_code for _ in range(4)]
        self.assertEqual(statuses, [204, 204, 204, 429])

    def test_invalid_email(self):
        c = self.client()
        for bad in ('nope', 'a@b', '', 'x' * 300 + '@example.com'):
            r = c.post('/api/auth/email/start', json={'email': bad})
            self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'INVALID_EMAIL'), bad)
        self.assertEqual(self.codes, [])

    def test_mutating_requests_from_other_origins_are_refused(self):
        c = self.client()
        r = c.post('/api/auth/email/start', json={'email': 'ann@example.com'}, headers={'Origin': 'https://evil.example'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.codes, [])
        ok = c.post('/api/auth/email/start', json={'email': 'ann@example.com'}, headers={'Origin': ORIGIN})
        self.assertEqual(ok.status_code, 204)

    def test_session_cookie_is_http_only_and_lax(self):
        c = self.client()
        c.post('/api/auth/email/start', json={'email': 'ann@example.com'})
        _, code, _ = self.codes[-1]
        r = c.post('/api/auth/email/verify', json={'email': 'ann@example.com', 'code': code})
        cookie = r.headers['set-cookie'].lower()
        self.assertIn('httponly', cookie)
        self.assertIn('samesite=lax', cookie)


class AccountTest(ApiCase):
    def test_kindle_address_is_validated_and_normalized(self):
        c = self.client()
        self.sign_in(c)
        r = c.patch('/api/me', json={'kindle_email': 'ann@gmail.com'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'INVALID_KINDLE_EMAIL'))
        r = c.patch('/api/me', json={'kindle_email': ' Ann_X1@Kindle.com '})
        self.assertEqual(r.json()['user']['kindle_email'], 'ann_x1@kindle.com')

    def test_changing_the_address_resets_the_check(self):
        c = self.client()
        self.sign_in(c)
        c.patch('/api/me', json={'kindle_email': 'ann@kindle.com'})
        self.assertTrue(c.post('/api/me/setup-verified').json()['user']['setup_verified'])
        same = c.patch('/api/me', json={'kindle_email': 'ann@kindle.com', 'image_links': True}).json()['user']
        self.assertTrue(same['setup_verified'])
        self.assertTrue(same['image_links'])
        changed = c.patch('/api/me', json={'kindle_email': 'other@kindle.com'}).json()['user']
        self.assertFalse(changed['setup_verified'])
        cleared = c.patch('/api/me', json={'kindle_email': ''}).json()['user']
        self.assertIsNone(cleared['kindle_email'])

    def test_language(self):
        c = self.client()
        self.sign_in(c)
        self.assertEqual(c.patch('/api/me', json={'language': 'de'}).json()['user']['language'], 'de')
        self.assertEqual(c.patch('/api/me', json={'language': 'fr'}).status_code, 400)

    def test_test_book(self):
        c = self.client()
        self.sign_in(c)
        self.assertEqual(c.post('/api/me/test-book').json()['error']['code'], 'NO_KINDLE')
        c.patch('/api/me', json={'kindle_email': 'ann@kindle.com', 'language': 'de'})
        self.assertEqual(c.post('/api/me/test-book').status_code, 204)
        self.assertEqual(self.test_books, [('Deine Kindle-Einrichtung funktioniert!', 'ann@kindle.com')])
        for _ in range(2):
            c.post('/api/me/test-book')
        self.assertEqual(c.post('/api/me/test-book').status_code, 429)

    def test_deleting_the_account(self):
        c = self.client()
        self.sign_in(c)
        c.patch('/api/me', json={'kindle_email': 'ann@kindle.com'})
        self.assertEqual(c.delete('/api/me').status_code, 204)
        self.assertIsNone(c.get('/api/session').json()['user'])
        self.assertIsNone(db.get_user(-1))
        self.assertEqual(accounts.identities(-1), [])
        # signing in again starts from scratch
        self.assertIsNone(self.sign_in(c)['kindle_email'])


class BookTest(ApiCase):
    def signed_in(self, kindle=True) -> TestClient:
        c = self.client()
        self.sign_in(c)
        if kindle:
            c.patch('/api/me', json={'kindle_email': 'ann@kindle.com'})
        return c

    def test_download_flow(self):
        c = self.signed_in()
        r = c.post('/api/books', json={'url': 'e.com/post', 'target': 'download'})
        self.assertEqual(r.status_code, 202, r.text)
        book = self.wait_for(c, r.json()['book']['id'])
        self.assertEqual((book['status'], book['delivered'], book['title'], book['host']),
                         ('sent', ['download'], 'A Post', 'e.com'))
        self.assertEqual(book['minutes'], 1)
        self.assertTrue(book['can_download'])
        self.assertEqual(self.mailed, [])
        epub = c.get(f"/api/books/{book['id']}/epub")
        self.assertEqual((epub.status_code, epub.content), (200, b'PK-fake-epub'))
        self.assertEqual(epub.headers['content-type'], 'application/epub+zip')
        self.assertIn('A-Post.epub', epub.headers['content-disposition'])
        listing = c.get('/api/books').json()
        self.assertEqual((listing['total'], listing['books'][0]['id']), (1, book['id']))

    def test_kindle_delivery(self):
        c = self.signed_in()
        r = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'kindle'})
        book = self.wait_for(c, r.json()['book']['id'])
        self.assertEqual((book['status'], book['delivered']), ('sent', ['kindle']))
        self.assertEqual([address for address, _ in self.mailed], ['ann@kindle.com'])

    def test_kindle_needs_an_address(self):
        c = self.signed_in(kindle=False)
        r = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'kindle'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'NO_KINDLE'))

    def test_bad_requests(self):
        c = self.signed_in()
        for url in ('', 'not a url', 'ftp://e.com/x', 'https://nodot', 'https://e.com/' + 'a' * 2100):
            r = c.post('/api/books', json={'url': url, 'target': 'download'})
            self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'INVALID_URL'), url[:30])
        r = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'carrier-pigeon'})
        self.assertEqual(r.json()['error']['code'], 'INVALID_TARGET')

    def test_duplicates_are_reported_and_can_be_forced(self):
        c = self.signed_in()
        first = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'download'}).json()['book']
        self.wait_for(c, first['id'])
        r = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'kindle'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'DUPLICATE'))
        self.assertEqual(r.json()['error']['book']['id'], first['id'])
        forced = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'kindle', 'force': True})
        self.assertEqual(forced.status_code, 202)
        self.assertNotEqual(forced.json()['book']['id'], first['id'])

    def test_resend_reuses_the_book(self):
        c = self.signed_in()
        book = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'download'}).json()['book']
        self.wait_for(c, book['id'])
        epubs_before = self.epubs
        r = c.post(f"/api/books/{book['id']}/send", json={'target': 'kindle'})
        self.assertEqual(r.status_code, 202)
        done = self.wait_for(c, book['id'], lambda b: b['status'] != 'processing' and b['delivered'])
        self.assertEqual(done['delivered'], ['kindle'])
        self.assertEqual(self.epubs, epubs_before)
        self.assertEqual(len(self.mailed), 1)

    def test_failures_say_what_went_wrong(self):
        c = self.signed_in()
        self.scrape_error = BlockedError('example.com refused the request (HTTP 403)')
        book = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'download'}).json()['book']
        done = self.wait_for(c, book['id'])
        self.assertEqual((done['status'], done['failure'], done['can_download']), ('failed', 'blocked', False))
        self.assertIn('403', done['detail'])
        self.assertEqual(c.get(f"/api/books/{book['id']}/epub").status_code, 404)

    def test_a_book_whose_mail_failed_can_still_be_downloaded(self):
        c = self.signed_in()
        self.mail_error = EmailError('Failed to send email: refused')
        book = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'kindle'}).json()['book']
        done = self.wait_for(c, book['id'])
        self.assertEqual((done['status'], done['failure'], done['can_download']), ('failed', 'email', True))
        self.assertIsNone(done['detail'])  # mail server details stay on the server
        self.assertEqual(c.get(f"/api/books/{book['id']}/epub").content, b'PK-fake-epub')

    def test_retry_after_a_failure(self):
        c = self.signed_in()
        self.scrape_error = BlockedError('refused')
        book = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'download'}).json()['book']
        self.wait_for(c, book['id'])
        self.scrape_error = None
        c.post(f"/api/books/{book['id']}/send", json={'target': 'download'})
        done = self.wait_for(c, book['id'], lambda b: b['status'] == 'sent')
        self.assertEqual(done['delivered'], ['download'])

    def test_a_server_restart_shows_unfinished_books_as_interrupted(self):
        c = self.signed_in()
        user = db.get_user(-1)
        article = db.create_article(user.user_id, 'https://e.com/lost')
        book = c.get(f'/api/books/{article.id}').json()['book']
        self.assertEqual(book['status'], 'interrupted')

    def test_other_peoples_books_are_off_limits(self):
        owner = self.signed_in()
        book = owner.post('/api/books', json={'url': 'https://e.com/post', 'target': 'download'}).json()['book']
        self.wait_for(owner, book['id'])
        other = self.client()
        self.sign_in(other, 'bob@example.com')
        self.assertEqual(other.get(f"/api/books/{book['id']}").status_code, 404)
        self.assertEqual(other.get(f"/api/books/{book['id']}/epub").status_code, 404)
        self.assertEqual(other.post(f"/api/books/{book['id']}/send", json={'target': 'download'}).status_code, 404)
        self.assertEqual(other.get('/api/books').json()['total'], 0)

    def test_files_removed_by_the_disk_monitor_are_gone(self):
        c = self.signed_in()
        book = c.post('/api/books', json={'url': 'https://e.com/post', 'target': 'download'}).json()['book']
        self.wait_for(c, book['id'])
        os.remove(db.get_article(book['id']).epub_path)
        self.assertEqual(c.get(f"/api/books/{book['id']}/epub").status_code, 410)
        self.assertFalse(c.get(f"/api/books/{book['id']}").json()['book']['can_download'])

    def test_history_pages(self):
        c = self.signed_in()
        user = db.get_user(-1)
        for i in range(25):
            db.update_article(db.create_article(user.user_id, f'https://e.com/{i}').id, status=db.SENT)
        first = c.get('/api/books?limit=20').json()
        second = c.get('/api/books?offset=20&limit=20').json()
        self.assertEqual((first['total'], len(first['books']), len(second['books'])), (25, 20, 5))


class PreviewTest(BookTest):
    def built(self, c) -> dict:
        r = c.post('/api/books', json={'url': 'https://e.com/post'})
        self.assertEqual(r.status_code, 202, r.text)
        return self.wait_for(c, r.json()['book']['id'])

    def test_a_book_is_built_first_and_sent_after_a_look(self):
        c = self.signed_in()
        book = self.built(c)
        self.assertEqual((book['status'], book['delivered'], book['can_download']), ('ready', [], True))
        self.assertEqual(self.mailed, [])
        self.assertEqual(c.get(f"/api/books/{book['id']}").json()['book']['status'], 'ready')
        self.assertEqual(c.get(f"/api/books/{book['id']}/epub").status_code, 200)
        # a ready book isn't "already sent", so making it again needs no confirmation
        again = c.post('/api/books', json={'url': 'https://e.com/post'})
        self.assertEqual(again.status_code, 202)

        c.post(f"/api/books/{book['id']}/send", json={'target': 'kindle'})
        done = self.wait_for(c, book['id'], lambda b: b['status'] == 'sent')
        self.assertEqual(done['delivered'], ['kindle'])
        self.assertEqual(self.epubs, 2)  # the send reused the first build
        self.assertEqual(len(self.mailed), 1)

    def test_a_failed_build_can_be_retried_without_delivering(self):
        c = self.signed_in()
        self.scrape_error = BlockedError('refused')
        book = self.built(c)
        self.assertEqual(book['status'], 'failed')
        self.scrape_error = None
        self.assertEqual(c.post(f"/api/books/{book['id']}/send", json={}).status_code, 202)
        done = self.wait_for(c, book['id'], lambda b: b['status'] == 'ready')
        self.assertEqual(done['delivered'], [])
        self.assertEqual(self.mailed, [])

    def test_a_build_without_a_kindle_address(self):
        c = self.signed_in(kindle=False)
        self.assertEqual(self.built(c)['status'], 'ready')

    def test_paywalled_flag(self):
        self.article.Is_Preview = True
        c = self.signed_in()
        self.assertTrue(self.built(c)['paywalled'])

    def test_preview_is_a_self_contained_sandboxed_page(self):
        self.real_epub = True
        c = self.signed_in()
        book = self.built(c)
        r = c.get(f"/api/books/{book['id']}/preview")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.headers['content-type'].startswith('text/html'))
        csp = r.headers['content-security-policy']
        self.assertIn("default-src 'none'", csp)
        self.assertIn("frame-ancestors 'self'", csp)
        self.assertNotIn('script-src', csp)
        self.assertEqual(r.headers['cache-control'], 'private, no-store')
        page = r.text
        self.assertIn('<h1>A Post</h1>', page)
        self.assertIn('one two three', page)
        self.assertIn('src="data:image/png;base64,', page)
        self.assertIn('font-size: 1.4em', page)
        self.assertNotIn('Table of contents', page)  # the nav document is skipped
        body = page.split('<body>', 1)[1]
        for bad in ('<script', 'onclick', 'javascript:', 'tracker.example'):
            self.assertNotIn(bad, body.lower(), bad)
        self.assertEqual(page.count('</style>'), 2)  # the book's style sheet can't close its element early
        self.assertIn('href="https://e.com/source"', page)
        self.assertIn('target="_blank"', page)

    def test_preview_needs_a_built_book_of_ones_own(self):
        self.real_epub = True
        c = self.signed_in()
        book = self.built(c)
        other = self.client()
        self.sign_in(other, 'bob@example.com')
        self.assertEqual(other.get(f"/api/books/{book['id']}/preview").status_code, 404)
        user = db.get_user(-1)
        unfinished = db.create_article(user.user_id, 'https://e.com/lost')
        self.assertEqual(c.get(f'/api/books/{unfinished.id}/preview').status_code, 404)
        os.remove(db.get_article(book['id']).epub_path)
        self.assertEqual(c.get(f"/api/books/{book['id']}/preview").status_code, 410)

    def test_an_unreadable_book_fails_cleanly(self):
        c = self.signed_in()
        book = self.built(c)  # the fake, not a zip
        r = c.get(f"/api/books/{book['id']}/preview")
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'PREVIEW_FAILED'))


class FeedbackTest(BookTest):
    def setUp(self):
        super().setUp()
        self.reports = []
        self.feedback_error = None

        async def fake_send(settings, user, article, reasons, message, filename):
            if self.feedback_error:
                raise self.feedback_error
            self.reports.append((settings.admin_id, user.user_id, article.id, reasons, message, filename))

        p = patch('web.routes_api.feedback.send', fake_send)
        p.start()
        self.addCleanup(p.stop)

    def configured(self):
        c = self.client(telegram_token='123:abc', admin_id='42')
        self.sign_in(c)
        book = c.post('/api/books', json={'url': 'https://e.com/post'}).json()['book']
        return c, self.wait_for(c, book['id'])

    def test_session_says_whether_feedback_works(self):
        self.assertFalse(self.client().get('/api/session').json()['feedback'])
        self.assertTrue(self.client(telegram_token='1:a', admin_id='42').get('/api/session').json()['feedback'])

    def test_feedback_reaches_the_admin(self):
        c, book = self.configured()
        r = c.post(f"/api/books/{book['id']}/feedback",
                   json={'reasons': ['other', 'images'], 'message': '  The photos are gone  '})
        self.assertEqual(r.status_code, 204, r.text)
        self.assertEqual(self.reports, [('42', -1, book['id'], ['images', 'other'], 'The photos are gone',
                                         'A-Post.epub')])

    def test_feedback_needs_something_to_say(self):
        c, book = self.configured()
        for body in ({}, {'reasons': [], 'message': '   '}, {'reasons': ['nonsense']},
                     {'message': 'x' * 1001}):
            r = c.post(f"/api/books/{book['id']}/feedback", json=body)
            self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'INVALID_REQUEST'), body)
        self.assertEqual(self.reports, [])

    def test_feedback_is_limited(self):
        c, book = self.configured()
        statuses = [c.post(f"/api/books/{book['id']}/feedback", json={'reasons': ['text']}).status_code
                    for _ in range(6)]
        self.assertEqual(statuses, [204] * 5 + [429])

    def test_feedback_without_an_admin(self):
        c = self.signed_in()
        book = self.wait_for(c, c.post('/api/books', json={'url': 'https://e.com/post'}).json()['book']['id'])
        r = c.post(f"/api/books/{book['id']}/feedback", json={'reasons': ['text']})
        self.assertEqual((r.status_code, r.json()['error']['code']), (503, 'FEEDBACK_UNAVAILABLE'))

    def test_telegram_refusing_the_report(self):
        from web.feedback import FeedbackError
        c, book = self.configured()
        self.feedback_error = FeedbackError('chat not found')
        r = c.post(f"/api/books/{book['id']}/feedback", json={'reasons': ['text']})
        self.assertEqual((r.status_code, r.json()['error']['code']), (502, 'FEEDBACK_FAILED'))

    def test_feedback_only_on_ones_own_books(self):
        c, book = self.configured()
        other = self.client(telegram_token='123:abc', admin_id='42')
        self.sign_in(other, 'bob@example.com')
        r = other.post(f"/api/books/{book['id']}/feedback", json={'reasons': ['text']})
        self.assertEqual(r.status_code, 404)

    def test_the_admin_report(self):
        from web import feedback
        user = db.get_user(self.sign_in(self.client()) and -1)
        article = db.update_article(db.create_article(user.user_id, 'https://e.com/post?a=1&b=2').id,
                                    title='<Bold> & co')
        text = feedback.report_text(user, article, ['images'], 'It <broke>')
        self.assertIn('&lt;Bold&gt; &amp; co', text)
        self.assertIn('href="https://e.com/post?a=1&amp;b=2"', text)
        self.assertIn('Images missing or broken', text)
        self.assertIn('<blockquote expandable>It &lt;broke&gt;</blockquote>', text)
        self.assertIn('ann@example.com', text)
        self.assertIn('email', text)


class FeedbackSenderTest(ApiCase):
    """The real `feedback.send`, with a fake Telegram bot."""

    def test_the_report_goes_out_as_a_message_and_the_book(self):
        import asyncio
        from telegram.error import NetworkError
        from web import feedback
        calls, fail = [], {}

        class FakeBot:
            def __init__(self, token):
                calls.append(('token', token))

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def send_message(self, chat_id, text, **kwargs):
                if 'message' in fail:
                    raise fail['message']
                calls.append(('message', chat_id, kwargs['parse_mode']))
                return type('Sent', (), {'message_id': 7})()

            async def send_document(self, chat_id, file, filename, reply_parameters, **kwargs):
                if 'document' in fail:
                    raise fail['document']
                calls.append(('document', chat_id, filename, file.read(), reply_parameters.message_id))

        user = db.get_user(self.sign_in(self.client()) and -1)
        path = os.path.join(_DIR, 'feedback.epub')
        Path(path).write_bytes(b'PK-book')
        article = db.update_article(db.create_article(user.user_id, 'https://e.com/post').id, title='T', epub_path=path)
        conf = settings(telegram_token='1:a', admin_id='42')
        with patch('web.feedback.Bot', FakeBot):
            asyncio.run(feedback.send(conf, user, article, ['text'], '', 'T.epub'))
            self.assertEqual(calls, [('token', '1:a'), ('message', '42', 'HTML'),
                                     ('document', '42', 'T.epub', b'PK-book', 7)])
            fail['document'] = NetworkError('upload timed out')
            asyncio.run(feedback.send(conf, user, article, ['text'], '', 'T.epub'))  # the report itself arrived
            fail['message'] = NetworkError('no connection')
            with self.assertRaises(feedback.FeedbackError):
                asyncio.run(feedback.send(conf, user, article, ['text'], '', 'T.epub'))


class ClientFilesTest(ApiCase):
    def test_unknown_paths_serve_the_app(self):
        c = self.client()
        r = c.get('/history')
        self.assertEqual(r.status_code, 200)
        self.assertIn('id="root"', r.text)
        self.assertEqual(r.headers['cache-control'], 'no-cache')

    def test_head_requests_work_for_health_checks(self):
        c = self.client()
        self.assertEqual(c.head('/').status_code, 200)
        self.assertEqual(c.head('/settings').status_code, 200)

    def test_assets_are_cached_forever_and_files_are_served(self):
        c = self.client()
        r = c.get('/assets/app-abc.js')
        self.assertIn('immutable', r.headers['cache-control'])
        self.assertEqual(c.get('/favicon.svg').text, '<svg/>')

    def test_nothing_outside_the_build_is_served(self):
        c = self.client()
        for path in ('/..%2f..%2fusers.db', '/%2e%2e/%2e%2e/etc/passwd', '/assets/../../users.db'):
            r = c.get(path)
            self.assertNotIn('root:', r.text)
            self.assertNotIn('SQLite', r.text)

    def test_unknown_api_paths_are_json_404s(self):
        r = self.client().get('/api/nope')
        self.assertEqual((r.status_code, r.json()), (404, {'error': {'code': 'NOT_FOUND'}}))

    def test_security_headers_allow_the_inline_theme_snippet_and_the_design_system(self):
        r = self.client().get('/')
        csp = r.headers['content-security-policy']
        self.assertIn("script-src 'self' https://gunne.one 'sha256-", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertEqual(r.headers['x-content-type-options'], 'nosniff')

    def test_missing_build(self):
        c = self.client(dist_dir=Path(tempfile.mkdtemp()) / 'nothing')
        self.assertEqual(c.get('/').status_code, 503)
        self.assertEqual(c.get('/api/session').status_code, 200)


KEY = RSAKey.generate_key(2048, {'kid': 'test-key'})
OTHER_KEY = RSAKey.generate_key(2048, {'kid': 'test-key'})
GOOGLE = config.OidcClient('google-id', 'google-secret')
TELEGRAM = config.OidcClient('12345', 'telegram-secret')
ISSUERS = {'google': 'https://accounts.google.com', 'telegram': 'https://oauth.telegram.org'}


class FakeProviders:
    """Google's and Telegram's OpenID endpoints, answering from memory."""

    def __init__(self):
        self.claims: dict = {}
        self.signing_key = KEY
        self.token_requests: list[httpx.Request] = []
        self.token_status = 200

    def id_token(self, provider, **overrides):
        client = {'google': GOOGLE, 'telegram': TELEGRAM}[provider]
        claims = {'iss': ISSUERS[provider], 'aud': client.client_id, 'exp': int(time.time()) + 600,
                  'iat': int(time.time()), **self.claims, **overrides}
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode({'alg': 'RS256', 'kid': 'test-key'}, claims, self.signing_key)

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for name, issuer in ISSUERS.items():
            if url.endswith('/.well-known/openid-configuration') and issuer.split('//')[1] in url:
                return httpx.Response(200, json={
                    'issuer': issuer, 'authorization_endpoint': f'{issuer}/auth', 'token_endpoint': f'{issuer}/token',
                    'jwks_uri': f'{issuer}/jwks'})
            if url == f'{issuer}/jwks':
                return httpx.Response(200, json=KeySet([KEY]).as_dict(private=False))
            if url == f'{issuer}/token':
                self.token_requests.append(request)
                form = parse_qs(request.content.decode())
                if self.token_status != 200 or not form.get('code_verifier'):
                    return httpx.Response(400, json={'error': 'invalid_grant'})
                return httpx.Response(200, json={'id_token': self.id_token(name), 'access_token': 'x', 'token_type': 'Bearer'})
        return httpx.Response(404)


class OidcTest(ApiCase):
    def setUp(self):
        super().setUp()
        self.providers = FakeProviders()

    def oidc_client(self) -> TestClient:
        c = self.client(google=GOOGLE, telegram=TELEGRAM)
        c.app.state.eselsohr.oidc.http = httpx.AsyncClient(transport=httpx.MockTransport(self.providers.handler))
        return c

    def begin(self, c, provider, next_path='/') -> str:
        r = c.get(f'/api/auth/{provider}/start', params={'next': next_path}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        return r.headers['location']

    def callback(self, c, provider, location, **extra):
        query = parse_qs(urlparse(location).query)
        params = {'code': 'the-code', 'state': query['state'][0], **extra}
        return c.get(f'/api/auth/{provider}/callback', params=params, follow_redirects=False)

    def test_authorization_request_uses_pkce_and_state(self):
        c = self.oidc_client()
        location = self.begin(c, 'google')
        query = parse_qs(urlparse(location).query)
        self.assertTrue(location.startswith('https://accounts.google.com/auth?'))
        self.assertEqual(query['client_id'], ['google-id'])
        self.assertEqual(query['redirect_uri'], [f'{ORIGIN}/api/auth/google/callback'])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(query['scope'], ['openid email profile'])
        self.assertTrue(query['state'][0] and query['code_challenge'][0] and query['nonce'][0])

    def test_google_sign_in(self):
        self.providers.claims = {'sub': 'g-1', 'email': 'Ann@Example.com', 'email_verified': True,
                                 'given_name': 'Ann', 'family_name': 'Lee'}
        c = self.oidc_client()
        r = self.callback(c, 'google', self.begin(c, 'google', '/history'))
        self.assertEqual((r.status_code, r.headers['location']), (303, '/history'))
        user = c.get('/api/session').json()['user']
        self.assertEqual((user['name'], user['email'], user['providers']), ('Ann', 'ann@example.com', ['google']))
        basic = self.providers.token_requests[0].headers['authorization']
        self.assertTrue(basic.startswith('Basic '))

    def test_google_and_email_with_the_same_address_are_one_account(self):
        c = self.client()
        self.sign_in(c, 'ann@example.com')
        c.post('/api/auth/signout')
        self.providers.claims = {'sub': 'g-1', 'email': 'ann@example.com', 'email_verified': True}
        c = self.oidc_client()
        self.callback(c, 'google', self.begin(c, 'google'))
        self.assertEqual(sorted(c.get('/api/session').json()['user']['providers']), ['email', 'google'])

    def test_unverified_google_addresses_are_refused(self):
        self.providers.claims = {'sub': 'g-1', 'email': 'ann@example.com', 'email_verified': False}
        c = self.oidc_client()
        r = self.callback(c, 'google', self.begin(c, 'google'))
        self.assertEqual(r.headers['location'], '/signin?error=EMAIL_UNVERIFIED')
        self.assertIsNone(c.get('/api/session').json()['user'])

    def test_telegram_sign_in_reaches_the_bots_account(self):
        db.upsert_user(4242, username='ann')
        db.update_user(4242, kindle_email='ann@kindle.com')
        self.providers.claims = {'sub': 'whatever', 'id': 4242, 'name': 'Ann Lee', 'preferred_username': 'ann'}
        c = self.oidc_client()
        self.callback(c, 'telegram', self.begin(c, 'telegram'))
        user = c.get('/api/session').json()['user']
        self.assertEqual((user['kindle_email'], user['name'], user['providers']), ('ann@kindle.com', 'Ann', ['telegram']))

    def test_telegram_is_connected_to_a_signed_in_web_account(self):
        c = self.oidc_client()
        self.sign_in(c)
        c.patch('/api/me', json={'kindle_email': 'ann@kindle.com'})
        self.providers.claims = {'sub': '777', 'id': '777', 'name': 'Ann'}
        r = self.callback(c, 'telegram', self.begin(c, 'telegram', '/settings'))
        self.assertEqual(r.headers['location'], '/settings')
        user = c.get('/api/session').json()['user']
        self.assertEqual((user['kindle_email'], sorted(user['providers'])), ('ann@kindle.com', ['email', 'telegram']))
        self.assertIsNone(db.get_user(-1))
        self.assertEqual(db.get_user(777).kindle_email, 'ann@kindle.com')

    def test_connecting_a_second_telegram_account_is_refused(self):
        c = self.oidc_client()
        self.providers.claims = {'sub': '1', 'id': '1', 'name': 'Ann'}
        self.callback(c, 'telegram', self.begin(c, 'telegram'))
        self.providers.claims = {'sub': '2', 'id': '2', 'name': 'Bob'}
        r = self.callback(c, 'telegram', self.begin(c, 'telegram'))
        self.assertEqual(r.headers['location'], '/settings?error=LINK_CONFLICT')
        self.assertEqual(c.get('/api/session').json()['user']['name'], 'Ann')

    def test_tokens_must_be_signed_by_the_provider(self):
        self.providers.claims = {'sub': 'g-1', 'email': 'ann@example.com', 'email_verified': True}
        self.providers.signing_key = OTHER_KEY
        c = self.oidc_client()
        r = self.callback(c, 'google', self.begin(c, 'google'))
        self.assertEqual(r.headers['location'], '/signin?error=INVALID_TOKEN')

    def test_tokens_must_be_for_this_app_and_unexpired(self):
        c = self.oidc_client()
        for overrides in ({'aud': 'someone-else'}, {'iss': 'https://evil.example'}, {'exp': int(time.time()) - 3600}):
            self.providers.claims = {'sub': 'g-1', 'email': 'ann@example.com', 'email_verified': True, **overrides}
            r = self.callback(c, 'google', self.begin(c, 'google'))
            self.assertEqual(r.headers['location'], '/signin?error=INVALID_TOKEN', overrides)

    def test_a_wrong_nonce_is_refused_but_a_missing_one_is_tolerated(self):
        c = self.oidc_client()
        self.providers.claims = {'sub': 'g-1', 'email': 'ann@example.com', 'email_verified': True, 'nonce': 'forged'}
        r = self.callback(c, 'google', self.begin(c, 'google'))
        self.assertEqual(r.headers['location'], '/signin?error=INVALID_TOKEN')
        self.providers.claims = {'sub': 'g-1', 'email': 'ann@example.com', 'email_verified': True}
        r = self.callback(c, 'google', self.begin(c, 'google'))
        self.assertEqual(r.headers['location'], '/')

    def test_state_must_match_and_is_single_use(self):
        self.providers.claims = {'sub': 'g-1', 'email': 'ann@example.com', 'email_verified': True}
        c = self.oidc_client()
        location = self.begin(c, 'google')
        forged = c.get('/api/auth/google/callback', params={'code': 'x', 'state': 'forged'}, follow_redirects=False)
        self.assertEqual(forged.headers['location'], '/signin?error=SESSION_EXPIRED')
        first = self.callback(c, 'google', location)
        self.assertEqual(first.headers['location'], '/')
        c.post('/api/auth/signout')
        replay = self.callback(c, 'google', location)
        self.assertEqual(replay.headers['location'], '/signin?error=SESSION_EXPIRED')

    def test_the_provider_denying_access(self):
        c = self.oidc_client()
        location = self.begin(c, 'google')
        state = parse_qs(urlparse(location).query)['state'][0]
        r = c.get('/api/auth/google/callback', params={'error': 'access_denied', 'state': state}, follow_redirects=False)
        self.assertEqual(r.headers['location'], '/signin?error=ACCESS_DENIED')

    def test_a_failing_token_exchange(self):
        self.providers.token_status = 500
        c = self.oidc_client()
        r = self.callback(c, 'google', self.begin(c, 'google'))
        self.assertEqual(r.headers['location'], '/signin?error=PROVIDER_ERROR')

    def test_unconfigured_providers(self):
        c = self.client()
        r = c.get('/api/auth/google/start', follow_redirects=False)
        self.assertEqual(r.headers['location'], '/signin?error=PROVIDER_UNAVAILABLE')
        r = c.get('/api/auth/github/start', follow_redirects=False)
        self.assertEqual(r.headers['location'], '/signin?error=PROVIDER_UNAVAILABLE')

    def test_next_must_stay_on_the_site(self):
        for bad in ('//evil.example', 'https://evil.example', '/\\evil.example', '', None):
            self.assertEqual(auth_oidc.safe_next(bad), '/', bad)
        self.assertEqual(auth_oidc.safe_next('/settings?x=1'), '/settings?x=1')


if __name__ == '__main__':
    unittest.main()
