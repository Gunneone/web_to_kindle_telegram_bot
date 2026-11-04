"""
/start (with deep links), /help, /privacy and /cancel.
"""

from telegram import Update
from telegram.ext import ContextTypes

from core import db

from .. import keyboards
from ..config import SENDER_EMAIL
from ..links import MAX_LINKS
from ..texts import for_device, t
from . import onboarding, settings, user_and_lang

TARGET_TEXTS = {frozenset({db.KINDLE}): 'target_kindle', frozenset({db.TELEGRAM}): 'target_telegram',
                frozenset({db.KINDLE, db.TELEGRAM}): 'target_both'}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deep links t.me/<bot>?start=setup|settings|help open that screen; otherwise greet by setup state."""
    payload = context.args[0].lower() if context.args else ''
    if payload == 'setup':
        await onboarding.ask_email(update, context)
        return
    if payload == 'settings':
        await settings.show(update, context)
        return
    if payload == 'help':
        await help_command(update, context)
        return

    user, lang = user_and_lang(update)
    if user.kindle_email or user.chose_chat_only:
        target = t(lang, for_device(TARGET_TEXTS[frozenset(user.targets)], user.kindle_email))
        await update.message.reply_text(t(lang, 'start_ready', target=target),
                                        reply_markup=keyboards.start_ready(lang))
    else:
        await update.message.reply_text(t(lang, 'start_new', name=update.effective_user.first_name),
                                        reply_markup=keyboards.start_new(lang))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, lang = user_and_lang(update)
    await context.bot.send_message(
        update.effective_chat.id,
        t(lang, 'help', max=MAX_LINKS, bot=context.bot.username, sender=SENDER_EMAIL or '—'))


async def on_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await help_command(update, context)


async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, lang = user_and_lang(update)
    await update.message.reply_text(t(lang, 'privacy'), reply_markup=keyboards.privacy(lang))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, lang = user_and_lang(update)
    context.user_data.pop(onboarding.AWAITING_EMAIL, None)
    await update.message.reply_text(t(lang, 'cancelled'))
