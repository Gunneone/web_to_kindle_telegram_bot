"""
Typed scraper errors. The message of each error is meant to be shown to the end user.
"""


class ScraperError(Exception):
    """Base class for all errors raised while fetching or extracting an article."""


class FetchError(ScraperError):
    """The page could not be downloaded (network error, timeout, HTTP error)."""


class BlockedError(ScraperError):
    """The site refused automated access (e.g. Cloudflare bot protection)."""

    def __init__(self, message: str, result=None):
        super().__init__(message)
        self.result = result


class ExtractionError(ScraperError):
    """The page was downloaded but no article content could be found."""
