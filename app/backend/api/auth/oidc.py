"""OIDC client for the optional "Sign in with ORCID" flow (SP1).

Authorization-code + PKCE against the callosum account platform (Authentik), which brokers ORCID and returns the
verified ORCID iD as a claim. Built on ``httpx`` (already a dep) + ``PyJWT[crypto]`` for id-token verification — the
JWT signature/JWKS check is **lazy-imported** so the app + the hermetic test suite run without PyJWT installed (only
the LIVE round-trip needs it). Pure of FastAPI; the client is injectable (``create_app(oidc_client=…)``) so tests use
a fake and never touch the network or crypto. Identity-only — no library data is sent.

Sub-tlety to carry forward: a public/native client uses PKCE and **no client secret** (RFC 8252); the redirect is a
loopback URI validated in the router. The id-token's ``sub`` is whatever the platform issues; the **ORCID iD** rides a
configured claim (default ``orcid``) the platform maps from its ORCID connector.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.backend import app_settings


class OidcError(Exception):
    """Any OIDC failure (discovery/token/verify). The router catches it → a graceful sign-in error, never a 500."""


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    client_id: str
    scopes: str = "openid profile"
    orcid_claim: str = "orcid"


@dataclass(frozen=True)
class Identity:
    sub: str
    display_name: str | None
    orcid: str | None
    expires_at: int | None


def generate_pkce() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for S256 PKCE (the challenge is base64url(sha256(verifier)))."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(32)


class OidcClient:
    """A thin authorization-code+PKCE OIDC client. The pure parts (PKCE, authorize-URL build, claim→Identity
    mapping) are unit-tested; the network discovery/token-exchange + JWKS id-token verification are the LIVE path
    (the maintainer's manual check), mirroring the LibreOffice/Word adapter pattern."""

    def __init__(self, config: OidcConfig, *, http: httpx.Client | None = None, timeout: float = 15.0) -> None:
        self.config = config
        self._http = http  # injectable; when None each call opens + closes its own short-lived client
        self._timeout = timeout
        self._discovery: dict | None = None

    # --- network ---
    def _get_json(self, url: str) -> dict:
        if self._http is not None:
            resp = self._http.get(url)
        else:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url)
        resp.raise_for_status()
        return resp.json()

    def _post_form(self, url: str, data: dict) -> dict:
        if self._http is not None:
            resp = self._http.post(url, data=data)
        else:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, data=data)
        resp.raise_for_status()
        return resp.json()

    def discovery(self) -> dict:
        """The issuer's OIDC discovery document (cached). Endpoints come from here, not from request data → no SSRF."""
        if self._discovery is None:
            try:
                self._discovery = self._get_json(f"{self.config.issuer}/.well-known/openid-configuration")
            except Exception as exc:  # noqa: BLE001 — any network/parse failure is an OIDC failure
                raise OidcError(f"OIDC discovery failed: {exc}") from exc
        return self._discovery

    # --- pure (unit-tested) ---
    def build_authorize_url(self, *, redirect_uri: str, state: str, code_challenge: str) -> str:
        d = self.discovery()
        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.config.scopes,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{d['authorization_endpoint']}?{urlencode(params)}"

    def _claims_to_identity(self, claims: dict) -> Identity:
        exp = claims.get("exp")
        return Identity(
            sub=str(claims.get("sub") or ""),
            display_name=claims.get("name") or claims.get("preferred_username") or None,
            orcid=claims.get(self.config.orcid_claim) or None,
            expires_at=int(exp) if exp else None,
        )

    # --- live (manual-check) ---
    def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> dict:
        d = self.discovery()
        try:
            return self._post_form(
                d["token_endpoint"],
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self.config.client_id,
                    "code_verifier": code_verifier,
                },
            )
        except Exception as exc:  # noqa: BLE001
            raise OidcError(f"Token exchange failed: {exc}") from exc

    def identity_from_tokens(self, tokens: dict) -> Identity:
        id_token = tokens.get("id_token")
        if not id_token:
            raise OidcError("No id_token in the token response.")
        return self._claims_to_identity(self._verify_id_token(id_token))

    def _verify_id_token(self, id_token: str) -> dict:
        # Lazy import: PyJWT is only needed for the live path, so the module + hermetic tests don't require it.
        try:
            import jwt
            from jwt import PyJWKClient
        except ImportError as exc:  # pragma: no cover - the dep is declared; this guards a missing install
            raise OidcError("PyJWT[crypto] is required for sign-in. Install it (see requirements.txt).") from exc
        d = self.discovery()
        try:
            signing_key = PyJWKClient(d["jwks_uri"]).get_signing_key_from_jwt(id_token)
            return jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.config.client_id,
                issuer=d.get("issuer", self.config.issuer),
                options={"require": ["exp", "iss", "aud"]},
            )
        except Exception as exc:  # noqa: BLE001 — a verification failure is never trusted
            raise OidcError(f"id-token verification failed: {exc}") from exc


def build_oidc_client_from_env() -> OidcClient | None:
    """Build the default client from the environment, or None when sign-in isn't configured (issuer/client absent)."""
    cfg = app_settings.oidc_config()
    if cfg is None:
        return None
    return OidcClient(
        OidcConfig(
            issuer=cfg["issuer"],
            client_id=cfg["client_id"],
            scopes=cfg["scopes"],
            orcid_claim=cfg["orcid_claim"],
        )
    )
