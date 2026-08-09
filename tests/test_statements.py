"""Open-science statement staging (backlog #33/#34 P2 item #21, inc 462).

Hermetic (pure in-memory staging, no DB/network/model — mirrors test_credit.py's own pending-hand-off tests).
Extends CRediT's "build in the web UI -> stage -> LibreOffice pulls & inserts" pattern to 7 more author-asserted
manuscript disclosures; this router does no formatting of its own (unlike /credit/statement) — it only stages
and returns whatever text the caller sent.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.api.routers import statements as statements_router


def _client(temp_db_url: str) -> TestClient:
    client = TestClient(create_app(db_url=temp_db_url))
    # the in-memory holder is module-level (shared across app instances); reset for isolation, the exact
    # test_credit.py::test_pending_roundtrip precedent.
    statements_router._pending_statements.clear()
    return client


def test_pending_roundtrip_single_kind(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    assert client.get("/statements/pending").json() == {}

    staged = client.post("/statements/pending", json={"kind": "funding", "text": "Funded by NSF #12345."})
    assert staged.status_code == 200
    assert staged.json() == {"funding": "Funded by NSF #12345."}
    assert client.get("/statements/pending").json() == {"funding": "Funded by NSF #12345."}


def test_multiple_kinds_coexist_independently(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    client.post("/statements/pending", json={"kind": "funding", "text": "Funded by NSF."})
    client.post("/statements/pending", json={"kind": "ethics", "text": "IRB approved, protocol #9."})
    resp = client.get("/statements/pending").json()
    assert resp == {"funding": "Funded by NSF.", "ethics": "IRB approved, protocol #9."}

    # re-staging one kind leaves the other untouched
    client.post("/statements/pending", json={"kind": "funding", "text": "Funded by NIH instead."})
    resp = client.get("/statements/pending").json()
    assert resp == {"funding": "Funded by NIH instead.", "ethics": "IRB approved, protocol #9."}


def test_empty_text_unstages(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    client.post("/statements/pending", json={"kind": "ai_use", "text": "No generative AI was used."})
    assert client.get("/statements/pending").json() == {"ai_use": "No generative AI was used."}

    cleared = client.post("/statements/pending", json={"kind": "ai_use", "text": ""})
    assert cleared.status_code == 200
    assert cleared.json() == {}
    assert client.get("/statements/pending").json() == {}


def test_whitespace_only_text_unstages(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    client.post("/statements/pending", json={"kind": "ethics", "text": "real text"})
    client.post("/statements/pending", json={"kind": "ethics", "text": "   "})
    assert client.get("/statements/pending").json() == {}


def test_unknown_kind_rejected(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    resp = client.post("/statements/pending", json={"kind": "not_a_real_kind", "text": "x"})
    assert resp.status_code == 422


def test_oversized_text_rejected(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    too_long = "x" * (statements_router.MAX_STATEMENT_LEN + 1)
    resp = client.post("/statements/pending", json={"kind": "data_availability", "text": too_long})
    assert resp.status_code == 422


def test_all_seven_kinds_accepted(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    for kind in statements_router.STATEMENT_KINDS:
        resp = client.post("/statements/pending", json={"kind": kind, "text": f"statement for {kind}"})
        assert resp.status_code == 200, kind
    assert set(client.get("/statements/pending").json().keys()) == set(statements_router.STATEMENT_KINDS)
