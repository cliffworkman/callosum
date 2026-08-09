from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api.app import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper


def _suggestion(dedup_key="doi:10.1/x", **overrides):
    payload = {
        "dedup_key": dedup_key,
        "title": "A Beyond-Library Suggestion",
        "sources": ["openalex"],
        "doi": "10.1/x",
        "abstract": "An abstract.",
        "authors": ["Smith, Jane"],
        "journal": "Journal of Things",
        "year": 2021,
        "url": "https://example.com/x",
        "reason": "Surfaced by openalex from title/abstract metadata; metadata term overlap 0.42.",
        "evidence_text": "An abstract.",
        "evidence_kind": "abstract",
        "relationship_kind": "cited_by_local_match",
        "relationship_label": "Cited by a locally relevant paper",
        "anchor_paper_id": 1,
        "anchor_title": "Anchor Paper",
        "source_query": "We rely on attention mechanisms.",
    }
    payload.update(overrides)
    return payload


def test_save_then_list_round_trips_the_full_payload(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    resp = client.post("/citations/beyond-library/save", json=_suggestion())
    assert resp.status_code == 200
    saved = resp.json()
    assert saved["dedup_key"] == "doi:10.1/x"
    assert saved["title"] == "A Beyond-Library Suggestion"
    assert saved["reason"].startswith("Surfaced by")
    assert saved["relationship_label"] == "Cited by a locally relevant paper"
    assert saved["source_query"] == "We rely on attention mechanisms."

    listed = client.get("/citations/beyond-library/saved")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["dedup_key"] == "doi:10.1/x"


def test_saving_twice_upserts_not_duplicates(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/citations/beyond-library/save", json=_suggestion())
    client.post("/citations/beyond-library/save", json=_suggestion(title="Updated Title"))
    items = client.get("/citations/beyond-library/saved").json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Updated Title"


def test_list_excludes_a_suggestion_already_in_the_library(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(conn, title="Already Here", csl_json={"title": "Already Here"}, doi="10.1/x")
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/citations/beyond-library/save", json=_suggestion())
    items = client.get("/citations/beyond-library/saved").json()["items"]
    assert items == []  # read-time filtered: the DOI already resolves to a live library paper


def test_add_imports_the_paper_and_removes_it_from_the_queue(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/citations/beyond-library/save", json=_suggestion())

    resp = client.post("/citations/beyond-library/add", json={"dedup_key": "doi:10.1/x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] is True
    paper_id = body["paper_id"]

    items = client.get("/citations/beyond-library/saved").json()["items"]
    assert items == []

    # re-adding the same dedup_key a second time should now find the just-created paper, not duplicate it
    client.post("/citations/beyond-library/save", json=_suggestion())
    resp2 = client.post("/citations/beyond-library/add", json={"dedup_key": "doi:10.1/x"})
    assert resp2.json() == {"paper_id": paper_id, "created": False}


def test_dismiss_removes_from_queue_without_touching_the_library(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/citations/beyond-library/save", json=_suggestion())

    resp = client.post("/citations/beyond-library/dismiss", json={"dedup_key": "doi:10.1/x"})
    assert resp.status_code == 204
    assert client.get("/citations/beyond-library/saved").json()["items"] == []
    assert client.get("/papers").json() == []  # dismiss never adds anything to the library


def test_add_and_dismiss_unknown_dedup_key_404(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/citations/beyond-library/add", json={"dedup_key": "doi:not-real"}).status_code == 404
    assert client.post("/citations/beyond-library/dismiss", json={"dedup_key": "doi:not-real"}).status_code == 404


def test_save_rejects_missing_required_fields(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/citations/beyond-library/save", json={"dedup_key": "doi:10.1/x"}).status_code == 422
    assert client.post("/citations/beyond-library/save", json={"title": "No dedup key"}).status_code == 422


def test_saving_a_dismissed_item_again_returns_it_to_the_queue(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/citations/beyond-library/save", json=_suggestion())
    client.post("/citations/beyond-library/dismiss", json={"dedup_key": "doi:10.1/x"})
    assert client.get("/citations/beyond-library/saved").json()["items"] == []

    client.post("/citations/beyond-library/save", json=_suggestion())
    items = client.get("/citations/beyond-library/saved").json()["items"]
    assert len(items) == 1 and items[0]["dedup_key"] == "doi:10.1/x"
