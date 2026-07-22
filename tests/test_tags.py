from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from alembic import command
from alembic.config import Config
from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, list_papers, soft_delete_paper
from app.backend.persistence.schema import tags
from app.backend.persistence.tags_repo import (
    TAG_SOURCE_NAMESPACES,
    add_tag_to_paper,
    add_tags_to_paper,
    get_tags_for_paper,
    list_tags,
    remove_tag_from_paper,
    tag_source_namespace,
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


def test_tag_lock_is_scoped_to_paper_tag_link(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="A", csl_json={"title": "A"})
        b = create_paper(conn, title="B", csl_json={"title": "B"})
        tid = int(add_tag_to_paper(conn, a, "keep-me")["id"])
        add_tag_to_paper(conn, b, "keep-me")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    locked = client.post(f"/papers/{a}/tags/{tid}/lock", json={"locked": True})
    assert locked.status_code == 200
    assert locked.json()["locked"] is True
    by_paper = {p: {t["name"]: t["locked"] for t in client.get(f"/papers/{p}").json()["tags"]} for p in (a, b)}
    assert by_paper[a] == {"keep-me": True}
    assert by_paper[b] == {"keep-me": False}
    assert client.post(f"/papers/{a}/tags", json={"name": "keep-me"}).json()["locked"] is True

    blocked = client.delete(f"/papers/{a}/tags/{tid}")
    assert blocked.status_code == 409
    assert "Unlock this tag" in blocked.json()["detail"]
    assert client.delete(f"/papers/{b}/tags/{tid}").status_code == 204

    unlocked = client.post(f"/papers/{a}/tags/{tid}/lock", json={"locked": False})
    assert unlocked.status_code == 200 and unlocked.json()["locked"] is False
    assert client.delete(f"/papers/{a}/tags/{tid}").status_code == 204
    assert client.post(f"/papers/{a}/tags/{tid}/lock", json={"locked": True}).status_code == 404


def test_deleted_keyword_tag_is_not_re_added_on_enrich(temp_db_url: str) -> None:
    # inc 143 (Librarian pass): deleting an imported keyword tag must be durable — a re-resolve / backfill that
    # re-runs apply_crossref_subject_tags must NOT silently resurrect it.
    from app.backend.metadata.enrichment import apply_crossref_subject_tags
    from app.backend.persistence.tags_repo import (
        add_tag_to_paper,
        get_tags_for_paper,
        remove_tag_from_paper,
        suppressed_tag_names,
    )

    csl = {"subject": ["Neuroscience", "Miscellaneous"]}
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_crossref_subject_tags(conn, pid, csl)  # the original import
        assert {t["name"] for t in get_tags_for_paper(conn, pid)} == {"Neuroscience", "Miscellaneous"}

        misc = next(t for t in get_tags_for_paper(conn, pid) if t["name"] == "Miscellaneous")
        remove_tag_from_paper(conn, pid, int(misc["id"]))  # the librarian deletes the noisy keyword
        assert suppressed_tag_names(conn, pid) == {"Miscellaneous"}

        apply_crossref_subject_tags(conn, pid, csl)  # re-resolve — must respect the deletion
        assert {t["name"] for t in get_tags_for_paper(conn, pid)} == {"Neuroscience"}

        add_tag_to_paper(conn, pid, "Miscellaneous")  # re-adding it clears the suppression
        assert suppressed_tag_names(conn, pid) == set()
        apply_crossref_subject_tags(conn, pid, csl)
        assert "Miscellaneous" in {t["name"] for t in get_tags_for_paper(conn, pid)}
    engine.dispose()


def test_removing_a_user_tag_does_not_suppress(temp_db_url: str) -> None:
    # inc 143: only imported keyword:* removals suppress — a user-typed tag is not enrich-re-added, so no suppression.
    from app.backend.persistence.tags_repo import add_tag_to_paper, remove_tag_from_paper, suppressed_tag_names

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        row = add_tag_to_paper(conn, pid, "my-tag")  # import_source defaults to "user"
        remove_tag_from_paper(conn, pid, int(row["id"]))
        assert suppressed_tag_names(conn, pid) == set()
    engine.dispose()


def test_set_tag_color_endpoint_and_responses(temp_db_url: str) -> None:
    # inc 207 (A5): a tag carries an optional palette color; set/clear via POST /tags/{id}/color, validated to the
    # allowlist; the color rides the tag responses + the paper detail.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        tid = int(add_tag_to_paper(conn, pid, "method")["id"])
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    # the palette is exposed; a fresh tag is uncolored
    assert "blue" in client.get("/tags/colors").json()
    assert {t["id"]: t["color"] for t in client.get("/tags").json()}[tid] is None

    # set a valid color → reflected in /tags, the paper detail, and a re-add
    assert client.post(f"/tags/{tid}/color", json={"color": "blue"}).status_code == 200
    assert {t["id"]: t["color"] for t in client.get("/tags").json()}[tid] == "blue"
    detail_tags = client.get(f"/papers/{pid}").json()["tags"]
    assert [t for t in detail_tags if t["id"] == tid][0]["color"] == "blue"

    # an invalid color → 422 (allowlist, rule #4); the stored color is unchanged
    assert client.post(f"/tags/{tid}/color", json={"color": "#ff0000"}).status_code == 422
    assert {t["id"]: t["color"] for t in client.get("/tags").json()}[tid] == "blue"

    # clear with null; unknown tag → 404
    assert client.post(f"/tags/{tid}/color", json={"color": None}).json()["color"] is None
    assert client.post("/tags/999999/color", json={"color": "blue"}).status_code == 404


# --- backlog #9: tag provenance vocabulary formalization ---


def test_tag_source_namespace_parses_the_formal_vocabulary() -> None:
    assert tag_source_namespace(None) == "user"
    assert tag_source_namespace("") == "user"
    assert tag_source_namespace("user") == "user"
    assert tag_source_namespace("import:zotero") == "import"
    assert tag_source_namespace("keyword:crossref") == "keyword"
    assert tag_source_namespace("keyword:openalex") == "keyword"
    assert tag_source_namespace("keyword:pubmed") == "keyword"
    assert tag_source_namespace("agent:mcp") == "agent"
    assert tag_source_namespace("system:retraction") == "system"  # reserved for #19, not yet produced
    assert tag_source_namespace("something-unrecognized") == "other"  # defensive fallback, never "user"
    assert set(TAG_SOURCE_NAMESPACES) == {"user", "import", "keyword", "agent", "system"}


def test_only_keyword_namespace_suppresses_on_removal(temp_db_url: str) -> None:
    # inc 143 preserved exactly across the #9 rename: only `keyword:*` removals suppress re-add. A `import:*` or
    # `agent:*` tag's removal must NOT suppress (unchanged behavior — this guards the rename didn't broaden it).
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        zrow = add_tag_to_paper(conn, pid, "z-tag", import_source="import:zotero")
        arow = add_tag_to_paper(conn, pid, "a-tag", import_source="agent:mcp")
        krow = add_tag_to_paper(conn, pid, "k-tag", import_source="keyword:crossref")

        remove_tag_from_paper(conn, pid, int(zrow["id"]))
        remove_tag_from_paper(conn, pid, int(arow["id"]))
        remove_tag_from_paper(conn, pid, int(krow["id"]))

        from app.backend.persistence.tags_repo import suppressed_tag_names

        assert suppressed_tag_names(conn, pid) == {"k-tag"}
    engine.dispose()


# --- backlog #19: system-fact tags are non-editable + the namespace is reserved ---


def test_system_tag_is_protected_from_user_mutation(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        tid = int(add_tag_to_paper(conn, pid, "system:retraction:retracted", import_source="system:retraction")["id"])
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    assert client.post(f"/tags/{tid}/color", json={"color": "blue"}).status_code == 409
    assert client.post(f"/papers/{pid}/tags/{tid}/lock", json={"locked": True}).status_code == 409
    assert client.delete(f"/papers/{pid}/tags/{tid}").status_code == 409
    # a plain, non-system tag on the same paper is unaffected by the guard
    other = client.post(f"/papers/{pid}/tags", json={"name": "ordinary"}).json()
    assert client.post(f"/tags/{other['id']}/color", json={"color": "blue"}).status_code == 200


def test_user_cannot_create_a_tag_in_the_reserved_system_namespace(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    r = client.post(f"/papers/{pid}/tags", json={"name": "system:whatever"})
    assert r.status_code == 422
    r2 = client.post(f"/papers/{pid}/tags", json={"name": "SYSTEM:whatever"})  # case-insensitive
    assert r2.status_code == 422


def test_migration_0047_renames_legacy_bare_tag_sources(tmp_path: Path) -> None:
    # A pre-#9 DB (any revision at/after 0044, when paper_tags.locked landed) could carry bare "zotero"/"ai-agent"
    # tags.import_source values. 0047 must rename them in place without touching any other table's provenance.
    db_url = f"sqlite:///{(tmp_path / 'pre-0047.sqlite').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "0046_overlooked_candidates")

    engine = make_engine(db_url)
    with engine.begin() as conn:
        conn.execute(tags.insert().values(name="legacy-zotero-tag", import_source="zotero"))
        conn.execute(tags.insert().values(name="legacy-agent-tag", import_source="ai-agent"))
        conn.execute(tags.insert().values(name="legacy-user-tag", import_source="user"))
    engine.dispose()

    command.upgrade(config, "head")

    engine = make_engine(db_url)
    with engine.begin() as conn:
        by_name = {
            r["name"]: r["import_source"] for r in conn.execute(select(tags.c.name, tags.c.import_source)).mappings()
        }
    engine.dispose()
    assert by_name["legacy-zotero-tag"] == "import:zotero"
    assert by_name["legacy-agent-tag"] == "agent:mcp"
    assert by_name["legacy-user-tag"] == "user"  # untouched
