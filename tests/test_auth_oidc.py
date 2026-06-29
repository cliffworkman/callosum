"""SP1 optional-account "Sign in with ORCID" (OIDC + PKCE) — hermetic tests.

An injected fake OIDC client exercises the security-relevant FLOW (state + PKCE storage, callback validation,
write-only token storage, the verified ORCID → My-Pubs profile, the callback gate-exemption, logout) with no
network. The real client's PURE helpers (PKCE, authorize-URL build, claim→Identity mapping) are unit-tested; the
JWKS-verified live round-trip is the maintainer's manual check. The autouse conftest fixture isolates
``CALLOSUM_SETTINGS_PATH`` per test, so token/session writes never touch the real store.
"""

from __future__ import annotations

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.backend import app_settings
from app.backend.api import create_app
from app.backend.api.auth.oidc import Identity, OidcClient, OidcConfig, generate_pkce


class FakeOidcClient:
    """Canned OIDC client — no network. Records calls so tests can assert the flow."""

    def __init__(self) -> None:
        self.exchanged: list[dict] = []

    def build_authorize_url(self, *, redirect_uri: str, state: str, code_challenge: str) -> str:
        # Echo the server-generated state so the test can read it back (the real provider returns it on the callback).
        return (
            f"https://idp.example/authorize?state={state}&redirect_uri={redirect_uri}&code_challenge={code_challenge}"
        )

    def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> dict:
        self.exchanged.append({"code": code, "code_verifier": code_verifier, "redirect_uri": redirect_uri})
        return {"access_token": "fake-access-TOKENXYZ", "refresh_token": "fake-refresh-RRR", "id_token": "fake.jwt"}

    def identity_from_tokens(self, tokens: dict) -> Identity:
        return Identity(sub="u-123", display_name="Ada Lovelace", orcid="0000-0002-1825-0097", expires_at=9999999999)


def _configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALLOSUM_OIDC_ISSUER", "https://idp.example")
    monkeypatch.setenv("CALLOSUM_OIDC_CLIENT_ID", "callosum")


def _sign_in(client: TestClient) -> None:
    """Drive login → callback so the test client ends up signed in (with the fake)."""
    url = client.get("/auth/login", params={"origin": "http://127.0.0.1:8080"}).json()["authorize_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    cb = client.get("/oauth/callback", params={"code": "auth-code", "state": state}, follow_redirects=False)
    assert cb.status_code == 303


# --- not configured (default-off) ---


def test_signin_not_configured_off_by_default(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CALLOSUM_OIDC_ISSUER", raising=False)
    monkeypatch.delenv("CALLOSUM_OIDC_CLIENT_ID", raising=False)
    client = TestClient(create_app(db_url=temp_db_url))  # no client injected, no env config
    acct = client.get("/settings").json()["account"]
    assert acct["configured"] is False and acct["signed_in"] is False
    assert client.get("/auth/login").status_code == 503  # sign-in not configured


# --- the flow ---


def test_login_then_callback_signs_in_and_populates_profile(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _configured(monkeypatch)
    fake = FakeOidcClient()
    client = TestClient(create_app(db_url=temp_db_url, oidc_client=fake))

    url = client.get("/auth/login", params={"origin": "http://127.0.0.1:8080"}).json()["authorize_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    cb = client.get("/oauth/callback", params={"code": "auth-code", "state": state}, follow_redirects=False)
    assert cb.status_code == 303 and cb.headers["location"] == "/?signin=ok"
    assert fake.exchanged and fake.exchanged[0]["code"] == "auth-code"  # the code was exchanged (+PKCE verifier)
    assert fake.exchanged[0]["code_verifier"]  # a verifier from the stored flow was used

    resp = client.get("/settings")
    acct = resp.json()["account"]
    assert acct["configured"] is True and acct["signed_in"] is True
    assert acct["orcid"] == "0000-0002-1825-0097" and acct["display_name"] == "Ada Lovelace"
    # tokens NEVER appear in the status response
    assert "fake-access-TOKENXYZ" not in resp.text and "fake-refresh-RRR" not in resp.text

    # the SP1 payoff: the verified ORCID + name populated the My-Pubs profile
    prof = client.get("/my-publications/profile").json()
    assert prof["orcid"] == "0000-0002-1825-0097" and prof["display_name"] == "Ada Lovelace"


def test_callback_rejects_bad_state_no_exchange(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _configured(monkeypatch)
    fake = FakeOidcClient()
    client = TestClient(create_app(db_url=temp_db_url, oidc_client=fake))
    client.get("/auth/login", params={"origin": "http://127.0.0.1:8080"})  # sets a flow with some state
    cb = client.get("/oauth/callback", params={"code": "x", "state": "WRONG-STATE"}, follow_redirects=False)
    assert cb.status_code == 303 and cb.headers["location"] == "/?signin=error"
    assert fake.exchanged == []  # CSRF/code-injection guard: no exchange on a bad state
    assert client.get("/settings").json()["account"]["signed_in"] is False


def test_logout_clears_session(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _configured(monkeypatch)
    client = TestClient(create_app(db_url=temp_db_url, oidc_client=FakeOidcClient()))
    _sign_in(client)
    assert client.get("/settings").json()["account"]["signed_in"] is True
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/settings").json()["account"]["signed_in"] is False


def test_login_rejects_non_loopback_redirect(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _configured(monkeypatch)
    client = TestClient(create_app(db_url=temp_db_url, oidc_client=FakeOidcClient()))
    assert client.get("/auth/login", params={"origin": "https://evil.example"}).status_code == 422
    assert client.get("/auth/login").status_code == 422  # no origin + no override → reject (no open-redirect)


def test_callback_exempt_under_remote_access(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _configured(monkeypatch)
    monkeypatch.delenv("CALLOSUM_DISABLE_REMOTE_ACCESS", raising=False)
    app_settings.set_access_token("the-bearer-token")
    app_settings.set_remote_access_enabled(True)
    client = TestClient(create_app(db_url=temp_db_url, oidc_client=FakeOidcClient()))
    # the callback is a browser navigation (no bearer) → must be EXEMPT (reaches the handler → 303, not 401)
    cb = client.get("/oauth/callback", params={"code": "x", "state": "nope"}, follow_redirects=False)
    assert cb.status_code == 303
    # a gated route without the token is still blocked
    assert client.get("/settings").status_code == 401


# --- pure helpers (the real client; no network) ---


def test_generate_pkce_is_s256() -> None:
    verifier, challenge = generate_pkce()
    assert verifier and challenge
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    assert challenge == expected and "=" not in challenge


def test_build_authorize_url_carries_pkce_and_params() -> None:
    client = OidcClient(OidcConfig(issuer="https://idp.example", client_id="cid"))
    client._discovery = {"authorization_endpoint": "https://idp.example/authorize"}  # skip network discovery
    url = client.build_authorize_url(
        redirect_uri="http://127.0.0.1:8080/oauth/callback", state="st", code_challenge="ch"
    )
    q = parse_qs(urlparse(url).query)
    assert q["response_type"] == ["code"] and q["client_id"] == ["cid"]
    assert q["code_challenge"] == ["ch"] and q["code_challenge_method"] == ["S256"]
    assert q["state"] == ["st"] and q["redirect_uri"] == ["http://127.0.0.1:8080/oauth/callback"]
    assert q["scope"] == ["openid profile"]


def test_claims_to_identity_maps_orcid_and_falls_back() -> None:
    client = OidcClient(OidcConfig(issuer="i", client_id="cid"))
    ident = client._claims_to_identity({"sub": "u1", "name": "Ada", "orcid": "0000-0002", "exp": 123})
    assert ident.sub == "u1" and ident.display_name == "Ada" and ident.orcid == "0000-0002" and ident.expires_at == 123
    ident2 = client._claims_to_identity(
        {"sub": "u2", "preferred_username": "ada2"}
    )  # no orcid / no exp / name fallback
    assert ident2.orcid is None and ident2.display_name == "ada2" and ident2.expires_at is None


def test_oidc_config_present_only_when_issuer_and_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CALLOSUM_OIDC_ISSUER", raising=False)
    monkeypatch.delenv("CALLOSUM_OIDC_CLIENT_ID", raising=False)
    assert app_settings.oidc_config() is None and app_settings.oidc_configured() is False
    monkeypatch.setenv("CALLOSUM_OIDC_ISSUER", "https://idp.example/")  # trailing slash stripped
    monkeypatch.setenv("CALLOSUM_OIDC_CLIENT_ID", "cid")
    cfg = app_settings.oidc_config()
    assert cfg is not None
    assert cfg["issuer"] == "https://idp.example" and cfg["client_id"] == "cid"
    assert cfg["scopes"] == "openid profile" and cfg["orcid_claim"] == "orcid"
