"""
Settings read from the environment (.env).
"""

import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')
# The address books are mailed from; users must approve it at Amazon
SENDER_EMAIL = os.getenv('EMAIL_FROM') or ''

# 🎉 confetti, shown when the test book arrived (message effects only work in private chats)
CONFETTI_EFFECT_ID = '5046509860389126442'

# Telegram's limit for files sent by bots through the public Bot API
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Amazon store per Telegram app language, for the "Personal Document Settings" link
AMAZON_DOMAINS = {
    'de': 'amazon.de', 'fr': 'amazon.fr', 'es': 'amazon.es', 'it': 'amazon.it', 'nl': 'amazon.nl',
    'ja': 'amazon.co.jp', 'en-gb': 'amazon.co.uk',
}


def amazon_settings_url(language_code: str | None) -> str:
    code = (language_code or '').lower()
    domain = AMAZON_DOMAINS.get(code) or AMAZON_DOMAINS.get(code.split('-')[0], 'amazon.com')
    return f'https://www.{domain}/hz/mycd/myx#/home/settings/payment'
