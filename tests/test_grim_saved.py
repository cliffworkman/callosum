"""Tests for saved per-paper GRIM/GRIMMER checks (inc 401) — an append-only, paper-scoped log. The crux: a
saved record's verdict must always match calling grim_test/grimmer_test directly on the same inputs, proving
the server re-derives it rather than trusting a client-supplied verdict (rule #9's deterministic-substrate
commitment)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.grim import grim_test, grimmer_test
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper


def _paper(conn, title="Grim Paper"):
    return create_paper(conn, title=title, csl_json={"title": title})


def test_list_is_empty_for_an_unchecked_paper_and_404s_for_a_missing_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _paper(conn)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get(f"/papers/{paper_id}/grim-checks").json() == {"checks": []}
    assert client.get("/papers/999999/grim-checks").status_code == 404
    assert client.post("/papers/999999/grim-checks", json={"mean": "3.48", "n": 20}).status_code == 404
    assert client.delete("/papers/999999/grim-checks/1").status_code == 404


def test_save_recomputes_server_side_and_matches_calling_grim_directly(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _paper(conn)
    client = TestClient(create_app(db_url=temp_db_url))

    saved = client.post(
        f"/papers/{paper_id}/grim-checks", json={"mean": "3.48", "n": 20, "label": "Table 1, condition A"}
    ).json()
    expected_grim = grim_test("3.48", 20, 1)
    assert saved["grim"]["consistent"] == expected_grim.consistent
    assert saved["grim"]["nearest"] == expected_grim.nearest
    assert saved["grimmer"] is None
    assert saved["label"] == "Table 1, condition A"
    assert saved["mean"] == "3.48" and saved["n"] == 20 and saved["items"] == 1
    assert saved["created_at"] is not None

    saved_with_sd = client.post(f"/papers/{paper_id}/grim-checks", json={"mean": "5.23", "sd": "2.55", "n": 31}).json()
    expected_grimmer = grimmer_test("5.23", "2.55", 31, 1)
    assert saved_with_sd["grimmer"]["consistent"] == expected_grimmer.consistent
    assert saved_with_sd["label"] is None  # optional, omitted here


def test_list_is_newest_first_and_paper_scoped(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_a = _paper(conn, "Paper A")
        paper_b = _paper(conn, "Paper B")
    client = TestClient(create_app(db_url=temp_db_url))
    first = client.post(f"/papers/{paper_a}/grim-checks", json={"mean": "3.48", "n": 20}).json()
    second = client.post(f"/papers/{paper_a}/grim-checks", json={"mean": "3.45", "n": 20}).json()
    client.post(f"/papers/{paper_b}/grim-checks", json={"mean": "3.48", "n": 20})

    checks_a = client.get(f"/papers/{paper_a}/grim-checks").json()["checks"]
    assert [c["id"] for c in checks_a] == [second["id"], first["id"]]  # newest first
    checks_b = client.get(f"/papers/{paper_b}/grim-checks").json()["checks"]
    assert len(checks_b) == 1  # paper B's list never includes paper A's saved checks


def test_delete_removes_it_and_is_scoped_to_the_owning_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_a = _paper(conn, "Owner")
        paper_b = _paper(conn, "Not the owner")
    client = TestClient(create_app(db_url=temp_db_url))
    check = client.post(f"/papers/{paper_a}/grim-checks", json={"mean": "3.48", "n": 20}).json()
    check_id = check["id"]

    # Deleting under the WRONG paper_id 404s and leaves the real row intact.
    assert client.delete(f"/papers/{paper_b}/grim-checks/{check_id}").status_code == 404
    assert len(client.get(f"/papers/{paper_a}/grim-checks").json()["checks"]) == 1

    assert client.delete(f"/papers/{paper_a}/grim-checks/{check_id}").status_code == 204
    assert client.get(f"/papers/{paper_a}/grim-checks").json()["checks"] == []
    assert client.delete(f"/papers/{paper_a}/grim-checks/{check_id}").status_code == 404  # already gone


def test_save_rejects_invalid_inputs_and_oversized_label(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _paper(conn)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post(f"/papers/{paper_id}/grim-checks", json={"mean": "3.45", "n": 0}).status_code == 422
    assert client.post(f"/papers/{paper_id}/grim-checks", json={"mean": "not-a-number", "n": 20}).status_code == 422
    oversized_label = "x" * 121
    assert (
        client.post(
            f"/papers/{paper_id}/grim-checks", json={"mean": "3.48", "n": 20, "label": oversized_label}
        ).status_code
        == 422
    )
