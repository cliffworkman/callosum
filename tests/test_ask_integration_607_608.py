"""Inc 607 + 608 together on the narrow Ask retrieval path (``pipeline._source_chunks_for_scope``).

The order is: the retrieval profile's own vectors rank the candidates (608, identity-scoped search), then the
inc-607 seam demotes anchored bibliography before the budget is sliced. Eligibility reads only ``chunk_structure``
by chunk id, so it cannot vary with the embedding model, and neither step rewrites a vector or a chunk. The fake
Arctic space here ranks the reference entry FIRST, so the demotion is doing real work under both profiles.
"""

from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import func, select

from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.profile_index import build_profile_index
from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, PROFILES, IncompleteEmbeddingIndexError
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import chunks, embeddings
from app.backend.summarization.evidence_selection import split_by_reference_eligibility
from app.backend.summarization.pipeline import SummaryScope, _source_chunk_from_row, _source_chunks_for_scope
from tests.api_helpers import ApiFakeEmbeddingModel
from tests.test_embedding_profiles import FakeArctic
from tests.test_reference_eligibility_selection import LABELS, REFERENCE, _seed

QUERY = "facial anomaly"


@dataclasses.dataclass
class ReferenceFirstArctic(FakeArctic):
    """Arctic stand-in whose space puts the bibliography entry nearest every query."""

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [[1.0, 0.0, 0.0] if t == REFERENCE else [0.0, 1.0, 0.0] for t in texts]


@pytest.fixture()
def small_arctic(monkeypatch: pytest.MonkeyPatch):
    profile = dataclasses.replace(PROFILES[ARCTIC_S_PROFILE_KEY], dimension=3)
    monkeypatch.setitem(PROFILES, ARCTIC_S_PROFILE_KEY, profile)
    return profile


class _RecordingStore(InMemoryVectorStore):
    def __init__(self) -> None:
        super().__init__()
        self.searched: list[set[int]] = []

    def search(self, conn, *, vector, top_k, candidate_embedding_ids=None):  # type: ignore[no-untyped-def]
        self.searched.append(set(candidate_embedding_ids or ()))
        return super().search(conn, vector=vector, top_k=top_k, candidate_embedding_ids=candidate_embedding_ids)


def _embedding_ids(conn, model) -> set[int]:  # type: ignore[no-untyped-def]
    return set(
        conn.execute(
            select(embeddings.c.id).where(
                embeddings.c.model_name == model.name, embeddings.c.model_version == model.version
            )
        ).scalars()
    )


def _pick(conn, ids, model, store, top_k):  # type: ignore[no-untyped-def]
    scope = SummaryScope(scope_type="query", query=QUERY)
    return [
        c.chunk_id for c in _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=top_k)
    ]


def test_both_profiles_hit_the_same_eligibility_policy_over_their_own_vectors(temp_db_url: str, small_arctic) -> None:
    engine = make_engine(temp_db_url)
    store = _RecordingStore()
    minilm, arctic = ApiFakeEmbeddingModel(), ReferenceFirstArctic()
    with engine.begin() as conn:
        ids = _seed(conn, LABELS)
        embed_chunks(conn, model=minilm, vector_store=store, chunk_ids=[ids[k] for k in LABELS])
    build_profile_index(engine, model=arctic, vector_store=store)
    with engine.begin() as conn:
        minilm_ids, arctic_ids = _embedding_ids(conn, minilm), _embedding_ids(conn, arctic)
        assert minilm_ids and arctic_ids and not (minilm_ids & arctic_ids)  # one shared 3-d store, two identities
        vectors_before = conn.execute(select(func.count()).select_from(embeddings)).scalar_one()
        versions_before = dict(conn.execute(select(chunks.c.id, chunks.c.chunk_version)).all())

        # Without the seam Arctic would put the reference entry in the first slot.
        raw = store.search(conn, vector=arctic.encode_queries([QUERY])[0], top_k=1, candidate_embedding_ids=arctic_ids)
        top = conn.execute(select(embeddings.c.target_id).where(embeddings.c.id == raw[0].embedding_id)).scalar_one()
        assert raw[0].embedding_id in arctic_ids and top == ids["reference"]
        store.searched.clear()

        for model, own_ids in ((minilm, minilm_ids), (arctic, arctic_ids)):
            assert set(_pick(conn, ids, model, store, top_k=2)) == {ids["prose0"], ids["prose1"]}
            assert store.searched[-1] <= own_ids  # 608: the search never saw the other model's vectors
            # 607: with budget to spare the disputed chunks are reachable, but only after every eligible one.
            assert _pick(conn, ids, model, store, top_k=4)[2:] in (
                [ids["reference"], ids["fp"]],
                [ids["fp"], ids["reference"]],
            )

        pool = [_source_chunk_from_row(r) for r in conn.execute(select(chunks)).mappings()]
        eligible, disputed = split_by_reference_eligibility(conn, pool)
        assert {c.chunk_id for c in disputed} == {ids["reference"], ids["fp"]}  # model-independent by construction
        assert {c.chunk_id for c in eligible} == {ids["prose0"], ids["prose1"]}

        # Neither step rewrites a vector or a chunk: identity and provenance survive eligibility decisions.
        assert conn.execute(select(func.count()).select_from(embeddings)).scalar_one() == vectors_before
        assert dict(conn.execute(select(chunks.c.id, chunks.c.chunk_version)).all()) == versions_before
    engine.dispose()


def test_incomplete_arctic_index_fails_closed_before_eligibility_runs(temp_db_url: str, small_arctic) -> None:
    engine = make_engine(temp_db_url)
    arctic = ReferenceFirstArctic()
    with engine.begin() as conn:
        ids = _seed(conn, LABELS)
        with pytest.raises(IncompleteEmbeddingIndexError):
            _pick(conn, ids, arctic, InMemoryVectorStore(), top_k=2)
    assert arctic.document_calls == []  # nothing embedded behind the user's back, no partial ranking returned
    engine.dispose()


def test_library_without_classifications_ranks_identically_with_and_without_the_seam(temp_db_url: str) -> None:
    """An unclassified corpus is an exact no-op for 607 under a selectable profile too: the comparison must not
    attribute a ranking difference to eligibility when no classification exists."""
    engine = make_engine(temp_db_url)
    store = InMemoryVectorStore()
    with engine.begin() as conn:
        ids = _seed(conn, {})
        model = ApiFakeEmbeddingModel()
        embed_chunks(conn, model=model, vector_store=store, chunk_ids=[ids[k] for k in LABELS])
        pool = [_source_chunk_from_row(r) for r in conn.execute(select(chunks)).mappings()]
        eligible, disputed = split_by_reference_eligibility(conn, pool)
        assert disputed == [] and len(eligible) == len(pool)
    engine.dispose()
