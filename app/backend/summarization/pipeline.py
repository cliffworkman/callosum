"""Summarization orchestration and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, insert, select, update

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.schema import (
    chunks,
    citation_mappings,
    cluster_node_papers,
    evidence_quotes,
    papers,
    summaries,
    summary_sentences,
)
from app.backend.summarization.chunk_filtering import is_front_matter_chunk
from app.backend.summarization.generators import SourceChunk, SummaryGenerator
from app.backend.summarization.overview import OverviewGenerator
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
    overview_generator: OverviewGenerator | None = None,
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
    verification_rows = [
        [
            verifier.verify(conn, sentence=candidate.text, citation=citation, source_chunks=source_chunks)
            for citation in candidate.citations
        ]
        for candidate in candidates
    ]
    summary_status = (
        "verified" if all(all(item.verified for item in row) and row for row in verification_rows) else "flagged"
    )
    summary_id = _insert_summary(
        conn,
        scope=scope,
        content=" ".join(candidate.text for candidate in candidates),
        generated_by=generator.name,
        verifications=[item for row in verification_rows for item in row],
        source_chunk_count=len(source_chunks),
        status=summary_status,
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
    _maybe_store_overview(
        conn,
        summary_id=summary_id,
        sentence_results=sentence_results,
        scope=scope,
        overview_generator=overview_generator,
    )
    return SummaryPersistenceResult(
        summary_id=summary_id,
        status=summary_status,
        sentences=sentence_results,
        source_chunk_count=len(source_chunks),
        section_filter=scope.sections or [],
    )


def _maybe_store_overview(
    conn: Connection,
    *,
    summary_id: int,
    sentence_results: list[SummarySentencePersistenceResult],
    scope: SummaryScope,
    overview_generator: OverviewGenerator | None,
) -> None:
    """Second pass: narrativize ONLY the verified claims into a per-sentence traceable Overview. Each Overview
    sentence's claim_indices (into the ordered verified claims) are validated and mapped to those claims'
    ordinals, then stored on summaries.overview_json. 0 verified claims → no overview; any error (egress-off
    included) → no overview (never fails the synthesis; the verified claims stand alone)."""
    if overview_generator is None:
        return
    verified = [sentence for sentence in sentence_results if not sentence.flagged]
    if not verified:
        return
    claims = [sentence.text for sentence in verified]
    try:
        produced = overview_generator.generate(verified_claims=claims, scope_ref=scope.to_ref())
    except Exception:
        return
    items: list[dict[str, object]] = []
    for sentence in produced:
        ordinals = sorted({verified[i].ordinal for i in sentence.claim_indices if 0 <= i < len(verified)})
        if sentence.text.strip() and ordinals:
            items.append({"text": sentence.text.strip(), "claim_ordinals": ordinals})
    if items:
        conn.execute(update(summaries).where(summaries.c.id == summary_id).values(overview_json=items))


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
    stmt = select(chunks).where(chunks.c.paper_id.in_(live_papers)).order_by(chunks.c.id)
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
        top_k=min(top_k, len(embedding_to_chunk)),
        candidate_embedding_ids=set(embedding_to_chunk),
    )
    source_by_id = {chunk.chunk_id: chunk for chunk in source_chunks}
    return [source_by_id[embedding_to_chunk[hit.embedding_id]] for hit in hits]


def _insert_summary(
    conn: Connection,
    *,
    scope: SummaryScope,
    content: str,
    generated_by: str,
    verifications: list[VerificationResult],
    source_chunk_count: int,
    status: str,
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
