"""
Generic content scraper for non-Substack websites.
"""

import logging
import os
import re
from datetime import datetime
from typing import Callable

import trafilatura
from bs4 import BeautifulSoup
from readability import Document

from .article import Article
from .errors import ExtractionError
from .html_cleanup import (build_header, count_words, promote_lazy_images, remove_chrome,
                           reveal_streamed_content, sanitize_for_kindle, strip_leading_title)
from .http import FetchResult, fetch
from .metadata import extract_metadata

logger = logging.getLogger(__name__)

# readability sometimes picks a single section of the article (BBC, Ars Technica);
# fall back to trafilatura when it returns less than this share of the reference length
MIN_COVERAGE = 0.7
MIN_WORDS = 30
JAVASCRIPT_REQUIRED = re.compile(r'(enable|requires|turn on|activate)\s+javascript', re.I)


class GenericScraper:
    """Handles content extraction from generic websites using readability, with a trafilatura fallback."""

    def extract_content(self, url: str, fetched: FetchResult | None = None) -> Article:
        """
        Extracts content from a generic webpage.

        Args:
            url (str): The URL to process
            fetched (FetchResult): The already downloaded page, if available

        Returns:
            Article: Article object containing extracted content
        """
        logger.info(f"Processing URL using readability-lxml: {url}... ")
        fetched = fetched or fetch(url)
        return self.extract_from_html(url, fetched.final_url, fetched.html)

    def extract_from_html(self, url: str, final_url: str, html: str,
                          prepare: Callable[[BeautifulSoup], None] | None = None) -> Article:
        """Extract an article from downloaded HTML; `prepare` can remove site-specific chrome first."""
        meta = extract_metadata(html, final_url)

        soup = BeautifulSoup(html, 'lxml')
        reveal_streamed_content(soup)
        promote_lazy_images(soup)
        remove_chrome(soup)
        if prepare:
            prepare(soup)
        cleaned_html = str(soup)

        content = self._extract_body(cleaned_html, final_url, meta.body_words)
        title = meta.title or Document(html).short_title() or 'Untitled'
        content = strip_leading_title(sanitize_for_kindle(content, final_url), title)
        content = build_header(title, meta.author, meta.site_name, meta.published) + content

        self._save_content_to_file(content, title)
        logger.info(f"Extracted '{title}' by {meta.author or 'unknown author'} ({count_words(content)} words)")
        return Article(
            url=url,
            title=title,
            author=meta.author,
            published_at=meta.published,
            content=content,
            publication=meta.site_name,
            language=meta.language,
        )

    def _extract_body(self, html: str, base_url: str, json_ld_words: int) -> str:
        """
        Run readability and trafilatura and keep the better result. readability preserves formatting
        best, but sometimes returns only one section of the article (BBC, Ars Technica) or drops the
        images that sit in <figure>s next to the text block it picked.
        """
        primary = Document(html, url=base_url).summary(html_partial=True, keep_all_images=True)
        alternative = trafilatura.extract(html, url=base_url, output_format='html', include_comments=False,
                                          include_images=True, include_tables=True, include_links=True,
                                          include_formatting=True) or ''
        primary_words, primary_images = count_words(primary), primary.count('<img')
        alternative_words, alternative_images = count_words(alternative), alternative.count('<img')

        reference = max(alternative_words, json_ld_words)
        truncated = primary_words < MIN_COVERAGE * reference and alternative_words > primary_words
        lost_images = (alternative_images > 0 and primary_images < alternative_images / 2
                       and alternative_words >= MIN_COVERAGE * primary_words)
        if truncated or lost_images:
            logger.info(f"Using trafilatura: readability {primary_words} words/{primary_images} images, "
                        f"trafilatura {alternative_words} words/{alternative_images} images (reference {reference})")
            content, words = alternative, alternative_words
        else:
            content, words = primary, primary_words

        if words < MIN_WORDS:
            raise ExtractionError("I couldn't find the article text on that page.")
        if words < 200 and JAVASCRIPT_REQUIRED.search(BeautifulSoup(content, 'lxml').get_text(' ')):
            raise ExtractionError("This page only shows its content when JavaScript runs in a browser, "
                                  "so I can't extract the article.")
        return content

    def _save_content_to_file(self, content: str, title: str) -> None:
        """Save content to HTML file with safe filename."""
        safe_title = ''.join(c for c in title.lower() if c.isalnum() or c in ' -_')
        safe_title = safe_title.replace(' ', '-')[:70]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        os.makedirs('./output/html', exist_ok=True)
        file_path = os.path.join('./output/html', f"{safe_title}-{timestamp}.html")

        with open(file_path, "w", encoding='utf-8') as f:
            f.write(content)
