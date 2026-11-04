"""
Kindle setup in three steps: address → approve the sender at Amazon → test book.
A PocketBook (@pbsync.com) address takes the same steps with its own wording: PocketBook has no
sender list, it emails its owner to confirm a new sender when the first book arrives.
"""

import logging

from telegram import ForceReply, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from core import db
from core.kindle import (AMAZON_STORES, POCKETBOOK, amazon_devices_url, amazon_store, device_of, is_device_email, looks_like_email,
                         normalize_email)

from .. import delivery, keyboards
from ..config import CONFETTI_EFFECT_ID, SENDER_EMAIL, amazon_settings_url
from ..texts import for_device, t
from . import user_and_lang

logger = logging.getLogger(__name__)

AWAITING_EMAIL = 'awaiting_email'
PENDING_ARTICLE = 'pending_article'  # sent to the chat before the Kindle was set up


def email_prompt(lang: str) -> ForceReply:
    return ForceReply(input_field_placeholder=t(lang, 'email_placeholder'))


async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 1: ask for the Kindle address. The answer arrives as a normal message (see messages.py)."""
    user, lang = user_and_lang(update)
    context.user_data[AWAITING_EMAIL] = True
    text = (t(lang, 'setup_step1_current', email=user.kindle_email) if user.kindle_email
            else t(lang, 'setup_step1', url=amazon_devices_url(chosen=user_store(update, user))))
    await context.bot.send_message(update.effective_chat.id, text, reply_markup=email_prompt(lang))


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Validate and save the Kindle (or PocketBook) address, then show step 2."""
    user, lang = user_and_lang(update)
    email = normalize_email(text)
    if not is_device_email(email):
        context.user_data[AWAITING_EMAIL] = True
        key = 'email_not_kindle' if looks_like_email(email) else 'email_invalid'
        url = amazon_devices_url(chosen=user_store(update, user))
        await update.message.reply_text(t(lang, key, email=email, url=url), reply_markup=email_prompt(lang))
        return

    context.user_data.pop(AWAITING_EMAIL, None)
    db.update_user(user.user_id, kindle_email=email,
                   # Setting a Kindle address means "deliver to my Kindle" (unless they already chose both)
                   delivery_mode=db.BOTH if user.delivery_mode == db.BOTH else db.KINDLE,
                   setup_verified=user.setup_verified if email == user.kindle_email else 0)
    logger.info(f"User {user.user_id} set their {device_of(email)} address")
    await update.message.reply_text(
        t(lang, for_device('setup_step2', email), email=email, sender=SENDER_EMAIL or '—'),
        reply_markup=keyboards.setup_sender(lang, SENDER_EMAIL, sender_settings_url(update, user, email)))


def user_store(update: Update, user: db.User) -> str:
    """The Amazon store the user picked, else a guess from their Telegram and bot language."""
    return amazon_store(update.effective_user.language_code, user.language, chosen=user.amazon_store)


def amazon_url(update: Update, user: db.User) -> str:
    return amazon_settings_url(chosen=user_store(update, user))


def sender_settings_url(update: Update, user: db.User, address: str | None) -> str | None:
    """Where to approve the sender: Amazon's settings, or None for a PocketBook (it asks by email)."""
    if device_of(address) == POCKETBOOK:
        return None
    return amazon_url(update, user)


def step_keyboard(update: Update, user: db.User, lang: str, where: str):
    """The keyboard the store picker was opened from, with links to the (new) store."""
    url = sender_settings_url(update, user, user.kindle_email)
    if where == keyboards.STORE_TROUBLESHOOT:
        return keyboards.troubleshoot(lang, SENDER_EMAIL, url)
    return keyboards.setup_sender(lang, SENDER_EMAIL, url)


async def on_store_button(update: Update, user: db.User, lang: str) -> None:
    """'setup:store:<where>' opens the picker; '...:<store>' saves that store, '...:back' closes it."""
    query = update.callback_query
    parts = query.data.split(':')
    where = parts[2] if len(parts) > 2 else keyboards.STORE_STEP2
    choice = parts[3] if len(parts) > 3 else None
    if choice is None:
        await query.answer()
        markup = keyboards.store_picker(lang, user_store(update, user), keyboards.setup_store(where),
                                        keyboards.setup_store(where, 'back'))
    else:
        if choice in AMAZON_STORES:
            user = db.update_user(user.user_id, amazon_store=choice)
            await query.answer(t(lang, 'toast_saved'))
        else:
            await query.answer()
        markup = step_keyboard(update, user, lang, where)
    try:
        await query.edit_message_reply_markup(markup)
    except BadRequest as e:
        if 'not modified' not in str(e).lower():
            raise


async def run_test(update: Update, context: ContextTypes.DEFAULT_TYPE, user: db.User, lang: str) -> None:
    """Send the test book, showing progress and the "did it arrive?" question in one message."""
    message = await context.bot.send_message(update.effective_chat.id,
                                             t(lang, 'test_sending', email=user.kindle_email))
    try:
        await delivery.send_test_book(context.bot, user, lang)
    except Exception as e:
        logger.exception(f"Test book for user {user.user_id} failed")
        await message.edit_text(t(lang, 'test_failed'), reply_markup=keyboards.test_retry(lang))
        await delivery.notify_admin(context.bot, delivery.error_report(update.effective_user, 'test book', e))
        return
    await message.edit_text(t(lang, for_device('test_sent', user.kindle_email), email=user.kindle_email),
                            reply_markup=keyboards.test_result(lang))


async def offer_pending(context: ContextTypes.DEFAULT_TYPE, chat_id: int, lang: str,
                        address: str | None) -> None:
    """After setup: offer to send the book they got in the chat before to their Kindle as well."""
    article_id = context.user_data.pop(PENDING_ARTICLE, None)
    article = db.get_article(article_id) if article_id else None
    if article and article.status in db.DELIVERED:
        await context.bot.send_message(chat_id, t(lang, for_device('offer_pending', address), title=article.title),
                                       reply_markup=keyboards.send_to_kindle(lang, article.id, address))


async def remove_buttons(update: Update) -> None:
    try:
        await update.callback_query.edit_message_reply_markup(None)
    except BadRequest:
        pass


async def on_setup_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user, lang = user_and_lang(update)
    chat_id = update.effective_chat.id

    if query.data.startswith('setup:store'):
        await on_store_button(update, user, lang)

    elif query.data == keyboards.SETUP_START:
        await query.answer()
        await ask_email(update, context)

    elif query.data == keyboards.SETUP_EPUB:
        db.update_user(user.user_id, delivery_mode=db.TELEGRAM)
        await query.answer(t(lang, 'toast_saved'))
        await query.edit_message_text(t(lang, 'epub_only_set'))

    elif query.data == keyboards.SETUP_ADDED:
        await query.answer()
        if not user.kindle_email:
            await ask_email(update, context)
            return
        await query.edit_message_text(t(lang, for_device('setup_step3', user.kindle_email), email=user.kindle_email),
                                      reply_markup=keyboards.setup_test(lang))

    elif query.data == keyboards.SETUP_TEST:
        if not user.kindle_email:
            await query.answer(t(lang, 'test_no_email'))
            await ask_email(update, context)
            return
        await query.answer()
        await remove_buttons(update)  # no second test from the same message while this one runs
        await run_test(update, context, user, lang)

    elif query.data == keyboards.SETUP_YES:
        db.update_user(user.user_id, setup_verified=1)
        await query.answer()
        await query.edit_message_text(t(lang, 'test_arrived'))
        done = t(lang, for_device('setup_done', user.kindle_email))
        try:
            await context.bot.send_message(chat_id, done, message_effect_id=CONFETTI_EFFECT_ID)
        except TelegramError:
            await context.bot.send_message(chat_id, done)
        await offer_pending(context, chat_id, lang, user.kindle_email)

    elif query.data == keyboards.SETUP_NO:
        await query.answer()
        await query.edit_message_text(
            t(lang, for_device('troubleshoot', user.kindle_email), sender=SENDER_EMAIL or '—',
              email=user.kindle_email or '—'),
            reply_markup=keyboards.troubleshoot(lang, SENDER_EMAIL, sender_settings_url(update, user, user.kindle_email)))

    elif query.data == keyboards.SETUP_SKIP:
        await query.answer()
        await query.edit_message_text(t(lang, for_device('setup_skipped', user.kindle_email)))
        await offer_pending(context, chat_id, lang, user.kindle_email)

    else:
        await query.answer()
