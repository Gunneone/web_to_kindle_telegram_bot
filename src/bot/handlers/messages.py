"""
Everything users type or forward in the private chat: links get delivered, Kindle addresses saved.
"""

import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from core import db
from core.kindle import looks_like_email

from .. import delivery, keyboards
from ..links import MAX_LINKS, extract_urls
from ..texts import t
from . import onboarding, user_and_lang


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    text = (message.text or message.caption or '').strip()
    urls = extract_urls(message, bot_id=context.bot.id)
    if not urls and (context.user_data.get(onboarding.AWAITING_EMAIL) or looks_like_email(text)):
        await onboarding.handle_email(update, context, text)
        return
    if not urls:
        _, lang = user_and_lang(update)
        await message.reply_text(t(lang, 'no_link'), reply_markup=keyboards.start_ready(lang))
        return
    await deliver_all(update, context, urls)


async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/send <link>, or /send as a reply to a message with links."""
    urls = extract_urls(update.message, bot_id=context.bot.id)
    if not urls:
        _, lang = user_and_lang(update)
        await update.message.reply_text(t(lang, 'no_link'))
        return
    await deliver_all(update, context, urls)


async def deliver_all(update: Update, context: ContextTypes.DEFAULT_TYPE, urls: list[str]) -> None:
    message = update.message
    user, lang = user_and_lang(update)
    if len(urls) > MAX_LINKS:
        await message.reply_text(t(lang, 'too_many_links', count=len(urls), max=MAX_LINKS))
        urls = urls[:MAX_LINKS]

    single = len(urls) == 1
    if not single:
        await set_reaction(context, message, delivery.REACT_RECEIVED)
    # One status message per link, all threaded under the user's message; with several links each
    # status names its link, and the reaction on the message sums them up at the end
    results = await asyncio.gather(*(
        delivery.deliver(context.bot, update.effective_user, message.chat_id, url, reply_to_id=message.message_id,
                         react=single, show_source=not single)
        for url in urls))
    if not single:
        failed = any(not r.ok and r.article_id is not None and _failed(r.article_id) for r in results)
        await set_reaction(context, message, delivery.REACT_FAILED if failed else delivery.REACT_DONE)

    # Delivered to the chat because no Kindle is set up yet: offer it for the Kindle after setup
    user = db.get_user(user.user_id)
    in_chat_only = [r for r in results if r.delivered == {db.TELEGRAM}]
    if in_chat_only and user and not user.kindle_email and not user.chose_chat_only:
        context.user_data[onboarding.PENDING_ARTICLE] = in_chat_only[-1].article_id


def _failed(article_id: int) -> bool:
    article = db.get_article(article_id)
    return bool(article) and article.status == db.FAILED


async def set_reaction(context: ContextTypes.DEFAULT_TYPE, message, emoji: str) -> None:
    try:
        await context.bot.set_message_reaction(message.chat_id, message.message_id, emoji)
    except Exception:  # reactions are decoration; never fail a delivery over them
        pass
