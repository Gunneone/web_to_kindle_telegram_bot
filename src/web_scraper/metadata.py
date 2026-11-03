"""
Article metadata extraction (title, author, date, site name, language).

Sources in order of trust: JSON-LD, OpenGraph / <meta> tags, then trafilatura's heuristics
(bylines, htmldate). The page's first <h1> is never used: on many blogs it is the site header.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ARTICLE_TYPES = {
    'Article', 'NewsArticle', 'BlogPosting', 'Report', 'ScholarlyArticle', 'TechArticle',
    'SocialMediaPosting', 'LiveBlogPosting', 'AnalysisNewsArticle', 'OpinionNewsArticle',
    'ReportageNewsArticle', 'BackgroundNewsArticle', 'ReviewNewsArticle', 'Review', 'Posting',
}
TITLE_SEPARATORS = re.compile(r'\s+[|–—\-:·•»]+\s+')


@dataclass
class Metadata:
    title: str | None = None
    author: str | None = None
    published: str | None = None  # ISO date, YYYY-MM-DD
    site_name: str | None = None
    language: str | None = None
    description: str | None = None
    is_accessible_for_free: bool | None = None
    body_words: int = 0  # word count of JSON-LD articleBody, used to detect truncated extraction


def extract_metadata(html: str, url: str, soup: BeautifulSoup | None = None) -> Metadata:
    soup = soup or BeautifulSoup(html, 'lxml')
    ld = _json_ld_article(soup)
    meta = _meta_tags(soup)
    fallback = _trafilatura_metadata(html, url)

    site_name = _first(meta.get('og:site_name'), _name_of(ld.get('publisher')), fallback.get('sitename'))
    raw_title = _first(meta.get('og:title'), ld.get('headline'), ld.get('name'), meta.get('twitter:title'),
                       fallback.get('title'), soup.title.string if soup.title else None)

    return Metadata(
        title=clean_title(raw_title, site_name, url),
        author=_first(_authors(ld.get('author')), _clean_author(meta.get('author')),
                      _clean_author(meta.get('parsely-author')), _clean_author(fallback.get('author'))),
        published=_first(parse_date(ld.get('datePublished')), parse_date(meta.get('article:published_time')),
                         parse_date(meta.get('publication_date')), parse_date(meta.get('date')),
                         parse_date(_first_time_datetime(soup)), parse_date(fallback.get('date'))),
        site_name=site_name,
        language=normalize_language(_first(soup.html.get('lang') if soup.html else None,
                                           meta.get('content-language'), meta.get('og:locale'),
                                           ld.get('inLanguage') if isinstance(ld.get('inLanguage'), str) else None)),
        description=_first(meta.get('og:description'), meta.get('description'), ld.get('description')),
        is_accessible_for_free=_parse_bool(ld.get('isAccessibleForFree')),
        body_words=len(str(ld.get('articleBody') or '').split()),
    )


def clean_title(title: str | None, site_name: str | None, url: str) -> str | None:
    """Strip a trailing ' | Site Name' style suffix from a title."""
    if not title:
        return None
    title = re.sub(r'\s+', ' ', title).strip()
    parts = TITLE_SEPARATORS.split(title)
    if len(parts) < 2:
        return title

    # 'en.wikipedia.org' -> {'wikipedia'}, 'www.bbc.co.uk' -> {'bbc'}, 'hacks.mozilla.org' -> {'hacks', 'mozilla'}
    host_labels = {label for label in (urlparse(url).hostname or '').lower().split('.')[:-1]
                   if len(label) > 2 and label not in ('www', 'com', 'org', 'net', 'gov', 'edu', 'blog')}
    site = _normalize(site_name or '')
    # Drop trailing segments that are (part of) the site name, keeping at least the first segment
    while len(parts) > 1:
        tail = _normalize(parts[-1])
        matches_site = site and (tail == site or (len(tail) >= 4 and tail in site) or site in tail)
        if matches_site or any(label in tail.replace(' ', '') for label in host_labels):
            parts.pop()
        else:
            break
    stripped = title[:_prefix_length(title, parts)].strip()
    return stripped or title


def parse_date(value) -> str | None:
    """Parse the many date formats found in the wild into YYYY-MM-DD."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).date().isoformat()  # RFC 2822, e.g. RSS pubDate
    except (TypeError, ValueError):
        pass
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})', value)  # e.g. "2026-10-06 10:00:00 +0000 UTC"
    if match:
        try:
            return datetime(*map(int, match.groups())).date().isoformat()
        except ValueError:
            return None
    return None


def format_date(iso_date: str | None) -> str | None:
    if not iso_date:
        return None
    try:
        return datetime.fromisoformat(iso_date).strftime("%B %d, %Y")
    except ValueError:
        return iso_date


def normalize_language(value: str | None) -> str | None:
    """'en_US' -> 'en-US', 'en-EUROPE' -> 'en', 'DE' -> 'de'."""
    if not value:
        return None
    parts = re.split(r'[-_]', value.strip())
    primary = parts[0].lower()
    if not re.fullmatch(r'[a-z]{2,3}', primary):
        return None
    if len(parts) > 1 and re.fullmatch(r'[A-Za-z]{2}|\d{3}', parts[1]):
        return f"{primary}-{parts[1].upper()}"
    return primary


def _json_ld_article(soup: BeautifulSoup) -> dict:
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or script.get_text() or '', strict=False)
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [data]
        while stack:
            node = stack.pop(0)
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                types = node.get('@type')
                types = set(types) if isinstance(types, list) else {types}
                if types & ARTICLE_TYPES:
                    return node
                if '@graph' in node:
                    stack.extend(node['@graph'] if isinstance(node['@graph'], list) else [node['@graph']])
    return {}


def _meta_tags(soup: BeautifulSoup) -> dict:
    values = {}
    for tag in soup.find_all('meta'):
        key = (tag.get('property') or tag.get('name') or tag.get('http-equiv') or '').strip().lower()
        content = (tag.get('content') or '').strip()
        if key and content and key not in values:
            values[key] = content
    return values


def _trafilatura_metadata(html: str, url: str) -> dict:
    try:
        from trafilatura.metadata import extract_metadata as trafilatura_extract_metadata
        document = trafilatura_extract_metadata(html, default_url=url)
    except Exception as e:  # trafilatura is a best-effort fallback
        logger.warning(f"trafilatura metadata extraction failed: {e}")
        return {}
    if document is None:
        return {}
    return {key: getattr(document, key, None) for key in ('title', 'author', 'date', 'sitename')}


def _authors(value) -> str | None:
    if not value:
        return None
    items = value if isinstance(value, list) else [value]
    names = []
    for item in items:
        name = _clean_author(item.get('name')) if isinstance(item, dict) else _clean_author(str(item))
        if name and name not in names:
            names.append(name)
    return ', '.join(names[:4]) or None


def _name_of(value) -> str | None:
    """Name of a JSON-LD Organization/Person (publisher). Unlike author names, "By ..." is kept."""
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get('name')
    if not isinstance(value, str):
        return None
    value = re.sub(r'\s+', ' ', value).strip()
    return value if value and not value.startswith(('http://', 'https://')) else None


def _clean_author(value) -> str | None:
    if not value or not isinstance(value, str):
        return None
    value = re.sub(r'\s+', ' ', value).strip()
    value = re.sub(r'^by\s+', '', value, flags=re.I)
    if not value or value.startswith(('http://', 'https://', '@')) or len(value) > 120:
        return None
    return value


def _first_time_datetime(soup: BeautifulSoup) -> str | None:
    container = soup.find('article') or soup
    time_tag = container.find('time', attrs={'datetime': True})
    return time_tag['datetime'] if time_tag else None


def _parse_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ('true', 'false'):
        return value.strip().lower() == 'true'
    return None


def _first(*values):
    for value in values:
        if isinstance(value, str):
            value = value.strip()
        if value:
            return value
    return None


def _normalize(text: str) -> str:
    text = re.sub(r'[–—\-|:·•»]+', ' ', text.lower())
    return re.sub(r'\s+', ' ', text).strip()


def _prefix_length(title: str, parts: list[str]) -> int:
    """Length of the original title covered by the first len(parts) segments."""
    position = 0
    for i, part in enumerate(parts):
        position = title.index(part, position) + len(part)
    return position
