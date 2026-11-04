#!/usr/bin/env python3
"""
Offline tests for core.accounts: which account a sign-in reaches, how web accounts get their ids,
and what happens when a web account and a Telegram account turn out to be the same person.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for scratch_db, however the tests are started

_DB_DIR = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_DB_DIR, 'users.db')}"

from core import accounts, db  # noqa: E402
from scratch_db import use_scratch_database  # noqa: E402


@use_scratch_database
class AccountsTest(unittest.TestCase):
    def setUp(self):
        with db.Session() as session:
            for model in (db.Identity, db.Article, db.User):
                session.query(model).delete()
            session.commit()

    def test_email_sign_in_creates_a_web_account_and_reuses_it(self):
        first = accounts.sign_in(accounts.EMAIL, ' Ann@Example.com ', email='Ann@Example.com')
        again = accounts.sign_in(accounts.EMAIL, 'ann@example.com', email='ann@example.com')
        self.assertLess(first.user_id, 0)
        self.assertEqual(first.user_id, again.user_id)
        self.assertEqual(accounts.email_of(first.user_id), 'ann@example.com')

    def test_web_accounts_get_distinct_negative_ids(self):
        a = accounts.sign_in(accounts.EMAIL, 'a@example.com', email='a@example.com')
        b = accounts.sign_in(accounts.EMAIL, 'b@example.com', email='b@example.com')
        self.assertEqual((a.user_id, b.user_id), (-1, -2))

    def test_google_and_email_with_the_same_address_are_one_account(self):
        by_mail = accounts.sign_in(accounts.EMAIL, 'ann@example.com', email='ann@example.com')
        by_google = accounts.sign_in(accounts.GOOGLE, 'g-123', email='ann@example.com', first_name='Ann')
        self.assertEqual(by_mail.user_id, by_google.user_id)
        self.assertEqual({i.provider for i in accounts.identities(by_mail.user_id)}, {'email', 'google'})
        self.assertEqual(db.get_user(by_mail.user_id).first_name, 'Ann')

    def test_telegram_sign_in_uses_the_telegram_id_the_bot_uses(self):
        db.upsert_user(4242, username='ann')
        db.update_user(4242, kindle_email='ann@kindle.com')
        user = accounts.sign_in(accounts.TELEGRAM, '4242', username='ann', first_name='Ann')
        self.assertEqual(user.user_id, 4242)
        self.assertEqual(db.get_user(4242).kindle_email, 'ann@kindle.com')

    def test_connecting_telegram_merges_the_web_account(self):
        web = accounts.sign_in(accounts.EMAIL, 'ann@example.com', email='ann@example.com')
        db.update_user(web.user_id, kindle_email='web@kindle.com', language='de', setup_verified=1)
        article = db.create_article(web.user_id, 'https://e.com/post')
        db.upsert_user(4242)
        db.update_user(4242, preserve_image_links=0)

        merged = accounts.sign_in(accounts.TELEGRAM, '4242', first_name='Ann', current_user_id=web.user_id)

        self.assertEqual(merged.user_id, 4242)
        self.assertIsNone(db.get_user(web.user_id))
        self.assertEqual(db.get_article(article.id).user_id, 4242)
        user = db.get_user(4242)
        self.assertEqual((user.kindle_email, user.language, user.setup_verified), ('web@kindle.com', 'de', 1))
        self.assertEqual({i.provider for i in accounts.identities(4242)}, {'email', 'telegram'})
        # signing in by email afterwards reaches the Telegram account
        self.assertEqual(accounts.sign_in(accounts.EMAIL, 'ann@example.com').user_id, 4242)

    def test_the_telegram_accounts_own_settings_win_a_merge(self):
        web = accounts.sign_in(accounts.EMAIL, 'ann@example.com', email='ann@example.com')
        db.update_user(web.user_id, kindle_email='web@kindle.com', language='de')
        db.upsert_user(4242)
        db.update_user(4242, kindle_email='tg@kindle.com')
        accounts.sign_in(accounts.TELEGRAM, '4242', current_user_id=web.user_id)
        user = db.get_user(4242)
        self.assertEqual((user.kindle_email, user.language), ('tg@kindle.com', 'de'))

    def test_a_second_telegram_account_is_refused(self):
        db.upsert_user(1)
        db.upsert_user(2)
        accounts.sign_in(accounts.TELEGRAM, '1')
        with self.assertRaises(accounts.LinkConflict):
            accounts.sign_in(accounts.TELEGRAM, '2', current_user_id=1)
        self.assertIsNotNone(db.get_user(1))
        self.assertIsNotNone(db.get_user(2))

    def test_google_account_owned_by_another_telegram_account_is_refused(self):
        web = accounts.sign_in(accounts.GOOGLE, 'g-1', email='a@example.com')
        accounts.sign_in(accounts.TELEGRAM, '1', current_user_id=web.user_id)  # now Telegram account 1
        db.upsert_user(2)
        with self.assertRaises(accounts.LinkConflict):
            accounts.sign_in(accounts.GOOGLE, 'g-1', current_user_id=2)

    def test_signed_in_web_account_connects_google(self):
        web = accounts.sign_in(accounts.EMAIL, 'ann@example.com', email='ann@example.com')
        same = accounts.sign_in(accounts.GOOGLE, 'g-9', email='other@example.com', current_user_id=web.user_id)
        self.assertEqual(same.user_id, web.user_id)
        self.assertEqual(len(accounts.identities(web.user_id)), 2)

    def test_deleting_the_user_removes_the_identities(self):
        user = accounts.sign_in(accounts.EMAIL, 'ann@example.com', email='ann@example.com')
        db.delete_user_data(user.user_id)
        self.assertEqual(accounts.identities(user.user_id), [])
        self.assertIsNone(db.get_user(user.user_id))
        fresh = accounts.sign_in(accounts.EMAIL, 'ann@example.com', email='ann@example.com')
        self.assertIsNone(db.get_article(1))
        self.assertLess(fresh.user_id, 0)

    def test_unknown_provider(self):
        with self.assertRaises(ValueError):
            accounts.sign_in('github', 'x')


if __name__ == '__main__':
    unittest.main()
