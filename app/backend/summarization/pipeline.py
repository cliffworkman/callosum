"""Summarization orchestration and persistence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, Engine, func, insert, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import current_chunk_embedding_ids, embed_chunks
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
from app.backend.summarization.chunk_filtering import (
    exclude_repeated_boilerplate_chunks,
    is_front_matter_chunk,
    repeated_boilerplate_keys,
)
from app.backend.summarization.generators import (
    CandidateCitation,
    SourceChunk,
    SummaryGenerator,
    TruncatedGenerationError,
)
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
    engine: Engine,
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
    on_stage: Callable[[str, str, int | None, bool], None] | None = None,
) -> SummaryPersistenceResult:
    """Three phases, each opening its own short connection -- no connection or writer lock is held
    across the (potentially slow, up to ~600s) generation call in between (LATENCY.md). Phase 1
    (prepare) and Phase 3 (verify + persist) are separate transactions; Phase 3 re-reads every
    source chunk fresh before verification so a chunk mutated during Phase 2 (a concurrent
    re-extraction, for instance) can never leave stale-vs-fresh verification signals inconsistent
    with each other or with the persisted provenance (see ``_refresh_source_chunks``). No
    ``summaries`` row is created until generation + verification have both succeeded -- a failed
    attempt leaves nothing behind, exactly as before this restructure.
    """
    if on_stage is not None:
        on_stage("preparing_sources", "Preparing sources", None, False)
    with engine.begin() as conn:
        source_chunks = _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=vector_store, top_k=top_k)

    # Phase 2: the generator (its cache-wrapper layer specifically) manages its own short
    # connections around this call and holds none of them open during it -- see cache.py.
    if on_stage is not None:
        on_stage("generating_synthesis", "Generating synthesis", len(source_chunks), True)
    # A provider that hit its output ceiling still finished some claims; keep them and record that the
    # answer is incomplete, so the result can say so rather than passing for a whole one.
    generation_truncated = False
    try:
        candidates = generator.generate(source_chunks=source_chunks, scope_ref=scope.to_ref(), engine=engine)
    except TruncatedGenerationError as truncation:
        candidates, generation_truncated = truncation.sentences, True

    with engine.begin() as conn:
        fresh_source_chunks = _refresh_source_chunks(conn, source_chunks)
        verifier = LocalCitationVerifier(
            model=model,
            vector_store=vector_store,
            config=verifier_config,
            support_scorer=support_scorer,
        )
        # inc 408: real per-claim progress for the ONE genuinely instrumentable stage. Retrieval + generation
        # above stay un-instrumented on purpose — the LLM call is a single opaque blocking request with no
        # sub-progress signal, and a cache hit would make a naive elapsed-time ETA misleading — so `on_progress`
        # is only ever called here, once N (the candidate count) is known.
        # inc 418: every (candidate, citation) pair across the WHOLE summary is verified in ONE verify_many() call
        # (one batched embedding-encode + one batched NLI call) instead of one verify() call per citation — same
        # per-item logic and thresholds, just batched. Results are unzipped back into their per-candidate rows
        # before on_progress fires, so the reported sequence is unchanged: still exactly one call per candidate,
        # in order.
        total_candidates = len(candidates)
        flat_items: list[tuple[str, CandidateCitation]] = [
            (candidate.text, citation) for candidate in candidates for citation in candidate.citations
        ]
        if on_stage is not None:
            on_stage("verifying_citations", "Verifying citations", len(flat_items), False)
        flat_results = verifier.verify_many(conn, items=flat_items, source_chunks=fresh_source_chunks)
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
        if on_stage is not None:
            on_stage("finalizing_result", "Finalizing result", len(candidates), False)
        summary_id = _insert_summary(
            conn,
            scope=scope,
            content=" ".join(candidate.text for candidate in candidates),
            generated_by=generator.name,
            verifications=[item for row in verification_rows for item in row],
            source_chunk_count=len(source_chunks),
            status=summary_status,
            overview_status=overview_status,
            generation_truncated=generation_truncated,
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


def _refresh_source_chunks(conn: Connection, source_chunks: list[SourceChunk]) -> list[SourceChunk]:
    """Re-read the given chunks fresh, immediately before verification (Phase 3).

    Closes a staleness gap: verification must never check a citation's quote/version against a
    retrieval-time (Phase 1) in-memory snapshot that could have gone stale during however long
    generation (Phase 2, a possibly slow provider call) took. A chunk that no longer qualifies
    (deleted, or its paper trashed, in the interim) is simply dropped from the fresh set -- any
    citation that pointed at it falls through to ``LocalCitationVerifier``'s own existing
    fresh-point-read fallback for a chunk id outside the pool, which fails the whole attempt
    honestly (a clean rollback, surfaced as a job error) if the chunk is truly gone, rather than
    fabricating a result against phantom data. A no-op in the common case: nothing changed between
    Phase 1 and Phase 3.
    """
    if not source_chunks:
        return []
    ids = [chunk.chunk_id for chunk in source_chunks]
    live_papers = select(papers.c.id).where(papers.c.deleted_at.is_(None))
    stmt = (
        select(chunks)
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .where(
            chunks.c.id.in_(ids),
            chunks.c.paper_id.in_(live_papers),
            attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES),
        )
    )
    fresh_by_id = {int(row["id"]): _source_chunk_from_row(row) for row in conn.execute(stmt).mappings()}
    return [fresh_by_id[chunk_id] for chunk_id in ids if chunk_id in fresh_by_id]


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
    # Repeated-boilerplate DETECTION must see the paper's whole chunk set; the section filter narrows
    # only what is RETURNED (inc 577). Fusing the two made the answer depend on which section-filtered
    # list was handed in -- measured, a `sections=['methods']` synthesis kept 112 running-head chunks
    # that whole-paper scope removes, because a header on five pages survived into too few selected
    # chunks to reach the page-count floor.
    #
    # The extra query runs ONLY when a section filter exists: without one the candidate rows already
    # ARE the whole-paper pool, so re-reading it would be pure cost on the path that already carries
    # the O(library) query-scope expense. It also selects just the three columns the detector needs,
    # never a second full chunk materialization.
    boilerplate_keys = None
    if scope.sections:
        boilerplate_keys = repeated_boilerplate_keys(
            conn.execute(stmt.with_only_columns(chunks.c.paper_id, chunks.c.page_start, chunks.c.text).order_by(None))
        )
        stmt = stmt.where(chunks.c.section.in_(scope.sections))
    rows = [_source_chunk_from_row(row) for row in conn.execute(stmt).mappings()]
    rows = exclude_repeated_boilerplate_chunks(rows, keys=boilerplate_keys)
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
    if missing:
        embed_chunks(conn, model=model, vector_store=vector_store, chunk_ids=[c.chunk_id for c in missing])
        # Re-read only the chunks that were just embedded, not the whole pool again. Their ids come from
        # the same set query rather than from embed_chunks' return order, so nothing here depends on the
        # positional correspondence between its input list and its returned ids.
        current.update(current_chunk_embedding_ids(conn, ((c.chunk_id, c.chunk_version) for c in missing), model=model))
    embedding_to_chunk = {embedding_id: chunk_id for chunk_id, embedding_id in current.items()}
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
    generation_truncated: bool = False,
) -> int:
    scope_ref = scope.to_ref()
    scope_ref["source_chunk_count"] = source_chunk_count
    if generation_truncated:
        # Recorded beside source_chunk_count in the same extensible blob, so the disclosure
        # survives a reload without a schema change. Absent means not truncated.
        scope_ref["generation_truncated"] = True
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
