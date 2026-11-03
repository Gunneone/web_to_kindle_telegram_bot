"""
Article data class for storing extracted content.
"""


class Article:
    def __init__(self, url, title, author, published_at, content, publication=None,
                 language=None, is_preview=False):
        self.URL = url
        self.Title = title
        self.Author = author  # None when unknown
        self.Published_At = published_at  # ISO date string (YYYY-MM-DD) or None when unknown
        self.Content = content
        self.Publication = publication  # publication / site name, e.g. "Astral Codex Ten", "BBC News"
        self.Language = language  # BCP 47 tag from the page, e.g. "en", "de", "en-GB"
        self.Is_Preview = is_preview  # True when the full post is paywalled and only a preview was extracted

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        return setattr(self, key, value)
