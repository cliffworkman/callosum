from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import fitz
import pytest
from sqlalchemy import func, select, update

from alembic import command
from alembic.config import Config
from app.backend.embeddings.models import (
    DEFAULT_NORMALIZATION,
    SentenceTransformerEmbeddingModel,
    l2_normalize,
    normalize_text,
)
from app.backend.embeddings.pipeline import embed_chunks, embed_papers, find_stale_embeddings
from app.backend.embeddings.retrieval import search_similar
from app.backend.embeddings.vector_store import InMemoryVectorStore, SQLiteVecVectorStore, VectorStore, _table_name
from app.backend.pdf_processing.ingest import ingest_pdf_scaffold
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import chunks, embeddings


@dataclass(frozen=True)
class FakeEmbeddingModel:
    name: str = "fake-keyword-model"
    version: str = "v1"
    dimension: int = 4
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            normalized = normalize_text(text, self.normalization)
            vectors.append(
                l2_normalize(
                    [
                        float(any(word in normalized for word in ("neural", "brain", "cortex"))),
                        float(any(word in normalized for word in ("banana", "fruit", "orchard"))),
                        float(any(word in normalized for word in ("quote", "stored", "evidence"))),
                        0.1,
                    ]
                )
            )
        return vectors


def test_sentence_transformer_dimension_prefers_current_api() -> None:
    class CurrentApiModel:
        def get_embedding_dimension(self) -> int:
            return 384

        def get_sentence_embedding_dimension(self) -> int:
            raise AssertionError("Deprecated dimension API should not be called")

    model = SentenceTransformerEmbeddingModel()
    model._model = CurrentApiModel()

    assert model.dimension == 384


def test_sentence_transformer_dimension_falls_back_to_legacy_api() -> None:
    class LegacyApiModel:
        def get_sentence_embedding_dimension(self) -> int:
            return 768

    model = SentenceTransformerEmbeddingModel()
    model._model = LegacyApiModel()

    assert model.dimension == 768


def test_embed_papers_reports_progress_per_paper(tmp_path: Path) -> None:
    # inc 142: the migrator's determinate "X of N" — embed_papers calls on_progress(current, total) once per paper.
    engine = _migrated_engine(tmp_path)
    model = FakeEmbeddingModel()
    vector_store: VectorStore = SQLiteVecVectorStore()
    calls: list[tuple[int, int]] = []
    with engine.begin() as conn:
        for i in range(3):
            create_paper(
                conn,
                title=f"Paper {i}",
                abstract=f"Abstract {i} about banana orchards.",
                year=2024,
                csl_json={"id": f"p{i}", "type": "article-journal", "title": f"Paper {i}"},
                processing_tier="abstract-embedded",
            )
        embed_papers(conn, model=model, vector_store=vector_store, on_progress=lambda c, t: calls.append((c, t)))
    engine.dispose()
    assert calls == [(1, 3), (2, 3), (3, 3)]  # one determinate tick per paper


def test_embed_papers_batches_encode_texts_into_one_call(tmp_path: Path) -> None:
    # inc 418: proves the batching actually happens (call COUNT), not just that the resulting vectors are
    # correct — 3 fresh papers must yield ONE encode_texts() call with all 3 texts, not 3 calls with 1 each.
    engine = _migrated_engine(tmp_path)
    encode_calls: list[list[str]] = []

    @dataclass(frozen=True)
    class CountingEmbeddingModel:
        name: str = "counting-keyword-model"
        version: str = "v1"
        dimension: int = 4
        normalization: str = DEFAULT_NORMALIZATION

        def encode_texts(self, texts: list[str]) -> list[list[float]]:
            encode_calls.append(list(texts))
            return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    model = CountingEmbeddingModel()
    vector_store: VectorStore = SQLiteVecVectorStore()
    with engine.begin() as conn:
        for i in range(3):
            create_paper(
                conn,
                title=f"Paper {i}",
                abstract=f"Abstract {i} about banana orchards.",
                year=2024,
                csl_json={"id": f"p{i}", "type": "article-journal", "title": f"Paper {i}"},
                processing_tier="abstract-embedded",
            )
        created = embed_papers(conn, model=model, vector_store=vector_store)
    engine.dispose()
    assert len(created) == 3
    assert len(encode_calls) == 1  # ONE batched call ...
    assert len(encode_calls[0]) == 3  # ... covering all 3 papers, not 3 separate one-item calls


def test_embed_chunks_batches_encode_texts_into_one_call(tmp_path: Path) -> None:
    # inc 418: same proof for embed_chunks — a paper's 2 fresh chunks must yield ONE encode_texts() call with
    # both texts, not one call per chunk.
    engine = _migrated_engine(tmp_path)
    encode_calls: list[list[str]] = []

    @dataclass(frozen=True)
    class CountingEmbeddingModel:
        name: str = "counting-keyword-model"
        version: str = "v1"
        dimension: int = 4
        normalization: str = DEFAULT_NORMALIZATION

        def encode_texts(self, texts: list[str]) -> list[list[float]]:
            encode_calls.append(list(texts))
            return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    model = CountingEmbeddingModel()
    vector_store: VectorStore = SQLiteVecVectorStore()
    with engine.begin() as conn:
        pdf_path = _make_embedding_fixture_pdf(tmp_path / "embed-chunks-batch.pdf")
        ingest = ingest_pdf_scaffold(conn, pdf_path, title="Embed Chunks Batch Fixture")
        chunk_ids = [
            int(row[0]) for row in conn.execute(select(chunks.c.id).where(chunks.c.paper_id == ingest["paper_id"]))
        ]
        assert len(chunk_ids) == 2  # the fixture PDF has exactly 2 sentences → 2 chunks
        created = embed_chunks(conn, model=model, vector_store=vector_store, chunk_ids=chunk_ids)
    engine.dispose()
    assert len(created) == 2
    assert len(encode_calls) == 1  # ONE batched call ...
    assert len(encode_calls[0]) == 2  # ... covering both chunks, not 2 separate one-item calls


def test_embedding_chunks_and_papers_store_metadata_and_sqlite_vec_vectors(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = FakeEmbeddingModel()
    vector_store: VectorStore = SQLiteVecVectorStore()

    with engine.begin() as conn:
        pdf_path = _make_embedding_fixture_pdf(tmp_path / "embedding-fixture.pdf")
        ingest = ingest_pdf_scaffold(conn, pdf_path, title="Neural Evidence Fixture")
        metadata_paper_id = create_paper(
            conn,
            title="Fruit Metadata Paper",
            abstract="Banana orchard fruit ripening study.",
            year=2024,
            csl_json={"id": "fruit-paper", "type": "article-journal", "title": "Fruit Metadata Paper"},
            processing_tier="abstract-embedded",
        )

        chunk_embedding_ids = embed_chunks(
            conn, model=model, vector_store=vector_store, document_roles=ARTICLE_DOCUMENT_ROLES
        )
        paper_embedding_ids = embed_papers(conn, model=model, vector_store=vector_store)

        embedding_rows = list(conn.execute(select(embeddings)).mappings())
        chunk_hits = search_similar(
            conn,
            query="brain cortex neural evidence",
            model=model,
            vector_store=vector_store,
            top_k=2,
            target_types=("chunk",),
            document_roles=ARTICLE_DOCUMENT_ROLES,
        )
        paper_hits = search_similar(
            conn,
            query="banana fruit orchard",
            model=model,
            vector_store=vector_store,
            top_k=1,
            target_types=("paper",),
        )

    assert chunk_embedding_ids
    assert paper_embedding_ids
    assert all(row["target_type"] in {"chunk", "paper"} for row in embedding_rows)
    for row in embedding_rows:
        assert row["model_name"] == model.name
        assert row["model_version"] == model.version
        assert row["dimension"] == model.dimension
        assert row["normalization"] == model.normalization
        assert row["source_text_version"]
        assert row["vector_store_kind"] == "sqlite-vec"
        assert row["vector_store_ref"].startswith("callosum_vec_embeddings_4:")
        if row["target_type"] == "chunk":
            assert row["source_chunk_version"]

    assert chunk_hits
    assert chunk_hits[0].paper_id == ingest["paper_id"]
    assert chunk_hits[0].chunk_id is not None
    assert chunk_hits[0].page_start == 1
    assert chunk_hits[0].bbox_json
    assert paper_hits[0].paper_id == metadata_paper_id


def test_retrieval_ranks_relevant_chunk_above_unrelated_with_fake_vector_store(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = FakeEmbeddingModel()
    vector_store: VectorStore = InMemoryVectorStore()

    with engine.begin() as conn:
        pdf_path = _make_embedding_fixture_pdf(tmp_path / "ranking-fixture.pdf")
        ingest_pdf_scaffold(conn, pdf_path, title="Ranking Fixture")
        embed_chunks(conn, model=model, vector_store=vector_store, document_roles=ARTICLE_DOCUMENT_ROLES)

        hits = search_similar(
            conn,
            query="banana fruit orchard",
            model=model,
            vector_store=vector_store,
            top_k=2,
            target_types=("chunk",),
            document_roles=ARTICLE_DOCUMENT_ROLES,
        )
        hit_texts = [
            conn.execute(select(chunks.c.text).where(chunks.c.id == hit.chunk_id)).scalar_one() for hit in hits
        ]

    assert "Banana fruit orchard unrelated control paragraph." in hit_texts[0]
    assert hits[0].score > hits[1].score


def test_retrieval_can_restrict_hits_to_candidate_target_ids(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = FakeEmbeddingModel()
    vector_store: VectorStore = InMemoryVectorStore()

    with engine.begin() as conn:
        pdf_path = _make_embedding_fixture_pdf(tmp_path / "candidate-target-fixture.pdf")
        ingest_pdf_scaffold(conn, pdf_path, title="Candidate Target Fixture")
        embed_chunks(conn, model=model, vector_store=vector_store, document_roles=ARTICLE_DOCUMENT_ROLES)
        chunk_rows = list(conn.execute(select(chunks.c.id, chunks.c.text)).mappings())
        neural_id = int(next(row["id"] for row in chunk_rows if "Neural" in row["text"]))

        hits = search_similar(
            conn,
            query="banana fruit orchard",
            model=model,
            vector_store=vector_store,
            top_k=5,
            target_types=("chunk",),
            candidate_target_ids={neural_id},
        )

    assert [hit.chunk_id for hit in hits] == [neural_id]


def test_embedding_model_change_creates_distinct_records_and_stale_detection(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    old_model = FakeEmbeddingModel(version="v1")
    new_model = FakeEmbeddingModel(version="v2")
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        pdf_path = _make_embedding_fixture_pdf(tmp_path / "stale-fixture.pdf")
        ingest_pdf_scaffold(conn, pdf_path, title="Stale Fixture")
        old_ids = embed_chunks(conn, model=old_model, vector_store=vector_store, document_roles=ARTICLE_DOCUMENT_ROLES)
        new_ids = embed_chunks(conn, model=new_model, vector_store=vector_store, document_roles=ARTICLE_DOCUMENT_ROLES)
        stale = find_stale_embeddings(conn, model=new_model)

        assert conn.execute(select(func.count()).select_from(embeddings)).scalar_one() == len(old_ids) + len(new_ids)

    assert set(old_ids).isdisjoint(new_ids)
    assert {item.embedding_id for item in stale} == set(old_ids)
    assert {item.reason for item in stale} == {"embedding-model-changed"}


def test_chunk_version_change_is_reported_as_stale(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = FakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        pdf_path = _make_embedding_fixture_pdf(tmp_path / "chunk-version-fixture.pdf")
        ingest_pdf_scaffold(conn, pdf_path, title="Chunk Version Fixture")
        embedding_ids = embed_chunks(
            conn, model=model, vector_store=vector_store, document_roles=ARTICLE_DOCUMENT_ROLES
        )
        first_chunk_id = conn.execute(select(chunks.c.id).order_by(chunks.c.id).limit(1)).scalar_one()
        conn.execute(update(chunks).where(chunks.c.id == first_chunk_id).values(chunk_version="changed-version"))
        stale = find_stale_embeddings(conn, model=model)

    assert embedding_ids
    assert any(item.reason == "chunk-version-changed" for item in stale)


def test_sqlite_vec_candidate_search_finds_subset_outside_global_knn_cap() -> None:
    engine = make_engine("sqlite:///:memory:")
    sqlite_store = SQLiteVecVectorStore()
    memory_store = InMemoryVectorStore()

    with engine.begin() as conn:
        _populate_vector_stores(conn, sqlite_store, memory_store, count=6000)
        candidates = set(range(5000, 5005))
        hits = sqlite_store.search(
            conn,
            vector=[1.0, 0.0],
            top_k=5,
            candidate_embedding_ids=candidates,
        )

    assert [hit.embedding_id for hit in hits] == [5000, 5001, 5002, 5003, 5004]


@pytest.mark.parametrize(
    ("count", "candidate_ids", "top_k"),
    [
        (128, {7, 11, 29, 67, 101}, 3),
        (6000, set(range(5000, 5007)), 5),
    ],
)
def test_sqlite_vec_candidate_search_matches_in_memory_store(
    count: int,
    candidate_ids: set[int],
    top_k: int,
) -> None:
    engine = make_engine("sqlite:///:memory:")
    sqlite_store = SQLiteVecVectorStore()
    memory_store = InMemoryVectorStore()

    with engine.begin() as conn:
        _populate_vector_stores(conn, sqlite_store, memory_store, count=count)
        sqlite_hits = sqlite_store.search(
            conn,
            vector=[1.0, 0.0],
            top_k=top_k,
            candidate_embedding_ids=candidate_ids,
        )
        memory_hits = memory_store.search(
            conn,
            vector=[1.0, 0.0],
            top_k=top_k,
            candidate_embedding_ids=candidate_ids,
        )

    assert [hit.embedding_id for hit in sqlite_hits] == [hit.embedding_id for hit in memory_hits]
    assert len(sqlite_hits) == min(top_k, len(candidate_ids))


def test_sqlite_vec_unscoped_large_k_is_capped_without_crashing() -> None:
    engine = make_engine("sqlite:///:memory:")
    store = SQLiteVecVectorStore()

    with engine.begin() as conn:
        _populate_vector_stores(conn, store, InMemoryVectorStore(), count=5000)
        hits = store.search(conn, vector=[1.0, 0.0], top_k=5000)

    assert len(hits) == store.max_knn_k
    assert {1, 2, 3, 4, 5}.issubset({hit.embedding_id for hit in hits[:16]})


def test_sqlite_vec_search_limit_caps_unscoped_and_candidate_knn() -> None:
    store = SQLiteVecVectorStore()

    assert store._search_limit(5000, None) == 4096
    assert store._search_limit(5, set(range(15000))) == 5
    assert store._search_limit(50, set(range(20))) == 20


def _migrated_engine(tmp_path: Path):
    db_path = tmp_path / "callosum-embeddings.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return make_engine(url)


def _make_embedding_fixture_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=460, height=420)
    page.insert_text((50, 70), "Neural brain cortex evidence quote appears here.", fontsize=12)
    page.insert_text((50, 115), "Banana fruit orchard unrelated control paragraph.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _populate_vector_stores(
    conn,
    sqlite_store: SQLiteVecVectorStore,
    memory_store: InMemoryVectorStore,
    *,
    count: int,
) -> None:
    sqlite_store.ensure_ready(conn, dimension=2)
    from sqlite_vec import serialize_float32

    rows = []
    for embedding_id in range(1, count + 1):
        vector = _unit_vector(embedding_id * 0.0001)
        rows.append((embedding_id, serialize_float32(vector)))
        memory_store.add(conn, embedding_id=embedding_id, vector=vector)
    conn.exec_driver_sql(
        f"INSERT OR REPLACE INTO {_table_name(2)}(rowid, embedding) VALUES (?, ?)",
        rows,
    )


def _unit_vector(angle: float) -> list[float]:
    return [math.cos(angle), math.sin(angle)]
