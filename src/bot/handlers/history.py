"""
/history: the user's recent books, five per page, with a button per book to send it again.
"""

from html import escape

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from core import db
from core.pipeline import host

from .. import keyboards
from ..texts import format_date, t
from . import user_and_lang

STATUS_ICONS = {db.SENT: '✅', db.PREVIEW: '🔒', db.FAILED: '❌', db.PROCESSING: '⏳', None: '✅'}
MAX_TITLE = 70


def render(user_id: int, lang: str, offset: int = 0):
    articles, total = db.history(user_id, offset, keyboards.HISTORY_PAGE_SIZE)
    if not articles and total:  # the page emptied (data deleted meanwhile): show the last one
        offset = max(0, (total - 1) // keyboards.HISTORY_PAGE_SIZE * keyboards.HISTORY_PAGE_SIZE)
        articles, total = db.history(user_id, offset, keyboards.HISTORY_PAGE_SIZE)
    if not articles:
        return t(lang, 'history_empty'), None

    lines = [t(lang, 'history_title', start=offset + 1, end=offset + len(articles), total=total), '']
    for number, article in enumerate(articles, offset + 1):
        title = article.title or host(article.article_url)
        if len(title) > MAX_TITLE:
            title = title[:MAX_TITLE - 1] + '…'
        icon = STATUS_ICONS.get(article.status, '✅')
        lines.append(f'{number}. {icon} <a href="{escape(article.article_url, quote=True)}">{escape(title)}</a>'
                     f' · {format_date(lang, article.timestamp)}')
    lines += ['', t(lang, 'history_hint')]
    return '\n'.join(lines), keyboards.history(articles, offset, total)


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, lang = user_and_lang(update)
    text, markup = render(user.user_id, lang)
    await update.message.reply_text(text, reply_markup=markup)


async def on_history_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user, lang = user_and_lang(update)
    await query.answer()
    try:
        offset = max(0, int(query.data.removeprefix('hist:')))
    except ValueError:
        return
    text, markup = render(user.user_id, lang, offset)
    try:
        await query.edit_message_text(text, reply_markup=markup)
    except BadRequest as e:
        if 'not modified' not in str(e).lower():
            raise
