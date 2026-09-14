"""Axis-scoped Ask (GitHub #82, inc 602): the axis resolves to a concrete paper set that becomes an ordinary
`papers` scope. Covers the hard corpus boundary, the eligibility tiers, execution-time provenance, and the
honest empty/no-full-text states. Hermetic; no network, no model.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import insert

from alembic import command
from alembic.config import Config
from app.backend.api import create_app
from app.backend.clustering.axis_assignments import add_manual_assignment, ensure_axis_node
from app.backend.clustering.axis_membership import papers_with_usable_fulltext, resolve_axis_corpus
from app.backend.clustering.axis_scoring import create_axis
from app.backend.pdf_processing.extraction import COORDINATE_SYSTEM, DEFAULT_CHUNKING_STRATEGY
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import cluster_node_papers

CUTOFF = 0.35  # DEFAULT_AXIS_CUTOFF


def _migrated(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'axis-ask.sqlite').as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return url


def _paper(conn, title: str, *, fulltext: bool = False) -> int:
    pid = create_paper(conn, title=title, csl_json={"title": title})
    if fulltext:
        att = create_attachment(
            conn,
            paper_id=pid,
            storage_mode="linked",
            availability="available",
            original_path=f"/f/{pid}.pdf",
            resolved_path=f"/f/{pid}.pdf",
            checksum=f"ck{pid}",
            file_size=10,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        create_chunk(
            conn,
            paper_id=pid,
            attachment_id=att,
            text=f"Body text for {title}.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system=COORDINATE_SYSTEM,
            extraction_tool="pymupdf",
            extraction_version="t",
            chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
            chunk_version=f"ck{pid}-v1",
            source_attachment_checksum=f"ck{pid}",
            char_start=0,
            char_end=10,
            bbox_json=[{"page": 1, "x0": 10, "y0": 10, "x1": 90, "y1": 30}],
        )
    return pid


def _score(conn, axis_id: int, paper_id: int, confidence: float) -> None:
    node = ensure_axis_node(conn, axis_id)
    conn.execute(insert(cluster_node_papers).values(cluster_node_id=node, paper_id=paper_id, confidence=confidence))


def test_resolve_axis_corpus_tiers(tmp_path):
    engine = make_engine(_migrated(tmp_path))
    with engine.begin() as conn:
        axis = create_axis(conn, label="Topic")
        p_manual = _paper(conn, "Manual")
        p_assigned = _paper(conn, "Assigned")
        p_uncertain = _paper(conn, "Uncertain")
        _outside = _paper(conn, "Outside")  # not in the axis at all
        add_manual_assignment(conn, axis_id=axis, paper_id=p_manual)  # confidence NULL -> manual
        _score(conn, axis, p_assigned, 0.9)  # >= cutoff -> assigned
        _score(conn, axis, p_uncertain, 0.25)  # < cutoff -> uncertain
    with engine.connect() as conn:
        assigned = resolve_axis_corpus(conn, axis, "assigned", cutoff=CUTOFF)
        allmembers = resolve_axis_corpus(conn, axis, "all", cutoff=CUTOFF)
    engine.dispose()
    assert assigned == sorted([p_manual, p_assigned])  # uncertain excluded by default
    assert allmembers == sorted([p_manual, p_assigned, p_uncertain])  # include uncertain
    assert _outside not in allmembers  # an unrelated Library paper is never in scope


def test_papers_with_usable_fulltext_matches_retrieval_eligibility(tmp_path):
    engine = make_engine(_migrated(tmp_path))
    with engine.begin() as conn:
        p_ft = _paper(conn, "HasText", fulltext=True)
        p_meta = _paper(conn, "MetaOnly")  # no chunks
    with engine.connect() as conn:
        eligible = papers_with_usable_fulltext(conn, [p_ft, p_meta])
    engine.dispose()
    assert eligible == {p_ft}  # only the chunked paper is retrieval-eligible


def test_ask_scope_endpoint_reports_both_tiers_and_eligibility(tmp_path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    with engine.begin() as conn:
        axis = create_axis(conn, label="My topic")
        a = _paper(conn, "A", fulltext=True)
        _score(conn, axis, a, 0.9)  # assigned + full text
        u = _paper(conn, "U")  # uncertain, no full text
        _score(conn, axis, u, 0.25)
    engine.dispose()
    body = TestClient(create_app(db_url=url)).get(f"/axes/{axis}/ask-scope").json()
    assert body["axis_label"] == "My topic"
    assert body["assigned"] == {"count": 1, "eligible_count": 1}
    assert body["all"] == {"count": 2, "eligible_count": 1}  # +uncertain paper, which has no full text


def test_axis_ask_persists_the_resolved_corpus_and_survives_membership_change(tmp_path):
    """The run snapshots the resolved paper set (scope_ref_json.paper_ids); a later axis change cannot rewrite
    a historical run's corpus. (Uses the injected fake generator so no provider/model is needed.)"""
    from app.backend.summarization.generators import FakeSummaryGenerator
    from tests.api_helpers import _summarization_app  # injects fake generator + embedding + vector store

    url = _migrated(tmp_path)
    engine = make_engine(url)
    with engine.begin() as conn:
        axis = create_axis(conn, label="Topic")
        p1 = _paper(conn, "P1", fulltext=True)
        _score(conn, axis, p1, 0.9)
    engine.dispose()
    client = TestClient(_summarization_app(url, generator=FakeSummaryGenerator(sentences=[])))
    r = client.post(
        "/summarize", json={"scope_type": "axis", "axis_id": axis, "query": "what?", "membership_tier": "all"}
    )
    assert r.status_code == 202
    # (job runs synchronously via BackgroundTasks in TestClient) — read the persisted run's scope_ref
    import sqlalchemy as sa

    from app.backend.persistence.schema import summaries as summaries_t

    eng2 = make_engine(url)
    with eng2.connect() as conn:
        ref = conn.execute(sa.select(summaries_t.c.scope_ref_json)).mappings().first()["scope_ref_json"]
    # add a NEW paper to the axis after the run
    with eng2.begin() as conn:
        p2 = _paper(conn, "P2 added later", fulltext=True)
        _score(conn, axis, p2, 0.9)
    eng2.dispose()
    assert ref["paper_ids"] == [p1]  # the historical run kept ONLY the paper eligible at run time
    assert ref["scope_origin"]["kind"] == "axis" and ref["scope_origin"]["id"] == axis
    assert ref["scope_origin"]["policy"] == "all"


def test_empty_axis_scope_fails_honestly_and_is_never_widened(tmp_path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    with engine.begin() as conn:
        axis = create_axis(conn, label="Empty")  # no members
        _lonely = _paper(conn, "A library paper NOT in the axis", fulltext=True)
    engine.dispose()
    r = TestClient(create_app(db_url=url)).post(
        "/summarize", json={"scope_type": "axis", "axis_id": axis, "query": "what?"}
    )
    assert r.status_code == 422  # honest empty-scope error; NOT widened to the whole library


def test_axis_scope_requires_axis_id_and_query(tmp_path):
    url = _migrated(tmp_path)
    client = TestClient(create_app(db_url=url))
    assert client.post("/summarize", json={"scope_type": "axis", "query": "q"}).status_code == 400
    assert client.post("/summarize", json={"scope_type": "axis", "axis_id": 1, "query": ""}).status_code == 400
