"""
Settings read from the environment (.env).
"""

import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEFAULT_DIST = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'


@dataclass(frozen=True)
class OidcClient:
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class Settings:
    public_url: str  # where the site is served, e.g. https://eselsohr.gunne.one
    session_secret: str
    google: OidcClient | None
    telegram: OidcClient | None
    dist_dir: Path
    mail: str  # 'smtp': send sign-in codes by mail; 'log': print them (development)
    g1_ds_url: str  # the shared gunne.one design system

    @property
    def https(self) -> bool:
        return self.public_url.startswith('https://')

    @property
    def origin(self) -> str:
        parts = urlparse(self.public_url)
        return f'{parts.scheme}://{parts.netloc}'

    @property
    def ds_origin(self) -> str:
        parts = urlparse(self.g1_ds_url)
        return f'{parts.scheme}://{parts.netloc}'

    @property
    def providers(self) -> dict[str, bool]:
        return {'google': self.google is not None, 'telegram': self.telegram is not None, 'email': True}


def _client(prefix: str) -> OidcClient | None:
    client_id, secret = os.getenv(f'{prefix}_CLIENT_ID'), os.getenv(f'{prefix}_CLIENT_SECRET')
    return OidcClient(client_id, secret) if client_id and secret else None


def load() -> Settings:
    load_dotenv()
    public_url = (os.getenv('PUBLIC_URL') or 'http://localhost:5173').rstrip('/')
    secret = os.getenv('SESSION_SECRET')
    if not secret:
        if public_url.startswith('https://'):
            raise RuntimeError('SESSION_SECRET must be set when PUBLIC_URL is https')
        logger.warning('SESSION_SECRET is not set: using a random one, so sign-ins end when the server restarts')
        secret = secrets.token_urlsafe(32)
    mail = (os.getenv('WEB_MAIL') or 'smtp').lower()
    if mail not in ('smtp', 'log'):
        raise RuntimeError("WEB_MAIL must be 'smtp' or 'log'")
    if mail == 'log' and public_url.startswith('https://'):
        raise RuntimeError("WEB_MAIL=log would print sign-in codes; use it only with a local PUBLIC_URL")
    return Settings(
        public_url=public_url,
        session_secret=secret,
        google=_client('GOOGLE'),
        telegram=_client('TELEGRAM_LOGIN'),
        dist_dir=Path(os.getenv('WEB_DIST_DIR') or DEFAULT_DIST),
        mail=mail,
        g1_ds_url=(os.getenv('G1_DS_URL') or 'https://gunne.one/ds/v1').rstrip('/'),
    )
