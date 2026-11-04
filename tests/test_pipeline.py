#!/usr/bin/env python3
"""
Offline tests for core.pipeline, the delivery service every front end shares: progress stages,
history entries, the "already sent" check, EPUB reuse, file size limits and failures.
Scraping, EPUB building and email are fakes; the database is a scratch SQLite file.
"""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(SRC))

# The database module connects on import; point it at a scratch file first
_DB_DIR = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_DB_DIR, 'users.db')}"

from core import db, pipeline  # noqa: E402
from core.pipeline import Failure, Stage  # noqa: E402
from email_sender import EmailError  # noqa: E402
from web_scraper import Article, BlockedError, ExtractionError, FetchError  # noqa: E402

logging.getLogger('core.pipeline').setLevel(logging.CRITICAL)  # the failures below are expected


class FakeFrontend(pipeline.Frontend):
    def __init__(self, max_file_bytes=None, fail_file=False):
        self.max_file_bytes = max_file_bytes
        self.fail_file = fail_file
        self.stages = []
        self.files = []  # what deliver_file got: (article id, targets delivered before it)

    async def stage(self, stage, article):
        self.stages.append(stage)

    async def deliver_file(self, article, book, delivered):
        if self.fail_file:
            raise RuntimeError('upload failed')
        self.files.append((article.id, delivered))


class PipelineTest(unittest.IsolatedAsyncioTestCase):
    last_user_id = 1000

    @classmethod
    def setUpClass(cls):
        db.init_db()

    def setUp(self):
        PipelineTest.last_user_id += 1
        db.upsert_user(self.last_user_id, first_name='Ann')
        self.user = db.update_user(self.last_user_id, kindle_email='ann@kindle.com', delivery_mode=db.KINDLE)
        self.article = Article('https://e.com/post', 'A Post', 'Ann', '2026-11-01',
                               '<p>one two three</p>', publication='The Paper')
        self.scrape_error = None
        self.mail_error = None
        self.scraped, self.mailed = [], []
        for name, fake in (('get_website_content', self.fake_scrape), ('convert_to_epub', self.fake_epub),
                           ('send_email', self.fake_mail)):
            patcher = patch(f'core.pipeline.{name}', fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_scrape(self, url):
        self.scraped.append(url)
        if self.scrape_error:
            raise self.scrape_error
        return self.article

    def fake_epub(self, article, image_links=False):
        path = os.path.join(_DB_DIR, f'{self.last_user_id}-{len(self.scraped)}.epub')
        Path(path).write_bytes(b'x' * 1000)
        return path

    def fake_mail(self, address, path):
        if self.mail_error:
            raise self.mail_error
        self.mailed.append((address, path))

    async def test_kindle_delivery(self):
        frontend = FakeFrontend()
        outcome = await pipeline.run(self.user, 'https://e.com/post', frontend)

        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.delivered, {db.KINDLE})
        self.assertEqual(frontend.stages, [Stage.RECEIVED, Stage.FETCHING, Stage.BUILDING, Stage.SENDING])
        self.assertEqual(frontend.files, [])
        self.assertEqual(self.mailed, [('ann@kindle.com', outcome.book.epub_path)])
        self.assertEqual((outcome.book.title, outcome.book.author, outcome.book.publication, outcome.book.words),
                         ('A Post', 'Ann', 'The Paper', 3))
        self.assertEqual(outcome.book.read_minutes, 1)
        self.assertEqual(outcome.book.size, 1000)
        article = db.get_article(outcome.article_id)
        self.assertEqual((article.status, article.title, article.epub_path),
                         (db.SENT, 'A Post', outcome.book.epub_path))
        self.assertIsNotNone(db.get_user(self.user.user_id).last_book_received_date)

    async def test_file_target_gets_what_was_already_delivered(self):
        user = db.update_user(self.user.user_id, delivery_mode=db.BOTH)
        frontend = FakeFrontend()
        outcome = await pipeline.run(user, 'https://e.com/post', frontend)
        self.assertEqual(outcome.delivered, {db.KINDLE, db.TELEGRAM})
        self.assertEqual(frontend.files, [(outcome.article_id, {db.KINDLE})])

    async def test_paywalled_preview(self):
        self.article.Is_Preview = True
        outcome = await pipeline.run(self.user, 'https://e.com/post', FakeFrontend())
        self.assertTrue(outcome.book.is_preview)
        self.assertEqual(db.get_article(outcome.article_id).status, db.PREVIEW)

    async def test_build_only_then_send(self):
        self.article.Is_Preview = True
        frontend = FakeFrontend()
        built = await pipeline.run(self.user, 'https://e.com/post', frontend, targets=set())
        self.assertEqual((built.delivered, built.failure), (set(), None))
        self.assertFalse(built.ok)
        self.assertEqual(frontend.stages, [Stage.RECEIVED, Stage.FETCHING, Stage.BUILDING])
        self.assertEqual(self.mailed, [])
        article = db.get_article(built.article_id)
        self.assertEqual((article.status, article.paywalled, article.error), (db.READY, 1, None))
        self.assertIsNone(db.recent_delivery(self.user.user_id, 'https://e.com/post'))  # not delivered yet

        sent = await pipeline.run(self.user, 'https://e.com/post', FakeFrontend(), targets={db.KINDLE},
                                  article_id=built.article_id, force=True)
        self.assertEqual(sent.delivered, {db.KINDLE})
        self.assertEqual(sent.book.epub_path, built.book.epub_path)
        self.assertTrue(sent.book.is_preview)  # the paywall note survives the reuse
        self.assertEqual(len(self.scraped), 1)
        self.assertEqual(db.get_article(built.article_id).status, db.PREVIEW)

    async def test_duplicate_is_not_sent_again_unless_forced(self):
        first = await pipeline.run(self.user, 'https://e.com/post', FakeFrontend())
        frontend = FakeFrontend()
        again = await pipeline.run(self.user, 'https://e.com/post', frontend)
        self.assertEqual(again.duplicate.id, first.article_id)
        self.assertFalse(again.ok)
        self.assertEqual(frontend.stages, [])
        self.assertEqual(len(self.scraped), 1)

        forced = await pipeline.run(self.user, 'https://e.com/post', FakeFrontend(), force=True)
        self.assertTrue(forced.ok)
        self.assertNotEqual(forced.article_id, first.article_id)
        self.assertEqual(len(self.scraped), 2)

    async def test_resend_reuses_the_epub(self):
        first = await pipeline.run(self.user, 'https://e.com/post', FakeFrontend())
        frontend = FakeFrontend()
        resent = await pipeline.run(self.user, 'https://e.com/post', frontend, targets={db.TELEGRAM},
                                    article_id=first.article_id, force=True)
        self.assertEqual(resent.article_id, first.article_id)
        self.assertEqual(resent.delivered, {db.TELEGRAM})
        self.assertEqual(resent.book.epub_path, first.book.epub_path)
        self.assertEqual(frontend.stages, [Stage.RECEIVED])
        self.assertEqual(len(self.scraped), 1)

    async def test_file_too_big_for_the_front_end(self):
        user = db.update_user(self.user.user_id, delivery_mode=db.TELEGRAM)
        frontend = FakeFrontend(max_file_bytes=999)
        outcome = await pipeline.run(user, 'https://e.com/post', frontend)
        self.assertFalse(outcome.ok)
        self.assertIsNone(outcome.failure)
        self.assertEqual(outcome.file_too_big, 1000)
        self.assertEqual(frontend.files, [])
        self.assertEqual(db.get_article(outcome.article_id).status, db.FAILED)

        both = db.update_user(self.user.user_id, delivery_mode=db.BOTH)
        outcome = await pipeline.run(both, 'https://e.com/other', FakeFrontend(max_file_bytes=999))
        self.assertEqual(outcome.delivered, {db.KINDLE})  # the Kindle still gets it
        self.assertEqual(outcome.file_too_big, 1000)
        self.assertEqual(db.get_article(outcome.article_id).status, db.SENT)

    async def test_scraper_failures(self):
        for error, failure in ((BlockedError('Cloudflare'), Failure.BLOCKED),
                               (ExtractionError('No text'), Failure.EXTRACT),
                               (FetchError('Timeout'), Failure.FETCH)):
            with self.subTest(failure=failure):
                self.scrape_error = error
                frontend = FakeFrontend()
                outcome = await pipeline.run(self.user, f'https://e.com/{failure}', frontend)
                self.assertEqual(outcome.failure, failure)
                self.assertIs(outcome.error, error)
                self.assertFalse(outcome.ok)
                self.assertEqual(frontend.stages, [Stage.RECEIVED, Stage.FETCHING])
                article = db.get_article(outcome.article_id)
                self.assertEqual((article.status, article.error), (db.FAILED, str(error)))
        self.assertEqual(self.mailed, [])

    async def test_mail_and_front_end_failures(self):
        self.mail_error = EmailError('Relay denied')
        outcome = await pipeline.run(self.user, 'https://e.com/mail', FakeFrontend())
        self.assertEqual(outcome.failure, Failure.EMAIL)
        self.assertEqual(db.get_article(outcome.article_id).status, db.FAILED)

        self.mail_error = None
        user = db.update_user(self.user.user_id, delivery_mode=db.TELEGRAM)
        outcome = await pipeline.run(user, 'https://e.com/upload', FakeFrontend(fail_file=True))
        self.assertEqual(outcome.failure, Failure.UNKNOWN)
        self.assertEqual(outcome.delivered, set())

    async def test_failed_resend_keeps_the_delivered_status(self):
        first = await pipeline.run(self.user, 'https://e.com/post', FakeFrontend())
        self.mail_error = EmailError('Relay denied')
        outcome = await pipeline.run(self.user, 'https://e.com/post', FakeFrontend(), article_id=first.article_id,
                                     force=True)
        self.assertEqual(outcome.failure, Failure.EMAIL)
        self.assertEqual(db.get_article(first.article_id).status, db.SENT)

    async def test_waiting_for_a_slot_is_reported(self):
        held = 0
        while not pipeline.GLOBAL_SLOTS.locked():  # every slot busy with someone else's book
            await pipeline.GLOBAL_SLOTS.acquire()
            held += 1
        frontend = FakeFrontend()
        task = asyncio.create_task(pipeline.run(self.user, 'https://e.com/post', frontend))
        await asyncio.sleep(0.05)
        self.assertEqual(frontend.stages, [Stage.RECEIVED, Stage.QUEUED])
        for _ in range(held):
            pipeline.GLOBAL_SLOTS.release()
        outcome = await task
        self.assertTrue(outcome.ok)
        self.assertEqual(frontend.stages[-1], Stage.SENDING)


class IndependenceTest(unittest.TestCase):
    def test_core_does_not_import_a_front_end(self):
        """Any front end must be able to use the core without the others' frameworks."""
        code = ("import sys; import core.db, core.accounts, core.kindle, core.pipeline; "
                "banned = ('telegram', 'fastapi', 'starlette', 'uvicorn', 'authlib', 'web', 'bot'); "
                "sys.exit(any(m.split('.')[0] in banned for m in sys.modules))")
        env = {**os.environ, 'PYTHONPATH': str(SRC)}
        result = subprocess.run([sys.executable, '-c', code], env=env, cwd=_DB_DIR, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == '__main__':
    unittest.main()
