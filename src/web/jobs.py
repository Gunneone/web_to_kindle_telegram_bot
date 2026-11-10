"""
Deliveries running in the background. `pipeline.run` reports stages to a `Frontend`; here they are
kept in memory so the client can poll `GET /api/books/{id}` while a book is being made. The
history row in the database stays the durable record.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from core import db, pipeline
from core.pipeline import Failure, Outcome, Stage

logger = logging.getLogger(__name__)

# In the API the db.TELEGRAM target ("the front end hands the file over") is a download
DOWNLOAD = 'download'
TARGETS = {db.KINDLE: db.KINDLE, DOWNLOAD: db.TELEGRAM}
KEEP_FINISHED_SECONDS = 600
MAX_ACTIVE_PER_USER = 10  # as many links as the bot takes from one message
MAX_ACTIVE_PER_GUEST = 2


@dataclass
class Live:
    user_id: int
    stage: Stage | None = None
    outcome: Outcome | None = None
    finished_at: float | None = None


LIVE: dict[int, Live] = {}
_TASKS: set[asyncio.Task] = set()


class WebFrontend(pipeline.Frontend):
    """Follows one delivery. The EPUB isn't pushed anywhere: the download endpoint serves it."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.received: asyncio.Future[int] = asyncio.get_running_loop().create_future()

    async def stage(self, stage: Stage, article: db.Article) -> None:
        live = LIVE.get(article.id)
        if live is None or live.user_id != self.user_id:  # ids can be reused after rows are deleted
            live = LIVE[article.id] = Live(self.user_id)
        live.stage, live.outcome, live.finished_at = stage, None, None
        if stage == Stage.RECEIVED and not self.received.done():
            self.received.set_result(article.id)

    async def deliver_file(self, article: db.Article, book: pipeline.Book, delivered: set[str]) -> None:
        pass


def prune() -> None:
    now = time.monotonic()
    for article_id in [i for i, live in LIVE.items() if live.finished_at and now - live.finished_at > KEEP_FINISHED_SECONDS]:
        del LIVE[article_id]


def active_count(user_id: int) -> int:
    return sum(1 for live in LIVE.values() if live.user_id == user_id and live.outcome is None)


def is_running(article_id: int) -> bool:
    live = LIVE.get(article_id)
    return live is not None and live.outcome is None


async def start(user: db.User, url: str, targets: set[str], *, article_id: int | None = None,
                force: bool = False) -> tuple[int | None, Outcome | None]:
    """
    Begin a delivery and return as soon as it has its history entry: (article id, None).
    When nothing was started (a recent duplicate) or it failed at once: (None, outcome).
    """
    prune()
    frontend = WebFrontend(user.user_id)
    if article_id is not None:  # a resend: show it as working before the task gets going
        LIVE[article_id] = Live(user.user_id, Stage.RECEIVED)
    task = asyncio.create_task(_run(user, url, targets, frontend, article_id, force))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    await asyncio.wait({frontend.received, task}, return_when=asyncio.FIRST_COMPLETED)
    if frontend.received.done():
        return frontend.received.result(), None
    if article_id is not None:
        LIVE.pop(article_id, None)
    return None, task.result()


async def _run(user, url, targets, frontend, article_id, force) -> Outcome:
    try:
        outcome = await pipeline.run(user, url, frontend, targets=targets, article_id=article_id, force=force)
    except Exception as e:  # run() handles article, mail and delivery problems itself
        logger.exception(f'Delivery of {url} crashed')
        found = [i for i, live in LIVE.items() if live.user_id == user.user_id and live.outcome is None
                 and (article_id is None or i == article_id)]
        outcome = Outcome(article_id or (found[-1] if found else 0), failure=Failure.UNKNOWN, error=e)
        if outcome.article_id:
            db.update_article(outcome.article_id, status=db.FAILED, error=str(e)[:500])
    live = LIVE.get(outcome.article_id)
    if live is not None:
        live.outcome, live.finished_at = outcome, time.monotonic()
    return outcome


def host(url: str | None) -> str:
    return pipeline.host(url or '')


def iso(value) -> str | None:
    return value.isoformat(timespec='seconds') + 'Z' if value else None


def file_size(path: str | None) -> int | None:
    try:
        return os.path.getsize(path) if path else None
    except OSError:
        return None


def serialize(article: db.Article) -> dict:
    """One history row as the API shows it, with live progress when a delivery is running."""
    live = LIVE.get(article.id)
    working = live is not None and live.outcome is None
    outcome = live.outcome if live else None
    if working:
        status = 'processing'
    elif article.status == db.PROCESSING:
        status = 'interrupted'  # the server restarted while this was being made
    else:
        status = article.status or db.SENT  # rows from before the status column were sent
    failure = detail = None
    delivered: list[str] = []
    if outcome is not None:
        delivered = sorted(DOWNLOAD if t == db.TELEGRAM else t for t in outcome.delivered)
        if outcome.failure:
            failure = outcome.failure.value
            if outcome.failure in pipeline.USER_FACING and outcome.error:
                detail = str(outcome.error)
        if outcome.book and not outcome.failure:
            if outcome.delivered:
                status = db.PREVIEW if outcome.book.is_preview else db.SENT
            elif article.status == db.READY:  # built only, for a look first
                status = db.READY
        if outcome.failure or outcome.file_too_big:
            status = db.FAILED
    size = file_size(article.epub_path)
    book = outcome.book if outcome else None
    return {
        'id': article.id,
        'url': article.article_url,
        'host': host(article.article_url),
        'title': article.title or host(article.article_url),
        'status': status,
        'stage': live.stage.value if working and live.stage else None,
        'delivered': delivered,
        'failure': failure,
        'detail': detail,
        'created_at': iso(article.timestamp),
        'size': size,
        'minutes': book.read_minutes if book else None,
        'paywalled': bool(book.is_preview if book else (article.paywalled or article.status == db.PREVIEW)),
        # The EPUB can be fetched whenever it exists and isn't being written: also after a failed mail
        'can_download': size is not None and not working and article.status != db.PROCESSING,
    }
