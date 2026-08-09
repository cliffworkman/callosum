"""Tests for saved per-paper DEBIT checks (inc 467) — an append-only, paper-scoped log. Mirrors
test_grim_saved.py: the crux is that a saved record's verdict must always match calling debit_test
directly on the same inputs, proving the server re-derives it rather than trusting a client-supplied
verdict (rule #9's deterministic-substrate commitment)."""

from __future__ import annotations

import math

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.grim import debit_test
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper

_SD_EXACT = f"{math.sqrt(5 * 5 / (10 * 9)):.3f}"


def _paper(conn, title="Debit Paper"):
    return create_paper(conn, title=title, csl_json={"title": title})


def test_list_is_empty_for_an_unchecked_paper_and_404s_for_a_missing_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _paper(conn)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get(f"/papers/{paper_id}/debit-checks").json() == {"checks": []}
    assert client.get("/papers/999999/debit-checks").status_code == 404
    assert client.post("/papers/999999/debit-checks", json={"mean": "0.5", "sd": "0.1", "n": 10}).status_code == 404
    assert client.delete("/papers/999999/debit-checks/1").status_code == 404


def test_save_recomputes_server_side_and_matches_calling_debit_directly(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _paper(conn)
    client = TestClient(create_app(db_url=temp_db_url))

    saved = client.post(
        f"/papers/{paper_id}/debit-checks",
        json={"mean": "0.500", "sd": _SD_EXACT, "n": 10, "label": "Table 1, response rate"},
    ).json()
    expected = debit_test("0.500", _SD_EXACT, 10)
    assert saved["debit"]["consistent"] == expected.consistent
    assert saved["debit"]["note"] == expected.note
    assert saved["label"] == "Table 1, response rate"
    assert saved["mean"] == "0.500" and saved["n"] == 10
    assert saved["created_at"] is not None

    saved_bad = client.post(f"/papers/{paper_id}/debit-checks", json={"mean": "0.500", "sd": "0.999", "n": 10}).json()
    expected_bad = debit_test("0.500", "0.999", 10)
    assert saved_bad["debit"]["consistent"] == expected_bad.consistent is False
    assert saved_bad["label"] is None  # optional, omitted here


def test_list_is_newest_first_and_paper_scoped(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_a = _paper(conn, "Paper A")
        paper_b = _paper(conn, "Paper B")
    client = TestClient(create_app(db_url=temp_db_url))
    first = client.post(f"/papers/{paper_a}/debit-checks", json={"mean": "0.500", "sd": _SD_EXACT, "n": 10}).json()
    second = client.post(f"/papers/{paper_a}/debit-checks", json={"mean": "0.000", "sd": "0.000", "n": 10}).json()
    client.post(f"/papers/{paper_b}/debit-checks", json={"mean": "0.500", "sd": _SD_EXACT, "n": 10})

    checks_a = client.get(f"/papers/{paper_a}/debit-checks").json()["checks"]
    assert [c["id"] for c in checks_a] == [second["id"], first["id"]]  # newest first
    checks_b = client.get(f"/papers/{paper_b}/debit-checks").json()["checks"]
    assert len(checks_b) == 1  # paper B's list never includes paper A's saved checks


def test_delete_removes_it_and_is_scoped_to_the_owning_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_a = _paper(conn, "Owner")
        paper_b = _paper(conn, "Not the owner")
    client = TestClient(create_app(db_url=temp_db_url))
    check = client.post(f"/papers/{paper_a}/debit-checks", json={"mean": "0.500", "sd": _SD_EXACT, "n": 10}).json()
    check_id = check["id"]

    # Deleting under the WRONG paper_id 404s and leaves the real row intact.
    assert client.delete(f"/papers/{paper_b}/debit-checks/{check_id}").status_code == 404
    assert len(client.get(f"/papers/{paper_a}/debit-checks").json()["checks"]) == 1

    assert client.delete(f"/papers/{paper_a}/debit-checks/{check_id}").status_code == 204
    assert client.get(f"/papers/{paper_a}/debit-checks").json()["checks"] == []
    assert client.delete(f"/papers/{paper_a}/debit-checks/{check_id}").status_code == 404  # already gone


def test_save_rejects_invalid_inputs_and_oversized_label(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _paper(conn)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post(f"/papers/{paper_id}/debit-checks", json={"mean": "0.5", "sd": "0.1", "n": 1}).status_code == 422
    assert (
        client.post(f"/papers/{paper_id}/debit-checks", json={"mean": "not-a-number", "sd": "0.1", "n": 10}).status_code
        == 422
    )
    oversized_label = "x" * 121
    assert (
        client.post(
            f"/papers/{paper_id}/debit-checks",
            json={"mean": "0.500", "sd": _SD_EXACT, "n": 10, "label": oversized_label},
        ).status_code
        == 422
    )
