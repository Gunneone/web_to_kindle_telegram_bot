"""
Passwordless email sign-in: a 6-digit code plus a one-click link, both valid for 15 minutes.
Only hashes are kept (in memory: a restart just means asking for a new code).
"""

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass
from urllib.parse import quote

from email_sender import send_message

from .config import Settings
from .texts import t

logger = logging.getLogger(__name__)

TTL_SECONDS = 15 * 60
MAX_ATTEMPTS = 5


class CodeError(Exception):
    """code: WRONG_CODE, EXPIRED or TOO_MANY_ATTEMPTS"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class _Entry:
    code_hash: str
    token_hash: str
    expires: float
    attempts: int = 0


class CodeStore:
    def __init__(self, secret: str):
        self._key = secret.encode()
        self._by_email: dict[str, _Entry] = {}
        self._email_by_token: dict[str, str] = {}

    def _hash(self, value: str) -> str:
        return hmac.new(self._key, value.encode(), hashlib.sha256).hexdigest()

    def issue(self, email: str) -> tuple[str, str]:
        """A fresh (code, link token) for the address; any earlier code for it stops working."""
        self._prune()
        self._drop(email)
        code = f'{secrets.randbelow(1_000_000):06d}'
        token = secrets.token_urlsafe(24)
        entry = _Entry(self._hash(code), self._hash(token), time.monotonic() + TTL_SECONDS)
        self._by_email[email] = entry
        self._email_by_token[entry.token_hash] = email
        return code, token

    def verify_code(self, email: str, code: str) -> None:
        entry = self._by_email.get(email)
        if entry is None or entry.expires < time.monotonic():
            self._drop(email)
            raise CodeError('EXPIRED')
        if entry.attempts >= MAX_ATTEMPTS:
            raise CodeError('TOO_MANY_ATTEMPTS')
        entry.attempts += 1
        if not hmac.compare_digest(entry.code_hash, self._hash(code.strip())):
            if entry.attempts >= MAX_ATTEMPTS:
                self._drop(email)
                raise CodeError('TOO_MANY_ATTEMPTS')
            raise CodeError('WRONG_CODE')
        self._drop(email)

    def verify_token(self, token: str) -> str:
        """The address a link token was issued for; the token is used up."""
        email = self._email_by_token.get(self._hash(token))
        entry = self._by_email.get(email) if email else None
        if entry is None or entry.expires < time.monotonic():
            if email:
                self._drop(email)
            raise CodeError('EXPIRED')
        self._drop(email)
        return email

    def _drop(self, email: str) -> None:
        entry = self._by_email.pop(email, None)
        if entry:
            self._email_by_token.pop(entry.token_hash, None)

    def _prune(self) -> None:
        now = time.monotonic()
        for email in [e for e, entry in self._by_email.items() if entry.expires < now]:
            self._drop(email)


def send_code(settings: Settings, email: str, code: str, token: str, lang: str, next_path: str = '/') -> None:
    """
    Mail the code (blocking: call it in a thread). The link signs in and then opens `next_path`, a path on
    this site (checked by the caller). Raises email_sender.EmailError.
    """
    link = f'{settings.public_url}/signin/verify?token={token}'
    if next_path != '/':
        link += f'&next={quote(next_path, safe="/")}'
    if settings.mail == 'log':
        logger.warning(f'Sign-in code for {email}: {code}  (link: {link})')
        return
    minutes = TTL_SECONDS // 60
    send_message(email, t(lang, 'code_subject', code=code),
                 t(lang, 'code_text', code=code, link=link, minutes=minutes),
                 t(lang, 'code_html', code=code, link=link, minutes=minutes))
