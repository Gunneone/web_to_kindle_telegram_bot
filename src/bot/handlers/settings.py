"""
The settings panel: one message that is edited in place on every tap.
"""

import logging
from html import escape

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from .. import db, keyboards, profile
from ..texts import LANGUAGE_NAMES, LANGUAGES, Raw, t
from . import onboarding, user_and_lang

logger = logging.getLogger(__name__)


def render(user: db.User, lang: str):
    email = Raw(f"<code>{escape(user.kindle_email)}</code>") if user.kindle_email else Raw(t(lang, 'not_set'))
    targets = user.targets
    mode = db.BOTH if len(targets) == 2 else next(iter(targets))
    text = t(lang, 'settings', email=email, delivery=t(lang, f'delivery_{mode}'),
             links=t(lang, 'on' if user.image_links else 'off'), language=LANGUAGE_NAMES[lang])
    return text, keyboards.settings(lang, user)


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, lang = user_and_lang(update)
    text, markup = render(user, lang)
    await context.bot.send_message(update.effective_chat.id, text, reply_markup=markup)


async def toggle_image_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/imagelinks (kept from earlier versions): toggle, then show the panel."""
    user, _ = user_and_lang(update)
    db.update_user(user.user_id, preserve_image_links=0 if user.image_links else 1)
    await show(update, context)


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/delete (kept from earlier versions): ask before deleting everything."""
    _, lang = user_and_lang(update)
    await context.bot.send_message(update.effective_chat.id, t(lang, 'delete_confirm'),
                                   reply_markup=keyboards.delete_confirm(lang))


async def on_settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user, lang = user_and_lang(update)
    data = query.data
    toast = None

    if data.startswith('set:mode:'):
        mode = data.removeprefix('set:mode:')
        if mode not in db.DELIVERY_MODES:
            await query.answer()
            return
        if mode != db.TELEGRAM and not user.kindle_email:
            await query.answer(t(lang, 'toast_need_email'))
            await onboarding.ask_email(update, context)
            return
        user = db.update_user(user.user_id, delivery_mode=mode)
        toast = t(lang, 'toast_saved')

    elif data == keyboards.SET_LINKS:
        user = db.update_user(user.user_id, preserve_image_links=0 if user.image_links else 1)
        toast = t(lang, 'toast_saved')

    elif data.startswith('set:lang:'):
        new_lang = data.removeprefix('set:lang:')
        if new_lang in LANGUAGES:
            user = db.update_user(user.user_id, language=new_lang)
            lang = new_lang
            await profile.set_chat_language(context.bot, update.effective_chat.id, lang)
            toast = t(lang, 'toast_saved')

    elif data == keyboards.SET_TEST:
        await query.answer()
        if not user.kindle_email:
            await onboarding.ask_email(update, context)
            return
        await onboarding.run_test(update, context, user, lang)
        return

    elif data == keyboards.SET_DELETE:
        await query.answer()
        await query.edit_message_text(t(lang, 'delete_confirm'), reply_markup=keyboards.delete_confirm(lang))
        return

    elif data == keyboards.SET_DELETE_YES:
        db.delete_user_data(user.user_id)
        context.user_data.clear()
        await profile.reset_chat_language(context.bot, update.effective_chat.id)
        logger.info(f"User {user.user_id} deleted their data")
        await query.answer()
        await query.edit_message_text(t(lang, 'deleted'))
        return

    await query.answer(toast)
    text, markup = render(user, lang)
    try:
        await query.edit_message_text(text, reply_markup=markup)
    except BadRequest as e:
        if 'not modified' not in str(e).lower():
            raise
