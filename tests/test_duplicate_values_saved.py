"""Tests for saved per-paper repeated-values checks (inc 469) — an append-only, paper-scoped log. Mirrors
test_debit_saved.py: the crux is that a saved record's result must always match calling
count_repeated_values directly on the same inputs, proving the server re-derives it rather than trusting a
client-supplied result (rule #9's deterministic-substrate commitment)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.duplicate_values import count_repeated_values
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper

_VALUES = ["3.45", "3.45", "3.45", "2.10", "5.00"]


def _paper(conn, title="Duplicate-Values Paper"):
    return create_paper(conn, title=title, csl_json={"title": title})


def test_list_is_empty_for_an_unchecked_paper_and_404s_for_a_missing_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _paper(conn)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get(f"/papers/{paper_id}/duplicate-value-checks").json() == {"checks": []}
    assert client.get("/papers/999999/duplicate-value-checks").status_code == 404
    assert client.post("/papers/999999/duplicate-value-checks", json={"values": ["1", "1"]}).status_code == 404
    assert client.delete("/papers/999999/duplicate-value-checks/1").status_code == 404


def test_save_recomputes_server_side_and_matches_calling_directly(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _paper(conn)
    client = TestClient(create_app(db_url=temp_db_url))

    saved = client.post(
        f"/papers/{paper_id}/duplicate-value-checks",
        json={"values": _VALUES, "label": "Table 2, all reported means"},
    ).json()
    expected = count_repeated_values(_VALUES)
    assert saved["duplicate_values"]["repeats"] == expected.repeats
    assert saved["duplicate_values"]["note"] == expected.note
    assert saved["label"] == "Table 2, all reported means"
    assert saved["values"] == _VALUES
    assert saved["created_at"] is not None

    saved_no_repeats = client.post(f"/papers/{paper_id}/duplicate-value-checks", json={"values": ["1.0", "2.0"]}).json()
    assert saved_no_repeats["duplicate_values"]["repeats"] == []
    assert saved_no_repeats["label"] is None  # optional, omitted here


def test_list_is_newest_first_and_paper_scoped(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_a = _paper(conn, "Paper A")
        paper_b = _paper(conn, "Paper B")
    client = TestClient(create_app(db_url=temp_db_url))
    first = client.post(f"/papers/{paper_a}/duplicate-value-checks", json={"values": _VALUES}).json()
    second = client.post(f"/papers/{paper_a}/duplicate-value-checks", json={"values": ["1.0", "1.0"]}).json()
    client.post(f"/papers/{paper_b}/duplicate-value-checks", json={"values": _VALUES})

    checks_a = client.get(f"/papers/{paper_a}/duplicate-value-checks").json()["checks"]
    assert [c["id"] for c in checks_a] == [second["id"], first["id"]]  # newest first
    checks_b = client.get(f"/papers/{paper_b}/duplicate-value-checks").json()["checks"]
    assert len(checks_b) == 1  # paper B's list never includes paper A's saved checks


def test_delete_removes_it_and_is_scoped_to_the_owning_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_a = _paper(conn, "Owner")
        paper_b = _paper(conn, "Not the owner")
    client = TestClient(create_app(db_url=temp_db_url))
    check = client.post(f"/papers/{paper_a}/duplicate-value-checks", json={"values": _VALUES}).json()
    check_id = check["id"]

    # Deleting under the WRONG paper_id 404s and leaves the real row intact.
    assert client.delete(f"/papers/{paper_b}/duplicate-value-checks/{check_id}").status_code == 404
    assert len(client.get(f"/papers/{paper_a}/duplicate-value-checks").json()["checks"]) == 1

    assert client.delete(f"/papers/{paper_a}/duplicate-value-checks/{check_id}").status_code == 204
    assert client.get(f"/papers/{paper_a}/duplicate-value-checks").json()["checks"] == []
    assert client.delete(f"/papers/{paper_a}/duplicate-value-checks/{check_id}").status_code == 404  # already gone


def test_save_rejects_invalid_inputs_and_oversized_label(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _paper(conn)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post(f"/papers/{paper_id}/duplicate-value-checks", json={"values": []}).status_code == 422
    assert client.post(f"/papers/{paper_id}/duplicate-value-checks", json={"values": ["1"] * 501}).status_code == 422
    oversized_label = "x" * 121
    assert (
        client.post(
            f"/papers/{paper_id}/duplicate-value-checks",
            json={"values": _VALUES, "label": oversized_label},
        ).status_code
        == 422
    )
