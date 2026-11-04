"""
"Continue with Google / Telegram": OpenID Connect, authorization code flow with PKCE.

Both providers are used the same way: send the browser to the authorization endpoint, exchange the
code on the server, and verify the signed ID token against the provider's published keys. Telegram
has no userinfo endpoint, so everything comes from the ID token.
"""

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from .config import OidcClient, Settings

STATE_TTL = 10 * 60
MAX_PENDING = 5

DISCOVERY = {
    'google': 'https://accounts.google.com/.well-known/openid-configuration',
    'telegram': 'https://oauth.telegram.org/.well-known/openid-configuration',
}
SCOPES = {'google': 'openid email profile', 'telegram': 'openid profile'}
ALGORITHMS = ['RS256', 'ES256', 'EdDSA', 'ES256K']


class OidcError(Exception):
    """code: ACCESS_DENIED, SESSION_EXPIRED, PROVIDER_ERROR, INVALID_TOKEN, EMAIL_UNVERIFIED"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class Identity:
    provider: str
    subject: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


def safe_next(value: str | None) -> str:
    """Only paths on this site: '/settings' yes, '//evil.com' and 'https://evil.com' no."""
    if value and value.startswith('/') and not value.startswith('//') and '\\' not in value and '\n' not in value:
        return value
    return '/'


def _pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()


class Oidc:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self.settings = settings
        self.http = http or httpx.AsyncClient(timeout=10)
        self._metadata: dict[str, dict] = {}
        self._keys: dict[str, tuple[float, KeySet]] = {}

    def client(self, provider: str) -> OidcClient | None:
        return getattr(self.settings, provider, None) if provider in DISCOVERY else None

    def redirect_uri(self, provider: str) -> str:
        return f'{self.settings.public_url}/api/auth/{provider}/callback'

    async def _discover(self, provider: str) -> dict:
        if provider not in self._metadata:
            response = await self.http.get(DISCOVERY[provider])
            response.raise_for_status()
            self._metadata[provider] = response.json()
        return self._metadata[provider]

    async def _key_set(self, provider: str, refresh: bool = False) -> KeySet:
        cached = self._keys.get(provider)
        if cached and not refresh and time.monotonic() - cached[0] < 3600:
            return cached[1]
        metadata = await self._discover(provider)
        response = await self.http.get(metadata['jwks_uri'])
        response.raise_for_status()
        key_set = KeySet.import_key_set(response.json())
        self._keys[provider] = (time.monotonic(), key_set)
        return key_set

    async def start(self, provider: str, session: dict, next_path: str) -> str:
        """The URL to send the browser to. Remembers state, PKCE verifier and nonce in the session."""
        client = self.client(provider)
        metadata = await self._discover(provider)
        state, verifier, nonce = (secrets.token_urlsafe(24) for _ in range(3))
        pending = {s: v for s, v in session.get('oidc', {}).items() if time.time() - v['at'] < STATE_TTL}
        while len(pending) >= MAX_PENDING:
            pending.pop(next(iter(pending)))
        pending[state] = {'provider': provider, 'verifier': verifier, 'nonce': nonce,
                          'next': safe_next(next_path), 'at': time.time()}
        session['oidc'] = pending
        query = httpx.QueryParams({
            'client_id': client.client_id, 'redirect_uri': self.redirect_uri(provider), 'response_type': 'code',
            'scope': SCOPES[provider], 'state': state, 'nonce': nonce,
            'code_challenge': _pkce_challenge(verifier), 'code_challenge_method': 'S256',
        })
        return f"{metadata['authorization_endpoint']}?{query}"

    async def finish(self, provider: str, session: dict, params: dict) -> tuple[Identity, str]:
        """Check the callback and return who signed in and where to go next."""
        pending = session.get('oidc', {}).pop(params.get('state') or '', None)
        if params.get('error'):
            raise OidcError('ACCESS_DENIED')
        if not pending or pending['provider'] != provider or time.time() - pending['at'] > STATE_TTL:
            raise OidcError('SESSION_EXPIRED')
        if not params.get('code'):
            raise OidcError('PROVIDER_ERROR')

        client = self.client(provider)
        metadata = await self._discover(provider)
        try:
            response = await self.http.post(
                metadata['token_endpoint'], auth=httpx.BasicAuth(client.client_id, client.client_secret),
                data={'grant_type': 'authorization_code', 'code': params['code'], 'client_id': client.client_id,
                      'redirect_uri': self.redirect_uri(provider), 'code_verifier': pending['verifier']})
            response.raise_for_status()
            id_token = response.json()['id_token']
        except (httpx.HTTPError, KeyError, ValueError):
            raise OidcError('PROVIDER_ERROR')

        claims = await self._verify(provider, metadata, client, id_token, pending['nonce'])
        return self._identity(provider, claims), pending['next']

    async def _verify(self, provider: str, metadata: dict, client: OidcClient, id_token: str, nonce: str) -> dict:
        registry = jwt.JWTClaimsRegistry(
            leeway=60,
            iss={'essential': True, 'value': metadata['issuer']},
            aud={'essential': True, 'value': client.client_id},
            exp={'essential': True}, iat={'essential': False}, sub={'essential': True})
        for refresh in (False, True):  # a provider may have rotated its keys since we cached them
            try:
                token = jwt.decode(id_token, await self._key_set(provider, refresh), algorithms=ALGORITHMS)
                registry.validate(token.claims)
                break
            except (JoseError, ValueError, KeyError):
                if refresh:
                    raise OidcError('INVALID_TOKEN')
            except httpx.HTTPError:
                raise OidcError('PROVIDER_ERROR')
        # Telegram doesn't document echoing the nonce; the code flow with PKCE and state covers replay
        if 'nonce' in token.claims and not secrets.compare_digest(str(token.claims['nonce']), nonce):
            raise OidcError('INVALID_TOKEN')
        return token.claims

    @staticmethod
    def _identity(provider: str, claims: dict) -> Identity:
        if provider == 'google':
            if claims.get('email_verified') not in (True, 'true') or not claims.get('email'):
                raise OidcError('EMAIL_UNVERIFIED')
            return Identity('google', str(claims['sub']), email=claims['email'].lower(),
                            first_name=claims.get('given_name') or claims.get('name'),
                            last_name=claims.get('family_name'))
        # Telegram: the numeric account id is the `id` claim
        raw = claims.get('id', claims.get('sub'))
        try:
            subject = str(int(raw))
        except (TypeError, ValueError):
            raise OidcError('INVALID_TOKEN')
        name = (claims.get('name') or '').strip()
        first, _, last = name.partition(' ')
        return Identity('telegram', subject, username=claims.get('preferred_username'),
                        first_name=claims.get('given_name') or first or None,
                        last_name=claims.get('family_name') or last or None)
