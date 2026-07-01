"""B2 SP1 — portable library bundle: build → round-trip → idempotent → non-destructive merge → selection/axes →
caps. Hermetic: two throwaway SQLite DBs, no network, no embedding (import_bundle returns the created ids; the
router embeds them separately)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.backend.clustering.axis_assignments import CURATED_KIND, add_manual_assignment, append_member_position
from app.backend.clustering.axis_scoring import create_axis
from app.backend.metadata.library_bundle import (
    BUNDLE_VERSION,
    MAX_BUNDLE_BYTES,
    BundleError,
    build_bundle,
    import_bundle,
    parse_bundle,
)
from app.backend.persistence import annotations_repo, tags_repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import annotations, cluster_node_papers, cluster_nodes, metadata, papers


def _db(tmp_path, name):
    engine = make_engine(f"sqlite:///{(tmp_path / name).as_posix()}")
    metadata.create_all(engine)
    return engine


def _seed(conn):
    p1 = create_paper(
        conn,
        title="Paper One",
        csl_json={
            "title": "Paper One",
            "DOI": "10.1234/one",
            "author": [{"family": "Alpha"}],
            "issued": {"date-parts": [[2020]]},
        },
        doi="10.1234/one",
        year=2020,
        first_author_family_name="Alpha",
        item_type="article-journal",
    )
    p2 = create_paper(
        conn,
        title="Paper Two",
        csl_json={"title": "Paper Two", "DOI": "10.1234/two"},
        doi="10.1234/two",
        year=2019,
        first_author_family_name="Beta",
        item_type="article-journal",
    )
    tags_repo.add_tag_to_paper(conn, p1, "method")
    colored = tags_repo.add_tag_to_paper(conn, p1, "important")
    tags_repo.set_tag_color(conn, int(colored["id"]), "blue")
    annotations_repo.create_annotation(
        conn, paper_id=p1, page=3, color="yellow", bboxes_json=[[1, 2, 3, 4]], anchor_text="key sentence", note="a note"
    )
    ax = create_axis(conn, label="My Curated", kind=CURATED_KIND)
    for pid in (p1, p2):
        add_manual_assignment(conn, axis_id=ax, paper_id=pid)
        append_member_position(conn, axis_id=ax, paper_id=pid)
    create_axis(conn, label="Keyword Axis", kind="standard")
    return p1, p2


def _paper_by_doi(conn, doi):
    return conn.execute(select(papers).where(papers.c.doi == doi)).mappings().first()


# ── export ──────────────────────────────────────────────────────────────────


def test_build_bundle_shape(tmp_path):
    engine = _db(tmp_path, "src.sqlite")
    with engine.begin() as conn:
        _seed(conn)
        b = build_bundle(conn, scope="library")
    assert b["callosum_bundle"] == BUNDLE_VERSION and b["scope"] == "library"
    assert len(b["papers"]) == 2
    p1 = next(p for p in b["papers"] if p["identity"].get("doi") == "10.1234/one")
    assert {t["name"] for t in p1["tags"]} == {"method", "important"}
    assert next(t for t in p1["tags"] if t["name"] == "important")["color"] == "blue"
    assert p1["annotations"][0]["note"] == "a note" and p1["annotations"][0]["page"] == 3
    curated = next(a for a in b["axes"] if a["label"] == "My Curated")
    assert curated["kind"] == "curated" and len(curated["members"]) == 2
    kw = next(a for a in b["axes"] if a["label"] == "Keyword Axis")
    assert kw["kind"] == "standard" and kw["members"] == []
    engine.dispose()


def test_selection_export_carries_no_axes(tmp_path):
    engine = _db(tmp_path, "src.sqlite")
    with engine.begin() as conn:
        p1, _ = _seed(conn)
        b = build_bundle(conn, scope="selection", paper_ids=[p1])
    assert b["scope"] == "selection" and len(b["papers"]) == 1
    assert b["papers"][0]["identity"]["doi"] == "10.1234/one"
    assert "axes" not in b  # a selection is a transient set, not a library structure
    engine.dispose()


# ── import ──────────────────────────────────────────────────────────────────


def test_round_trip_into_empty_library(tmp_path):
    src, dst = _db(tmp_path, "s.sqlite"), _db(tmp_path, "d.sqlite")
    with src.begin() as conn:
        _seed(conn)
        bundle = build_bundle(conn, scope="library")
    with dst.begin() as conn:
        res = import_bundle(conn, bundle)
    s = res["summary"]
    assert s["papers_created"] == 2 and s["papers_merged"] == 0
    assert s["annotations_added"] == 1 and s["tags_applied"] == 2
    assert s["axes_created"] == 2 and s["axes_members_added"] == 2
    assert len(res["created"]) == 2
    with dst.begin() as conn:
        one = _paper_by_doi(conn, "10.1234/one")
        assert one is not None and one["imported_source"] == "bundle-import"
        assert {t["name"] for t in tags_repo.get_tags_for_paper(conn, int(one["id"]))} == {"method", "important"}
        anns = annotations_repo.list_annotations_for_paper(conn, int(one["id"]))
        assert len(anns) == 1 and anns[0]["note"] == "a note"
    src.dispose()
    dst.dispose()


def test_reimport_is_idempotent(tmp_path):
    src, dst = _db(tmp_path, "s.sqlite"), _db(tmp_path, "d.sqlite")
    with src.begin() as conn:
        _seed(conn)
        bundle = build_bundle(conn, scope="library")
    with dst.begin() as conn:
        import_bundle(conn, bundle)
    with dst.begin() as conn:
        res2 = import_bundle(conn, bundle)  # second import of the same bundle
        # nothing new lands
        assert res2["summary"]["papers_created"] == 0 and res2["summary"]["papers_merged"] == 2
        assert res2["summary"]["annotations_added"] == 0 and res2["summary"]["axes_members_added"] == 0
        assert len(list(conn.execute(select(papers.c.id)))) == 2  # no duplicate papers
        assert len(list(conn.execute(select(annotations.c.id)))) == 1  # no duplicate annotations
    src.dispose()
    dst.dispose()


def test_merge_is_non_destructive(tmp_path):
    src, dst = _db(tmp_path, "s.sqlite"), _db(tmp_path, "d.sqlite")
    with src.begin() as conn:
        _seed(conn)
        bundle = build_bundle(conn, scope="library")
    with dst.begin() as conn:  # dest already has the same paper by DOI, with a DIFFERENT title + no tags
        create_paper(
            conn,
            title="Recipient's Own Title",
            csl_json={"title": "Recipient's Own Title", "DOI": "10.1234/one"},
            doi="10.1234/one",
            imported_source="user-edited",
        )
    with dst.begin() as conn:
        res = import_bundle(conn, bundle)
        assert (
            res["summary"]["papers_merged"] == 1 and res["summary"]["papers_created"] == 1
        )  # one merged, two created (p2)
        one = _paper_by_doi(conn, "10.1234/one")
        assert one["title"] == "Recipient's Own Title"  # metadata NOT overwritten
        assert one["imported_source"] == "user-edited"  # provenance NOT downgraded
        assert {t["name"] for t in tags_repo.get_tags_for_paper(conn, int(one["id"]))} == {
            "method",
            "important",
        }  # gained tags
        assert len(annotations_repo.list_annotations_for_paper(conn, int(one["id"]))) == 1  # gained the highlight
    src.dispose()
    dst.dispose()


def test_curated_members_resolve_keyword_axis_definition_only(tmp_path):
    src, dst = _db(tmp_path, "s.sqlite"), _db(tmp_path, "d.sqlite")
    with src.begin() as conn:
        _seed(conn)
        bundle = build_bundle(conn, scope="library")
    with dst.begin() as conn:
        import_bundle(conn, bundle)
        # the curated axis got both members (resolved by identity); the keyword axis exists but has no members
        node_ids = list(conn.execute(select(cluster_nodes.c.id)).scalars())
        members = list(
            conn.execute(
                select(cluster_node_papers.c.paper_id).where(cluster_node_papers.c.cluster_node_id.in_(node_ids))
            )
        )
        assert len(members) == 2  # only the curated axis's two members; the keyword axis is definition-only
    src.dispose()
    dst.dispose()


def test_annotation_attachment_id_is_dropped(tmp_path):
    src, dst = _db(tmp_path, "s.sqlite"), _db(tmp_path, "d.sqlite")
    with src.begin() as conn:
        _seed(conn)
        bundle = build_bundle(conn, scope="library")
    with dst.begin() as conn:
        import_bundle(conn, bundle)
        row = conn.execute(select(annotations.c.attachment_id).limit(1)).first()
        assert row is not None and row[0] is None  # the per-device PDF pointer is applied NULL
    src.dispose()
    dst.dispose()


# ── parse / caps ─────────────────────────────────────────────────────────────


def test_parse_bundle_valid_and_malformed():
    assert parse_bundle('{"callosum_bundle": 1, "papers": []}')["papers"] == []
    with pytest.raises(BundleError):
        parse_bundle("not json at all")
    with pytest.raises(BundleError):
        parse_bundle('{"callosum_bundle": 99, "papers": []}')  # unsupported version
    with pytest.raises(BundleError):
        parse_bundle('{"callosum_bundle": 1}')  # no papers list
    with pytest.raises(BundleError):
        parse_bundle('{"callosum_bundle": 1, "papers": []}' + " " * (MAX_BUNDLE_BYTES + 10))  # oversized
