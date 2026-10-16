"""
Web scraper package for extracting content from various websites.
"""

from .article import Article
from .errors import BlockedError, ExtractionError, FetchError, ScraperError
from .generic_scraper import GenericScraper
from .medium_scraper import MediumScraper
from .substack_scraper import SubstackScraper
from .scraper_factory import get_website_content
from .url_utils import extract_url, normalize_url

__all__ = ['Article', 'GenericScraper', 'MediumScraper', 'SubstackScraper', 'get_website_content',
           'ScraperError', 'FetchError', 'BlockedError', 'ExtractionError', 'extract_url', 'normalize_url']
