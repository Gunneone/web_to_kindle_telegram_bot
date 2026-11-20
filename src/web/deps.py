"""
What the routes share: the settings, the limiters, and who is signed in.
"""

from dataclasses import dataclass, field

from fastapi import Request

from core import accounts, db

from .auth_email import CodeStore
from .auth_oidc import Oidc
from .config import Settings
from .errors import ApiError
from .limits import RateLimiter
from .texts import pick_language


@dataclass
class State:
    settings: Settings
    oidc: Oidc
    codes: CodeStore
    email_per_address: RateLimiter = field(default_factory=lambda: RateLimiter(3, 15 * 60))
    email_per_ip: RateLimiter = field(default_factory=lambda: RateLimiter(10, 3600))
    verify_per_ip: RateLimiter = field(default_factory=lambda: RateLimiter(30, 3600))
    books_per_user: RateLimiter = field(default_factory=lambda: RateLimiter(30, 3600))
    test_books_per_user: RateLimiter = field(default_factory=lambda: RateLimiter(3, 3600))
    feedback_per_user: RateLimiter = field(default_factory=lambda: RateLimiter(5, 3600))
    # Trying it without signing in: a few books per address and hour, previews and downloads only
    guest_books_per_ip: RateLimiter = field(default_factory=lambda: RateLimiter(5, 3600))


def state(request: Request) -> State:
    return request.app.state.eselsohr


def client_ip(request: Request) -> str:
    return request.client.host if request.client else 'unknown'


GUEST_KEY = 'guest'


def current_user(request: Request) -> db.User | None:
    """The signed-in account. A guest (someone trying it without signing in) is not one."""
    user_id = request.session.get('uid')
    user = db.get_user(user_id) if isinstance(user_id, int) else None
    if user is not None and user.is_guest:
        user = None
    if user is None and 'uid' in request.session:
        request.session.pop('uid')
    return user


def current_guest(request: Request) -> db.User | None:
    """The guest account of a visitor who made a book without signing in, while it still exists."""
    user_id = request.session.get(GUEST_KEY)
    user = db.get_user(user_id) if isinstance(user_id, int) else None
    if user is not None and not user.is_guest:
        user = None
    if user is None and GUEST_KEY in request.session:
        request.session.pop(GUEST_KEY)
    return user


def start_guest(request: Request) -> db.User:
    user = accounts.new_guest()
    request.session[GUEST_KEY] = user.user_id
    return user


def book_owner(request: Request) -> db.User:
    """Whoever may look at their own books: the signed-in account, else the visitor's guest account."""
    user = current_user(request) or current_guest(request)
    if user is None:
        raise ApiError(401, 'UNAUTHENTICATED')
    return user


def require_user(request: Request) -> db.User:
    user = current_user(request)
    if user is None:
        raise ApiError(401, 'UNAUTHENTICATED')
    return user


def request_language(request: Request, user: db.User | None = None) -> str:
    return pick_language(user.language if user else None, request.headers.get('accept-language'))


def sign_in_session(request: Request, user: db.User) -> None:
    """
    Start a fresh session for the user (the old one, with any pending sign-in state, is dropped).
    Books made as a guest before signing in move to the account.
    """
    guest = current_guest(request)
    request.session.clear()
    request.session['uid'] = user.user_id
    if guest is not None and guest.user_id != user.user_id:
        accounts.merge(guest.user_id, user.user_id)
