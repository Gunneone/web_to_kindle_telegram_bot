"""
"Something is wrong with this book": a report to the admin in Telegram, sent through the bot's own
token, followed by the EPUB the person was looking at.
"""

import logging
import os
from html import escape

from telegram import Bot, LinkPreviewOptions, ReplyParameters
from telegram.constants import ParseMode
from telegram.error import TelegramError

from core import accounts, db

from .config import Settings
from .jobs import host

logger = logging.getLogger(__name__)

REASONS = ('text', 'images', 'layout', 'wrong', 'other')
REASON_LABELS = {
    'text': 'Text missing or cut off',
    'images': 'Images missing or broken',
    'layout': 'Formatting looks off',
    'wrong': 'Wrong content / page junk',
    'other': 'Something else',
}
MAX_MESSAGE = 1000
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024  # what the Bot API accepts from bots
UPLOAD_TIMEOUT = 60  # seconds; books with many images run to several MB


class FeedbackError(Exception):
    """Telegram didn't take the report."""


def who(user: db.User) -> str:
    name = ' '.join(filter(None, [user.first_name, user.last_name])) or None
    parts = [name, f'@{user.username}' if user.username else None, accounts.email_of(user.user_id)]
    providers = sorted({i.provider for i in accounts.identities(user.user_id)})
    label = ' · '.join(escape(p) for p in parts if p) or 'someone'
    return f"{label} (id {user.user_id}{', ' + ', '.join(providers) if providers else ''})"


def report_text(user: db.User, article: db.Article, reasons: list[str], message: str) -> str:
    url = article.article_url or ''
    lines = [
        '📝 <b>Feedback on a preview</b>',
        f'<b>{escape(article.title or host(url))}</b>',
        f'<a href="{escape(url, quote=True)}">{escape(host(url))}</a> · book #{article.id}',
        f'From {who(user)}',
    ]
    if reasons:
        lines += ['', *(f'• {escape(REASON_LABELS.get(r, r))}' for r in reasons)]
    if message:
        lines += ['', f'<blockquote expandable>{escape(message)}</blockquote>']
    return '\n'.join(lines)[:4096]


async def send(settings: Settings, user: db.User, article: db.Article, reasons: list[str], message: str,
               filename: str) -> None:
    """Message the admin, then attach the EPUB. Raises FeedbackError when Telegram refuses."""
    text = report_text(user, article, reasons, message)
    path = article.epub_path
    try:
        async with Bot(settings.telegram_token) as bot:
            sent = await bot.send_message(settings.admin_id, text, parse_mode=ParseMode.HTML,
                                          link_preview_options=LinkPreviewOptions(is_disabled=True))
            if path and os.path.exists(path) and os.path.getsize(path) <= MAX_DOCUMENT_BYTES:
                # The report is in: a failed upload shouldn't make the person send it again
                try:
                    with open(path, 'rb') as file:
                        await bot.send_document(settings.admin_id, file, filename=filename,
                                                write_timeout=UPLOAD_TIMEOUT, read_timeout=UPLOAD_TIMEOUT,
                                                reply_parameters=ReplyParameters(sent.message_id,
                                                                                 allow_sending_without_reply=True))
                except TelegramError as e:
                    logger.warning(f'Could not attach the EPUB to the feedback on book {article.id}: {e!r}')
    except TelegramError as e:
        logger.error(f'Could not send feedback on book {article.id} to the admin: {e!r}')
        raise FeedbackError(str(e)) from e
    logger.info(f'Feedback on book {article.id} from user {user.user_id} sent to the admin')
