"""
A small in-memory sliding-window limiter. The web server runs as a single process, so this is
enough to keep one address from flooding the mail server or hammering the scraper.
"""

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_hits: int, window_seconds: float):
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Count a hit; False when `key` already used up its allowance within the window."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.max_hits:
            return False
        hits.append(now)
        if len(self._hits) > 10_000:  # never grow without bound
            self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] > self.window]:
            del self._hits[key]
