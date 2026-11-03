"""
Kindle setup in three steps: address → approve the sender at Amazon → test book.
"""

import logging

from telegram import ForceReply, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from core import db
from core.kindle import is_kindle_email, looks_like_email, normalize_email

from .. import delivery, keyboards
from ..config import CONFETTI_EFFECT_ID, SENDER_EMAIL, amazon_settings_url
from ..texts import t
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
            else t(lang, 'setup_step1'))
    await context.bot.send_message(update.effective_chat.id, text, reply_markup=email_prompt(lang))


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Validate and save the Kindle address, then show step 2."""
    user, lang = user_and_lang(update)
    email = normalize_email(text)
    if not is_kindle_email(email):
        context.user_data[AWAITING_EMAIL] = True
        key = 'email_not_kindle' if looks_like_email(email) else 'email_invalid'
        await update.message.reply_text(t(lang, key, email=email), reply_markup=email_prompt(lang))
        return

    context.user_data.pop(AWAITING_EMAIL, None)
    db.update_user(user.user_id, kindle_email=email,
                   # Setting a Kindle address means "deliver to my Kindle" (unless they already chose both)
                   delivery_mode=db.BOTH if user.delivery_mode == db.BOTH else db.KINDLE,
                   setup_verified=user.setup_verified if email == user.kindle_email else 0)
    logger.info(f"User {user.user_id} set their Kindle address")
    await update.message.reply_text(
        t(lang, 'setup_step2', email=email, sender=SENDER_EMAIL or '—'),
        reply_markup=keyboards.setup_sender(lang, SENDER_EMAIL, sender_settings_url(update)))


def sender_settings_url(update: Update) -> str:
    return amazon_settings_url(update.effective_user.language_code)


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
    await message.edit_text(t(lang, 'test_sent', email=user.kindle_email),
                            reply_markup=keyboards.test_result(lang))


async def offer_pending(context: ContextTypes.DEFAULT_TYPE, chat_id: int, lang: str) -> None:
    """After setup: offer to send the book they got in the chat before to their Kindle as well."""
    article_id = context.user_data.pop(PENDING_ARTICLE, None)
    article = db.get_article(article_id) if article_id else None
    if article and article.status in db.DELIVERED:
        await context.bot.send_message(chat_id, t(lang, 'offer_pending', title=article.title),
                                       reply_markup=keyboards.send_to_kindle(lang, article.id))


async def remove_buttons(update: Update) -> None:
    try:
        await update.callback_query.edit_message_reply_markup(None)
    except BadRequest:
        pass


async def on_setup_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user, lang = user_and_lang(update)
    chat_id = update.effective_chat.id

    if query.data == keyboards.SETUP_START:
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
        await query.edit_message_text(t(lang, 'setup_step3', email=user.kindle_email),
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
        try:
            await context.bot.send_message(chat_id, t(lang, 'setup_done'), message_effect_id=CONFETTI_EFFECT_ID)
        except TelegramError:
            await context.bot.send_message(chat_id, t(lang, 'setup_done'))
        await offer_pending(context, chat_id, lang)

    elif query.data == keyboards.SETUP_NO:
        await query.answer()
        await query.edit_message_text(
            t(lang, 'troubleshoot', sender=SENDER_EMAIL or '—', email=user.kindle_email or '—'),
            reply_markup=keyboards.troubleshoot(lang, SENDER_EMAIL, sender_settings_url(update)))

    elif query.data == keyboards.SETUP_SKIP:
        await query.answer()
        await query.edit_message_text(t(lang, 'setup_skipped'))
        await offer_pending(context, chat_id, lang)

    else:
        await query.answer()
