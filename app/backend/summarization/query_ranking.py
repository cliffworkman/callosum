"""Query-scoped evidence ranking for the single-query (narrow) synthesis path.

Split out of ``pipeline.py`` (600-line cap). Ranking uses the RETRIEVAL embedding model, which may be a selectable
profile (``embeddings/profiles.py``); verification uses its own model and never reaches this module.
"""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.embeddings.models import EmbeddingModel, encode_query
from app.backend.embeddings.pipeline import current_chunk_embedding_ids, embed_chunks
from app.backend.embeddings.profiles import IncompleteEmbeddingIndexError
from app.backend.embeddings.vector_store import VectorStore
from app.backend.summarization.evidence_selection import ELIGIBILITY_OVERFETCH, order_for_budget
from app.backend.summarization.generators import SourceChunk


def _rank_chunks_for_query(
    conn: Connection,
    *,
    source_chunks: list[SourceChunk],
    query: str,
    model: EmbeddingModel,
    vector_store: VectorStore,
    top_k: int,
    preserve_paper_coverage: bool = False,
) -> list[SourceChunk]:
    if not source_chunks:
        return []
    # The candidate pool here is every article chunk in the library for a query-scoped synthesis, and in the
    # overwhelmingly common case every one of them is already embedded. Classify first, using the chunk_version
    # each SourceChunk already carries, and only call embed_chunks for the stragglers: embed_chunks re-reads
    # every row it is given (all columns, including text) purely to decide "does this need embedding?", which at
    # library scale costs more than the entire rest of the ranking pass. Handing it only the chunks that really
    # need work keeps the semantics identical -- embed_chunks would classify these same chunks the same way --
    # while making the cost proportional to what changed rather than to library size.
    current = current_chunk_embedding_ids(
        conn, ((chunk.chunk_id, chunk.chunk_version) for chunk in source_chunks), model=model
    )
    missing = [chunk for chunk in source_chunks if chunk.chunk_id not in current]
    if missing and not getattr(model, "lazy_indexing", True):
        # A selectable profile's index is built by its own Status-tracked job, never as a surprise inside Ask; a
        # gap means the index is incomplete and ranking over it would favor the papers that happen to be indexed.
        raise IncompleteEmbeddingIndexError(
            f"{len(missing)} candidate passages have no {model.name} vector; build the retrieval index first."
        )
    if missing:
        embed_chunks(conn, model=model, vector_store=vector_store, chunk_ids=[c.chunk_id for c in missing])
        # Re-read only the chunks that were just embedded, not the whole pool again. Their ids come from
        # the same set query rather than from embed_chunks' return order, so nothing here depends on the
        # positional correspondence between its input list and its returned ids.
        current.update(current_chunk_embedding_ids(conn, ((c.chunk_id, c.chunk_version) for c in missing), model=model))
    embedding_to_chunk = {embedding_id: chunk_id for chunk_id, embedding_id in current.items()}
    hits = vector_store.search(
        conn,
        vector=encode_query(model, query),  # query side of an asymmetric profile; identical for MiniLM
        # A selected-papers synthesis is an explicit request to consider those papers: retrieve the full ranked set so
        # the selector below can reserve each paper's strongest hit. Library/query searches over-fetch a bounded few so
        # chunks demoted as disputed bibliography are backfilled from eligible ones (evidence_selection).
        top_k=min(
            len(embedding_to_chunk) if preserve_paper_coverage else top_k * ELIGIBILITY_OVERFETCH,
            len(embedding_to_chunk),
        ),
        candidate_embedding_ids=set(embedding_to_chunk),
    )
    source_by_id = {chunk.chunk_id: chunk for chunk in source_chunks}
    ranked = order_for_budget(conn, [source_by_id[embedding_to_chunk[hit.embedding_id]] for hit in hits], top_k)
    return _select_ranked_with_paper_coverage(ranked, top_k) if preserve_paper_coverage else ranked[:top_k]


def _select_ranked_with_paper_coverage(ranked: list[SourceChunk], top_k: int) -> list[SourceChunk]:
    """Keep global relevance order while reserving one best-ranked chunk per selected paper when possible.

    A focus query over an explicit paper selection should not silently erase a selected paper merely because
    another paper contains the query phrase many more times. If the budget is smaller than the number of papers,
    global relevance remains authoritative because complete coverage is impossible.
    """
    if top_k <= 0:
        return []
    paper_ids = {chunk.paper_id for chunk in ranked}
    if len(paper_ids) <= 1 or top_k < len(paper_ids):
        return ranked[:top_k]
    reserved: set[int] = set()
    seen_papers: set[int] = set()
    for chunk in ranked:
        if chunk.paper_id not in seen_papers:
            reserved.add(chunk.chunk_id)
            seen_papers.add(chunk.paper_id)
    selected = set(reserved)
    for chunk in ranked:
        if len(selected) >= top_k:
            break
        selected.add(chunk.chunk_id)
    return [chunk for chunk in ranked if chunk.chunk_id in selected]
