"""
The bot's command menu and description, set on startup in every language so self-hosted bots
get them too. A user's own language choice in /settings switches their command menu as well.
"""

import logging

from telegram import Bot, BotCommand, BotCommandScopeChat
from telegram.error import TelegramError

from .texts import DEFAULT_LANGUAGE, LANGUAGES, t

logger = logging.getLogger(__name__)

COMMANDS = ('start', 'settings', 'history', 'help', 'privacy')


def commands(lang: str) -> list[BotCommand]:
    return [BotCommand(name, t(lang, f'cmd_{name}')) for name in COMMANDS]


async def setup_profile(application) -> None:
    """post_init hook: command menu, description and short description for each language."""
    bot: Bot = application.bot
    for lang in LANGUAGES:
        code = None if lang == DEFAULT_LANGUAGE else lang
        try:
            await bot.set_my_commands(commands(lang), language_code=code)
            description = t(lang, 'bot_description')
            if (await bot.get_my_description(language_code=code)).description != description:
                await bot.set_my_description(description, language_code=code)
            short = t(lang, 'bot_short_description')
            if (await bot.get_my_short_description(language_code=code)).short_description != short:
                await bot.set_my_short_description(short, language_code=code)
        except TelegramError as e:
            logger.warning(f"Could not set the bot profile for '{lang}': {e}")


async def set_chat_language(bot: Bot, chat_id: int, lang: str) -> None:
    try:
        await bot.set_my_commands(commands(lang), scope=BotCommandScopeChat(chat_id))
    except TelegramError as e:
        logger.warning(f"Could not set commands for chat {chat_id}: {e}")


async def reset_chat_language(bot: Bot, chat_id: int) -> None:
    try:
        await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id))
    except TelegramError as e:
        logger.warning(f"Could not reset commands for chat {chat_id}: {e}")
