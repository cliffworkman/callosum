"""Optional-account auth router (SP1): "Sign in with ORCID" via OIDC + PKCE.

- ``GET /auth/login?origin=<browser origin>`` → ``{authorize_url}`` (a fetch — carries the inc-168 bearer when remote
  access is on, so it needs no gate exemption). Sets up the single-use state + PKCE flow server-side. 503 if sign-in
  isn't configured; 422 on a non-loopback redirect.
- ``GET /oauth/callback?code=&state=`` → validate the state, exchange the code (+PKCE verifier), verify the id-token,
  store the session, populate the My-Pubs profile with the VERIFIED ORCID + name, then redirect to ``/``. This is a
  browser **navigation** (no bearer header — the inc-172 gotcha), so it is EXEMPT from the remote-access gate. It
  carries no library data (an opaque code+state validated against the stored verifier).
- ``POST /auth/logout`` → clear the stored session (a fetch; bearer-carried when the gate is on).

Identity-only: nothing about the library is sent. Tokens are stored write-only (``app_settings``); ``GET /settings``
reports only a non-secret status.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi import status as http_status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.backend import app_settings
from app.backend.api.auth import oidc as oidc_mod
from app.backend.persistence import profile_repo

router = APIRouter()
logger = logging.getLogger("callosum")

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_CALLBACK_PATH = "/oauth/callback"


def _client(request: Request) -> oidc_mod.OidcClient | None:
    return getattr(request.app.state, "oidc_client", None)


def _resolve_redirect_uri(origin: str | None) -> str:
    """Build + validate the loopback redirect URI. A configured override wins; otherwise the browser origin + the
    callback path. Rejects anything that isn't an ``http`` loopback address (no open-redirect)."""
    override = (app_settings.oidc_config() or {}).get("redirect_override")
    candidate = override or ((origin or "").rstrip("/") + _CALLBACK_PATH if origin else "")
    parsed = urlparse(candidate)
    if parsed.scheme != "http" or (parsed.hostname or "") not in _LOOPBACK_HOSTS:
        raise HTTPException(status_code=422, detail="Redirect URI must be a loopback (127.0.0.1 / localhost) address.")
    return candidate


class AuthorizeUrl(BaseModel):
    authorize_url: str


@router.get("/auth/login", response_model=AuthorizeUrl)
def auth_login(request: Request, origin: str | None = None) -> AuthorizeUrl:
    client = _client(request)
    if client is None:
        raise HTTPException(status_code=503, detail="Sign-in is not configured on this Callosum.")
    redirect_uri = _resolve_redirect_uri(origin)
    verifier, challenge = oidc_mod.generate_pkce()
    state = oidc_mod.generate_state()
    app_settings.set_oauth_flow(state=state, code_verifier=verifier, redirect_uri=redirect_uri)
    try:
        url = client.build_authorize_url(redirect_uri=redirect_uri, state=state, code_challenge=challenge)
    except oidc_mod.OidcError as exc:
        raise HTTPException(status_code=502, detail="Could not reach the sign-in provider.") from exc
    return AuthorizeUrl(authorize_url=url)


@router.get("/oauth/callback", include_in_schema=False)
def oauth_callback(request: Request, code: str | None = None, state: str | None = None) -> RedirectResponse:
    flow = app_settings.pop_oauth_flow()  # single-use → popped even on error (no replay)
    if not code or not state or not flow or state != flow.get("state"):
        return RedirectResponse(url="/?signin=error", status_code=303)
    client = _client(request)
    if client is None:
        return RedirectResponse(url="/?signin=error", status_code=303)
    try:
        tokens = client.exchange_code(code=code, code_verifier=flow["code_verifier"], redirect_uri=flow["redirect_uri"])
        identity = client.identity_from_tokens(tokens)
    except oidc_mod.OidcError as exc:
        logger.warning("sign-in callback failed: %s", exc)
        return RedirectResponse(url="/?signin=error", status_code=303)

    app_settings.set_oauth_session(
        {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "id_token": tokens.get("id_token"),
            "sub": identity.sub,
            "display_name": identity.display_name,
            "orcid": identity.orcid,
            "email": identity.email,  # SP2: email/Google logins; None for an ORCID-only token
            "expires_at": identity.expires_at,
        }
    )

    # The SP1 payoff: a VERIFIED ORCID populates the My-Pubs profile (reusing profile_repo.upsert_profile), so
    # authorship resolution is authoritative. SP2: only an ORCID login does this — a Google/email login sets the
    # account identity but must NOT overwrite the My-Pubs profile from a non-authoritative display name. Manual
    # name-variants are preserved; the existing display name is the fallback.
    if identity.orcid:
        with request.app.state.engine.begin() as conn:
            existing = profile_repo.get_profile(conn) or {}
            profile_repo.upsert_profile(
                conn,
                display_name=identity.display_name or existing.get("display_name"),
                name_variants=existing.get("name_variants") or [],
                orcid=identity.orcid,
            )

    return RedirectResponse(url="/?signin=ok", status_code=303)


@router.post("/auth/logout", status_code=http_status.HTTP_204_NO_CONTENT)
def auth_logout() -> Response:
    app_settings.clear_oauth_session()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
