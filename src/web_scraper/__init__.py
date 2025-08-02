"""
Web scraper package for extracting content from various websites.
"""

from .article import Article
from .generic_scraper import GenericScraper
from .substack_scraper import SubstackScraper
from .scraper_factory import get_website_content

__all__ = ['Article', 'GenericScraper', 'SubstackScraper', 'get_website_content']
