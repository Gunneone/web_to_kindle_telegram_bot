"""
Wiring: handlers, defaults and startup.
"""

import logging
import traceback
from html import escape

from telegram import LinkPreviewOptions, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes, Defaults,
                          MessageHandler, filters)

from core import db

from . import delivery, profile
from .config import TOKEN
from .handlers import articles, guest, history, messages, onboarding, settings, start

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)  # one INFO line per long-poll request otherwise
logger = logging.getLogger(__name__)

# Normal messages in the bot's private chat. Guest messages (from chats the bot isn't in) also carry
# chat and text, so every private-chat handler excludes them explicitly.
PRIVATE = filters.UpdateType.MESSAGE & filters.ChatType.PRIVATE

ALLOWED_UPDATES = [Update.MESSAGE, Update.CALLBACK_QUERY, Update.GUEST_MESSAGE]


def is_transient(error: BaseException | None) -> bool:
    """Connection drops and timeouts talking to Telegram; the library retries these on its own.
    BadRequest subclasses NetworkError too, but it means our request was wrong, so it isn't one."""
    return isinstance(error, NetworkError) and not isinstance(error, BadRequest)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_transient(context.error):
        logger.warning("Transient network error: %s", context.error)
        return
    logger.error("Unhandled error", exc_info=context.error)
    trace = ''.join(traceback.format_exception(context.error))[-3000:]
    await delivery.notify_admin(context.bot, f"💥 <b>Unhandled error</b>\n"
                                             f"<blockquote expandable>{escape(trace)}</blockquote>")


def build_application(token: str = TOKEN) -> Application:
    defaults = Defaults(parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
    application = (Application.builder().token(token).defaults(defaults)
                   # Each article takes seconds to minutes; don't make other users wait for it
                   .concurrent_updates(True)
                   .post_init(profile.setup_profile)
                   .build())

    commands = {
        'start': start.start,
        'help': start.help_command,
        'privacy': start.privacy,
        'cancel': start.cancel,
        'settings': settings.show,
        'history': history.show,
        'send': messages.send_command,
        # Commands from earlier versions, no longer in the menu
        'config': onboarding.ask_email,
        'imagelinks': settings.toggle_image_links,
        'delete': settings.confirm_delete,
    }
    for name, callback in commands.items():
        application.add_handler(CommandHandler(name, callback, filters=PRIVATE))

    application.add_handler(CallbackQueryHandler(onboarding.on_setup_button, pattern=r'^setup:'))
    application.add_handler(CallbackQueryHandler(settings.on_settings_button, pattern=r'^set:'))
    application.add_handler(CallbackQueryHandler(start.on_help_button, pattern=r'^help:'))
    application.add_handler(CallbackQueryHandler(articles.on_article_button, pattern=r'^art:'))
    application.add_handler(CallbackQueryHandler(history.on_history_button, pattern=r'^hist:'))

    application.add_handler(MessageHandler(filters.UpdateType.GUEST_MESSAGE, guest.on_guest_message))
    application.add_handler(MessageHandler(PRIVATE & (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
                                           messages.on_message))
    application.add_error_handler(on_error)
    return application


def main() -> None:
    db.init_db()
    build_application().run_polling(allowed_updates=ALLOWED_UPDATES)
