"""
What the routes share: the settings, the limiters, and who is signed in.
"""

from dataclasses import dataclass, field

from fastapi import Request

from core import db

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


def state(request: Request) -> State:
    return request.app.state.eselsohr


def client_ip(request: Request) -> str:
    return request.client.host if request.client else 'unknown'


def current_user(request: Request) -> db.User | None:
    user_id = request.session.get('uid')
    user = db.get_user(user_id) if isinstance(user_id, int) else None
    if user is None and 'uid' in request.session:
        request.session.pop('uid')
    return user


def require_user(request: Request) -> db.User:
    user = current_user(request)
    if user is None:
        raise ApiError(401, 'UNAUTHENTICATED')
    return user


def request_language(request: Request, user: db.User | None = None) -> str:
    return pick_language(user.language if user else None, request.headers.get('accept-language'))


def sign_in_session(request: Request, user: db.User) -> None:
    """Start a fresh session for the user (the old one, with any pending sign-in state, is dropped)."""
    request.session.clear()
    request.session['uid'] = user.user_id
