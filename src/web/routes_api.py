"""
The account and the books.
"""

import asyncio
import logging
import os
import re
from datetime import date

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from core import accounts, db, kindle, pipeline
from email_sender import EmailError
from web_scraper import Article as WebArticle
from web_scraper.url_utils import normalize_url

from . import feedback, jobs, preview
from .deps import (State, book_owner, client_ip, current_guest, current_user, request_language, require_user,
                   start_guest, state)
from .errors import ApiError
from .texts import LANGUAGES, t

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api')

MAX_URL_LENGTH = 2000
PAGE_SIZE = 20


def amazon_store(user: db.User, request: Request) -> str:
    """The store the user picked, else a guess from the browser's time zone (sent by the client as
    X-Time-Zone) and languages: an English browser in Berlin should still land on amazon.de."""
    return kindle.amazon_store(request.headers.get('accept-language'), user.language,
                               chosen=user.amazon_store, time_zone=request.headers.get('x-time-zone'))


def me_payload(user: db.User, request: Request) -> dict:
    store = amazon_store(user, request)
    name = user.first_name or user.username or (accounts.email_of(user.user_id) or '').split('@')[0]
    return {
        'name': name or None,
        'email': accounts.email_of(user.user_id),
        'kindle_email': user.kindle_email,
        # Which reader kindle_email belongs to ('kindle' or 'pocketbook'), so the client can word the setup
        'device': kindle.device_of(user.kindle_email) if user.kindle_email else None,
        'setup_verified': bool(user.setup_verified),
        'image_links': user.image_links,
        'language': user.language if user.language in LANGUAGES else None,
        'sender_email': kindle.sender_email() or None,
        'amazon_store': store,
        'amazon_store_chosen': bool(user.amazon_store),
        'amazon_stores': list(kindle.AMAZON_STORES),
        'amazon_settings_url': kindle.amazon_settings_url(chosen=store),
        'amazon_devices_url': kindle.amazon_devices_url(chosen=store),
        'providers': sorted({i.provider for i in accounts.identities(user.user_id)}),
        # When the last test book went out, so the setup can ask "did it arrive?" after a reload
        'test_sent_at': jobs.iso(user.test_book_sent_at),
        # How many books went to the Kindle: the first few get a "not on your Kindle?" hint
        'kindle_books': db.kindle_count(user.user_id),
    }


@router.get('/session')
async def get_session(request: Request, app: State = Depends(state)):
    user = current_user(request)
    return {'user': me_payload(user, request) if user else None, 'providers': app.settings.providers,
            'feedback': app.settings.feedback}


class MePatch(BaseModel):
    kindle_email: str | None = None
    image_links: bool | None = None
    language: str | None = None
    amazon_store: str | None = None  # '' goes back to guessing


@router.patch('/me')
async def patch_me(body: MePatch, request: Request, user: db.User = Depends(require_user)):
    fields: dict = {}
    if body.kindle_email is not None:
        address = kindle.normalize_email(body.kindle_email)
        if address and not kindle.is_device_email(address):
            raise ApiError(400, 'INVALID_KINDLE_EMAIL')
        address = address or None  # '': remove the address (only ever on an explicit "remove")
        if address != user.kindle_email:
            fields.update(kindle_email=address, setup_verified=0, test_book_sent_at=None)
            if address:  # like the bot: an address means "deliver to my Kindle", unless both were chosen
                fields['delivery_mode'] = db.BOTH if user.delivery_mode == db.BOTH else db.KINDLE
    if body.image_links is not None:
        fields['preserve_image_links'] = int(body.image_links)
    if body.amazon_store is not None:
        if body.amazon_store and body.amazon_store not in kindle.AMAZON_STORES:
            raise ApiError(400, 'INVALID_AMAZON_STORE')
        fields['amazon_store'] = body.amazon_store or None
    if body.language is not None:
        if body.language not in LANGUAGES:
            raise ApiError(400, 'INVALID_LANGUAGE')
        fields['language'] = body.language
    if fields:
        user = db.update_user(user.user_id, **fields)
    return {'user': me_payload(user, request)}


@router.delete('/me', status_code=204)
async def delete_me(request: Request, user: db.User = Depends(require_user)):
    db.delete_user_data(user.user_id)
    request.session.clear()
    return Response(status_code=204)


@router.post('/me/test-book', status_code=204)
async def test_book(request: Request, user: db.User = Depends(require_user), app: State = Depends(state)):
    if not user.kindle_email:
        raise ApiError(400, 'NO_KINDLE')
    if not app.test_books_per_user.allow(str(user.user_id)):
        raise ApiError(429, 'RATE_LIMITED')
    lang = request_language(request, user)
    suffix = '_pocketbook' if kindle.device_of(user.kindle_email) == kindle.POCKETBOOK else ''
    article = WebArticle(
        # A unique URL gives every test book its own EPUB identifier, so Kindle never skips it as a duplicate
        url=f'{app.settings.public_url}/#test-{user.user_id}-{int(db.utcnow().timestamp())}',
        title=t(lang, 'test_book_title' + suffix), author='Eselsohr', published_at=date.today().isoformat(),
        content=t(lang, 'test_book_body' + suffix), language=lang)
    try:
        await pipeline.email_article(article, user.kindle_email)
    except EmailError as e:
        logger.error(f'Could not send the test book to user {user.user_id}: {e}')
        raise ApiError(502, 'EMAIL_FAILED')
    db.update_user(user.user_id, test_book_sent_at=db.utcnow())
    return Response(status_code=204)


@router.post('/me/setup-verified')
async def setup_verified(request: Request, user: db.User = Depends(require_user)):
    if not user.kindle_email:
        raise ApiError(400, 'NO_KINDLE')
    user = db.update_user(user.user_id, setup_verified=1)
    return {'user': me_payload(user, request)}


MAX_SEARCH_LENGTH = 200


@router.get('/books')
async def list_books(offset: int = 0, limit: int = PAGE_SIZE, q: str = '', show: str = '',
                     user: db.User = Depends(require_user)):
    """A page of the history; `q` searches titles and links, `show` is one of db.SHOWS (or empty: all)."""
    if show and show not in db.SHOWS:
        raise ApiError(400, 'INVALID_REQUEST')
    articles, total = db.history(user.user_id, max(0, offset), min(max(1, limit), 50),
                                 search=q[:MAX_SEARCH_LENGTH], show=show or None)
    return {'books': [jobs.serialize(a) for a in articles], 'total': total}


def _owned(article_id: int, user: db.User) -> db.Article:
    article = db.get_article(article_id)
    if article is None or article.user_id != user.user_id:  # someone else's book looks like no book
        raise ApiError(404, 'NOT_FOUND')
    return article


@router.get('/books/{article_id}')
async def get_book(article_id: int, user: db.User = Depends(book_owner)):
    return {'book': jobs.serialize(_owned(article_id, user))}


@router.delete('/books/{article_id}', status_code=204)
async def delete_book(article_id: int, user: db.User = Depends(book_owner)):
    """Remove one book from the history, with its EPUB."""
    article = _owned(article_id, user)
    if jobs.is_running(article.id):
        raise ApiError(409, 'ALREADY_RUNNING')
    jobs.LIVE.pop(article.id, None)
    db.delete_article(article.id)
    return Response(status_code=204)


class NewBook(BaseModel):
    url: str
    target: str | None = None  # None: only build it, for a look before it goes anywhere
    force: bool = False


class Resend(BaseModel):
    target: str | None = None  # None: build it again, without delivering (a retry after a failure)


def _targets(target: str, user: db.User) -> set[str]:
    if target not in jobs.TARGETS:
        raise ApiError(400, 'INVALID_TARGET')
    if target == db.KINDLE and not user.kindle_email:
        raise ApiError(400, 'NO_KINDLE')
    return {jobs.TARGETS[target]}


def _clean_url(text: str) -> str:
    url = normalize_url(text) if text.strip() else ''
    if (not url or len(url) > MAX_URL_LENGTH or re.search(r'\s', url)
            or not re.match(r'^https?://[^/\s]+\.[^/\s]+', url, re.I)):
        raise ApiError(400, 'INVALID_URL')
    return url


def _guard_capacity(user: db.User, app: State) -> None:
    limit = jobs.MAX_ACTIVE_PER_GUEST if user.is_guest else jobs.MAX_ACTIVE_PER_USER
    if jobs.active_count(user.user_id) >= limit or not app.books_per_user.allow(str(user.user_id)):
        raise ApiError(429, 'RATE_LIMITED')


@router.post('/books', status_code=202)
async def new_book(body: NewBook, request: Request, app: State = Depends(state)):
    """
    Make a book. Without a sign-in this is a try: the book is only built (to look at and download),
    under a guest account that moves into the real one when the visitor signs in.
    """
    url = _clean_url(body.url)
    user = current_user(request)
    if user is None:
        if body.target is not None:  # delivering needs an account with an address
            raise ApiError(401, 'UNAUTHENTICATED')
        if not app.guest_books_per_ip.allow(client_ip(request)):
            raise ApiError(429, 'RATE_LIMITED')
        user = current_guest(request) or start_guest(request)
    targets = set() if body.target is None else _targets(body.target, user)
    _guard_capacity(user, app)
    article_id, outcome = await jobs.start(user, url, targets, force=body.force)
    if outcome is not None and outcome.duplicate:
        raise ApiError(409, 'DUPLICATE', book=jobs.serialize(outcome.duplicate))
    if article_id is None:
        raise ApiError(500, 'UNKNOWN')
    return {'book': jobs.serialize(db.get_article(article_id))}


@router.post('/books/{article_id}/send', status_code=202)
async def send_book(article_id: int, body: Resend, request: Request, user: db.User = Depends(book_owner),
                    app: State = Depends(state)):
    if user.is_guest and body.target is not None:  # a guest may only retry a failed build
        raise ApiError(401, 'UNAUTHENTICATED')
    if user.is_guest and not app.guest_books_per_ip.allow(client_ip(request)):
        raise ApiError(429, 'RATE_LIMITED')
    article = _owned(article_id, user)
    targets = set() if body.target is None else _targets(body.target, user)
    if jobs.is_running(article.id):
        raise ApiError(409, 'ALREADY_RUNNING')
    _guard_capacity(user, app)
    started, outcome = await jobs.start(user, article.article_url, targets, article_id=article.id, force=True)
    if started is None:
        raise ApiError(500, 'UNKNOWN')
    return {'book': jobs.serialize(db.get_article(article.id))}


def _filename(title: str | None) -> str:
    slug = re.sub(r'[^\w\- ]+', '', title or '', flags=re.UNICODE).strip().replace(' ', '-')[:80]
    return f'{slug or "book"}.epub'


def _built(article_id: int, user: db.User) -> db.Article:
    """The user's book with its EPUB on disk."""
    article = _owned(article_id, user)
    # Nothing built yet. The path is only stored once the file is complete, and a book that has one is never
    # rebuilt (a resend reuses it), so it can be served while it is being re-sent, and after a restart
    if not article.epub_path:
        raise ApiError(404, 'NOT_FOUND')
    if not os.path.exists(article.epub_path):
        raise ApiError(410, 'FILE_GONE')  # the disk monitor cleans up old books
    return article


@router.get('/books/{article_id}/preview')
async def preview_book(article_id: int, request: Request, user: db.User = Depends(book_owner)):
    article = _built(article_id, user)
    try:
        page = await asyncio.to_thread(preview.render, article.epub_path, article.title,
                                       request_language(request, user))
    except preview.PreviewError as e:
        logger.error(f'Could not preview book {article.id}: {e}')
        raise ApiError(500, 'PREVIEW_FAILED')
    return HTMLResponse(page, headers={'Content-Security-Policy': preview.CSP,
                                       'Cache-Control': 'private, no-store'})


class Feedback(BaseModel):
    reasons: list[str] = Field(default_factory=list, max_length=len(feedback.REASONS))
    message: str = Field(default='', max_length=feedback.MAX_MESSAGE)


@router.post('/books/{article_id}/feedback', status_code=204)
async def book_feedback(article_id: int, body: Feedback, user: db.User = Depends(require_user),
                        app: State = Depends(state)):
    article = _owned(article_id, user)
    reasons = [r for r in feedback.REASONS if r in body.reasons]  # known ones, in a fixed order
    message = body.message.strip()
    if len(reasons) != len(set(body.reasons)) or not (reasons or message):
        raise ApiError(400, 'INVALID_REQUEST')
    if not app.settings.feedback:
        raise ApiError(503, 'FEEDBACK_UNAVAILABLE')
    if not app.feedback_per_user.allow(str(user.user_id)):
        raise ApiError(429, 'RATE_LIMITED')
    try:
        await feedback.send(app.settings, user, article, reasons, message, _filename(article.title))
    except feedback.FeedbackError:
        raise ApiError(502, 'FEEDBACK_FAILED')
    return Response(status_code=204)


@router.get('/books/{article_id}/epub')
async def download_book(article_id: int, user: db.User = Depends(require_user)):
    """The EPUB file. Only for signed-in accounts: a visitor may look at the preview, then sign in to keep it."""
    article = _built(article_id, user)
    return FileResponse(article.epub_path, media_type='application/epub+zip', filename=_filename(article.title),
                        headers={'Cache-Control': 'private, no-store'})
