"""
E-reader addresses. Kindle is the main target; PocketBook's Send-to-PocketBook (@pbsync.com) works the
same way (a book mailed as an attachment lands on the reader), so it is accepted too.

Every front end checks an address with `is_device_email` before saving it, so books are only mailed
to Amazon's Send-to-Kindle and PocketBook's Send-to-PocketBook domains. The only other mail the server
sends is the web app's fixed-template, rate-limited sign-in code, so it can't be used for anything else.
"""

import os
import re

KINDLE_EMAIL = re.compile(r'^[a-z0-9._%+-]+@(?:free\.)?kindle\.(?:com|cn)$')
POCKETBOOK_EMAIL = re.compile(r'^[a-z0-9._%+-]+@pbsync\.com$')
EMAIL_LIKE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def normalize_email(text: str) -> str:
    """' Name_AB12@Kindle.com ' / 'mailto:name@kindle.com' -> 'name_ab12@kindle.com'"""
    text = text.strip().strip('<>').strip()
    if text.lower().startswith('mailto:'):
        text = text[len('mailto:'):]
    return text.lower()


def looks_like_email(text: str | None) -> bool:
    """A single token with an @, i.e. something the user meant as an email address."""
    return bool(text) and bool(EMAIL_LIKE.match(normalize_email(text)))


def is_kindle_email(text: str | None) -> bool:
    return bool(text) and bool(KINDLE_EMAIL.match(normalize_email(text)))


def is_pocketbook_email(text: str | None) -> bool:
    return bool(text) and bool(POCKETBOOK_EMAIL.match(normalize_email(text)))


def is_device_email(text: str | None) -> bool:
    """An address books may be mailed to: Kindle, or PocketBook."""
    return is_kindle_email(text) or is_pocketbook_email(text)


KINDLE = 'kindle'
POCKETBOOK = 'pocketbook'


def device_of(address: str | None) -> str:
    """Which reader an address belongs to. Kindle unless it is clearly a PocketBook address."""
    return POCKETBOOK if is_pocketbook_email(address) else KINDLE


def sender_email() -> str:
    """The address books are mailed from; users must approve it at Amazon."""
    return os.getenv('EMAIL_FROM') or ''


# Amazon stores with Send-to-Kindle, in the order the store picker lists them
AMAZON_STORES = (
    'amazon.com', 'amazon.de', 'amazon.co.uk', 'amazon.fr', 'amazon.es', 'amazon.it', 'amazon.nl',
    'amazon.ca', 'amazon.com.au', 'amazon.co.jp', 'amazon.in', 'amazon.com.br', 'amazon.com.mx',
)
DEFAULT_STORE = 'amazon.com'

# Country -> the store its Kindle accounts live in (Austria and Switzerland use amazon.de, Ireland
# amazon.co.uk, New Zealand amazon.com.au)
REGION_STORES = {
    'US': 'amazon.com', 'DE': 'amazon.de', 'AT': 'amazon.de', 'CH': 'amazon.de', 'LI': 'amazon.de',
    'LU': 'amazon.de', 'GB': 'amazon.co.uk', 'IE': 'amazon.co.uk', 'FR': 'amazon.fr', 'ES': 'amazon.es',
    'IT': 'amazon.it', 'NL': 'amazon.nl', 'CA': 'amazon.ca', 'AU': 'amazon.com.au', 'NZ': 'amazon.com.au',
    'JP': 'amazon.co.jp', 'IN': 'amazon.in', 'BR': 'amazon.com.br', 'MX': 'amazon.com.mx',
}
# Language without a country -> store (English says nothing about where someone lives)
LANGUAGE_STORES = {'de': 'amazon.de', 'fr': 'amazon.fr', 'es': 'amazon.es', 'it': 'amazon.it',
                   'nl': 'amazon.nl', 'ja': 'amazon.co.jp'}
# Browser time zone -> country; the best hint we get for someone whose browser is in English
TIME_ZONE_REGIONS = {
    'Europe/Berlin': 'DE', 'Europe/Busingen': 'DE', 'Europe/Vienna': 'AT', 'Europe/Zurich': 'CH',
    'Europe/Vaduz': 'LI', 'Europe/Luxembourg': 'LU', 'Europe/London': 'GB', 'Europe/Dublin': 'IE',
    'Europe/Paris': 'FR', 'Europe/Madrid': 'ES', 'Atlantic/Canary': 'ES', 'Europe/Rome': 'IT',
    'Europe/Amsterdam': 'NL', 'Asia/Tokyo': 'JP', 'Asia/Kolkata': 'IN', 'Asia/Calcutta': 'IN',
    'America/Sao_Paulo': 'BR', 'America/Mexico_City': 'MX', 'America/Toronto': 'CA',
    'America/Vancouver': 'CA', 'America/Edmonton': 'CA', 'America/Winnipeg': 'CA', 'America/Halifax': 'CA',
    'America/St_Johns': 'CA', 'America/Regina': 'CA', 'Pacific/Auckland': 'NZ',
}


def language_tags(*values: str | None) -> list[str]:
    """'en-US,en;q=0.9,de;q=0.8', 'de_DE', None -> ['en-us', 'en', 'de', 'de-de']: every tag, in order."""
    tags = []
    for value in values:
        for part in (value or '').split(','):
            tag = part.split(';')[0].strip().replace('_', '-').lower()
            if tag and tag != '*':
                tags.append(tag)
    return tags


def amazon_store(*languages: str | None, chosen: str | None = None, time_zone: str | None = None) -> str:
    """
    The Amazon store whose settings to link to: the one the user picked, else a guess from where they
    seem to be. Time zone first (an English browser in Berlin), then a country in a language tag
    ('en-GB'), then the language itself ('de'), else amazon.com.
    """
    if chosen in AMAZON_STORES:
        return chosen
    region = TIME_ZONE_REGIONS.get(time_zone or '')
    if region is None and (time_zone or '').startswith('Australia/'):
        region = 'AU'
    if region in REGION_STORES:
        return REGION_STORES[region]
    tags = language_tags(*languages)
    for tag in tags:
        country = tag.split('-')[1].upper() if '-' in tag else ''
        if country in REGION_STORES:
            return REGION_STORES[country]
    for tag in tags:
        store = LANGUAGE_STORES.get(tag.split('-')[0])
        if store:
            return store
    return DEFAULT_STORE


def amazon_settings_url(*languages: str | None, chosen: str | None = None, time_zone: str | None = None) -> str:
    """The Preferences page; its Personal Document Settings section, a bit further down, has the
    approved sender list (setup step 2)."""
    store = amazon_store(*languages, chosen=chosen, time_zone=time_zone)
    return f'https://www.{store}/hz/mycd/preferences/myx#/home/settings/payment'


def amazon_devices_url(*languages: str | None, chosen: str | None = None, time_zone: str | None = None) -> str:
    """The list of devices: pick the Kindle to see its Send-to-Kindle address (setup step 1)."""
    store = amazon_store(*languages, chosen=chosen, time_zone=time_zone)
    return f'https://www.{store}/hz/mycd/digital-console/alldevices'
