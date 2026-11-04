#!/usr/bin/env python3
"""
Offline tests for the Telegram bot's conversation layer: link and address detection, texts,
keyboards, result cards and storage. Uses real python-telegram-bot objects, no network.
"""

import os
import re
import sqlite3
import string
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(SRC))

# The database module connects on import; point it at a scratch file first
_DB_DIR = tempfile.mkdtemp()
_DB_PATH = os.path.join(_DB_DIR, 'users.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_PATH}'

from telegram import Message, MessageEntity  # noqa: E402

from core import db  # noqa: E402
from core.kindle import (AMAZON_STORES, amazon_store, device_of, is_device_email, is_kindle_email, is_pocketbook_email,  # noqa: E402
                         looks_like_email, normalize_email)
from core.pipeline import word_count  # noqa: E402
from bot import keyboards  # noqa: E402
from bot.config import amazon_settings_url  # noqa: E402
from core.kindle import amazon_devices_url  # noqa: E402
from bot.delivery import Book, card_text, upsert_user  # noqa: E402
from bot.handlers import history as history_screen  # noqa: E402
from bot.handlers import settings as settings_screen  # noqa: E402
from bot.links import MAX_LINKS, extract_urls  # noqa: E402
from bot.profile import COMMANDS  # noqa: E402
from bot.texts import (LANGUAGES, TEXTS, Raw, for_device, format_date, format_size, resolve_lang,  # noqa: E402
                       t)

BOT_ID = 4242


def make_message(text=None, entities=(), caption=None, caption_entities=(), reply=None, from_id=1, is_bot=False):
    data = {'message_id': 1, 'date': 0, 'chat': {'id': from_id, 'type': 'private'},
            'from': {'id': from_id, 'is_bot': is_bot, 'first_name': 'A'}}
    if text is not None:
        data['text'] = text
        data['entities'] = list(entities)
    if caption is not None:
        data['caption'] = caption
        data['caption_entities'] = list(caption_entities)
        data['photo'] = [{'file_id': 'x', 'file_unique_id': 'x', 'width': 1, 'height': 1}]
    if reply is not None:
        data['reply_to_message'] = reply
    return Message.de_json(data, None)


def url_entity(text, link):
    return {'type': MessageEntity.URL, 'offset': text.index(link), 'length': len(link)}


def text_link(text, label, url):
    return {'type': MessageEntity.TEXT_LINK, 'offset': text.index(label), 'length': len(label), 'url': url}


class ExtractUrlsTest(unittest.TestCase):
    def test_plain_link_entity(self):
        text = 'Great read: https://example.com/post.'
        message = make_message(text, [url_entity(text, 'https://example.com/post.')])
        self.assertEqual(extract_urls(message), ['https://example.com/post'])

    def test_share_sheet_text_without_entities(self):
        message = make_message('The Title of the Post\nhttps://example.substack.com/p/title')
        self.assertEqual(extract_urls(message), ['https://example.substack.com/p/title'])

    def test_bare_domain(self):
        self.assertEqual(extract_urls(make_message('medium.com/@user/post-123')), ['https://medium.com/@user/post-123'])

    def test_hidden_text_link(self):
        text = 'New essay, Read more'
        message = make_message(text, [text_link(text, 'Read more', 'https://blog.example.org/essay')])
        self.assertEqual(extract_urls(message), ['https://blog.example.org/essay'])

    def test_photo_caption(self):
        caption = 'Our story https://news.example.com/a'
        message = make_message(caption=caption, caption_entities=[url_entity(caption, 'https://news.example.com/a')])
        self.assertEqual(extract_urls(message), ['https://news.example.com/a'])

    def test_several_links_in_order_without_duplicates(self):
        text = 'https://a.example/1 and https://b.example/2 and again https://a.example/1'
        entities = [{'type': 'url', 'offset': m.start(), 'length': len(m.group())}
                    for m in re.finditer(r'https://\S+', text)]
        message = make_message(text, entities)
        self.assertEqual(extract_urls(message), ['https://a.example/1', 'https://b.example/2'])

    def test_more_than_the_limit_are_all_returned(self):
        text = ' '.join(f'https://example.com/{i}' for i in range(MAX_LINKS + 3))
        self.assertEqual(len(extract_urls(make_message(text))), MAX_LINKS + 3)

    def test_non_web_links_are_skipped(self):
        text = 'Join, mail me'
        message = make_message(text, [text_link(text, 'Join', 'tg://resolve?domain=x'),
                                      text_link(text, 'mail me', 'mailto:a@b.de')])
        self.assertEqual(extract_urls(message), [])

    def test_port_is_kept(self):
        text = 'example.com:8080/post'
        message = make_message(text, [url_entity(text, text)])
        self.assertEqual(extract_urls(message), ['https://example.com:8080/post'])

    def test_falls_back_to_replied_message(self):
        reply = {'message_id': 0, 'date': 0, 'chat': {'id': 1, 'type': 'group'},
                 'from': {'id': 7, 'is_bot': False, 'first_name': 'B'}, 'text': 'https://example.com/x'}
        self.assertEqual(extract_urls(make_message('@SomeBot', reply=reply)), ['https://example.com/x'])

    def test_ignores_replies_to_the_bots_own_messages(self):
        reply = {'message_id': 0, 'date': 0, 'chat': {'id': 1, 'type': 'private'},
                 'from': {'id': BOT_ID, 'is_bot': True, 'first_name': 'Bot'}, 'text': 'https://example.com/x'}
        self.assertEqual(extract_urls(make_message('thanks', reply=reply), bot_id=BOT_ID), [])

    def test_email_is_not_a_link(self):
        self.assertEqual(extract_urls(make_message('name_ab12@kindle.com')), [])


class KindleEmailTest(unittest.TestCase):
    def test_accepted(self):
        for email in ('name_ab12@kindle.com', ' Name_AB12@Kindle.COM ', 'a.b+c@free.kindle.com',
                      'x@kindle.cn', 'mailto:name@kindle.com', '<name@kindle.com>'):
            with self.subTest(email=email):
                self.assertTrue(is_kindle_email(email))

    def test_rejected(self):
        for email in ('name@gmail.com', 'a b@kindle.com', '@kindle.com', 'name@kindle.com.evil.org',
                      'name@kindle.co', 'kindle.com', ''):
            with self.subTest(email=email):
                self.assertFalse(is_kindle_email(email))

    def test_regular_address_is_recognised_as_email(self):
        self.assertTrue(looks_like_email('name@gmail.com'))
        self.assertFalse(looks_like_email('hello there'))
        self.assertFalse(looks_like_email('https://example.com'))

    def test_normalize(self):
        self.assertEqual(normalize_email(' Name@Kindle.com\n'), 'name@kindle.com')

    def test_pocketbook_addresses_are_accepted_as_a_second_reader(self):
        for email in ('ann_x1@pbsync.com', ' Ann@PBSync.com ', 'mailto:ann@pbsync.com'):
            with self.subTest(email=email):
                self.assertTrue(is_pocketbook_email(email))
                self.assertTrue(is_device_email(email))
                self.assertFalse(is_kindle_email(email))
                self.assertEqual(device_of(email), 'pocketbook')
        for email in ('ann@pbsync.com.evil.org', 'ann@mail.pbsync.com', '@pbsync.com', 'ann@gmail.com'):
            with self.subTest(email=email):
                self.assertFalse(is_device_email(email))
        self.assertTrue(is_device_email('name@kindle.com'))
        self.assertEqual(device_of('name@kindle.com'), 'kindle')
        self.assertEqual(device_of(None), 'kindle')  # Kindle is the default wording

    def test_amazon_store_guess(self):
        # Germany with an English browser or Telegram: the time zone or the region decides, not the language
        self.assertEqual(amazon_store('en', time_zone='Europe/Berlin'), 'amazon.de')
        self.assertEqual(amazon_store('en-US,en;q=0.9', time_zone='Europe/Vienna'), 'amazon.de')
        self.assertEqual(amazon_store('en-DE'), 'amazon.de')
        self.assertEqual(amazon_store('en', 'de'), 'amazon.de')  # Telegram in English, bot set to German
        self.assertEqual(amazon_store('en-GB'), 'amazon.co.uk')
        self.assertEqual(amazon_store('de-CH'), 'amazon.de')
        self.assertEqual(amazon_store('en', time_zone='Australia/Sydney'), 'amazon.com.au')
        self.assertEqual(amazon_store('en-US,en;q=0.9,de;q=0.8'), 'amazon.com')  # the US region wins
        self.assertEqual(amazon_store('en'), 'amazon.com')
        self.assertEqual(amazon_store(None), 'amazon.com')
        # A store the user picked beats every guess; anything else is ignored
        self.assertEqual(amazon_store('de', chosen='amazon.co.uk', time_zone='Europe/Berlin'), 'amazon.co.uk')
        self.assertEqual(amazon_store('de', chosen='evil.example'), 'amazon.de')

    def test_step1_links_to_amazon_devices(self):
        url = amazon_devices_url(chosen='amazon.de')
        self.assertEqual(url, 'https://www.amazon.de/hz/mycd/digital-console/alldevices')
        self.assertEqual(amazon_settings_url(chosen='amazon.de'),
                         'https://www.amazon.de/hz/mycd/preferences/myx#/home/settings/payment')
        for lang in LANGUAGES:
            for key in ('setup_step1', 'email_not_kindle'):
                with self.subTest(lang=lang, key=key):
                    self.assertIn(f'<a href="{url}">', t(lang, key, email='a@gmail.com', url=url))

    def test_pocketbook_texts_only_where_they_differ(self):
        self.assertEqual(for_device('setup_step2', 'a@pbsync.com'), 'setup_step2_pocketbook')
        self.assertEqual(for_device('setup_step2', 'a@kindle.com'), 'setup_step2')
        self.assertEqual(for_device('setup_step2', None), 'setup_step2')
        self.assertEqual(for_device('help', 'a@pbsync.com'), 'help')  # no PocketBook version: Kindle text
        for lang in LANGUAGES:
            for key in TEXTS['en']:
                if key.endswith('_pocketbook'):
                    with self.subTest(lang=lang, key=key):
                        self.assertIn(key.removesuffix('_pocketbook'), TEXTS['en'])  # a variant of a real text
                        self.assertNotIn('Kindle', TEXTS[lang][key])


class TagChecker(HTMLParser):
    """Telegram rejects messages with unknown or unbalanced tags."""
    ALLOWED = {'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'a', 'code', 'pre',
               'blockquote', 'tg-spoiler', 'span'}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.ALLOWED:
            self.errors.append(f'<{tag}> not supported')
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.errors.append(f'unbalanced </{tag}>')


def placeholders(template):
    return {field for _, field, _, _ in string.Formatter().parse(template) if field}


class TextsTest(unittest.TestCase):
    NOT_TELEGRAM_HTML = {'test_book_body'}  # goes into the EPUB, not into a message

    def test_every_key_in_every_language_with_the_same_placeholders(self):
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                self.assertEqual(set(TEXTS[lang]), set(TEXTS['en']))
                for key, template in TEXTS['en'].items():
                    self.assertEqual(placeholders(TEXTS[lang][key]), placeholders(template), key)

    def test_html_is_valid_for_telegram(self):
        for lang in LANGUAGES:
            for key, template in TEXTS[lang].items():
                if key in self.NOT_TELEGRAM_HTML:
                    continue
                checker = TagChecker()
                checker.feed(template)
                with self.subTest(lang=lang, key=key):
                    self.assertEqual(checker.errors + checker.stack, [])

    def test_every_key_used_in_the_code_exists(self):
        used = set()
        for path in (SRC / 'bot').rglob('*.py'):
            used |= set(re.findall(r"\bt\([^,()]+, '([a-z0-9_]+)'", path.read_text()))
        used |= {f'cmd_{name}' for name in COMMANDS}
        used |= {f'{prefix}_{mode}' for prefix in ('mode', 'delivery') for mode in db.DELIVERY_MODES}
        self.assertTrue(used)
        self.assertEqual(used - set(TEXTS['en']), set())

    def test_profile_length_limits(self):
        for lang in LANGUAGES:
            self.assertLessEqual(len(t(lang, 'bot_description')), 512)
            self.assertLessEqual(len(t(lang, 'bot_short_description')), 120)
            for name in COMMANDS:
                self.assertLessEqual(len(t(lang, f'cmd_{name}')), 256)
            self.assertLessEqual(len(t(lang, 'email_placeholder')), 64)

    def test_arguments_are_escaped_unless_raw(self):
        self.assertIn('&lt;b&gt;', t('en', 'duplicate', title='<b>', date='today'))
        self.assertIn('<code>x</code>', t('en', 'settings', email=Raw('<code>x</code>'), delivery='K',
                                          links='on', language='EN'))

    def test_language_resolution(self):
        class TgUser:
            def __init__(self, code):
                self.language_code = code

        class Row:
            def __init__(self, language):
                self.language = language

        self.assertEqual(resolve_lang(None, TgUser('de')), 'de')
        self.assertEqual(resolve_lang(None, TgUser('de-AT')), 'de')
        self.assertEqual(resolve_lang(None, TgUser('fr')), 'en')
        self.assertEqual(resolve_lang(None, TgUser(None)), 'en')
        self.assertEqual(resolve_lang(Row('en'), TgUser('de')), 'en')
        self.assertEqual(resolve_lang(Row(None), TgUser('de')), 'de')

    def test_formatting(self):
        self.assertEqual(format_size('en', 1536 * 1024), '1.5 MB')
        self.assertEqual(format_size('de', 1536 * 1024), '1,5 MB')
        self.assertEqual(format_size('en', 300), '1 KB')
        day = datetime(2026, 11, 3)
        self.assertEqual(format_date('en', day), '3 Nov 2026')
        self.assertEqual(format_date('de', day), '3. Nov. 2026')
        self.assertEqual(format_date('de', datetime(2026, 3, 1)), '1. März 2026')

    def test_amazon_link_follows_app_language(self):
        self.assertIn('www.amazon.de/', amazon_settings_url('de'))
        self.assertIn('www.amazon.co.uk/', amazon_settings_url('en-GB'))
        self.assertIn('www.amazon.com/', amazon_settings_url('en'))
        self.assertIn('www.amazon.com/', amazon_settings_url(None))


def all_buttons(markup):
    return [button for row in markup.inline_keyboard for button in row] if markup else []


class KeyboardsTest(unittest.TestCase):
    def setUp(self):
        self.user = db.User(user_id=1, kindle_email='name@kindle.com', preserve_image_links=0)

    def test_callback_data_fits_telegram_limit(self):
        big_id = 10 ** 15
        markups = [
            keyboards.start_new('de'), keyboards.start_ready('de'), keyboards.setup_test('de'),
            keyboards.test_result('de'), keyboards.test_retry('de'), keyboards.delete_confirm('de'),
            keyboards.settings('de', self.user), keyboards.privacy('de'),
            keyboards.result_card('de', big_id, 'https://e.com', set(), self.user, True),
            keyboards.error_card('de', big_id, 'https://e.com'), keyboards.duplicate('de', big_id),
            keyboards.send_to_kindle('de', big_id),
            keyboards.history([db.Article(id=big_id + i) for i in range(5)], big_id, big_id * 3),
            keyboards.setup_sender('de', 'bot@example.com', 'https://www.amazon.de/'),
            keyboards.troubleshoot('de', 'bot@example.com', 'https://www.amazon.de/'),
        ]
        for markup in markups:
            for button in all_buttons(markup):
                with self.subTest(button=button.text):
                    if button.callback_data:
                        self.assertLessEqual(len(button.callback_data.encode()), 64)
                    if button.copy_text:
                        self.assertLessEqual(len(button.copy_text.text), 256)
                    self.assertTrue(button.callback_data or button.url or button.copy_text)

    def test_amazon_buttons_name_the_store_and_offer_others(self):
        markup = keyboards.setup_sender('en', 'a@b.de', amazon_settings_url(chosen='amazon.de'))
        buttons = all_buttons(markup)
        self.assertIn(t('en', 'btn_open_amazon', store='amazon.de'), [b.text for b in buttons])
        self.assertIn(keyboards.setup_store(keyboards.STORE_STEP2), [b.callback_data for b in buttons])
        troubleshoot = all_buttons(keyboards.troubleshoot('en', 'a@b.de', amazon_settings_url()))
        self.assertIn(keyboards.setup_store(keyboards.STORE_TROUBLESHOOT), [b.callback_data for b in troubleshoot])

    def test_store_picker(self):
        prefix = keyboards.setup_store(keyboards.STORE_TROUBLESHOOT)
        buttons = all_buttons(keyboards.store_picker('en', 'amazon.de', prefix, keyboards.SHOW_SETTINGS))
        self.assertEqual([b.callback_data for b in buttons[:-1]], [f'{prefix}:{s}' for s in AMAZON_STORES])
        self.assertIn('✓ amazon.de', [b.text for b in buttons])
        self.assertEqual(buttons[-1].callback_data, keyboards.SHOW_SETTINGS)
        for button in buttons:
            self.assertLessEqual(len(button.callback_data.encode()), 64)
        settings = all_buttons(keyboards.settings('en', self.user, 'amazon.de'))
        self.assertIn(keyboards.SET_STORE, [b.callback_data for b in settings])
        pocketbook = db.User(user_id=2, kindle_email='a@pbsync.com')
        self.assertNotIn(keyboards.SET_STORE, [b.callback_data for b in all_buttons(keyboards.settings('en', pocketbook, 'amazon.de'))])

    def test_pocketbook_setup_has_no_amazon_button(self):
        for markup in (keyboards.setup_sender('en', 'a@b.de', None), keyboards.troubleshoot('en', 'a@b.de', None)):
            self.assertFalse(any(b.url for b in all_buttons(markup)))
        step2 = all_buttons(keyboards.setup_sender('en', 'a@b.de', None))
        self.assertIn(keyboards.SETUP_ADDED, [b.callback_data for b in step2])

    def test_result_card_names_the_pocketbook(self):
        user = db.User(user_id=1, kindle_email='name@pbsync.com')
        labels = [b.text for b in all_buttons(keyboards.result_card('en', 1, 'https://e.com', {db.TELEGRAM}, user, False))]
        self.assertIn(t('en', 'btn_send_to_kindle_pocketbook'), labels)

    def test_copy_button_only_with_a_sender(self):
        self.assertTrue(any(b.copy_text for b in all_buttons(keyboards.setup_sender('en', 'a@b.de', 'https://x'))))
        self.assertFalse(any(b.copy_text for b in all_buttons(keyboards.setup_sender('en', '', 'https://x'))))

    def test_result_card_offers_what_was_not_delivered(self):
        to_kindle = all_buttons(keyboards.result_card('en', 1, 'https://e.com', {db.KINDLE}, self.user, False))
        self.assertIn('art:file:1', [b.callback_data for b in to_kindle])
        self.assertIn('art:kindle:1', [b.callback_data for b in to_kindle])

        chat_only = db.User(user_id=2, delivery_mode=db.TELEGRAM)
        buttons = all_buttons(keyboards.result_card('en', 1, 'https://e.com', {db.TELEGRAM}, chat_only, False))
        self.assertEqual([b.url for b in buttons], ['https://e.com'])  # no setup nudge after "EPUB only"

        undecided = db.User(user_id=3)
        buttons = all_buttons(keyboards.result_card('en', 1, 'https://e.com', {db.TELEGRAM}, undecided, False))
        self.assertIn(keyboards.SETUP_START, [b.callback_data for b in buttons])

    def test_settings_marks_the_active_delivery_mode(self):
        both = db.User(user_id=1, kindle_email='a@kindle.com', delivery_mode=db.BOTH)
        labels = [b.text for b in all_buttons(keyboards.settings('en', both))]
        self.assertIn('✓ ' + t('en', 'mode_both'), labels)
        no_email = db.User(user_id=1, delivery_mode=db.KINDLE)  # address deleted: chat is all that's left
        labels = [b.text for b in all_buttons(keyboards.settings('en', no_email))]
        self.assertIn('✓ ' + t('en', 'mode_telegram'), labels)


class CardTest(unittest.TestCase):
    def test_card_contents(self):
        with tempfile.NamedTemporaryFile(suffix='.epub') as file:
            file.write(b'x' * 2048)
            file.flush()
            book = Book(title='Fish & <Chips>', url='https://e.com', epub_path=file.name, author='Ann',
                        publication='The Paper', words=2300, is_preview=True)
            text = card_text('en', book, {db.KINDLE})
        self.assertIn('<b>Fish &amp; &lt;Chips&gt;</b>', text)
        self.assertIn('by Ann · The Paper', text)
        self.assertIn('~10 min read · 2 KB', text)
        self.assertIn(t('en', 'card_preview'), text)
        self.assertIn(t('en', 'footer_kindle'), text)

    def test_card_footer_per_delivery(self):
        book = Book(title='T', url='https://e.com', epub_path='/nonexistent.epub')
        self.assertIn(t('de', 'footer_both'), card_text('de', book, {db.KINDLE, db.TELEGRAM}))
        self.assertIn(t('de', 'footer_telegram'), card_text('de', book, {db.TELEGRAM}))

    def test_card_footer_names_the_pocketbook(self):
        book = Book(title='T', url='https://e.com', epub_path='/nonexistent.epub')
        self.assertIn(t('en', 'footer_kindle_pocketbook'), card_text('en', book, {db.KINDLE}, 'a@pbsync.com'))
        self.assertIn(t('en', 'footer_kindle'), card_text('en', book, {db.KINDLE}, 'a@kindle.com'))

    def test_long_titles_are_shortened(self):
        book = Book(title='A' * 500, url='https://e.com', epub_path='/nonexistent.epub')
        self.assertLess(len(card_text('en', book, {db.KINDLE})), 400)

    def test_word_count(self):
        self.assertEqual(word_count('<p>One <b>two</b></p><p>three</p>'), 3)


class TgUser:
    def __init__(self, user_id, first_name='Ann', username=None, language_code='en'):
        self.id = user_id
        self.first_name = first_name
        self.last_name = None
        self.username = username
        self.language_code = language_code


class StorageTest(unittest.TestCase):
    """Runs against a database that starts with the schema of earlier versions."""

    @classmethod
    def setUpClass(cls):
        # Test files share one engine, created by whichever imported core.db first
        with sqlite3.connect(db.engine.url.database) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, kindle_email VARCHAR,
                    username VARCHAR, first_name VARCHAR, last_name VARCHAR,
                    last_book_received_date VARCHAR, preserve_image_links INTEGER);
                CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY, user_id INTEGER,
                    article_url VARCHAR, timestamp DATETIME, epub_path VARCHAR);
                INSERT OR IGNORE INTO users (user_id, kindle_email, first_name, preserve_image_links)
                    VALUES (100, 'old@kindle.com', 'Old', 1);
                INSERT OR IGNORE INTO articles (id, user_id, article_url, timestamp, epub_path)
                    VALUES (1, 100, 'https://example.com/old', datetime('now', '-1 day'), '/gone.epub');
            """)
        db.init_db()

    def test_existing_users_keep_working(self):
        user = db.get_user(100)
        self.assertEqual(user.targets, {db.KINDLE})
        self.assertTrue(user.image_links)
        self.assertFalse(user.chose_chat_only)
        # Rows from before the status column counted as sent
        self.assertIsNotNone(db.recent_delivery(100, 'https://example.com/old'))
        text, _ = history_screen.render(100, 'en')
        self.assertIn('example.com', text)

    def test_delivery_targets(self):
        self.assertEqual(db.User(user_id=1).targets, {db.TELEGRAM})
        self.assertEqual(db.User(user_id=1, kindle_email='a@kindle.com').targets, {db.KINDLE})
        self.assertEqual(db.User(user_id=1, kindle_email='a@kindle.com', delivery_mode=db.BOTH).targets,
                         {db.KINDLE, db.TELEGRAM})
        self.assertEqual(db.User(user_id=1, kindle_email='a@kindle.com', delivery_mode=db.TELEGRAM).targets,
                         {db.TELEGRAM})

    def test_history_paging_and_duplicates(self):
        user = upsert_user(TgUser(200))
        ids = []
        for i in range(7):
            article = db.create_article(user.user_id, f'https://example.com/{i}')
            db.update_article(article.id, status=db.SENT, title=f'Post {i}',
                              timestamp=db.utcnow() - timedelta(minutes=10 - i))
            ids.append(article.id)
        db.update_article(ids[0], status=db.FAILED)

        page, total = db.history(user.user_id, 0, keyboards.HISTORY_PAGE_SIZE)
        self.assertEqual(total, 7)
        self.assertEqual([a.title for a in page], ['Post 6', 'Post 5', 'Post 4', 'Post 3', 'Post 2'])
        text, markup = history_screen.render(user.user_id, 'en', 5)
        self.assertIn('6. ✅', text)
        self.assertIn('7. ❌', text)
        self.assertEqual([b.callback_data for b in markup.inline_keyboard[-1]], ['hist:0'])

        self.assertIsNotNone(db.recent_delivery(user.user_id, 'https://example.com/3'))
        self.assertIsNone(db.recent_delivery(user.user_id, 'https://example.com/0'))  # failed
        db.update_article(ids[3], timestamp=db.utcnow() - timedelta(days=40))
        self.assertIsNone(db.recent_delivery(user.user_id, 'https://example.com/3'))  # too long ago

    def test_settings_panel(self):
        user = upsert_user(TgUser(300))
        text, _ = settings_screen.render(user, 'de')
        self.assertIn(t('de', 'not_set'), text)
        self.assertIn(t('de', 'delivery_telegram'), text)
        user = db.update_user(300, kindle_email='me@kindle.com', delivery_mode=db.BOTH)
        text, _ = settings_screen.render(user, 'en')
        self.assertIn('<code>me@kindle.com</code>', text)
        self.assertIn(t('en', 'delivery_both'), text)

    def test_delete_user_data(self):
        user = upsert_user(TgUser(400))
        epub = os.path.join(_DB_DIR, 'mine.epub')
        shared = os.path.join(_DB_DIR, 'shared.epub')
        for path in (epub, shared):
            Path(path).write_bytes(b'x')
        db.update_article(db.create_article(user.user_id, 'https://e.com/a').id, epub_path=epub, status=db.SENT)
        db.update_article(db.create_article(user.user_id, 'https://e.com/b').id, epub_path=shared, status=db.SENT)
        other = upsert_user(TgUser(401))
        db.update_article(db.create_article(other.user_id, 'https://e.com/b').id, epub_path=shared, status=db.SENT)

        db.delete_user_data(user.user_id)
        self.assertIsNone(db.get_user(user.user_id))
        self.assertEqual(db.history(user.user_id)[1], 0)
        self.assertFalse(os.path.exists(epub))
        self.assertTrue(os.path.exists(shared))  # still in someone else's history
        self.assertEqual(db.history(other.user_id)[1], 1)


class ErrorHandlerTest(unittest.IsolatedAsyncioTestCase):
    """Network blips while polling are logged only; everything else still reaches the admin."""

    async def run_handler(self, error):
        from unittest import mock
        from bot import app
        context = mock.Mock(error=error)
        with mock.patch.object(app.delivery, 'notify_admin', mock.AsyncMock()) as notify, \
                self.assertLogs(app.logger, 'WARNING'):
            await app.on_error(None, context)
        return notify

    async def test_transient_errors_are_not_reported(self):
        from telegram.error import NetworkError, TimedOut
        for error in (NetworkError('httpx.ConnectError: '), TimedOut()):
            with self.subTest(error=type(error).__name__):
                (await self.run_handler(error)).assert_not_awaited()

    async def test_real_errors_are_reported(self):
        from telegram.error import BadRequest, Conflict
        for error in (BadRequest("Can't parse entities"), Conflict('terminated by other getUpdates'),
                      ValueError('boom')):
            with self.subTest(error=type(error).__name__):
                (await self.run_handler(error)).assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
