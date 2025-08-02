"""
Article data class for storing extracted content.
"""


class Article:
    def __init__(self, url, title, author, published_at, content, publication=None):
        self.URL = url
        self.Title = title
        self.Author = author
        self.Published_At = published_at
        self.Content = content
        self.Publication = publication

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        return setattr(self, key, value)
