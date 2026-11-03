"""
Telegram update handlers, grouped by screen.
"""

from telegram import Update

from .. import db
from ..texts import resolve_lang


def user_and_lang(update: Update) -> tuple[db.User, str]:
    """The user's database row (created on first contact) and the language to answer in."""
    tg_user = update.effective_user
    user = db.upsert_user(tg_user)
    return user, resolve_lang(user, tg_user)
