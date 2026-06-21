from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, list_papers, soft_delete_paper
from app.backend.persistence.schema import tags
from app.backend.persistence.tags_repo import (
    add_tag_to_paper,
    add_tags_to_paper,
    get_tags_for_paper,
    list_tags,
    remove_tag_from_paper,
)


def _names(rows):
    return [r["name"] for r in rows]


def test_add_get_dedupe_and_idempotent(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="A", csl_json={"title": "A"})
        b = create_paper(conn, title="B", csl_json={"title": "B"})
        t1 = add_tag_to_paper(conn, a, "  Method  ")  # trimmed
        assert t1["name"] == "Method"
        assert add_tag_to_paper(conn, a, "Method")["id"] == t1["id"]  # idempotent: same tag, no dup link
        assert _names(get_tags_for_paper(conn, a)) == ["Method"]
        assert add_tag_to_paper(conn, b, "Method")["id"] == t1["id"]  # another paper reuses the global tag
        assert {r["name"]: r["paper_count"] for r in list_tags(conn)} == {"Method": 2}
    engine.dispose()


def test_import_source_provenance_set_on_create_and_preserved(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="A", csl_json={"title": "A"})
        b = create_paper(conn, title="B", csl_json={"title": "B"})

        def source(name):
            return conn.execute(select(tags.c.import_source).where(tags.c.name == name)).scalar_one()

        add_tags_to_paper(conn, a, ["Neuroscience", "Vision"], import_source="keyword:crossref")  # batch + provenance
        assert source("Neuroscience") == "keyword:crossref"
        assert {r["name"] for r in get_tags_for_paper(conn, a)} == {"Neuroscience", "Vision"}

        # a user adds the SAME name to another paper → reuses the tag, source NOT relabeled
        add_tag_to_paper(conn, b, "Neuroscience", import_source="user")
        assert source("Neuroscience") == "keyword:crossref"  # first creator's provenance preserved
        # a fresh user tag gets "user"
        add_tag_to_paper(conn, b, "my-note")
        assert source("my-note") == "user"
    engine.dispose()


def test_remove_unlinks_and_prunes_orphan(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="A", csl_json={"title": "A"})
        b = create_paper(conn, title="B", csl_json={"title": "B"})
        tid = add_tag_to_paper(conn, a, "Shared")["id"]
        add_tag_to_paper(conn, b, "Shared")

        assert remove_tag_from_paper(conn, a, tid) is True  # b still has it → tag survives
        assert _names(get_tags_for_paper(conn, a)) == []
        assert any(r["id"] == tid for r in list_tags(conn))

        assert remove_tag_from_paper(conn, b, tid) is True  # now orphaned → pruned
        assert all(r["id"] != tid for r in list_tags(conn))
        assert remove_tag_from_paper(conn, a, 999999) is False  # not linked
    engine.dispose()


def test_list_papers_tag_filter_composes(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="Alpha", csl_json={"title": "Alpha"})
        create_paper(conn, title="Beta", csl_json={"title": "Beta"})  # untagged → excluded
        tid = add_tag_to_paper(conn, a, "keep")["id"]
        assert {r["id"] for r in list_papers(conn, tag_id=tid)} == {a}
        assert list_papers(conn, tag_id=tid, q="zzznope") == []  # composes with q
        soft_delete_paper(conn, a)
        assert list_papers(conn, tag_id=tid) == []  # trashed excluded
    engine.dispose()


def test_tag_endpoints_add_remove_filter_and_validation(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="Endpoint Alpha", csl_json={"title": "Endpoint Alpha"})
        create_paper(conn, title="Endpoint Beta", csl_json={"title": "Endpoint Beta"})  # untagged
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    added = client.post(f"/papers/{a}/tags", json={"name": "method"})
    assert added.status_code == 201 and added.json()["name"] == "method"
    tid = added.json()["id"]
    assert [t["name"] for t in client.get(f"/papers/{a}").json()["tags"]] == ["method"]  # in the detail
    assert client.post(f"/papers/{a}/tags", json={"name": "method"}).status_code == 201  # idempotent
    assert len(client.get(f"/papers/{a}").json()["tags"]) == 1
    assert client.post(f"/papers/{a}/tags", json={"name": "   "}).status_code == 422  # blank
    assert client.post("/papers/999999/tags", json={"name": "x"}).status_code == 404  # unknown paper

    assert {t["name"]: t["paper_count"] for t in client.get("/tags").json()}.get("method") == 1
    assert {p["id"] for p in client.get("/papers", params={"tag_id": tid}).json()} == {a}  # filter

    assert client.delete(f"/papers/{a}/tags/{tid}").status_code == 204
    assert client.get(f"/papers/{a}").json()["tags"] == []
    assert client.delete(f"/papers/{a}/tags/{tid}").status_code == 404  # gone (+ pruned)


def test_tag_source_exposed_on_responses(temp_db_url: str) -> None:
    # inc-100: the UI distinguishes imported author/index keywords from tags you added, by the `source` field.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="P", csl_json={"title": "P"})
        add_tags_to_paper(conn, a, ["Neuroscience"], import_source="keyword:crossref")  # an imported keyword
        add_tag_to_paper(conn, a, "my-note")  # a user tag
    client = TestClient(create_app(db_url=temp_db_url))
    detail = {t["name"]: t["source"] for t in client.get(f"/papers/{a}").json()["tags"]}
    assert detail == {"Neuroscience": "keyword:crossref", "my-note": "user"}
    listed = {t["name"]: t["source"] for t in client.get("/tags").json()}
    assert listed["Neuroscience"] == "keyword:crossref" and listed["my-note"] == "user"
    assert client.post(f"/papers/{a}/tags", json={"name": "fresh"}).json()["source"] == "user"  # POST returns it
