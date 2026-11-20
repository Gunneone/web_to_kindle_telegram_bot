"""
Signing in and out: email code, Google, Telegram.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from core import accounts, kindle
from email_sender import EmailError

from . import auth_email
from .auth_oidc import OidcError, safe_next
from .deps import State, client_ip, current_user, request_language, sign_in_session, state
from .errors import ApiError
from .routes_api import me_payload
from .texts import pick_language

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api/auth')


class EmailStart(BaseModel):
    email: str
    lang: str | None = None
    next: str = '/'  # where the link in the mail leads after signing in


class EmailVerify(BaseModel):
    email: str | None = None
    code: str | None = None
    token: str | None = None


@router.post('/email/start', status_code=204)
async def email_start(body: EmailStart, request: Request, app: State = Depends(state)):
    email = kindle.normalize_email(body.email)
    if len(email) > 254 or not kindle.looks_like_email(email):
        raise ApiError(400, 'INVALID_EMAIL')
    if not app.email_per_ip.allow(client_ip(request)) or not app.email_per_address.allow(email):
        raise ApiError(429, 'RATE_LIMITED')
    lang = pick_language(body.lang, request_language(request))
    code, token = app.codes.issue(email)
    try:
        await asyncio.to_thread(auth_email.send_code, app.settings, email, code, token, lang,
                                safe_next(body.next))
    except EmailError as e:
        logger.error(f'Could not mail a sign-in code: {e}')
        raise ApiError(502, 'EMAIL_FAILED')
    return Response(status_code=204)


@router.post('/email/verify')
async def email_verify(body: EmailVerify, request: Request, app: State = Depends(state)):
    if not app.verify_per_ip.allow(client_ip(request)):
        raise ApiError(429, 'RATE_LIMITED')
    try:
        if body.token:
            email = app.codes.verify_token(body.token)
        elif body.email and body.code:
            email = kindle.normalize_email(body.email)
            app.codes.verify_code(email, body.code)
        else:
            raise ApiError(400, 'INVALID_REQUEST')
    except auth_email.CodeError as e:
        raise ApiError(400, e.code)
    current = current_user(request)
    try:
        user = accounts.sign_in(accounts.EMAIL, email, email=email, current_user_id=current.user_id if current else None)
    except accounts.LinkConflict:
        raise ApiError(409, 'LINK_CONFLICT')
    sign_in_session(request, user)
    return {'user': me_payload(user, request)}


@router.post('/signout', status_code=204)
async def signout(request: Request):
    request.session.clear()
    return Response(status_code=204)


def _failure(request: Request, code: str) -> RedirectResponse:
    page = '/settings' if current_user(request) else '/signin'
    return RedirectResponse(f'{page}?error={code}', status_code=303)


@router.get('/{provider}/start')
async def oidc_start(provider: str, request: Request, next: str = '/', app: State = Depends(state)):
    if app.oidc.client(provider) is None:
        return _failure(request, 'PROVIDER_UNAVAILABLE')
    try:
        url = await app.oidc.start(provider, request.session, safe_next(next))
    except Exception:
        logger.exception(f'Could not start the {provider} sign-in')
        return _failure(request, 'PROVIDER_ERROR')
    return RedirectResponse(url, status_code=303)


@router.get('/{provider}/callback')
async def oidc_callback(provider: str, request: Request, app: State = Depends(state)):
    if app.oidc.client(provider) is None:
        return _failure(request, 'PROVIDER_UNAVAILABLE')
    current = current_user(request)
    try:
        identity, next_path = await app.oidc.finish(provider, request.session, dict(request.query_params))
        user = accounts.sign_in(
            identity.provider, identity.subject, email=identity.email, username=identity.username,
            first_name=identity.first_name, last_name=identity.last_name,
            current_user_id=current.user_id if current else None)
    except OidcError as e:
        return _failure(request, e.code)
    except accounts.LinkConflict:
        return _failure(request, 'LINK_CONFLICT')
    except Exception:
        logger.exception(f'The {provider} sign-in failed')
        return _failure(request, 'PROVIDER_ERROR')
    sign_in_session(request, user)
    return RedirectResponse(next_path, status_code=303)
