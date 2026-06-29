"""Sync-server auth — the server is an OIDC **resource server**: it validates the Authentik access token (the same
platform accounts SP1 made callosum a client of) and scopes storage to the token's ``sub``.

The verifier is an injectable **Protocol** so tests run with a fake (a fixed ``sub``) and prod uses ``JwksVerifier``
(issuer + audience + signature via Authentik's JWKS, lazy ``PyJWT[crypto]`` — like ``api/auth/oidc.py``). A
verification failure raises ``InvalidToken`` → the route maps it to **401** (fail-closed; never trust an unverified
token).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class InvalidToken(Exception):
    """The bearer token is missing, malformed, expired, or fails signature/issuer/audience checks — fail closed."""


@dataclass(frozen=True)
class Identity:
    sub: str  # the account id — scopes every row to this user


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Identity: ...


class JwksVerifier:
    """Validates an Authentik-issued JWT access token against the issuer's JWKS. Lazy-imports PyJWT so the server's
    test path (with an injected fake verifier) needs no crypto extras loaded."""

    def __init__(self, issuer: str, audience: str, jwks_url: str | None = None) -> None:
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._jwks_url = jwks_url or f"{self._issuer}/jwks/"
        self._jwk_client = None

    def verify(self, token: str) -> Identity:
        try:
            import jwt
            from jwt import PyJWKClient
        except ImportError as exc:  # pragma: no cover - prod-only dependency
            raise InvalidToken("JWT verification unavailable") from exc
        if self._jwk_client is None:
            self._jwk_client = PyJWKClient(self._jwks_url)
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
            )
        except Exception as exc:  # any decode/verify failure → fail closed
            raise InvalidToken("token verification failed") from exc
        sub = claims.get("sub")
        if not sub:
            raise InvalidToken("token has no subject")
        return Identity(sub=str(sub))


def verifier_from_env() -> TokenVerifier | None:
    """A ``JwksVerifier`` from ``CALLOSUM_SYNC_OIDC_ISSUER`` + ``CALLOSUM_SYNC_OIDC_AUDIENCE`` (+ optional
    ``…_JWKS_URL``), or None when unconfigured (the server then refuses every request — default-closed)."""
    issuer = os.getenv("CALLOSUM_SYNC_OIDC_ISSUER")
    audience = os.getenv("CALLOSUM_SYNC_OIDC_AUDIENCE")
    if not issuer or not audience:
        return None
    return JwksVerifier(issuer, audience, os.getenv("CALLOSUM_SYNC_OIDC_JWKS_URL"))
