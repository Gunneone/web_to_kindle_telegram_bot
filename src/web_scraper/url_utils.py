"""
Helpers for finding and normalizing article URLs in user input.
"""

import re

URL_PATTERN = re.compile(r'(?:https?://|www\.)[^\s<>"\'\]]+', re.I)
BARE_DOMAIN_PATTERN = re.compile(r'^[\w-]+(\.[\w-]+)+(/\S*)?$')


def extract_url(text: str | None) -> str | None:
    """
    Find the first URL in a message, e.g. "Great read! https://example.com/post" or a
    share-sheet text that puts the title before the link.
    """
    if not text:
        return None
    match = URL_PATTERN.search(text)
    if match:
        url = match.group(0).rstrip('.,;:!?»”’')
        # Keep balanced parentheses (Wikipedia: .../Python_(programming_language)), drop a closing one from prose
        while url.endswith(')') and url.count(')') > url.count('('):
            url = url[:-1].rstrip('.,;:!?»”’')
        return normalize_url(url)
    candidate = text.strip()
    if BARE_DOMAIN_PATTERN.match(candidate):
        return normalize_url(candidate)
    return None


def normalize_url(url: str) -> str:
    """Trim whitespace and add a scheme to scheme-less links like 'medium.com/@user/post'."""
    url = url.strip()
    if not re.match(r'^https?://', url, re.I):
        url = 'https://' + url.removeprefix('//')
    return url
