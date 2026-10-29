"""Reference-exclusion repair: the narrow synthesis path consumes anchored ``chunk_structure`` labels.

Before the repair ``_source_chunks_for_scope`` never read ``chunk_structure``, so a reference-list chunk the
anchored detector had already labelled ``bibliographic`` could fill a substantive slot whenever it ranked (or, for
the no-query path, simply came first). Now such a chunk is demoted behind every eligible candidate, eligible chunks
backfill the budget, and it is used only as a disputed fallback -- never deleted, since the same label also hits
genuine Results prose.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.pdf_processing.chunk_structure import ChunkStructure
from app.backend.persistence.chunk_structure_repo import raw_sha, replace_paper_structure, structure_role_states
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import chunks
from app.backend.summarization import evidence_selection
from app.backend.summarization.evidence_selection import split_by_reference_eligibility
from app.backend.summarization.generators import SourceChunk
from app.backend.summarization.pipeline import SummaryScope, _source_chunks_for_scope
from tests.api_helpers import ApiFakeEmbeddingModel

REFERENCE = (
    "12. Smith GS, Kramer E, Ma Y. The facial neuroanatomy of geriatric depression. Int J Geriatr Psychiatry 2009."
)
PROSE = [
    "Facial anomalies reduced trust ratings in the main experiment (d = 0.41).",
    "Facial anomaly effects persisted after controlling for attractiveness.",
]
RESULTS_FALSE_POSITIVE = "In conclusion, facial anomaly ratings were lower than controls (Smith et al., 2009)."


def _seed(conn, labels: dict[str, str]) -> dict[str, int]:
    paper_id = create_paper(conn, title="Reference eligibility", csl_json={"title": "Reference eligibility"})
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum="refelig",
    )
    ids = {}
    texts = {"reference": REFERENCE, "fp": RESULTS_FALSE_POSITIVE, "prose0": PROSE[0], "prose1": PROSE[1]}
    for name, body in texts.items():  # reference + false positive are created FIRST (lowest ids, earliest rank)
        ids[name] = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text=body,
            page_start=3,
            page_end=3,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version=f"{name}-v1",
            source_attachment_checksum="refelig",
            section="discussion",
        )
    replace_paper_structure(
        conn,
        paper_id=paper_id,
        results=[
            ChunkStructure(
                ids[name], "reference_entry" if role == "bibliographic" else "body_prose", role, ["fixture"], 0.85
            )
            for name, role in labels.items()
        ],
        source={ids[name]: (raw_sha(texts[name]), f"{name}-v1") for name in labels},
    )
    ids["paper"] = paper_id
    return ids


LABELS = {"reference": "bibliographic", "fp": "bibliographic", "prose0": "scientific", "prose1": "scientific"}


def test_no_query_scope_backfills_eligible_chunks_ahead_of_anchored_bibliography(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ids = _seed(conn, LABELS)
        scope = SummaryScope(scope_type="papers", paper_ids=[ids["paper"]])
        model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
        picked = [
            c.chunk_id for c in _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=2)
        ]
        assert picked == [ids["prose0"], ids["prose1"]]
        # With budget to spare the disputed chunks are still reachable -- demoted, never deleted.
        everything = [
            c.chunk_id for c in _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=4)
        ]
        assert everything == [ids["prose0"], ids["prose1"], ids["reference"], ids["fp"]]
    engine.dispose()


def test_query_scope_demotes_anchored_bibliography_before_slicing_the_budget(temp_db_url: str, caplog) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ids = _seed(conn, LABELS)
        scope = SummaryScope(scope_type="query", query="facial anomaly")
        model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
        with caplog.at_level(logging.INFO, logger="app.backend.summarization.evidence_selection"):
            picked = {
                c.chunk_id
                for c in _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=2)
            }
        assert picked == {ids["prose0"], ids["prose1"]}
        assert "demoted as disputed bibliography" in caplog.text
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="app.backend.summarization.evidence_selection"):
            filled = [
                c.chunk_id
                for c in _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=3)
            ]
        assert filled[:2] == [ids["prose0"], ids["prose1"]] and len(filled) == 3
        assert "used as fallback" in caplog.text  # a disputed slot is reported, not silently passed off
    engine.dispose()


def test_stale_labels_are_reported_and_never_demote(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ids = _seed(conn, LABELS)
        conn.execute(chunks.update().where(chunks.c.id == ids["reference"]).values(text=REFERENCE + " (re-extracted)"))
        states = structure_role_states(conn, [ids["reference"], ids["prose0"], 999999])
        assert states[ids["reference"]].state == "stale" and states[ids["reference"]].stale_reason == "text_hash"
        assert states[ids["prose0"]].state == "current" and 999999 not in states
        pool = [
            SourceChunk(cid, ids["paper"], 1, text, 3, 3, version)
            for cid, text, version in conn.execute(
                select(chunks.c.id, chunks.c.text, chunks.c.chunk_version).where(chunks.c.paper_id == ids["paper"])
            )
        ]
        eligible, disputed = split_by_reference_eligibility(conn, pool)
        assert ids["reference"] in {c.chunk_id for c in eligible}  # stale label ignored, not reused
        assert [c.chunk_id for c in disputed] == [ids["fp"]]  # the still-current label keeps demoting
    engine.dispose()


def test_library_without_chunk_structure_is_an_exact_no_op(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ids = _seed(conn, {})
        scope = SummaryScope(scope_type="papers", paper_ids=[ids["paper"]])
        picked = [
            c.chunk_id
            for c in _source_chunks_for_scope(
                conn, scope=scope, model=ApiFakeEmbeddingModel(), vector_store=InMemoryVectorStore(), top_k=2
            )
        ]
        assert picked == [ids["reference"], ids["fp"]]
    engine.dispose()


def test_app_seam_never_builds_comparison_keys_and_decides_identically(temp_db_url: str, monkeypatch) -> None:
    # H1 regression: with no native authority the comparison key is never consulted by ``decide``, but building it
    # costs ~1 ms per chunk, and the selected-papers path sends every chunk of every selected paper through here.
    from app.backend.summarization import evidence_eligibility

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ids = _seed(conn, LABELS)
        pool = [
            SourceChunk(cid, ids["paper"], 1, text, 3, 3, version)
            for cid, text, version in conn.execute(
                select(chunks.c.id, chunks.c.text, chunks.c.chunk_version).where(chunks.c.paper_id == ids["paper"])
            )
        ]
        states = structure_role_states(conn, [c.chunk_id for c in pool])

        def forbidden(*_args, **_kwargs):
            raise AssertionError("the application seam must not build comparison keys")

        monkeypatch.setattr(evidence_eligibility, "_canonicalize_text", forbidden)
        eligible, disputed = split_by_reference_eligibility(conn, pool)
        monkeypatch.undo()
        assert [c.chunk_id for c in eligible] == [ids["prose0"], ids["prose1"]]
        assert [c.chunk_id for c in disputed] == [ids["reference"], ids["fp"]]
        # The decision without a key equals the decision with the real key length, for every anchored state.
        for chunk in pool:
            anchored = evidence_selection._anchored(states.get(chunk.chunk_id))
            real = len(evidence_eligibility.comparison_key(chunk.text)[0])
            with_key = evidence_eligibility.decide("u", key_length=real, native=None, anchored=anchored)
            without = evidence_eligibility.decide("u", key_length=0, native=None, anchored=anchored)
            assert (with_key.substantive, with_key.decision, with_key.reasons) == (
                without.substantive,
                without.decision,
                without.reasons,
            )
    engine.dispose()
