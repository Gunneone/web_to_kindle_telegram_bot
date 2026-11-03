"""
Turning a link into a delivered book, for any front end: the history entry, the "you already got
this" check, fetching, building the EPUB, mailing it to the Kindle, and how much runs at once.

A front end passes a `Frontend` that shows the progress and hands over the EPUB file itself
(a file in the Telegram chat; a download in a web app), then renders the `Outcome`.
"""

import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from email_sender import EmailError, send_email
from epub_converter import convert_to_epub
from web_scraper import Article as WebArticle
from web_scraper import BlockedError, ExtractionError, ScraperError, get_website_content

from . import db

logger = logging.getLogger(__name__)

WORDS_PER_MINUTE = 230

# Scraping, image downloads and SMTP run in threads; keep a slow user from starving everyone else.
# The limits hold per process: front ends running in separate processes each get their own.
GLOBAL_SLOTS = asyncio.Semaphore(4)
USER_SLOTS: dict[int, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(2))


class Stage(StrEnum):
    RECEIVED = 'received'  # the link has its history entry
    QUEUED = 'queued'  # waiting for a free slot; only reported when it has to wait
    FETCHING = 'fetching'
    BUILDING = 'building'
    SENDING = 'sending'  # mailing the EPUB to the Kindle


class Failure(StrEnum):
    BLOCKED = 'blocked'  # the site refused the request
    EXTRACT = 'extract'  # the page has no article text
    FETCH = 'fetch'  # timeouts, network errors and other scraping problems
    EMAIL = 'email'  # the mail server could not be reached or refused the book
    UNKNOWN = 'unknown'  # a bug, or a front end's own delivery failed


# The scraper's message tells the user something useful (which site, which status); the others don't
USER_FACING = {Failure.BLOCKED, Failure.EXTRACT, Failure.FETCH}


@dataclass
class Book:
    title: str
    url: str
    epub_path: str
    author: str | None = None
    publication: str | None = None
    words: int | None = None
    is_preview: bool = False

    @property
    def read_minutes(self) -> int | None:
        return max(1, round(self.words / WORDS_PER_MINUTE)) if self.words else None

    @property
    def size(self) -> int | None:
        """Bytes, or None once the file is gone."""
        try:
            return os.path.getsize(self.epub_path)
        except OSError:
            return None


@dataclass
class Outcome:
    article_id: int
    book: Book | None = None
    delivered: set[str] = field(default_factory=set)
    duplicate: db.Article | None = None  # delivered recently, so nothing was done (see `force`)
    failure: Failure | None = None
    error: BaseException | None = None
    file_too_big: int | None = None  # the EPUB's size, when it was too big for Frontend.max_file_bytes

    @property
    def ok(self) -> bool:
        return bool(self.delivered)


class Frontend:
    """How a front end follows one delivery. Override `stage` to show progress."""

    # The largest EPUB `deliver_file` accepts; None for no limit
    max_file_bytes: int | None = None

    async def stage(self, stage: Stage, article: db.Article) -> None:
        """Progress, in order. FETCHING and BUILDING are skipped when an earlier EPUB is reused."""

    async def deliver_file(self, article: db.Article, book: Book, delivered: set[str]) -> None:
        """Hand the EPUB to the user (the db.TELEGRAM target). `delivered`: targets already done."""
        raise NotImplementedError


def host(url: str) -> str:
    return urlparse(url).netloc.removeprefix('www.') or url


def word_count(html: str) -> int:
    return len(BeautifulSoup(html or '', 'html.parser').get_text(' ').split())


def classify(error: BaseException) -> Failure:
    if isinstance(error, BlockedError):
        return Failure.BLOCKED
    if isinstance(error, ExtractionError):
        return Failure.EXTRACT
    if isinstance(error, ScraperError):
        return Failure.FETCH
    if isinstance(error, EmailError):
        return Failure.EMAIL
    return Failure.UNKNOWN


async def run(user: db.User, url: str, frontend: Frontend, *, targets: set[str] | None = None,
              article_id: int | None = None, force: bool = False) -> Outcome:
    """
    Fetch an article, build the EPUB and deliver it to the Kindle and/or through the front end.
    Never raises for problems with the article, the mail server or the front end's delivery:
    those come back as `Outcome.failure`, already recorded in the history.

    targets:    where to deliver; default is the user's delivery setting
    article_id: history entry to reuse (resend, retry); its EPUB is reused while it's still on disk
    force:      skip the "you already got this" check
    """
    targets = targets or user.targets

    if not force and article_id is None:
        previous = db.recent_delivery(user.user_id, url)
        if previous:
            return Outcome(previous.id, duplicate=previous)

    article = db.get_article(article_id) if article_id else None
    if article is None:
        article = db.create_article(user.user_id, url)
    reuse = (article_id is not None and article.status in (*db.DELIVERED, None)
             and bool(article.epub_path) and os.path.exists(article.epub_path))

    await frontend.stage(Stage.RECEIVED, article)
    user_slots = USER_SLOTS[user.user_id]
    if user_slots.locked() or GLOBAL_SLOTS.locked():
        await frontend.stage(Stage.QUEUED, article)

    async with user_slots, GLOBAL_SLOTS:
        book = None
        delivered: set[str] = set()
        too_big = None
        try:
            if reuse:
                book = Book(title=article.title or host(url), url=url, epub_path=article.epub_path,
                            is_preview=article.status == db.PREVIEW)
            else:
                await frontend.stage(Stage.FETCHING, article)
                content = await asyncio.to_thread(get_website_content, url)
                await frontend.stage(Stage.BUILDING, article)
                epub_path = await asyncio.to_thread(convert_to_epub, content, user.image_links)
                words = await asyncio.to_thread(word_count, content.Content)
                book = Book(title=content.Title or host(url), url=url, epub_path=epub_path,
                            author=content.Author, publication=content.Publication,
                            words=words, is_preview=bool(content.Is_Preview))
                db.update_article(article.id, title=book.title, epub_path=epub_path)

            if db.KINDLE in targets:
                await frontend.stage(Stage.SENDING, article)
                await asyncio.to_thread(send_email, user.kindle_email, book.epub_path)
                delivered.add(db.KINDLE)

            if db.TELEGRAM in targets:
                size = os.path.getsize(book.epub_path)
                if frontend.max_file_bytes is not None and size > frontend.max_file_bytes:
                    too_big = size
                else:
                    await frontend.deliver_file(article, book, set(delivered))
                    delivered.add(db.TELEGRAM)

        except Exception as e:
            failure = classify(e)
            if failure in USER_FACING:
                logger.warning(f"Could not process URL {url}: {e}")
            elif failure == Failure.EMAIL:
                logger.error(f"Could not email {url} to user {user.user_id}: {e}")
            else:
                logger.exception(f"Error processing URL {url}")
            if not reuse:
                db.update_article(article.id, status=db.FAILED, error=str(e)[:500])
            return Outcome(article.id, book, delivered, failure=failure, error=e, file_too_big=too_big)

        if delivered:
            db.update_article(article.id, status=db.PREVIEW if book.is_preview else db.SENT, error=None,
                              timestamp=db.utcnow())
            if db.KINDLE in delivered:
                db.update_user(user.user_id, last_book_received_date=date.today().isoformat())
            logger.info(f"Delivered '{book.title}' to user {user.user_id} via {sorted(delivered)}")
        elif not reuse:
            db.update_article(article.id, status=db.FAILED, error=f'EPUB too large to deliver ({too_big} bytes)')
        return Outcome(article.id, book, delivered, file_too_big=too_big)


async def email_article(article: WebArticle, kindle_email: str) -> None:
    """Build an EPUB from an article already in hand (the setup test book) and mail it.
    Raises EmailError when the mail server refuses it."""
    epub_path = await asyncio.to_thread(convert_to_epub, article)
    await asyncio.to_thread(send_email, kindle_email, epub_path)
