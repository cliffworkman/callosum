"""SQLite host-parameter limits must not depend on whose machine the code runs on.

`Synthesize -> Ask` failed for the first user with a genuinely large library (716,670 chunks) with
`sqlite3.OperationalError: too many SQL variables`, in a path that had never failed in development.
The reason it never failed in development is the point of this file: `SQLITE_MAX_VARIABLE_NUMBER`
is a **build-time** property of whichever SQLite the interpreter was linked against —

- the development interpreter for this project reports 250,000;
- the CPython runtime shipped inside the packaged desktop app reports the upstream default 32,766.

So these tests deliberately **lower the limit on the connection** instead of trying to allocate a
library big enough to exceed whatever the local build happens to allow. That reproduces a real
user's failure on any machine, and keeps the guarantee ("no id list size can produce an invalid
statement") independent of the SQLite the test happens to run against.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import func, insert, select, update

from alembic import command
from alembic.config import Config
from app.backend.embeddings.models import DEFAULT_NORMALIZATION, l2_normalize
from app.backend.embeddings.pipeline import current_chunk_embedding_ids, embed_chunks
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_paper
from app.backend.persistence.schema import chunks, embeddings
from app.backend.persistence.sql_batch import SQL_VARIABLE_BATCH, in_batches

# The lowered limit must sit ABOVE the batch size (or even correct batching would fail) and BELOW
# the id count (or an unbatched IN would succeed and the test would prove nothing).
CHUNK_COUNT = 1500
LOWERED_LIMIT = SQL_VARIABLE_BATCH + 50


class _FixedEmbeddingModel:
    name = "fake-batch-model"
    version = "v1"
    dimension = 2
    normalization = DEFAULT_NORMALIZATION

    def __init__(self) -> None:
        self.encoded: list[str] = []

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        self.encoded.extend(texts)
        return [l2_normalize([1.0, float(len(text) % 7)]) for text in texts]


@pytest.fixture()
def migrated_db_url(tmp_path: Path) -> str:
    db_path = tmp_path / "callosum-sql-batch.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return url


def _lower_variable_limit(conn, limit: int = LOWERED_LIMIT) -> None:
    """Pin this connection to a small parameter budget, emulating a stricter SQLite build."""
    conn.connection.driver_connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, limit)


def _seed_chunks(conn, count: int = CHUNK_COUNT) -> list[int]:
    paper_id = create_paper(
        conn,
        title="Large library",
        csl_json={"id": "large-library", "type": "article-journal", "title": "Large library"},
    )
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="managed",
        availability="available",
        checksum="checksum-batch",
        content_type="application/pdf",
        role="article-fulltext",
    )
    conn.execute(
        insert(chunks),
        [
            {
                "paper_id": paper_id,
                "attachment_id": attachment_id,
                "text": f"Chunk {index} about the cortex.",
                "page_start": 1,
                "page_end": 1,
                "bbox_coordinate_system": "pdf-points-top-left",
                "extraction_tool": "test",
                "extraction_version": "0.1",
                "chunking_strategy": "paragraph-v1",
                "chunk_version": "paragraph-v1:checksum-batch",
                "source_attachment_checksum": "checksum-batch",
            }
            for index in range(count)
        ],
    )
    return [int(row[0]) for row in conn.execute(select(chunks.c.id).order_by(chunks.c.id))]


def test_in_batches_never_exceeds_the_batch_size() -> None:
    values = list(range(2000))
    batches = list(in_batches(values))
    assert [item for batch in batches for item in batch] == values, "batching must not lose or reorder ids"
    assert all(len(batch) <= SQL_VARIABLE_BATCH for batch in batches)
    assert SQL_VARIABLE_BATCH < 999, "must hold on pre-3.32 SQLite builds too, not just modern ones"
    assert list(in_batches([])) == []


def test_embed_chunks_survives_an_id_list_larger_than_the_parameter_limit(migrated_db_url: str) -> None:
    """The reported failure: every chunk id passed at once, on a build with a real limit."""
    engine = make_engine(migrated_db_url)
    model, store = _FixedEmbeddingModel(), InMemoryVectorStore()

    with engine.begin() as conn:
        chunk_ids = _seed_chunks(conn)

    with engine.begin() as conn:
        _lower_variable_limit(conn)
        created = embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)

    assert len(created) == CHUNK_COUNT
    with engine.begin() as conn:
        stored = conn.execute(select(func.count()).select_from(embeddings)).scalar_one()
    assert stored == CHUNK_COUNT


def test_embed_chunks_stays_idempotent_when_classified_in_bulk(migrated_db_url: str) -> None:
    """The bulk classifier must agree with the per-row predicate it replaced.

    If it under-matched, a second run would re-embed everything; if it over-matched, stale text
    would keep an outdated vector. Both are silent, so both are asserted.
    """
    engine = make_engine(migrated_db_url)
    model, store = _FixedEmbeddingModel(), InMemoryVectorStore()

    with engine.begin() as conn:
        chunk_ids = _seed_chunks(conn)
    with engine.begin() as conn:
        _lower_variable_limit(conn)
        first = embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)

    encoded_after_first = len(model.encoded)
    with engine.begin() as conn:
        _lower_variable_limit(conn)
        second = embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)

    assert second == first, "an already-embedded chunk must resolve to its existing embedding"
    assert len(model.encoded) == encoded_after_first, "nothing should have been re-encoded"


def test_a_stale_chunk_is_still_re_embedded_after_bulk_classification(migrated_db_url: str) -> None:
    """Version drift must still force a fresh vector — the guard that keeps edited text from being
    verified against a vector of its previous wording."""
    engine = make_engine(migrated_db_url)
    model, store = _FixedEmbeddingModel(), InMemoryVectorStore()

    with engine.begin() as conn:
        chunk_ids = _seed_chunks(conn)
    with engine.begin() as conn:
        _lower_variable_limit(conn)
        first = embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)

    edited = chunk_ids[7]
    with engine.begin() as conn:
        conn.execute(
            update(chunks)
            .where(chunks.c.id == edited)
            .values(text="Rewritten cortex passage.", chunk_version="paragraph-v1:checksum-EDITED")
        )

    encoded_before = len(model.encoded)
    with engine.begin() as conn:
        _lower_variable_limit(conn)
        second = embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)

    assert len(model.encoded) == encoded_before + 1, "exactly the edited chunk should be re-encoded"
    changed = [index for index, (a, b) in enumerate(zip(first, second, strict=True)) if a != b]
    assert changed == [7], "only the stale chunk's embedding id should change"


def test_chunk_embedding_id_lookup_survives_the_parameter_limit(migrated_db_url: str) -> None:
    """The synthesis-side lookup takes the same library-wide id list as embed_chunks."""
    engine = make_engine(migrated_db_url)
    model, store = _FixedEmbeddingModel(), InMemoryVectorStore()

    with engine.begin() as conn:
        chunk_ids = _seed_chunks(conn)
    with engine.begin() as conn:
        _lower_variable_limit(conn)
        embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)

    with engine.begin() as conn:
        _lower_variable_limit(conn)
        current = current_chunk_embedding_ids(
            conn, [(cid, "paragraph-v1:checksum-batch") for cid in chunk_ids], model=model
        )

    assert sorted(current) == sorted(chunk_ids), "every chunk must resolve to its current embedding"


def test_a_superseded_embedding_is_not_offered_as_a_retrieval_candidate(migrated_db_url: str) -> None:
    """Re-embedding INSERTs, it does not replace: an edited chunk keeps its old embedding row too
    (inc 438's "history left intact"). Only the current one may be a retrieval candidate — otherwise
    a chunk could be retrieved into a synthesis on the strength of wording it no longer contains.
    """
    engine = make_engine(migrated_db_url)
    model, store = _FixedEmbeddingModel(), InMemoryVectorStore()

    with engine.begin() as conn:
        chunk_ids = _seed_chunks(conn, count=3)
    with engine.begin() as conn:
        embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)

    edited = chunk_ids[1]
    with engine.begin() as conn:
        conn.execute(
            update(chunks)
            .where(chunks.c.id == edited)
            .values(text="Rewritten passage.", chunk_version="paragraph-v1:checksum-EDITED")
        )
        embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)

    with engine.begin() as conn:
        rows_for_edited = conn.execute(
            select(func.count()).select_from(embeddings).where(embeddings.c.target_id == edited)
        ).scalar_one()
        current = current_chunk_embedding_ids(
            conn,
            [
                (int(cid), "paragraph-v1:checksum-EDITED" if cid == edited else "paragraph-v1:checksum-batch")
                for cid in chunk_ids
            ],
            model=model,
        )
        newest = conn.execute(select(func.max(embeddings.c.id)).where(embeddings.c.target_id == edited)).scalar_one()

    assert rows_for_edited == 2, "the superseded embedding row must still exist to make this meaningful"
    assert current[edited] == newest, "the current embedding must be the post-edit one, not the stale row"


def test_unbatched_in_clause_would_fail_at_this_limit(migrated_db_url: str) -> None:
    """Proves the lowered limit is actually load-bearing.

    Without this, a batching regression could pass silently because the test's own id list happened
    to fit — the precise way the original bug hid on the maintainer's 250,000-parameter build.
    """
    engine = make_engine(migrated_db_url)
    with engine.begin() as conn:
        chunk_ids = _seed_chunks(conn)
        _lower_variable_limit(conn)
        with pytest.raises(Exception, match="too many SQL variables"):
            conn.execute(select(chunks.c.id).where(chunks.c.id.in_(chunk_ids))).all()
