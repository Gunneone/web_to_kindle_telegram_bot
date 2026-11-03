"""
Substack-specific content scraper.
"""

import logging
import os
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .article import Article
from .errors import ExtractionError
from .html_cleanup import build_header, promote_lazy_images, sanitize_for_kindle
from .http import FetchResult, fetch
from .metadata import extract_metadata

logger = logging.getLogger(__name__)

# Substack UI inside the post body: subscribe/share widgets, image zoom buttons, paywall CTA
SUBSTACK_CHROME = [
    '.subscription-widget-wrap', '.subscription-widget-wrap-editor', '.subscribe-widget', '.subscription-widget',
    '.image-link-expand', '.post-ufi', '.share-dialog', '.button-wrapper', '.paywall', '.paywall-jump',
    '.pc-display-flex', '.modal', '.popup', '.post-footer', '.footer',
]


class SubstackScraper:
    """Handles content extraction from Substack websites."""

    @staticmethod
    def is_substack_url(url: str) -> bool:
        """substack.com share links (inbox/home/@user/open.substack.com) and *.substack.com publications."""
        host = (urlparse(url).hostname or '').lower()
        return host == 'substack.com' or host.endswith('.substack.com')

    @staticmethod
    def is_substack_html(html: str) -> bool:
        """Substack publications on custom domains (e.g. astralcodexten.com)."""
        return 'substackcdn.com' in html and 'newsletter-post' in html

    @classmethod
    def is_substack_site(cls, url: str, html: str | None = None) -> bool:
        """
        Determines if a URL is a Substack site by checking the URL and, for custom domains, the page HTML.

        Args:
            url (str): The URL to check
            html (str): The page HTML, if already downloaded

        Returns:
            bool: True if the site is detected as Substack, False otherwise
        """
        return cls.is_substack_url(url) or (html is not None and cls.is_substack_html(html))

    def extract_content(self, url: str, fetched: FetchResult | None = None) -> Article:
        """
        Extracts the main article content from a Substack blog post URL.

        Args:
            url (str): The URL of the Substack blog post
            fetched (FetchResult): The already downloaded page, if available

        Returns:
            Article: Article object containing extracted content

        Raises:
            ScraperError: If the page cannot be retrieved or has no article content
        """
        logger.info(f"Processing URL using Substack Extractor: {url}... ")
        fetched = fetched or fetch(url)
        return self.extract_from_html(url, fetched.final_url, fetched.html)

    def extract_from_html(self, url: str, final_url: str, html: str) -> Article:
        soup = BeautifulSoup(html, 'lxml')
        article = soup.find('article')
        if article is None:
            raise ExtractionError("Could not find article content")

        # Metadata comes from the page's JSON-LD (author, datePublished, publisher) and <meta> tags
        meta = extract_metadata(html, final_url, soup=soup)
        heading = article.find('h1')
        title = meta.title or (heading.get_text(strip=True) if heading else 'Untitled')
        subtitle_element = article.select_one('h3.subtitle')
        subtitle = subtitle_element.get_text(strip=True) if subtitle_element else None

        # Paid posts: the page only contains the free preview, followed by a paywall CTA
        is_preview = meta.is_accessible_for_free is False or soup.select_one('.paywall, [data-testid=paywall]') is not None

        promote_lazy_images(soup)
        body = article.select_one('.available-content') or article.select_one('.body.markup') or article
        for element in body.select('.post-header'):
            element.decompose()
        self._clean_article_content(body)

        content = build_header(title, meta.author, meta.site_name, meta.published, subtitle)
        content += sanitize_for_kindle(str(body), final_url)

        self._save_content_to_file(content, title)
        logger.info(f"Content extracted using Substack Extractor: '{title}' by {meta.author}"
                    f"{' (paywalled preview)' if is_preview else ''}")
        return Article(
            url=url,
            title=title,
            author=meta.author,
            published_at=meta.published,
            content=content,
            publication=meta.site_name,
            language=meta.language,
            is_preview=is_preview,
        )

    def _clean_article_content(self, body) -> None:
        """Remove unwanted elements from article content."""
        for element in body.select(', '.join(SUBSTACK_CHROME)):
            element.decompose()

    def _save_content_to_file(self, content: str, title: str) -> None:
        """Save content to HTML file with safe filename."""
        safe_title = ''.join(c for c in title.lower() if c.isalnum() or c in ' -_')
        safe_title = safe_title.replace(' ', '-')[:70]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Ensure html directory exists
        os.makedirs('./output/html', exist_ok=True)

        # Use os.path.join for proper path handling
        file_path = os.path.join('./output/html', f"{safe_title}-{timestamp}.html")

        with open(file_path, "w", encoding='utf-8') as f:
            f.write(content)
