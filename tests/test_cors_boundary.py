"""The loopback CORS policy as a pinned boundary, not an incidental setting (browser-capture research, #61).

``app/backend/api/local_only.py``'s ``require_local_machine_action`` explicitly *depends* on this policy:
its CSRF resistance is "a non-safelisted header forces browser preflight, which Callosum's GET-only
localhost CORS policy denies to every foreign origin". That reasoning silently stops holding if
``allow_methods`` ever widens or the origin regex ever loosens, and nothing in the suite noticed — the only
prior CORS assertion was a single line in ``test_word_https_lifecycle.py``.

These tests pin the two properties that load-bearing argument rests on, ahead of the browser-extension
capture work that will add the first deliberate non-UI client. They assert the *policy*, not any one route.

Note what they do NOT claim: a browser extension's background worker with ``host_permissions`` bypasses CORS
entirely, so this policy is not a boundary against an extension (hostile or otherwise). That case needs a
real credential — see the browser-capture research doc.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app

# Origins that must never be granted CORS access. The extension schemes matter because the capture work
# will introduce an extension client, and "just allow the extension origin" is the tempting wrong fix.
FOREIGN_ORIGINS = [
    "https://evil.example",
    "http://evil.example",
    "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
    "moz-extension://11111111-2222-3333-4444-555555555555",
    "http://127.0.0.1.evil.example",  # suffix trick — the regex is anchored, so this must not match
    "http://localhost.evil.example",
    "https://notlocalhost",
    "null",
]

LOOPBACK_ORIGINS = [
    "http://localhost",
    "http://localhost:8888",
    "http://127.0.0.1:5173",
    "https://127.0.0.1",
]


@pytest.fixture(name="client")
def _client(temp_db_url: str) -> TestClient:
    return TestClient(create_app(db_url=temp_db_url))


@pytest.mark.parametrize("origin", FOREIGN_ORIGINS)
def test_foreign_origin_gets_no_cors_grant(client: TestClient, origin: str) -> None:
    """A non-loopback origin is never echoed back an allow-origin header, on a plain GET or a preflight."""
    got = client.get("/health", headers={"origin": origin})
    assert got.headers.get("access-control-allow-origin") is None

    preflight = client.options(
        "/papers",
        headers={
            "origin": origin,
            "access-control-request-method": "GET",
        },
    )
    assert preflight.headers.get("access-control-allow-origin") is None


@pytest.mark.parametrize("origin", LOOPBACK_ORIGINS)
def test_loopback_origin_is_allowed_for_get(client: TestClient, origin: str) -> None:
    """The app's own UI origin keeps working — this pin must not be mistaken for "deny everything"."""
    response = client.get("/health", headers={"origin": origin})
    assert response.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_mutating_methods_are_not_preflight_approved_even_for_loopback(client: TestClient, method: str) -> None:
    """GET-only is the property ``local_only.require_local_machine_action`` leans on.

    If this ever fails, that function's CSRF argument is void and every non-safelisted-header gate built on
    it needs re-deriving — not just this test updating.
    """
    preflight = client.options(
        "/papers",
        headers={
            "origin": "http://localhost:8888",
            "access-control-request-method": method,
        },
    )
    allowed = preflight.headers.get("access-control-allow-methods", "")
    assert method not in allowed, f"{method} became cross-origin preflightable; local_only.py's CSRF basis is gone"


def test_credentials_are_never_allowed(client: TestClient) -> None:
    """No cookie/session auth exists; an allow-credentials grant would be a silent posture change."""
    response = client.get("/health", headers={"origin": "http://localhost:8888"})
    assert response.headers.get("access-control-allow-credentials") is None
