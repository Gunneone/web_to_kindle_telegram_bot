"""
Settings read from the environment (.env).
"""

import os

from dotenv import load_dotenv

from core.kindle import amazon_settings_url, sender_email  # noqa: F401  (re-exported for the handlers)

load_dotenv()

TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')
# The address books are mailed from; users must approve it at Amazon
SENDER_EMAIL = sender_email()

# 🎉 confetti, shown when the test book arrived (message effects only work in private chats)
CONFETTI_EFFECT_ID = '5046509860389126442'

# Telegram's limit for files sent by bots through the public Bot API
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
