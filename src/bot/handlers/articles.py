"""
Buttons on result cards, error cards, duplicate notices and the history list.
"""

from telegram import Update
from telegram.ext import ContextTypes

from .. import db, delivery
from ..texts import t
from . import onboarding, user_and_lang

TARGETS = {'kindle': {db.KINDLE}, 'file': {db.TELEGRAM}}  # 'again' and 'retry' use the user's setting


async def on_article_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user, lang = user_and_lang(update)
    try:
        _, action, raw_id = query.data.split(':')
        article = db.get_article(int(raw_id))
    except ValueError:
        article = None
    if not article or article.user_id != user.user_id:
        await query.answer(t(lang, 'article_gone'), show_alert=True)
        return
    if action == 'kindle' and not user.kindle_email:
        await query.answer(t(lang, 'toast_need_email'))
        await onboarding.ask_email(update, context)
        return
    await query.answer()

    message = query.message
    retry_in_place = action == 'retry'  # error cards and duplicate notices turn into the new status message
    original = message.reply_to_message.message_id if message.reply_to_message else None
    await delivery.deliver(
        context.bot, update.effective_user, message.chat_id, article.article_url,
        reply_to_id=original if retry_in_place else message.message_id,
        targets=TARGETS.get(action), article_id=article.id, force=True,
        react=False, show_source=True, status_message=message if retry_in_place else None)
