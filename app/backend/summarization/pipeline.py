"""Summarization orchestration and persistence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, func, insert, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.schema import (
    attachments,
    chunks,
    citation_mappings,
    cluster_node_papers,
    evidence_quotes,
    papers,
    summaries,
    summary_sentences,
)
from app.backend.summarization.chunk_filtering import is_front_matter_chunk
from app.backend.summarization.generators import CandidateCitation, SourceChunk, SummaryGenerator
from app.backend.summarization.verification import (
    LocalCitationVerifier,
    SupportScorer,
    VerificationConfig,
    VerificationResult,
)


@dataclass(frozen=True)
class SummaryScope:
    scope_type: Literal["papers", "cluster_node", "query"]
    paper_ids: list[int] | None = None
    cluster_node_id: int | None = None
    query: str | None = None
    sections: list[str] | None = None

    def to_ref(self) -> dict[str, object]:
        ref: dict[str, object] = {
            "paper_ids": self.paper_ids,
            "cluster_node_id": self.cluster_node_id,
            "query": self.query,
        }
        if self.sections:
            ref["sections"] = self.sections
        return ref


@dataclass(frozen=True)
class CitationPersistenceResult:
    mapping_id: int
    evidence_quote_id: int
    chunk_id: int
    status: str
    retrieval_confidence: float
    quote_confidence: float
    support_confidence: float
    coordinate_precision: str | None


@dataclass(frozen=True)
class SummarySentencePersistenceResult:
    sentence_id: int
    ordinal: int
    text: str
    flagged: bool
    citations: list[CitationPersistenceResult]


@dataclass(frozen=True)
class SummaryPersistenceResult:
    summary_id: int
    status: str
    sentences: list[SummarySentencePersistenceResult]
    source_chunk_count: int
    section_filter: list[str]

    @property
    def flagged_sentences(self) -> list[SummarySentencePersistenceResult]:
        return [sentence for sentence in self.sentences if sentence.flagged]


def summarize_scope(
    conn: Connection,
    *,
    scope: SummaryScope,
    generator: SummaryGenerator,
    model: EmbeddingModel,
    vector_store: VectorStore,
    top_k: int = 8,
    verifier_config: VerificationConfig | None = None,
    support_scorer: SupportScorer | None = None,
    overview_requested: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> SummaryPersistenceResult:
    source_chunks = _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=vector_store, top_k=top_k)
    # Pass conn so the cache wrapper can read/write llm_cache on this same transaction (a second SQLite
    # connection mid-transaction would lock). Verification below runs on every result, cached or fresh.
    candidates = generator.generate(source_chunks=source_chunks, scope_ref=scope.to_ref(), conn=conn)
    verifier = LocalCitationVerifier(
        model=model,
        vector_store=vector_store,
        config=verifier_config,
        support_scorer=support_scorer,
    )
    # inc 408: real per-claim progress for the ONE genuinely instrumentable stage. Retrieval + generation above
    # stay un-instrumented on purpose — the LLM call is a single opaque blocking request with no sub-progress
    # signal, and a cache hit would make a naive elapsed-time ETA misleading — so `on_progress` is only ever
    # called here, once N (the candidate count) is known.
    # inc 418: every (candidate, citation) pair across the WHOLE summary is verified in ONE verify_many() call
    # (one batched embedding-encode + one batched NLI call) instead of one verify() call per citation — same
    # per-item logic and thresholds, just batched. Results are unzipped back into their per-candidate rows before
    # on_progress fires, so the reported sequence is unchanged: still exactly one call per candidate, in order.
    total_candidates = len(candidates)
    flat_items: list[tuple[str, CandidateCitation]] = [
        (candidate.text, citation) for candidate in candidates for citation in candidate.citations
    ]
    flat_results = verifier.verify_many(conn, items=flat_items, source_chunks=source_chunks)
    verification_rows: list[list[VerificationResult]] = []
    cursor = 0
    for index, candidate in enumerate(candidates, start=1):
        count = len(candidate.citations)
        verification_rows.append(flat_results[cursor : cursor + count])
        cursor += count
        if on_progress is not None:
            on_progress(index, total_candidates, "Verifying claim")
    summary_status = (
        "verified" if all(all(item.verified for item in row) and row for row in verification_rows) else "flagged"
    )
    overview_status = (
        "pending"
        if overview_requested and any(row and all(item.verified for item in row) for row in verification_rows)
        else "not_requested"
    )
    summary_id = _insert_summary(
        conn,
        scope=scope,
        content=" ".join(candidate.text for candidate in candidates),
        generated_by=generator.name,
        verifications=[item for row in verification_rows for item in row],
        source_chunk_count=len(source_chunks),
        status=summary_status,
        overview_status=overview_status,
    )
    sentence_results = []
    for ordinal, (candidate, verifications) in enumerate(zip(candidates, verification_rows, strict=False)):
        sentence_id = conn.execute(
            insert(summary_sentences).values(summary_id=summary_id, ordinal=ordinal, text=candidate.text)
        ).inserted_primary_key[0]
        citation_results = [
            _persist_verification(conn, sentence_id=int(sentence_id), verification=verification)
            for verification in verifications
        ]
        sentence_results.append(
            SummarySentencePersistenceResult(
                sentence_id=int(sentence_id),
                ordinal=ordinal,
                text=candidate.text,
                flagged=not citation_results or any(result.status != "verified" for result in citation_results),
                citations=citation_results,
            )
        )
    return SummaryPersistenceResult(
        summary_id=summary_id,
        status=summary_status,
        sentences=sentence_results,
        source_chunk_count=len(source_chunks),
        section_filter=scope.sections or [],
    )


def _source_chunks_for_scope(
    conn: Connection,
    *,
    scope: SummaryScope,
    model: EmbeddingModel,
    vector_store: VectorStore,
    top_k: int,
) -> list[SourceChunk]:
    # Exclude trashed (soft-deleted) papers from every scope: their chunks must not be retrieved into a new
    # synthesis (inc 65 closed the purge path; inc 66 closes this soft-delete leak). For the query scope (no
    # paper filter below) this is the only guard; for papers/cluster scopes it's defense-in-depth.
    live_papers = select(papers.c.id).where(papers.c.deleted_at.is_(None))
    stmt = (
        select(chunks)
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .where(chunks.c.paper_id.in_(live_papers), attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES))
        .order_by(chunks.c.id)
    )
    if scope.scope_type == "papers":
        paper_ids = scope.paper_ids or []
        stmt = stmt.where(chunks.c.paper_id.in_(paper_ids)) if paper_ids else stmt.where(False)
    elif scope.scope_type == "cluster_node":
        paper_ids = [
            int(row[0])
            for row in conn.execute(
                select(cluster_node_papers.c.paper_id).where(
                    cluster_node_papers.c.cluster_node_id == scope.cluster_node_id
                )
            )
        ]
        stmt = stmt.where(chunks.c.paper_id.in_(paper_ids)) if paper_ids else stmt.where(False)
    if scope.sections:
        stmt = stmt.where(chunks.c.section.in_(scope.sections))
    rows = [_source_chunk_from_row(row) for row in conn.execute(stmt).mappings()]
    if scope.query:
        return _rank_chunks_for_query(
            conn,
            source_chunks=rows,
            query=scope.query,
            model=model,
            vector_store=vector_store,
            top_k=top_k,
            preserve_paper_coverage=scope.scope_type == "papers",
        )
    # No query → prefer real body content over title-page/masthead chunks, then spread the budget across the
    # selected papers so a multi-paper summary covers them all (rows are chunk-id-ordered = import order, so the
    # first chunk of each paper is its front matter). Single paper → still drops its own masthead first.
    return _select_no_query(rows, top_k)


def _select_no_query(rows: list[SourceChunk], top_k: int) -> list[SourceChunk]:
    """Round-robin content chunks across papers first, then front-matter chunks as fallback, then slice top_k.
    Front matter (titles/mastheads/DOIs/author lines) is never dropped outright — a paper with only front matter
    still contributes once content is exhausted."""
    content = [chunk for chunk in rows if not is_front_matter_chunk(chunk.text)]
    front = [chunk for chunk in rows if is_front_matter_chunk(chunk.text)]
    ordered = list(_round_robin_by_paper(content)) + list(_round_robin_by_paper(front))
    return ordered[:top_k]


def _round_robin_by_paper(rows: list[SourceChunk]) -> list[SourceChunk]:
    """Interleave chunks across papers (paper1.c1, paper2.c1, …, paper1.c2, …), preserving each paper's own
    chunk order and the order papers first appear, so a top_k slice spans all selected papers. ≤1 paper is
    returned unchanged."""
    by_paper: dict[int, list[SourceChunk]] = {}
    for chunk in rows:
        by_paper.setdefault(chunk.paper_id, []).append(chunk)
    if len(by_paper) <= 1:
        return rows
    groups = list(by_paper.values())
    ordered: list[SourceChunk] = []
    for index in range(max(len(group) for group in groups)):
        for group in groups:
            if index < len(group):
                ordered.append(group[index])
    return ordered


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
    embed_chunks(conn, model=model, vector_store=vector_store, chunk_ids=[chunk.chunk_id for chunk in source_chunks])
    embedding_to_chunk = _chunk_embedding_ids_for_chunks(
        conn, model=model, chunk_ids=[chunk.chunk_id for chunk in source_chunks]
    )
    hits = vector_store.search(
        conn,
        vector=model.encode_texts([query])[0],
        # A selected-papers synthesis is an explicit request to consider those papers. Retrieve the full ranked
        # candidate set so the selector below can reserve each paper's strongest hit; ordinary library/query
        # searches retain the narrower global top-k behavior.
        top_k=min(len(embedding_to_chunk) if preserve_paper_coverage else top_k, len(embedding_to_chunk)),
        candidate_embedding_ids=set(embedding_to_chunk),
    )
    source_by_id = {chunk.chunk_id: chunk for chunk in source_chunks}
    ranked = [source_by_id[embedding_to_chunk[hit.embedding_id]] for hit in hits]
    return _select_ranked_with_paper_coverage(ranked, top_k) if preserve_paper_coverage else ranked


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


def _insert_summary(
    conn: Connection,
    *,
    scope: SummaryScope,
    content: str,
    generated_by: str,
    verifications: list[VerificationResult],
    source_chunk_count: int,
    status: str,
    overview_status: str,
) -> int:
    scope_ref = scope.to_ref()
    scope_ref["source_chunk_count"] = source_chunk_count
    result = conn.execute(
        insert(summaries).values(
            scope_type=scope.scope_type,
            scope_ref_json=scope_ref,
            content=content,
            generated_by=generated_by,
            chunk_version_verified_against=_combined_chunk_version(verifications),
            embedding_version_verified_against=_combined_embedding_version(verifications),
            verification_version="local-verifier-v1",
            status=status,
            overview_status=overview_status,
            overview_updated_at=func.current_timestamp(),
        )
    )
    return int(result.inserted_primary_key[0])


def _persist_verification(
    conn: Connection,
    *,
    sentence_id: int,
    verification: VerificationResult,
) -> CitationPersistenceResult:
    mapping_id = conn.execute(
        insert(citation_mappings).values(
            summary_sentence_id=sentence_id,
            chunk_id=verification.chunk_id,
            status=verification.status,
            chunk_version_verified_against=verification.chunk_version_verified_against,
            embedding_version_verified_against=verification.embedding_version_verified_against,
            verification_version=verification.verification_version,
        )
    ).inserted_primary_key[0]
    evidence_quote_id = conn.execute(
        insert(evidence_quotes).values(
            citation_mapping_id=int(mapping_id),
            chunk_id=verification.chunk_id,
            quote_text=verification.quote_text,
            page_start=verification.page_start,
            page_end=verification.page_end,
            bbox_json=verification.bbox_json,
            retrieval_confidence=verification.retrieval_confidence,
            quote_confidence=verification.quote_confidence,
            support_confidence=verification.support_confidence,
        )
    ).inserted_primary_key[0]
    return CitationPersistenceResult(
        mapping_id=int(mapping_id),
        evidence_quote_id=int(evidence_quote_id),
        chunk_id=verification.chunk_id,
        status=verification.status,
        retrieval_confidence=verification.retrieval_confidence,
        quote_confidence=verification.quote_confidence,
        support_confidence=verification.support_confidence,
        coordinate_precision=verification.coordinate_precision,
    )


def _source_chunk_from_row(row) -> SourceChunk:  # type: ignore[no-untyped-def]
    return SourceChunk(
        chunk_id=int(row["id"]),
        paper_id=int(row["paper_id"]),
        attachment_id=int(row["attachment_id"]),
        text=str(row["text"]),
        page_start=int(row["page_start"]),
        page_end=int(row["page_end"]),
        chunk_version=str(row["chunk_version"]),
        bbox_json=row["bbox_json"],
        section=row["section"],
    )


def _chunk_embedding_ids_for_chunks(
    conn: Connection,
    *,
    model: EmbeddingModel,
    chunk_ids: list[int],
) -> dict[int, int]:
    from app.backend.persistence.schema import embeddings

    embedding_rows = conn.execute(
        select(embeddings.c.id, embeddings.c.target_id).where(
            embeddings.c.target_type == "chunk",
            embeddings.c.target_id.in_(chunk_ids),
            embeddings.c.model_name == model.name,
            embeddings.c.model_version == model.version,
            embeddings.c.dimension == model.dimension,
            embeddings.c.normalization == model.normalization,
        )
    )
    return {int(row.id): int(row.target_id) for row in embedding_rows}


def _combined_chunk_version(verifications: list[VerificationResult]) -> str:
    versions = sorted(
        {item.chunk_version_verified_against for item in verifications if item.chunk_version_verified_against}
    )
    return ",".join(versions) or "none"


def _combined_embedding_version(verifications: list[VerificationResult]) -> str:
    versions = sorted(
        {item.embedding_version_verified_against for item in verifications if item.embedding_version_verified_against}
    )
    return ",".join(versions) or "none"
