"""
The Telegram side of delivering a book: reactions on the user's message, one status message that
is edited step by step and ends as the result card (or an error card with a retry button).
The work itself (fetching, building, mailing, history) is in core.pipeline.
"""

import logging
import os
import traceback
from datetime import date
from html import escape

from telegram import Bot, Message, ReplyParameters
from telegram.error import BadRequest, TelegramError

from core import db, pipeline
from core.pipeline import Book, Failure, Outcome, Stage, host
from web_scraper import Article as WebArticle

from . import keyboards
from .config import ADMIN_ID, MAX_UPLOAD_BYTES
from .texts import for_device, format_date, format_size, resolve_lang, t

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 200

REACT_RECEIVED = '👀'
REACT_WORKING = '✍'
REACT_DONE = '👌'
REACT_FAILED = '💔'

STATUS_TEXTS = {Stage.QUEUED: 'status_queued', Stage.FETCHING: 'status_fetching',
                Stage.BUILDING: 'status_building', Stage.SENDING: 'status_sending'}
ERROR_TEXTS = {Failure.BLOCKED: 'err_blocked', Failure.EXTRACT: 'err_extract', Failure.FETCH: 'err_fetch',
               Failure.EMAIL: 'err_email', Failure.UNKNOWN: 'err_unknown'}


def upsert_user(tg_user) -> db.User:
    """The user's row, created on first contact, with their Telegram name kept current."""
    return db.upsert_user(tg_user.id, username=tg_user.username, first_name=tg_user.first_name,
                          last_name=tg_user.last_name)


def who(tg_user) -> str:
    return f"@{tg_user.username}" if tg_user.username else f"{tg_user.first_name} ({tg_user.id})"


def reply_to(message_id: int | None) -> ReplyParameters | None:
    return ReplyParameters(message_id, allow_sending_without_reply=True) if message_id else None


def card_text(lang: str, book: Book, delivered: set[str], address: str | None = None) -> str:
    """The caption of a delivered book; `address` is the reader it was mailed to (Kindle or PocketBook)."""
    title = book.title if len(book.title) <= MAX_TITLE_LENGTH else book.title[:MAX_TITLE_LENGTH - 1] + '…'
    lines = [f"📚 <b>{escape(title)}</b>"]
    byline = [t(lang, 'card_by', author=book.author)] if book.author else []
    if book.publication and book.publication != book.author:
        byline.append(escape(book.publication))
    if byline:
        lines.append(' · '.join(byline))
    stats = []
    if book.read_minutes:
        stats.append(t(lang, 'card_read_time', minutes=book.read_minutes))
    size = book.size
    if size is not None:
        stats.append(format_size(lang, size))
    if stats:
        lines.append(' · '.join(stats))
    if book.is_preview:
        lines += ['', t(lang, 'card_preview')]
    if db.KINDLE in delivered:
        lines += ['', t(lang, for_device('footer_both' if db.TELEGRAM in delivered else 'footer_kindle', address))]
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


class Chat(pipeline.Frontend):
    """A delivery followed in a Telegram chat; the EPUB file arrives there as a document."""

    max_file_bytes = MAX_UPLOAD_BYTES

    def __init__(self, bot: Bot, user: db.User, lang: str, chat_id: int, progress: Progress,
                 reply_to_id: int | None):
        self.bot = bot
        self.user = user
        self.lang = lang
        self.chat_id = chat_id
        self.progress = progress
        self.reply_to_id = reply_to_id

    async def stage(self, stage: Stage, article: db.Article) -> None:
        if stage == Stage.RECEIVED:
            await self.progress.react(REACT_RECEIVED)
            return
        await self.progress.show(for_device(STATUS_TEXTS[stage], self.user.kindle_email))
        if stage == Stage.BUILDING:
            await self.progress.react(REACT_WORKING)

    async def deliver_file(self, article: db.Article, book: Book, delivered: set[str]) -> None:
        await self.progress.show('status_uploading')
        delivered = delivered | {db.TELEGRAM}
        with open(book.epub_path, 'rb') as document:
            await self.bot.send_document(
                self.chat_id, document, filename=os.path.basename(book.epub_path),
                caption=card_text(self.lang, book, delivered, self.user.kindle_email),
                reply_markup=keyboards.result_card(self.lang, article.id, book.url, delivered, self.user,
                                                   book.is_preview),
                reply_parameters=reply_to(self.reply_to_id))
        await self.progress.remove()


async def deliver(bot: Bot, tg_user, chat_id: int, url: str, *, reply_to_id: int | None = None,
                  targets: set[str] | None = None, article_id: int | None = None, force: bool = False,
                  react: bool = True, show_source: bool = False, status_message: Message | None = None) -> Outcome:
    """
    Deliver the article at `url` (see core.pipeline.run) and show it in this chat.

    targets, article_id, force: as in core.pipeline.run
    react:          show progress as reactions on the message `reply_to_id` (the user's link message)
    show_source:    start the status message with the link (when it isn't a reply to the link itself)
    status_message: an existing bot message to turn into the status message (retry buttons)
    """
    user = upsert_user(tg_user)
    lang = resolve_lang(user, tg_user)
    progress = Progress(bot, chat_id, lang, url, reply_to_id=reply_to_id, react=react,
                        show_source=show_source, message=status_message)
    outcome = await pipeline.run(user, url, Chat(bot, user, lang, chat_id, progress, reply_to_id),
                                 targets=targets, article_id=article_id, force=force)

    if outcome.duplicate:
        previous = outcome.duplicate
        await bot.send_message(
            chat_id, t(lang, 'duplicate', title=previous.title or host(url),
                       date=format_date(lang, previous.timestamp)),
            reply_markup=keyboards.duplicate(lang, previous.id), reply_parameters=reply_to(reply_to_id))
    elif outcome.failure:
        await _show_error(progress, lang, outcome, url)
        if outcome.failure not in pipeline.USER_FACING:
            await notify_admin(bot, error_report(tg_user, url, outcome.error))
    else:
        await _show_result(progress, lang, user, url, outcome)
        if outcome.delivered:
            preview = ' (preview)' if outcome.book.is_preview else ''
            await notify_admin(bot, f"📚 {escape(outcome.book.title)}{preview} → {escape(who(tg_user))} "
                                    f"via {', '.join(sorted(outcome.delivered))}")
    return outcome


async def _show_result(progress: Progress, lang: str, user: db.User, url: str, outcome: Outcome) -> None:
    """The result card, unless the EPUB in the chat already is one."""
    book = outcome.book
    if progress.message is not None or not outcome.delivered:
        text = card_text(lang, book, outcome.delivered, user.kindle_email)
        offered = outcome.delivered
        if outcome.file_too_big:
            text += '\n\n' + t(lang, 'file_too_big', size=format_size(lang, outcome.file_too_big))
            offered = offered | {db.TELEGRAM}  # no "EPUB here" button when the file is too big for Telegram
        try:
            await progress.finish(text, keyboards.result_card(lang, outcome.article_id, url, offered, user,
                                                              book.is_preview))
        except TelegramError as e:
            logger.warning(f"Could not show the result card: {e}")
    await progress.react(REACT_DONE if outcome.delivered else REACT_FAILED)


async def _show_error(progress: Progress, lang: str, outcome: Outcome, url: str) -> None:
    text = progress.source + t(lang, ERROR_TEXTS[outcome.failure])
    if outcome.failure in pipeline.USER_FACING and str(outcome.error):
        text += f"\n<blockquote expandable>{escape(str(outcome.error))}</blockquote>"
    try:
        await progress.finish(text, keyboards.error_card(lang, outcome.article_id, url))
    except TelegramError as e:
        logger.warning(f"Could not show the error card: {e}")
    await progress.react(REACT_FAILED)


async def send_test_book(bot: Bot, user: db.User, lang: str) -> None:
    """Email a one-page book to the user's Kindle. Raises EmailError when the mail server refuses it."""
    article = WebArticle(
        # A unique URL gives every test book its own EPUB identifier, so Kindle never skips it as a duplicate
        url=f"https://t.me/{bot.username}#test-{user.user_id}-{int(db.utcnow().timestamp())}",
        title=t(lang, for_device('test_book_title', user.kindle_email)),
        author=bot.first_name,
        published_at=date.today().isoformat(),
        content=t(lang, 'test_book_body', bot=bot.username),
        language=lang,
    )
    await pipeline.email_article(article, user.kindle_email)
