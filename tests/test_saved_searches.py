from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app


def test_saved_search_crud_and_upsert(temp_db_url: str) -> None:
    # inc 208 (A1): a saved search persists a named bundle of the existing library facets; re-saving a name
    # overwrites (upsert); only known facet keys are stored (extra → 422); delete is 204 / 404.
    client = TestClient(create_app(db_url=temp_db_url))

    assert client.get("/saved-searches").json() == []

    params = {
        "q": "memory",
        "search_field": "title",
        "item_type": "article-journal",
        "sort": "year_desc",
        "axis": {"id": 3, "label": "Attention", "hideUncertain": True},
        "needs_review": False,
        "signal": None,
    }
    created = client.post("/saved-searches", json={"name": "My view", "params": params})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "My view"
    assert body["params"]["q"] == "memory" and body["params"]["axis"]["hideUncertain"] is True
    sid = body["id"]

    # listed back
    listed = client.get("/saved-searches").json()
    assert [s["id"] for s in listed] == [sid]

    # re-save the same name → upsert (same id, new params), not a duplicate
    updated = client.post("/saved-searches", json={"name": "My view", "params": {"q": "vision", "sort": "added"}})
    assert updated.status_code == 201 and updated.json()["id"] == sid
    assert updated.json()["params"]["q"] == "vision"
    assert len(client.get("/saved-searches").json()) == 1  # no duplicate

    # an unknown facet key → 422 (extra="forbid"; rule #4)
    assert client.post("/saved-searches", json={"name": "junk", "params": {"evil": 1}}).status_code == 422
    # a blank name → 422
    assert client.post("/saved-searches", json={"name": "  ", "params": {}}).status_code == 422

    # delete → 204, then 404
    assert client.delete(f"/saved-searches/{sid}").status_code == 204
    assert client.get("/saved-searches").json() == []
    assert client.delete(f"/saved-searches/{sid}").status_code == 404
