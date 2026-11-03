"""
Turning a link into a delivered book, with live progress in the chat:
reactions on the user's message, one status message that is edited step by step and ends as the
result card (or an error card with a retry button).
"""

import asyncio
import logging
import os
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from html import escape
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from telegram import Bot, Message, ReplyParameters
from telegram.error import BadRequest, TelegramError

from email_sender import EmailError, send_email
from epub_converter import convert_to_epub
from web_scraper import Article as WebArticle
from web_scraper import BlockedError, ExtractionError, ScraperError, get_website_content

from . import db, keyboards
from .config import ADMIN_ID, MAX_UPLOAD_BYTES
from .texts import format_date, format_size, resolve_lang, t

logger = logging.getLogger(__name__)

WORDS_PER_MINUTE = 230
MAX_TITLE_LENGTH = 200

# Scraping, image downloads and SMTP run in threads; keep a slow user from starving everyone else
GLOBAL_SLOTS = asyncio.Semaphore(4)
USER_SLOTS: dict[int, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(2))

REACT_RECEIVED = '👀'
REACT_WORKING = '✍'
REACT_DONE = '👌'
REACT_FAILED = '💔'


@dataclass
class Book:
    title: str
    url: str
    epub_path: str
    author: str | None = None
    publication: str | None = None
    words: int | None = None
    is_preview: bool = False


@dataclass
class Result:
    article_id: int | None
    delivered: set[str] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return bool(self.delivered)


def host(url: str) -> str:
    return urlparse(url).netloc.removeprefix('www.') or url


def who(tg_user) -> str:
    return f"@{tg_user.username}" if tg_user.username else f"{tg_user.first_name} ({tg_user.id})"


def reply_to(message_id: int | None) -> ReplyParameters | None:
    return ReplyParameters(message_id, allow_sending_without_reply=True) if message_id else None


def word_count(html: str) -> int:
    return len(BeautifulSoup(html or '', 'html.parser').get_text(' ').split())


def card_text(lang: str, book: Book, delivered: set[str]) -> str:
    title = book.title if len(book.title) <= MAX_TITLE_LENGTH else book.title[:MAX_TITLE_LENGTH - 1] + '…'
    lines = [f"📚 <b>{escape(title)}</b>"]
    byline = [t(lang, 'card_by', author=book.author)] if book.author else []
    if book.publication and book.publication != book.author:
        byline.append(escape(book.publication))
    if byline:
        lines.append(' · '.join(byline))
    stats = []
    if book.words:
        stats.append(t(lang, 'card_read_time', minutes=max(1, round(book.words / WORDS_PER_MINUTE))))
    if os.path.exists(book.epub_path):
        stats.append(format_size(lang, os.path.getsize(book.epub_path)))
    if stats:
        lines.append(' · '.join(stats))
    if book.is_preview:
        lines += ['', t(lang, 'card_preview')]
    if db.KINDLE in delivered:
        lines += ['', t(lang, 'footer_both' if db.TELEGRAM in delivered else 'footer_kindle')]
    elif db.TELEGRAM in delivered:
        lines += ['', t(lang, 'footer_telegram')]
    return '\n'.join(lines)


async def notify_admin(bot: Bot, text: str) -> None:
    if not ADMIN_ID:
        return
    try:
        await bot.send_message(ADMIN_ID, text[:4096])
    except TelegramError as e:
        logger.warning(f"Could not notify admin: {e}")


def error_report(tg_user, url: str, error: BaseException) -> str:
    trace = ''.join(traceback.format_exception(error))[-3000:]
    return (f"💥 <b>Error</b> for {escape(who(tg_user))}\n{escape(url)}\n"
            f"<blockquote expandable>{escape(trace)}</blockquote>")


class Progress:
    """The status message for one link, edited in place, plus reactions on the user's message."""

    def __init__(self, bot: Bot, chat_id: int, lang: str, url: str, *, reply_to_id: int | None,
                 react: bool, show_source: bool, message: Message | None = None):
        self.bot = bot
        self.chat_id = chat_id
        self.lang = lang
        self.reply_to_id = reply_to_id
        self.react_to = reply_to_id if react else None
        self.source = (f'🔗 <a href="{escape(url, quote=True)}">{escape(host(url))}</a>\n\n'
                       if show_source else '')
        self.message = message

    async def react(self, emoji: str) -> None:
        if not self.react_to:
            return
        try:
            await self.bot.set_message_reaction(self.chat_id, self.react_to, emoji)
        except TelegramError as e:
            logger.debug(f"Could not set reaction: {e}")

    async def show(self, key: str) -> None:
        await self.finish(self.source + t(self.lang, key))

    async def finish(self, text: str, reply_markup=None) -> None:
        if self.message is None:
            self.message = await self.bot.send_message(self.chat_id, text, reply_markup=reply_markup,
                                                       reply_parameters=reply_to(self.reply_to_id))
            return
        try:
            await self.message.edit_text(text, reply_markup=reply_markup)
        except BadRequest as e:
            if 'not modified' in str(e).lower():
                return
            # The status message is gone (deleted by the user): start a new one
            logger.debug(f"Could not edit status message: {e}")
            self.message = None
            await self.finish(text, reply_markup)

    async def remove(self) -> None:
        if self.message is not None:
            try:
                await self.message.delete()
            except TelegramError as e:
                logger.debug(f"Could not delete status message: {e}")
            self.message = None


async def deliver(bot: Bot, tg_user, chat_id: int, url: str, *, reply_to_id: int | None = None,
                  targets: set[str] | None = None, article_id: int | None = None, force: bool = False,
                  react: bool = True, show_source: bool = False, status_message: Message | None = None) -> Result:
    """
    Fetch an article, build the EPUB and deliver it to the Kindle and/or this chat.

    targets:        where to deliver; default is the user's delivery setting
    article_id:     history entry to reuse (resend, retry); its EPUB is reused while it's still on disk
    force:          skip the "you already got this" check
    react:          show progress as reactions on the message `reply_to_id` (the user's link message)
    show_source:    start the status message with the link (when it isn't a reply to the link itself)
    status_message: an existing bot message to turn into the status message (retry buttons)
    """
    user = db.upsert_user(tg_user)
    lang = resolve_lang(user, tg_user)
    targets = targets or user.targets

    if not force and article_id is None:
        previous = db.recent_delivery(user.user_id, url)
        if previous:
            await bot.send_message(
                chat_id, t(lang, 'duplicate', title=previous.title or host(url),
                           date=format_date(lang, previous.timestamp)),
                reply_markup=keyboards.duplicate(lang, previous.id), reply_parameters=reply_to(reply_to_id))
            return Result(previous.id)

    article = db.get_article(article_id) if article_id else None
    if article is None:
        article = db.create_article(user.user_id, url)
    reuse = (article_id is not None and article.status in (*db.DELIVERED, None)
             and bool(article.epub_path) and os.path.exists(article.epub_path))

    progress = Progress(bot, chat_id, lang, url, reply_to_id=reply_to_id, react=react,
                        show_source=show_source, message=status_message)
    await progress.react(REACT_RECEIVED)
    user_slots = USER_SLOTS[user.user_id]
    if user_slots.locked() or GLOBAL_SLOTS.locked():
        await progress.show('status_queued')

    async with user_slots, GLOBAL_SLOTS:
        delivered: set[str] = set()
        try:
            if reuse:
                book = Book(title=article.title or host(url), url=url, epub_path=article.epub_path,
                            is_preview=article.status == db.PREVIEW)
            else:
                await progress.show('status_fetching')
                content = await asyncio.to_thread(get_website_content, url)
                await progress.show('status_building')
                await progress.react(REACT_WORKING)
                epub_path = await asyncio.to_thread(convert_to_epub, content, user.image_links)
                words = await asyncio.to_thread(word_count, content.Content)
                book = Book(title=content.Title or host(url), url=url, epub_path=epub_path,
                            author=content.Author, publication=content.Publication,
                            words=words, is_preview=bool(content.Is_Preview))
                db.update_article(article.id, title=book.title, epub_path=epub_path)

            if db.KINDLE in targets:
                await progress.show('status_sending')
                await asyncio.to_thread(send_email, user.kindle_email, book.epub_path)
                delivered.add(db.KINDLE)

            too_big = None
            if db.TELEGRAM in targets:
                size = os.path.getsize(book.epub_path)
                if size > MAX_UPLOAD_BYTES:
                    too_big = t(lang, 'file_too_big', size=format_size(lang, size))
                else:
                    await progress.show('status_uploading')
                    delivered.add(db.TELEGRAM)
                    with open(book.epub_path, 'rb') as document:
                        await bot.send_document(
                            chat_id, document, filename=os.path.basename(book.epub_path),
                            caption=card_text(lang, book, delivered),
                            reply_markup=keyboards.result_card(lang, article.id, url, delivered, user,
                                                               book.is_preview),
                            reply_parameters=reply_to(reply_to_id))
                    await progress.remove()

            if progress.message is not None or not delivered:
                text = card_text(lang, book, delivered)
                if too_big:
                    text += '\n\n' + too_big
                # No "EPUB here" button when the file is too big for Telegram
                offered = delivered | ({db.TELEGRAM} if too_big else set())
                await progress.finish(text, keyboards.result_card(lang, article.id, url, offered, user,
                                                                  book.is_preview))

            if delivered:
                db.update_article(article.id, status=db.PREVIEW if book.is_preview else db.SENT, error=None,
                                  timestamp=db.utcnow())
                if db.KINDLE in delivered:
                    db.update_user(user.user_id, last_book_received_date=date.today().isoformat())
            elif not reuse:
                db.update_article(article.id, status=db.FAILED, error='EPUB too large for Telegram')
            await progress.react(REACT_DONE if delivered else REACT_FAILED)
            logger.info(f"Delivered '{book.title}' to {who(tg_user)} via {sorted(delivered)}")
            if delivered:
                preview = ' (preview)' if book.is_preview else ''
                await notify_admin(bot, f"📚 {escape(book.title)}{preview} → {escape(who(tg_user))} "
                                        f"via {', '.join(sorted(delivered))}")
            return Result(article.id, delivered)

        except ScraperError as e:
            # Blocked sites, paywalls, timeouts, pages without article text: the message explains it
            logger.warning(f"Could not process URL {url}: {e}")
            key = ('err_blocked' if isinstance(e, BlockedError)
                   else 'err_extract' if isinstance(e, ExtractionError) else 'err_fetch')
            await _fail(progress, lang, article, url, key, e, keep_status=reuse)
        except EmailError as e:
            logger.error(f"Could not email {url} to {who(tg_user)}: {e}")
            await _fail(progress, lang, article, url, 'err_email', e, keep_status=reuse, detail=False)
            await notify_admin(bot, error_report(tg_user, url, e))
        except Exception as e:
            logger.exception(f"Error processing URL {url}")
            await _fail(progress, lang, article, url, 'err_unknown', e, keep_status=reuse, detail=False)
            await notify_admin(bot, error_report(tg_user, url, e))
        return Result(article.id, delivered)


async def _fail(progress: Progress, lang: str, article: db.Article, url: str, key: str, error: Exception,
                *, keep_status: bool, detail: bool = True) -> None:
    if not keep_status:
        db.update_article(article.id, status=db.FAILED, error=str(error)[:500])
    text = progress.source + t(lang, key)
    if detail and str(error):
        text += f"\n<blockquote expandable>{escape(str(error))}</blockquote>"
    try:
        await progress.finish(text, keyboards.error_card(lang, article.id, url))
    except TelegramError as e:
        logger.warning(f"Could not show the error card: {e}")
    await progress.react(REACT_FAILED)


async def send_test_book(bot: Bot, user: db.User, lang: str) -> None:
    """Email a one-page book to the user's Kindle. Raises EmailError when the mail server refuses it."""
    article = WebArticle(
        # A unique URL gives every test book its own EPUB identifier, so Kindle never skips it as a duplicate
        url=f"https://t.me/{bot.username}#test-{user.user_id}-{int(db.utcnow().timestamp())}",
        title=t(lang, 'test_book_title'),
        author=bot.first_name,
        published_at=date.today().isoformat(),
        content=t(lang, 'test_book_body', bot=bot.username),
        language=lang,
    )
    epub_path = await asyncio.to_thread(convert_to_epub, article)
    await asyncio.to_thread(send_email, user.kindle_email, epub_path)
