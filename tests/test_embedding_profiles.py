"""Selectable retrieval embedding profiles: identity, encoding contract, no vector-space mixing, completeness gating,
resumable/cancellable index builds, and the API/Ask wiring (verification stays on the baseline)."""

from __future__ import annotations

import ast
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.embeddings.models import (
    DEFAULT_NORMALIZATION,
    WHITESPACE_NORMALIZATION,
    EmbeddingModelConfigurationError,
    SentenceTransformerEmbeddingModel,
    normalize_text,
)
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.profile_index import build_profile_index, pending_chunks_by_paper
from app.backend.embeddings.profiles import (
    ARCTIC_QUERY_PREFIX,
    ARCTIC_S_PROFILE_KEY,
    BASELINE_PROFILE_KEY,
    PROFILES,
    IncompleteEmbeddingIndexError,
    active_retrieval_profile,
    profile_coverage,
    require_complete_index,
    set_active_retrieval_profile,
)
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import summaries
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
from app.backend.summarization.query_ranking import _rank_chunks_for_query
from tests.api_helpers import ApiFakeEmbeddingModel, _seed_summarization_library, _summarization_app

ARCTIC = PROFILES[ARCTIC_S_PROFILE_KEY]


@dataclass
class FakeArctic:
    """Stands in for the Arctic S encoder: the profile's identity, a query side that differs from the document
    side, and lazy_indexing=False. Vectors are deliberately the *reverse* of ApiFakeEmbeddingModel's so any
    mixing of the two spaces changes the ranking."""

    name: str = ARCTIC.model_name
    version: str = ARCTIC.model_version
    normalization: str = ARCTIC.normalization
    dimension: int = 3
    lazy_indexing: bool = False
    query_calls: list[list[str]] = field(default_factory=list)
    document_calls: list[list[str]] = field(default_factory=list)

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [[0.0, 0.0, 1.0] if "facial" in t.lower() else [1.0, 0.0, 0.0] for t in texts]

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        self.query_calls.append(list(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]


@pytest.fixture()
def small_arctic(monkeypatch: pytest.MonkeyPatch):
    """The real profile, at the fakes' 3-d dimension (coverage filters on dimension)."""
    profile = dataclasses.replace(ARCTIC, dimension=3)
    monkeypatch.setitem(PROFILES, ARCTIC_S_PROFILE_KEY, profile)
    return profile


# ---- identity + encoding contract ------------------------------------------------------------------------------


def test_profile_identities_are_explicit_and_baseline_is_unchanged() -> None:
    baseline = PROFILES[BASELINE_PROFILE_KEY]
    assert (baseline.model_version, baseline.normalization) == ("all-MiniLM-L6-v2", DEFAULT_NORMALIZATION)
    assert ARCTIC.model_name == "Snowflake/snowflake-arctic-embed-s"
    assert ARCTIC.revision == "e596f507467533e48a2e17c007f0e1dacc837b33"
    assert ARCTIC.revision in ARCTIC.model_version and "pooling=cls" in ARCTIC.model_version
    assert (ARCTIC.normalization, ARCTIC.dimension, ARCTIC.pooling) == (WHITESPACE_NORMALIZATION, 384, "cls")
    assert ARCTIC.query_prefix == "Represent this sentence for searching relevant passages: "
    assert ARCTIC.document_prefix == "" and ARCTIC.lazy_indexing is False
    # Distinct identity from the baseline in every field a candidate filter checks.
    assert (ARCTIC.model_name, ARCTIC.model_version) != (baseline.model_name, baseline.model_version)


def test_whitespace_normalization_keeps_case() -> None:
    assert normalize_text("  Theory\tof  Mind ", WHITESPACE_NORMALIZATION) == "Theory of Mind"
    assert normalize_text("  Theory\tof  Mind ", DEFAULT_NORMALIZATION) == "theory of mind"


class _Pooling:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def get_pooling_mode_str(self) -> str:
        return self.mode


class _FakeST:
    def __init__(self, pooling: str = "cls", max_seq_length: int = 512) -> None:
        self._modules = {"0": object(), "1": _Pooling(pooling)}
        self.max_seq_length = max_seq_length
        self.inputs: list[list[str]] = []

    def encode(self, texts, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["normalize_embeddings"] is True
        self.inputs.append(list(texts))
        import numpy as np

        return np.ones((len(texts), 2))


def _wrapper(fake: _FakeST) -> SentenceTransformerEmbeddingModel:
    model = SentenceTransformerEmbeddingModel(
        name=ARCTIC.model_name,
        version=ARCTIC.model_version,
        normalization=ARCTIC.normalization,
        query_prefix=ARCTIC.query_prefix,
        expected_pooling="cls",
        expected_max_seq_length=512,
        lazy_indexing=False,
    )
    model._model = fake
    return model


def test_query_and_document_sides_are_encoded_separately() -> None:
    fake = _FakeST()
    model = _wrapper(fake)
    model.encode_queries(["Theory  of mind"])
    model.encode_documents(["Theory  of mind"])
    model.encode_texts(["Body text"])
    assert fake.inputs == [[ARCTIC_QUERY_PREFIX + "Theory of mind"], ["Theory of mind"], ["Body text"]]


@pytest.mark.parametrize("fake", [_FakeST(pooling="mean"), _FakeST(max_seq_length=256)])
def test_checkpoint_contract_mismatch_refuses_to_encode(fake: _FakeST) -> None:
    with pytest.raises(EmbeddingModelConfigurationError):
        _wrapper(fake).encode_queries(["q"])
    assert fake.inputs == []


# ---- no vector-space mixing + completeness ---------------------------------------------------------------------


def _all_chunk_ids(engine) -> list[int]:
    return [cid for ids in pending_chunks_by_paper(engine, ApiFakeEmbeddingModel()).values() for cid in ids]


def test_search_never_mixes_profiles_in_a_shared_store(temp_db_url: str, small_arctic) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    store = InMemoryVectorStore()
    arctic = FakeArctic()
    with engine.begin() as conn:
        ids = _all_chunk_ids(engine)
        embed_chunks(conn, model=ApiFakeEmbeddingModel(), vector_store=store, chunk_ids=ids)
    build_profile_index(engine, model=arctic, vector_store=store)
    from app.backend.persistence.schema import chunks
    from app.backend.summarization.pipeline import _source_chunk_from_row

    with engine.begin() as conn:
        pool = [_source_chunk_from_row(r) for r in conn.execute(select(chunks)).mappings()]
        ranked_arctic = _rank_chunks_for_query(
            conn, source_chunks=pool, query="facial social judgment", model=arctic, vector_store=store, top_k=1
        )
        ranked_minilm = _rank_chunks_for_query(
            conn,
            source_chunks=pool,
            query="facial social judgment",
            model=ApiFakeEmbeddingModel(),
            vector_store=store,
            top_k=1,
        )
    # MiniLM ranks the facial chunk first; Arctic's (reversed) space ranks a non-facial chunk first. Had the
    # candidate set mixed spaces, the MiniLM facial vector would have won both searches.
    assert ranked_minilm[0].chunk_id == seeded["facial_chunk_id"]
    assert ranked_arctic[0].chunk_id != seeded["facial_chunk_id"]
    assert arctic.query_calls == [["facial social judgment"]]
    engine.dispose()


def test_incomplete_profile_index_is_refused_not_lazily_filled(temp_db_url: str, small_arctic) -> None:
    _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    arctic = FakeArctic()
    from app.backend.persistence.schema import chunks
    from app.backend.summarization.pipeline import _source_chunk_from_row

    with engine.begin() as conn:
        coverage = profile_coverage(conn, small_arctic)
        assert coverage["indexed_chunks"] == 0 and coverage["eligible_chunks"] > 0 and not coverage["complete"]
        with pytest.raises(IncompleteEmbeddingIndexError):
            require_complete_index(conn, small_arctic)
        pool = [_source_chunk_from_row(r) for r in conn.execute(select(chunks)).mappings()]
        with pytest.raises(IncompleteEmbeddingIndexError):
            _rank_chunks_for_query(
                conn, source_chunks=pool, query="q", model=arctic, vector_store=InMemoryVectorStore(), top_k=2
            )
    assert arctic.document_calls == []  # nothing was embedded behind the user's back
    engine.dispose()


def test_index_build_is_resumable_cancellable_and_idempotent(temp_db_url: str, small_arctic) -> None:
    _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    store = InMemoryVectorStore()
    papers_pending = len(pending_chunks_by_paper(engine, FakeArctic()))
    assert papers_pending >= 2

    calls = {"n": 0}

    def cancel_after_first() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    first = build_profile_index(engine, model=FakeArctic(), vector_store=store, should_cancel=cancel_after_first)
    assert first["cancelled"] is True and first["papers_indexed"] == 1
    with engine.connect() as conn:
        assert not profile_coverage(conn, small_arctic)["complete"]
    second = build_profile_index(engine, model=FakeArctic(), vector_store=store)
    assert second["papers_pending"] == papers_pending - 1 and not second["cancelled"]
    with engine.connect() as conn:
        assert profile_coverage(conn, small_arctic)["complete"]
        # The baseline space was never touched by the Arctic build.
        assert profile_coverage(conn, PROFILES[BASELINE_PROFILE_KEY])["indexed_chunks"] == 0
    third = build_profile_index(engine, model=FakeArctic(), vector_store=store)
    assert third["papers_pending"] == 0 and third["chunks_indexed"] == 0
    engine.dispose()


def test_active_profile_defaults_to_baseline_and_ignores_unknown_keys(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert active_retrieval_profile(conn).key == BASELINE_PROFILE_KEY
        set_active_retrieval_profile(conn, ARCTIC_S_PROFILE_KEY)
        assert active_retrieval_profile(conn).key == ARCTIC_S_PROFILE_KEY
        set_active_retrieval_profile(conn, BASELINE_PROFILE_KEY)
        assert active_retrieval_profile(conn).key == BASELINE_PROFILE_KEY
        from app.backend.persistence.schema import library_settings

        conn.execute(library_settings.update().values(value="from-the-future"))
        assert active_retrieval_profile(conn).key == BASELINE_PROFILE_KEY
    engine.dispose()


# ---- structural invariant -------------------------------------------------------------------------------------


def test_every_production_vector_search_scopes_its_candidates() -> None:
    """Same-dimension profiles share one vec table, so a search without candidate ids could rank across models."""
    offenders, seen = [], 0
    for path in [*Path("app/backend").rglob("*.py"), *Path("integrations").rglob("*.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "search"
                and isinstance(node.func.value, (ast.Name, ast.Attribute))
                and "store" in ast.unparse(node.func.value).lower()
            ):
                seen += 1
                if not any(kw.arg == "candidate_embedding_ids" for kw in node.keywords):
                    offenders.append(f"{path}:{node.lineno}")
    assert seen >= 6  # the guard must keep seeing the production searches it protects
    assert offenders == []


# ---- API + Ask wiring -----------------------------------------------------------------------------------------


def _profile_app(temp_db_url: str, arctic: FakeArctic, generator=None):
    app = _summarization_app(temp_db_url, generator=generator)
    app.state.profile_embedding_models = {ARCTIC_S_PROFILE_KEY: arctic}
    return app


def test_profiles_api_gates_selection_on_a_complete_index(temp_db_url: str, small_arctic) -> None:
    _seed_summarization_library(temp_db_url)
    client = TestClient(_profile_app(temp_db_url, FakeArctic()))
    state = client.get("/embedding-profiles").json()
    assert state["active"] == BASELINE_PROFILE_KEY and state["verification_model"] == "MiniLM (baseline)"
    arctic_row = next(p for p in state["profiles"] if p["key"] == ARCTIC_S_PROFILE_KEY)
    assert arctic_row["revision"] == ARCTIC.revision and arctic_row["coverage"]["complete"] is False

    assert client.put("/embedding-profiles/active", json={"key": ARCTIC_S_PROFILE_KEY}).status_code == 409
    assert client.put("/embedding-profiles/active", json={"key": "nope"}).status_code == 404
    assert client.post(f"/embedding-profiles/{BASELINE_PROFILE_KEY}/index").status_code == 400

    started = client.post(f"/embedding-profiles/{ARCTIC_S_PROFILE_KEY}/index")
    assert started.status_code == 202
    done = client.get(f"/embedding-profiles/index/{started.json()['job_id']}").json()
    assert done["status"] == "done" and done["summary"]["chunks_indexed"] > 0
    row = next(j for j in client.get("/status/jobs").json()["jobs"] if j["job_id"] == started.json()["job_id"])
    assert row["nav"] == {"workspace": "settings"}

    selected = client.put("/embedding-profiles/active", json={"key": ARCTIC_S_PROFILE_KEY})
    assert selected.status_code == 200 and selected.json()["active"] == ARCTIC_S_PROFILE_KEY


def test_ask_retrieves_with_profile_but_verifies_with_baseline(temp_db_url: str, small_arctic) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    claim = "Facial anomalies influence social judgments."
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text=claim, citations=[CandidateCitation(chunk_id=seeded["facial_chunk_id"], quote=claim)]
            )
        ]
    )
    arctic = FakeArctic()
    client = TestClient(_profile_app(temp_db_url, arctic, generator=generator))
    job = client.post(f"/embedding-profiles/{ARCTIC_S_PROFILE_KEY}/index").json()["job_id"]
    assert client.get(f"/embedding-profiles/index/{job}").json()["status"] == "done"
    assert client.put("/embedding-profiles/active", json={"key": ARCTIC_S_PROFILE_KEY}).status_code == 200

    started = client.post(
        "/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]], "query": "facial"}
    )
    payload = client.get(f"/summarize/{started.json()['job_id']}").json()
    assert payload["status"] == "done", payload
    assert arctic.query_calls  # retrieval used the profile's query side
    citation = payload["sentences"][0]["citations"][0]
    # Arctic's fake places the facial passage far from its query; a verified 1.0 retrieval confidence can only
    # come from the MiniLM baseline scoring the claim -- verification was not rescaled by the profile switch.
    assert citation["status"] == "verified" and citation["retrieval_confidence"] == pytest.approx(1.0)
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        scope_ref = conn.execute(
            select(summaries.c.scope_ref_json).where(summaries.c.id == payload["summary_id"])
        ).scalar_one()
    engine.dispose()
    provenance = scope_ref["retrieval_embedding"]
    assert provenance["profile"] == ARCTIC_S_PROFILE_KEY and provenance["model_version"] == ARCTIC.model_version
    assert provenance["verification_embedding"] == ApiFakeEmbeddingModel().version


def test_ask_fails_closed_when_the_active_profile_index_became_incomplete(temp_db_url: str, small_arctic) -> None:
    _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:  # selected earlier, then new chunks arrived (here: never indexed at all)
        set_active_retrieval_profile(conn, ARCTIC_S_PROFILE_KEY)
    engine.dispose()
    client = TestClient(_profile_app(temp_db_url, FakeArctic()))
    started = client.post("/summarize", json={"scope_type": "query", "query": "facial", "top_k": 2})
    payload = client.get(f"/summarize/{started.json()['job_id']}").json()
    assert payload["status"] == "error"
    assert "Arctic S index covers 0 of" in payload["detail"]
