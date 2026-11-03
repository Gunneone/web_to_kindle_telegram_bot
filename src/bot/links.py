"""
Finding article links in what users send.
"""

import re

from telegram import Message, MessageEntity

from web_scraper import extract_url
from web_scraper.url_utils import URL_PATTERN

MAX_LINKS = 10
OTHER_SCHEME = re.compile(r'^[a-z][a-z0-9+.-]*:(?!\d)', re.I)  # 'tg:', 'mailto:', not 'host.com:8080'


def _candidates(message: Message) -> list[str]:
    found = []
    for parse in (message.parse_entities, message.parse_caption_entities):
        for entity, text in parse([MessageEntity.URL, MessageEntity.TEXT_LINK]).items():
            found.append(entity.url if entity.type == MessageEntity.TEXT_LINK else text)
    if found:
        return found
    # Telegram marks links as entities, but fall back to the text for clients and forwards that don't
    for text in filter(None, (message.text, message.caption)):
        matches = [m.group(0) for m in URL_PATTERN.finditer(text)]
        if not matches and (url := extract_url(text)):  # a bare 'medium.com/@user/post'
            matches = [url]
        found.extend(matches)
    return found


def extract_urls(message: Message | None, include_reply: bool = True, bot_id: int | None = None) -> list[str]:
    """
    All web links in a message, in order and without duplicates: plain links, hyperlinked text and
    links in captions. If the message has none, the message it replies to is searched instead,
    unless that one was sent by the bot itself (bot_id), e.g. the /history list.
    """
    if message is None:
        return []
    urls = []
    for candidate in _candidates(message):
        if OTHER_SCHEME.match(candidate) and not candidate.lower().startswith(('http:', 'https:')):
            continue  # tg://, mailto:, ...
        if not re.match(r'^https?://', candidate, re.I):
            candidate = 'https://' + candidate.removeprefix('//')  # Telegram also links 'example.com:8080/x'
        url = extract_url(candidate)
        if url and url not in urls:
            urls.append(url)
    reply = message.reply_to_message
    if not urls and include_reply and reply and not (bot_id and reply.from_user and reply.from_user.id == bot_id):
        return extract_urls(reply, include_reply=False)
    return urls
