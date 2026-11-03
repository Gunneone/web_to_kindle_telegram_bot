"""
Medium-specific content scraper.

Medium answers plain HTTP clients with a Cloudflare block page; http.fetch retries with browser
impersonation, which gets the server-rendered article. If even that is blocked (e.g. from a
datacenter IP), the post is looked up in the author's or publication's RSS feed, which carries
the full text of the ~10 most recent posts.
"""

import logging
import re
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from .article import Article
from .errors import BlockedError, ScraperError
from .generic_scraper import GenericScraper
from .html_cleanup import build_header, sanitize_for_kindle, strip_leading_title
from .http import FetchResult, fetch
from .metadata import extract_metadata, parse_date

logger = logging.getLogger(__name__)

POST_ID = re.compile(r'-([0-9a-f]{8,12})$')
BLOCKED_MESSAGE = ("Medium blocks automated access to this post. I can only fetch an author's most recent "
                   "posts (through their RSS feed), and this one isn't among them.")
# Byline, tag list, "Listen/Share" bar, "click to view image in full size" hints, response/clap UI
MEDIUM_CHROME = ['.speechify-ignore', '[data-testid=headerClapButton]', '[data-testid=audioPlayButton]',
                 '[aria-label=responses]', '[data-testid=authorPhoto]']


class MediumScraper:
    """Handles content extraction from Medium (medium.com, *.medium.com and custom domains)."""

    @staticmethod
    def is_medium_host(url: str) -> bool:
        host = (urlparse(url).hostname or '').lower()
        return host == 'medium.com' or host.endswith('.medium.com')

    @staticmethod
    def is_medium_html(html: str) -> bool:
        """Medium publications on custom domains (netflixtechblog.com, uxdesign.cc, ...)."""
        return bool(re.search(r'<meta[^>]+(?:al:ios:app_name|twitter:app:name:iphone)[^>]+content="Medium"', html))

    @staticmethod
    def post_id(url: str) -> str | None:
        """Medium post URLs end in a hex id: .../some-title-a64152b37c35 or /p/a64152b37c35."""
        segments = [s for s in urlparse(url).path.split('/') if s]
        if not segments:
            return None
        match = POST_ID.search(segments[-1])
        if match:
            return match.group(1)
        if len(segments) >= 2 and segments[-2] == 'p' and re.fullmatch(r'[0-9a-f]{8,12}', segments[-1]):
            return segments[-1]
        return None

    def extract_content(self, url: str, fetched: FetchResult | None = None) -> Article:
        logger.info(f"Processing URL using Medium Extractor: {url}... ")
        if fetched is None:
            try:
                fetched = fetch(self._strip_query(url))
            except BlockedError:
                logger.info("Medium page is blocked, falling back to the RSS feed")
                return self.extract_from_feed(url)
        if fetched.html and BeautifulSoup(fetched.html, 'lxml').find('article'):
            return self.extract_from_page(url, fetched)
        return self.extract_from_feed(url)

    def extract_from_page(self, url: str, fetched: FetchResult) -> Article:
        article = GenericScraper().extract_from_html(url, fetched.final_url, fetched.html, prepare=self._remove_chrome)
        meta = extract_metadata(fetched.html, fetched.final_url)
        article.Is_Preview = meta.is_accessible_for_free is False or 'Member-only story' in fetched.html
        return article

    def extract_from_feed(self, url: str) -> Article:
        post_id = self.post_id(url)
        if not post_id:
            raise BlockedError(BLOCKED_MESSAGE)
        for feed_url in self.feed_urls(url):
            try:
                feed = fetch(feed_url)
            except ScraperError as e:
                logger.info(f"Medium feed {feed_url} not available: {e}")
                continue
            article = self.article_from_feed(feed.html, post_id, url)
            if article:
                return article
        raise BlockedError(BLOCKED_MESSAGE)

    @staticmethod
    def feed_urls(url: str) -> list[str]:
        """RSS feeds that may contain the post, derived from the URL shape."""
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        segments = [s for s in parsed.path.split('/') if s]
        if host in ('medium.com', 'www.medium.com'):
            if len(segments) >= 2 and segments[0] != 'p':
                return [f'https://medium.com/feed/{segments[0]}']  # @user or publication slug
            return []
        if host.endswith('.medium.com'):
            user = host.removesuffix('.medium.com')
            return [f'https://{host}/feed', f'https://medium.com/feed/@{user}']
        return [f'https://{host}/feed']  # publication on a custom domain

    def article_from_feed(self, feed_xml: str, post_id: str, url: str) -> Article | None:
        feed = BeautifulSoup(feed_xml, 'xml')
        channel_title = feed.channel.title.get_text(strip=True) if feed.channel and feed.channel.title else ''
        publication = None if channel_title.startswith('Stories by') else (channel_title.removesuffix(' - Medium') or None)

        for item in feed.find_all('item'):
            guid = item.find('guid')
            if not guid or not guid.get_text(strip=True).endswith(f'/{post_id}'):
                continue
            encoded = item.find('encoded') or item.find('description')
            raw_content = encoded.get_text() if encoded else ''
            title = item.find('title').get_text(strip=True) if item.find('title') else 'Untitled'
            author = item.find('creator').get_text(strip=True) if item.find('creator') else None
            published = parse_date(item.find('pubDate').get_text(strip=True)) if item.find('pubDate') else None
            is_preview = 'Continue reading on' in raw_content

            body = BeautifulSoup(raw_content, 'lxml')
            for pixel in body.select('img[src*="/_/stat"]'):
                pixel.decompose()
            content = strip_leading_title(sanitize_for_kindle(str(body), url), title)
            content = build_header(title, author, publication or 'Medium', published) + content

            logger.info(f"Content extracted from Medium RSS feed: '{title}' by {author}")
            return Article(url=url, title=title, author=author, published_at=published, content=content,
                           publication=publication or 'Medium', language='en', is_preview=is_preview)
        return None

    @staticmethod
    def _remove_chrome(soup: BeautifulSoup) -> None:
        for element in soup.select(', '.join(MEDIUM_CHROME)):
            element.decompose()

    @staticmethod
    def _strip_query(url: str) -> str:
        """Drop tracking parameters such as ?source=rss-... from Medium links."""
        return urlunparse(urlparse(url)._replace(query='', fragment=''))
