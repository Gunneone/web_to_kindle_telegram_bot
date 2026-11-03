"""
Kindle addresses. Every front end checks an address with `is_kindle_email` before saving it, so
books are only mailed to Amazon's Send-to-Kindle domains and the mail server can't be used for
anything else.
"""

import re

KINDLE_EMAIL = re.compile(r'^[a-z0-9._%+-]+@(?:free\.)?kindle\.(?:com|cn)$')
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
