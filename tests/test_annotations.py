from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import (
    annotations,
)
from tests.api_helpers import (
    _annotation_body,
    _seed_library,
)


def test_annotation_create_list_delete_round_trip(temp_db_url: str) -> None:
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))

    created = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body())
    assert created.status_code == 201
    data = created.json()
    assert data["paper_id"] == paper_id
    assert data["page"] == 2
    assert data["color"] == "#ffd54a"
    assert data["source"] == "user"
    assert data["note"] is None
    assert data["anchor_text"] == "Compared with typical faces"
    assert len(data["bboxes_json"]) == 2
    assert data["created_at"] and data["updated_at"]
    annotation_id = data["id"]

    listed = client.get(f"/papers/{paper_id}/annotations")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [annotation_id]

    deleted = client.delete(f"/annotations/{annotation_id}")
    assert deleted.status_code == 204
    assert client.get(f"/papers/{paper_id}/annotations").json() == []
    assert client.delete(f"/annotations/{annotation_id}").status_code == 404


def test_annotation_list_excludes_imported_rows(temp_db_url: str) -> None:
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            insert(annotations).values(
                paper_id=paper_id,
                page=1,
                annotation_type="highlight",
                body="imported note",
                import_source="zotero",
                external_id="zotero-1",
            )
        )
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    created = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body())
    assert created.status_code == 201

    rows = client.get(f"/papers/{paper_id}/annotations").json()
    # The native (user) row is listed; the imported (source NULL) row is not.
    assert [row["source"] for row in rows] == ["user"]
    assert [row["id"] for row in rows] == [created.json()["id"]]


def test_annotation_create_and_list_unknown_paper_404(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/papers/999999/annotations", json=_annotation_body()).status_code == 404
    assert client.get("/papers/999999/annotations").status_code == 404


def test_annotation_create_rejects_invalid_payloads(temp_db_url: str) -> None:
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))

    assert client.post(f"/papers/{paper_id}/annotations", json=_annotation_body(color="#000000")).status_code == 422
    assert client.post(f"/papers/{paper_id}/annotations", json=_annotation_body(bboxes=[])).status_code == 422
    degenerate = _annotation_body(bboxes=[{"x0": 10.0, "y0": 10.0, "x1": 10.0, "y1": 20.0}])
    assert client.post(f"/papers/{paper_id}/annotations", json=degenerate).status_code == 422
    missing_anchor = _annotation_body()
    del missing_anchor["anchor_text"]
    assert client.post(f"/papers/{paper_id}/annotations", json=missing_anchor).status_code == 422


def test_annotation_create_with_note_persists(temp_db_url: str) -> None:
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    created = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body(note="initial thought"))
    assert created.status_code == 201
    assert created.json()["note"] == "initial thought"
    assert [r["note"] for r in client.get(f"/papers/{paper_id}/annotations").json()] == ["initial thought"]


def test_annotation_patch_updates_note_and_color(temp_db_url: str) -> None:
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    created = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body()).json()
    aid = created["id"]
    assert created["note"] is None

    patched = client.patch(f"/annotations/{aid}", json={"note": "a comment", "color": "#7bc67e"})
    assert patched.status_code == 200
    body = patched.json()
    assert body["id"] == aid
    assert body["note"] == "a comment"
    assert body["color"] == "#7bc67e"
    # Immutable fields are untouched by PATCH.
    assert body["page"] == created["page"]
    assert body["anchor_text"] == created["anchor_text"]
    assert body["bboxes_json"] == created["bboxes_json"]

    listed = client.get(f"/papers/{paper_id}/annotations").json()
    assert listed[0]["note"] == "a comment" and listed[0]["color"] == "#7bc67e"


def test_annotation_patch_can_clear_note(temp_db_url: str) -> None:
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    aid = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body(note="temp")).json()["id"]
    cleared = client.patch(f"/annotations/{aid}", json={"note": None})
    assert cleared.status_code == 200
    assert cleared.json()["note"] is None
    assert cleared.json()["color"] == "#ffd54a"  # color left untouched


def test_annotation_patch_rejects_bad_requests(temp_db_url: str) -> None:
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    aid = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body()).json()["id"]
    assert client.patch("/annotations/999999", json={"note": "x"}).status_code == 404
    assert client.patch(f"/annotations/{aid}", json={"color": "#000000"}).status_code == 422
    assert client.patch(f"/annotations/{aid}", json={"note": "x" * 4001}).status_code == 422
    assert client.patch(f"/annotations/{aid}", json={}).status_code == 422  # no updatable fields


def test_annotation_create_rejects_over_cap_note(temp_db_url: str) -> None:
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    over = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body(note="x" * 4001))
    assert over.status_code == 422


def test_annotation_create_defaults_source_to_user(temp_db_url: str) -> None:
    # Omitting source preserves the original behavior: a hand-made user highlight.
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    created = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body())
    assert created.status_code == 201
    assert created.json()["source"] == "user"


def test_annotation_create_accepts_synthesis_source(temp_db_url: str) -> None:
    # A verified, exact-coordinate citation passage can be saved as a synthesis-sourced
    # annotation; the source round-trips through create and list.
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    created = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body(source="synthesis"))
    assert created.status_code == 201
    assert created.json()["source"] == "synthesis"
    assert [r["source"] for r in client.get(f"/papers/{paper_id}/annotations").json()] == ["synthesis"]


def test_annotation_create_rejects_forged_source(temp_db_url: str) -> None:
    # Any source outside the allowlist (NATIVE_ANNOTATION_SOURCES) is rejected, so a
    # client cannot persist a forged/arbitrary provenance string.
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    for forged in ("admin", "zotero", "import", ""):
        resp = client.post(f"/papers/{paper_id}/annotations", json=_annotation_body(source=forged))
        assert resp.status_code == 422, forged
    assert client.get(f"/papers/{paper_id}/annotations").json() == []
