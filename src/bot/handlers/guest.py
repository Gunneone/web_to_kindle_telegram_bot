"""
Guest mode (Bot API 10.0): in any chat, a user replies to a message with a link and mentions the bot.
The bot answers there once, without any personal details, and delivers the book via the user's
private chat with the bot, where the usual progress and result card appear.
"""

import asyncio
import logging
from uuid import uuid4

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ContextTypes

from .. import db, delivery, keyboards
from ..links import MAX_LINKS, extract_urls
from ..texts import resolve_lang, t

logger = logging.getLogger(__name__)


async def on_guest_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.guest_message
    caller = message.from_user
    if caller is None:
        return
    user = db.get_user(caller.id)  # only users who started the bot can get books in a private chat
    lang = resolve_lang(user, caller)
    urls = extract_urls(message)[:MAX_LINKS]

    markup = None
    if not urls:
        text = t(lang, 'guest_no_link')
    elif user is None:
        text = t(lang, 'guest_not_setup')
        markup = keyboards.guest_setup(lang, context.bot.username)
    else:
        text = t(lang, 'guest_sending', name=caller.first_name)
    await context.bot.answer_guest_query(
        message.guest_query_id,
        InlineQueryResultArticle(id=uuid4().hex, title=t(lang, 'guest_title'),
                                 input_message_content=InputTextMessageContent(text), reply_markup=markup))

    if urls and user is not None:
        logger.info(f"Guest request from user {caller.id} with {len(urls)} link(s)")
        await asyncio.gather(*(
            delivery.deliver(context.bot, caller, caller.id, url, react=False, show_source=True)
            for url in urls))
