"""B2 SP1 — portable library bundle: build → round-trip → idempotent → non-destructive merge → selection/axes →
caps. Hermetic: two throwaway SQLite DBs, no network, no embedding (import_bundle returns the created ids; the
router embeds them separately)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from app.backend.api import create_app
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
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import (
    annotations,
    citation_mappings,
    cluster_node_papers,
    cluster_nodes,
    evidence_quotes,
    metadata,
    papers,
    summaries,
    summary_sentences,
)


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


# ── B2 SP2: syntheses (relayed, not re-verified) ─────────────────────────────


def _seed_native_synthesis(conn):
    """A native papers-scope synthesis over one paper: 1 sentence, 1 verified citation into its chunk."""
    pid = create_paper(
        conn,
        title="Synth Paper",
        csl_json={"title": "Synth Paper", "DOI": "10.9/synth"},
        doi="10.9/synth",
        year=2022,
        first_author_family_name="Synthor",
    )
    aid = create_attachment(
        conn,
        paper_id=pid,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum="synthchk",
    )
    cid = create_chunk(
        conn,
        paper_id=pid,
        attachment_id=aid,
        text="the finding sentence",
        page_start=3,
        page_end=3,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="fixture",
        extraction_version="1",
        chunking_strategy="paragraph",
        chunk_version="cv1",
        source_attachment_checksum="synthchk",
    )
    sm = conn.execute(
        insert(summaries).values(
            scope_type="papers",
            scope_ref_json={"paper_ids": [pid]},
            content="A synthesis.",
            generated_by="fake",
            chunk_version_verified_against="cv",
            embedding_version_verified_against="ev",
            verification_version="vv",
            status="verified",
            overview_json=[{"text": "Overview line.", "claim_ordinals": [0]}],
        )
    ).inserted_primary_key[0]
    st = conn.execute(
        insert(summary_sentences).values(summary_id=sm, ordinal=0, text="The finding holds.")
    ).inserted_primary_key[0]
    mp = conn.execute(
        insert(citation_mappings).values(
            summary_sentence_id=st,
            chunk_id=cid,
            status="verified",
            chunk_version_verified_against="cv",
            embedding_version_verified_against="ev",
            verification_version="vv",
        )
    ).inserted_primary_key[0]
    conn.execute(
        insert(evidence_quotes).values(
            citation_mapping_id=mp,
            chunk_id=cid,
            quote_text="the finding sentence",
            page_start=3,
            page_end=3,
            retrieval_confidence=0.9,
            quote_confidence=1.0,
            support_confidence=0.8,
        )
    )
    return pid


def test_synthesis_export_carries_sentences_and_source_identity(tmp_path):
    engine = _db(tmp_path, "src.sqlite")
    with engine.begin() as conn:
        _seed_native_synthesis(conn)
        b = build_bundle(conn, scope="library")
    assert len(b["syntheses"]) == 1
    syn = b["syntheses"][0]
    assert syn["scope_type"] == "papers"
    assert any(i.get("doi") == "10.9/synth" for i in syn["scope_identities"])
    cite = syn["sentences"][0]["citations"][0]
    assert cite["status"] == "verified" and cite["quote_text"] == "the finding sentence"
    assert cite["source"]["doi"] == "10.9/synth"  # travels by identity, not chunk id
    engine.dispose()


def test_imported_synthesis_is_relayed_and_read_via_api(tmp_path):
    src = _db(tmp_path, "s.sqlite")
    with src.begin() as conn:
        _seed_native_synthesis(conn)
        bundle = build_bundle(conn, scope="library")
    dst_url = f"sqlite:///{(tmp_path / 'd.sqlite').as_posix()}"
    dst = make_engine(dst_url)
    metadata.create_all(dst)
    with dst.begin() as conn:  # dest has the source paper so the citation resolves by identity
        create_paper(
            conn,
            title="Synth Paper",
            csl_json={"title": "Synth Paper", "DOI": "10.9/synth"},
            doi="10.9/synth",
            year=2022,
            first_author_family_name="Synthor",
        )
        res = import_bundle(conn, bundle)
        assert res["summary"]["syntheses_imported"] == 1
        row = conn.execute(select(summaries).where(summaries.c.status == "imported")).mappings().first()
        assert row is not None and row["imported_json"] is not None  # a relayed display blob, never in the tables
    dst.dispose()
    app = create_app(db_url=dst_url)
    cl = TestClient(app)
    listed = cl.get("/summaries").json()
    imported = [s for s in listed if s["imported"]]
    assert len(imported) == 1
    detail = cl.get(f"/summaries/{imported[0]['summary_id']}").json()
    assert detail["imported"] is True
    cit = detail["sentences"][0]["citations"][0]
    assert cit["coordinate_precision"] == "region"  # never a fabricated exact box
    assert cit["paper_id"] is not None and cit["quote"] == "the finding sentence" and cit["status"] == "verified"
    src.dispose()


def test_synthesis_reimport_idempotent(tmp_path):
    src, dst = _db(tmp_path, "s.sqlite"), _db(tmp_path, "d.sqlite")
    with src.begin() as conn:
        _seed_native_synthesis(conn)
        bundle = build_bundle(conn, scope="library")
    with dst.begin() as conn:
        import_bundle(conn, bundle)
    with dst.begin() as conn:
        res2 = import_bundle(conn, bundle)
        assert res2["summary"]["syntheses_imported"] == 0  # dedup by content
        assert len(list(conn.execute(select(summaries.c.id).where(summaries.c.status == "imported")))) == 1
    src.dispose()
    dst.dispose()


def test_synthesis_citation_source_not_in_library(tmp_path):
    # A hand-crafted bundle whose synthesis cites a paper NOT carried in `papers` → the citation can't resolve.
    dst = _db(tmp_path, "d.sqlite")
    bundle = {
        "callosum_bundle": 1,
        "scope": "library",
        "papers": [],
        "syntheses": [
            {
                "scope_type": "query",
                "scope_identities": [],
                "scope_ref": {"query": "risk"},
                "content": "A relayed synthesis.",
                "overview_json": None,
                "generated_by": "fake",
                "sentences": [
                    {
                        "ordinal": 0,
                        "text": "A claim.",
                        "citations": [
                            {
                                "quote_text": "an external quote",
                                "page_start": 5,
                                "page_end": 5,
                                "status": "verified",
                                "retrieval_confidence": 0.9,
                                "quote_confidence": 1.0,
                                "support_confidence": 0.8,
                                "source": {"doi": "10.9/absent", "title": "Absent Paper"},
                            }
                        ],
                    }
                ],
            }
        ],
    }
    with dst.begin() as conn:
        assert import_bundle(conn, bundle)["summary"]["syntheses_imported"] == 1
        blob = conn.execute(select(summaries.c.imported_json).where(summaries.c.status == "imported")).scalars().first()
        cit = blob["sentences"][0]["citations"][0]
        assert cit["paper_id"] is None  # source not in your library
        assert cit["quote"] == "an external quote"  # evidence still carried (silence is not a certificate)
    dst.dispose()


def test_native_synthesis_only_never_re_exports_a_relayed_one(tmp_path):
    src, dst = _db(tmp_path, "s.sqlite"), _db(tmp_path, "d.sqlite")
    with src.begin() as conn:
        _seed_native_synthesis(conn)
        bundle = build_bundle(conn, scope="library")
    with dst.begin() as conn:
        import_bundle(conn, bundle)
        b2 = build_bundle(conn, scope="library")  # dest now holds a RELAYED synthesis
        assert b2["syntheses"] == []  # imported syntheses are never re-exported (clean provenance)
    src.dispose()
    dst.dispose()


def test_selection_bundle_carries_fully_contained_synthesis_only(tmp_path):
    engine = _db(tmp_path, "src.sqlite")
    with engine.begin() as conn:
        pid = _seed_native_synthesis(conn)
        other = create_paper(conn, title="Other", csl_json={"title": "Other"}, doi="10.9/other")
        b_in = build_bundle(conn, scope="selection", paper_ids=[pid])  # scope paper is selected
        b_out = build_bundle(conn, scope="selection", paper_ids=[other])  # synth's scope paper NOT selected
    assert len(b_in["syntheses"]) == 1 and b_out["syntheses"] == []
    engine.dispose()
