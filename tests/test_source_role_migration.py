"""Inc 611: v1 classifications cannot masquerade as current, and the repair reaches Ask retrieval.

Persistence: ``chunk-structure-v2`` makes every v1 row stale. Stale rows are recorded but never obeyed, so a
library that has not been re-derived yet gets the pre-607 behaviour (no demotion) rather than v1's false
demotions. The backfill re-derives only non-current papers, one committed paper at a time, is resumable after an
interruption, is idempotent, and writes nothing but ``chunk_structure``.

Ask: whole-library (query scope) and selected-paper (papers scope) retrieval, under MiniLM and an Arctic-shaped
profile, keep cited scientific prose and mislabelled conclusions in the pool, still demote genuine bibliography,
and never exceed the slot budget.
"""

from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import func, select, update

from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.profile_index import build_profile_index
from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, PROFILES, IncompleteEmbeddingIndexError
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.pdf_processing.chunk_structure import ChunkInput, classify_paper
from app.backend.persistence.chunk_structure_repo import raw_sha, replace_paper_structure, structure_role_states
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import chunks, embeddings, papers
from app.backend.persistence.schema_chunk_structure import DERIVATION_VERSION, chunk_structure
from app.backend.summarization.pipeline import SummaryScope, _source_chunks_for_scope
from tests.api_helpers import ApiFakeEmbeddingModel
from tests.test_embedding_profiles import FakeArctic
from tests.test_source_role_repair import (
    APA_ENTRY,
    CONCLUSION_IN_REFERENCES,
    CONCLUSION_WITH_CITATIONS,
    SCIENTIFIC_SOUNDING_TITLE,
)
from tools.backfill_chunk_structure import backfill, coverage

V1 = "chunk-structure-v1"
QUERY = "careless responders screening"
PLAIN = "Participants completed every block of the task, and we recorded their responses carefully throughout."


def _paper(conn, title: str, texts: dict[str, tuple[str, str | None]]) -> dict[str, int]:  # type: ignore[no-untyped-def]
    paper_id = create_paper(conn, title=title, csl_json={"title": title})
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum=f"sr-{title}",
        role="article-fulltext",
    )
    ids = {"paper": paper_id}
    for name, (body, section) in texts.items():
        ids[name] = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text=body,
            page_start=5,
            page_end=5,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version=f"{name}-v1",
            source_attachment_checksum=f"sr-{title}",
            section=section,
        )
    return ids


def _classify(conn, ids: dict[str, int], texts: dict, *, region: set[str] = frozenset()) -> None:  # type: ignore[no-untyped-def]
    names = [n for n in texts]
    results = classify_paper(
        [ChunkInput(chunk_id=ids[n], paper_id=ids["paper"], text=texts[n][0], chunk_version=f"{n}-v1") for n in names],
        reference_region={ids[n] for n in region},
        reference_region_source="anchored",
    )
    replace_paper_structure(
        conn,
        paper_id=ids["paper"],
        results=results,
        source={ids[n]: (raw_sha(texts[n][0]), f"{n}-v1") for n in names},
    )


def _as_v1(conn, chunk_role: dict[int, str]) -> None:  # type: ignore[no-untyped-def]
    """Rewrite rows as the OLD derivation would have left them (the v1 false demotion included)."""
    for chunk_id, role in chunk_role.items():
        conn.execute(
            update(chunk_structure)
            .where(chunk_structure.c.chunk_id == chunk_id)
            .values(derivation_version=V1, evidence_role=role)
        )


def _snapshot(conn):  # type: ignore[no-untyped-def]
    return (
        sorted(conn.execute(select(chunks)).all()),
        sorted(conn.execute(select(embeddings)).all()),
        sorted(conn.execute(select(papers.c.id, papers.c.title, papers.c.deleted_at)).all()),
    )


# --- persistence ---------------------------------------------------------------------------------


def test_v1_rows_are_stale_and_never_demote_under_v2(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    texts = {"prose": (CONCLUSION_WITH_CITATIONS, "discussion"), "ref": (APA_ENTRY, "references")}
    with engine.begin() as conn:
        ids = _paper(conn, "A", texts)
        _classify(conn, ids, texts, region={"prose", "ref"})
        _as_v1(conn, {ids["prose"]: "bibliographic"})
        states = structure_role_states(conn, [ids["prose"]])
        assert states[ids["prose"]].state != "current"  # v1 is recorded, not obeyed
    assert DERIVATION_VERSION == "chunk-structure-v2"
    engine.dispose()


def test_backfill_reclassifies_resumably_idempotently_and_touches_nothing_else(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    a_texts = {"prose": (CONCLUSION_WITH_CITATIONS, "discussion"), "ref": (APA_ENTRY, "references")}
    b_texts = {"plain": (PLAIN, "methods"), "ref": (SCIENTIFIC_SOUNDING_TITLE, "references")}
    with engine.begin() as conn:
        a = _paper(conn, "A", a_texts)
        b = _paper(conn, "B", b_texts)
        embed_chunks(
            conn,
            model=ApiFakeEmbeddingModel(),
            vector_store=InMemoryVectorStore(),
            chunk_ids=[a["prose"], a["ref"], b["plain"], b["ref"]],
        )
        _classify(conn, a, a_texts, region={"prose", "ref"})
        _classify(conn, b, b_texts)
        _as_v1(conn, {a["prose"]: "bibliographic", a["ref"]: "bibliographic", b["plain"]: "scientific"})
        _as_v1(conn, {b["ref"]: "bibliographic"})
        before = _snapshot(conn)

    assert coverage(engine)["papers_needing_derivation"] == 2

    first = backfill(engine, limit=1)  # an interrupted run: one paper committed, the other untouched
    assert first["papers"] == 1
    cov = coverage(engine)
    assert (cov["papers_current"], cov["papers_needing_derivation"]) == (1, 1)

    resumed = backfill(engine)
    assert (resumed["papers"], resumed["skipped_current"]) == (1, 1)  # resumes exactly where it stopped

    again = backfill(engine)
    assert (again["papers"], again["chunks"], again["skipped_current"]) == (0, 0, 2)  # idempotent

    with engine.begin() as conn:
        assert _snapshot(conn) == before  # no chunk, vector or paper write
        roles = {
            int(r.chunk_id): (r.evidence_role, r.derivation_version)
            for r in conn.execute(
                select(
                    chunk_structure.c.chunk_id, chunk_structure.c.evidence_role, chunk_structure.c.derivation_version
                )
            )
        }
    assert roles[a["prose"]] == ("scientific", DERIVATION_VERSION)
    assert roles[b["ref"]] == ("bibliographic", DERIVATION_VERSION)
    assert coverage(engine)["rows_by_derivation_version"] == {DERIVATION_VERSION: 4}
    engine.dispose()


# --- Ask integration -----------------------------------------------------------------------------


@dataclasses.dataclass
class ReferenceFirstArctic(FakeArctic):
    """Arctic stand-in whose space puts every genuine reference nearest the query."""

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [[1.0, 0.0, 0.0] if t in (APA_ENTRY, SCIENTIFIC_SOUNDING_TITLE) else [0.6, 0.8, 0.0] for t in texts]


@pytest.fixture()
def small_arctic(monkeypatch: pytest.MonkeyPatch):
    profile = dataclasses.replace(PROFILES[ARCTIC_S_PROFILE_KEY], dimension=3)
    monkeypatch.setitem(PROFILES, ARCTIC_S_PROFILE_KEY, profile)
    return profile


ASK_TEXTS = {
    "cited": (CONCLUSION_WITH_CITATIONS, "discussion"),  # was a v1 `ref_region.member`
    "mislabelled": (CONCLUSION_IN_REFERENCES, "references"),  # was excluded in SQL by its heading
    "plain": (PLAIN, "results"),
    "ref": (APA_ENTRY, "references"),  # genuine, heading-labelled: stays excluded in query scope
    "ref2": (SCIENTIFIC_SOUNDING_TITLE, "discussion"),  # genuine, region-anchored: demoted
}


def _seeded(engine, minilm, arctic):  # type: ignore[no-untyped-def]
    store = InMemoryVectorStore()
    with engine.begin() as conn:
        ids = _paper(conn, "Ask", ASK_TEXTS)
        _classify(conn, ids, ASK_TEXTS, region={"cited", "ref", "ref2"})
        embed_chunks(conn, model=minilm, vector_store=store, chunk_ids=[ids[k] for k in ASK_TEXTS])
    build_profile_index(engine, model=arctic, vector_store=store)
    return ids, store


def _pick(conn, model, store, scope: SummaryScope, top_k: int) -> list[int]:  # type: ignore[no-untyped-def]
    return [
        c.chunk_id for c in _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=top_k)
    ]


def test_whole_library_and_selected_papers_keep_prose_and_control_references(temp_db_url: str, small_arctic) -> None:
    engine = make_engine(temp_db_url)
    minilm, arctic = ApiFakeEmbeddingModel(), ReferenceFirstArctic()
    ids, store = _seeded(engine, minilm, arctic)
    with engine.begin() as conn:
        vectors_before = conn.execute(select(func.count()).select_from(embeddings)).scalar_one()
        whole_library = SummaryScope(scope_type="query", query=QUERY)
        selected = SummaryScope(scope_type="papers", paper_ids=[ids["paper"]], query=QUERY)
        for model in (minilm, arctic):
            wl = _pick(conn, model, store, whole_library, top_k=8)
            assert {ids["cited"], ids["mislabelled"], ids["plain"]} <= set(wl)  # science reaches retrieval
            assert ids["ref"] not in wl  # the heading filter still removes genuine references
            assert wl[-1] == ids["ref2"]  # 607 still demotes anchored bibliography behind every eligible chunk
            assert len(wl) <= 8

            sp = _pick(conn, model, store, selected, top_k=3)
            assert len(sp) == 3  # the budget is respected
            assert ids["ref2"] not in sp and ids["ref"] not in sp  # demotion promotes prose into the slots
            assert ids["cited"] in sp
        assert conn.execute(select(func.count()).select_from(embeddings)).scalar_one() == vectors_before
    engine.dispose()


def test_incomplete_index_still_fails_closed_with_the_repair(temp_db_url: str, small_arctic) -> None:
    engine = make_engine(temp_db_url)
    arctic = ReferenceFirstArctic()
    with engine.begin() as conn:
        _paper(conn, "Unindexed", ASK_TEXTS)
        with pytest.raises(IncompleteEmbeddingIndexError):
            _pick(conn, arctic, InMemoryVectorStore(), SummaryScope(scope_type="query", query=QUERY), top_k=8)
    assert arctic.document_calls == []
    engine.dispose()
