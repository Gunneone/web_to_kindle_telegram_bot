"""
Factory for determining which scraper to use based on URL.
"""

import logging

from .article import Article
from .errors import BlockedError, ExtractionError
from .generic_scraper import GenericScraper
from .http import fetch
from .medium_scraper import MediumScraper
from .substack_scraper import SubstackScraper
from .url_utils import extract_url, normalize_url

logger = logging.getLogger(__name__)


def get_website_content(url: str) -> Article:
    """
    Downloads the page once and hands it to the matching scraper (Medium, Substack or generic).

    Args:
        url (str): The URL to process

    Returns:
        Article: Article object containing extracted content

    Raises:
        ScraperError: with a user-facing message when the article can't be fetched or extracted
    """
    url = extract_url(url) or normalize_url(url)

    if MediumScraper.is_medium_host(url):
        return MediumScraper().extract_content(url)

    try:
        fetched = fetch(url)
    except BlockedError:
        # Medium publications on custom domains sit behind the same Cloudflare block
        if MediumScraper.post_id(url):
            logger.info(f"Blocked URL looks like a Medium post, trying its RSS feed: {url}")
            return MediumScraper().extract_from_feed(url)
        raise

    if MediumScraper.is_medium_html(fetched.html):
        return MediumScraper().extract_content(url, fetched)

    if SubstackScraper.is_substack_site(url, fetched.html):
        try:
            return SubstackScraper().extract_content(url, fetched)
        except ExtractionError:
            if SubstackScraper.is_substack_url(url):
                # substack.com links that aren't posts (deleted posts, notes) render the JavaScript app shell
                raise ExtractionError("This Substack link doesn't lead to a readable post.")
            logger.info(f"No Substack post layout found, using the generic scraper: {url}")

    return GenericScraper().extract_content(url, fetched)
