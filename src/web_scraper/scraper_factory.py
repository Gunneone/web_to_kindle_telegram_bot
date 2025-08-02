"""
Factory for determining which scraper to use based on URL.
"""

from .substack_scraper import SubstackScraper
from .generic_scraper import GenericScraper
from .article import Article


def get_website_content(url: str) -> Article:
    """
    Determines if URL is a Substack page and extracts content accordingly.

    Args:
        url (str): The URL to process

    Returns:
        Article: Article object containing extracted content
    """
    substack_scraper = SubstackScraper()

    if substack_scraper.is_substack_site(url):
        return substack_scraper.extract_content(url)
    else:
        generic_scraper = GenericScraper()
        return generic_scraper.extract_content(url)
