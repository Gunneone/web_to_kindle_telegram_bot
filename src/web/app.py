"""
The FastAPI app: the JSON API under /api and the built React client everywhere else.
"""

import base64
import hashlib
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from core import db

from . import config
from .auth_email import CodeStore
from .auth_oidc import Oidc
from .deps import State
from .errors import ApiError
from .routes_api import router as api_router
from .routes_auth import router as auth_router

logger = logging.getLogger(__name__)

SESSION_COOKIE = 'eselsohr_session'
SESSION_MAX_AGE = 90 * 24 * 3600
UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
INLINE_SCRIPT = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', re.S | re.I)


def _csp(settings: config.Settings, index_html: str | None) -> str:
    hashes = ' '.join(
        "'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'"
        for body in INLINE_SCRIPT.findall(index_html or '') if body.strip())
    ds = settings.ds_origin
    return '; '.join([
        "default-src 'self'",
        f"script-src 'self' {ds} {hashes}".strip(),
        f"style-src 'self' {ds}",
        "style-src-attr 'unsafe-inline'",  # React's style={{…}} attributes
        f"font-src 'self' {ds}",
        f"img-src 'self' data: {ds}",
        "connect-src 'self'",
        "frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'", "object-src 'none'",
    ])


def create_app(settings: config.Settings | None = None) -> FastAPI:
    settings = settings or config.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.init_db()
        yield

    app = FastAPI(title='Eselsohr', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.eselsohr = State(settings=settings, oidc=Oidc(settings), codes=CodeStore(settings.session_secret))

    index_file = settings.dist_dir / 'index.html'
    index_html = index_file.read_text(encoding='utf-8') if index_file.exists() else None
    csp = _csp(settings, index_html)

    @app.exception_handler(ApiError)
    async def api_error(_request: Request, e: ApiError):
        return JSONResponse({'error': {'code': e.code, **e.extra}}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def invalid(_request: Request, _e: RequestValidationError):
        return JSONResponse({'error': {'code': 'INVALID_REQUEST'}}, status_code=400)

    @app.middleware('http')
    async def guard(request: Request, call_next):
        path = request.url.path
        if request.method in UNSAFE_METHODS and path.startswith('/api/'):
            origin = request.headers.get('origin')
            if origin is not None and origin != settings.origin:
                return JSONResponse({'error': {'code': 'FORBIDDEN'}}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault('Content-Security-Policy', csp)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        if settings.https:
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000')
        if path.startswith('/api/'):
            response.headers.setdefault('Cache-Control', 'no-store')
        return response

    # Added last, so it wraps the guard and the session is there for every route
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, session_cookie=SESSION_COOKIE,
                       max_age=SESSION_MAX_AGE, same_site='lax', https_only=settings.https)

    app.include_router(auth_router)
    app.include_router(api_router)

    @app.api_route('/api/{rest:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], include_in_schema=False)
    async def api_not_found(rest: str):
        raise ApiError(404, 'NOT_FOUND')

    assets = settings.dist_dir / 'assets'
    if assets.is_dir():
        class ImmutableFiles(StaticFiles):
            async def get_response(self, path, scope):
                response = await super().get_response(path, scope)
                response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
                return response

        app.mount('/assets', ImmutableFiles(directory=assets), name='assets')

    dist_root = settings.dist_dir.resolve()

    @app.api_route('/{path:path}', methods=['GET', 'HEAD'], include_in_schema=False)
    async def client(path: str):
        if index_html is None:
            return PlainTextResponse('The client is not built. Run `npm run build` in frontend/, '
                                     'or use the Vite dev server.', status_code=503)
        candidate = (dist_root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist_root) and candidate != dist_root / 'index.html':
            return FileResponse(candidate, headers={'Cache-Control': 'public, max-age=3600'})
        return FileResponse(dist_root / 'index.html', headers={'Cache-Control': 'no-cache'})

    return app
