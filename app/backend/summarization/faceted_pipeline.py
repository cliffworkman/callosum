"""Faceted broad-Ask synthesis (inc 581).

The narrow path (``pipeline.summarize_scope``) embeds the whole question as one vector and retrieves
a single top-k -- which fails a broad, multifaceted question (the centroid is near nothing
specific). This module runs the query-planner's facets independently: per-facet retrieval, an
H1a evidence-hygiene *deprioritization* pass (never deletion), diversity/dedup/budget caps, bounded
per-facet generation via the UNCHANGED generator, ONE batched ``verify_many`` over every claim (the
verifier and its thresholds are untouched), verified-first assembly, and explicit per-facet coverage
that never renders retrieval failure as library absence.

No reconstructed evidence, no assembled quotations, no schema migration: the facet plan + coverage
ride the existing ``summaries.scope_ref_json`` blob. Generation text stays the exact stored chunk
text, so verbatim-quote verification is unaffected.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Literal

from sqlalchemy import Connection, Engine, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import current_chunk_embedding_ids, embed_chunks
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.chunk_structure_repo import current_structure_roles
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.schema import attachments, chunks, papers
from app.backend.summarization.chunk_filtering import exclude_repeated_boilerplate_chunks
from app.backend.summarization.generators import CandidateSummarySentence, SourceChunk, SummaryGenerator
from app.backend.summarization.pipeline import (
    SummaryPersistenceResult,
    SummaryScope,
    _persist_verified_summary,
    _refresh_source_chunks,
    _source_chunk_from_row,
    _verify_candidates,
)
from app.backend.summarization.query_planner import QueryPlan
from app.backend.summarization.responsiveness import classify_responsiveness
from app.backend.summarization.verification import (
    LocalCitationVerifier,
    SupportScorer,
    VerificationConfig,
)

# Budgets (deterministic post-retrieval caps -- no retrieval redesign).
PER_FACET_TOP_K = 6
GLOBAL_CHUNK_CAP = 36
PER_PAPER_CAP = 3
# Post-hoc rendered-claim caps per facet -- bounds the answer and the noise. Verified claims are the
# main synthesis; a few flagged candidates are retained (secondary) for transparency.
MAX_VERIFIED_PER_FACET = 3
MAX_FLAGGED_PER_FACET = 2

# Evidence roles the hygiene seam DEPRIORITIZES (never deletes -- the H1a study found no reason code
# clears the >=95% precision gate). `scientific` and `unknown` stay full priority; `unknown` is the
# dominant class and holds most real evidence, so it is a peer of `scientific`, never below it.
_DEPRIORITIZED_ROLES = frozenset({"bibliographic", "structural"})

CoverageStatus = Literal["supported", "partial", "retrieved_unverified", "no_evidence_retrieved"]


@dataclass(frozen=True)
class FacetEvidence:
    """One retrieved chunk, attributed to a facet, carrying faithful text + hygiene metadata.

    ``text`` is the exact stored chunk text (never normalized/assembled), so downstream verbatim
    quote matching is unaffected. ``evidence_role``/``chunk_type`` come from H1a when current, else
    ``None`` (treated as full-priority ``unknown``).
    """

    chunk: SourceChunk
    facet_index: int
    facet_label: str
    evidence_role: str | None = None
    chunk_type: str | None = None


@dataclass(frozen=True)
class FacetCoverage:
    label: str
    status: CoverageStatus
    retrieved_chunk_count: int
    verified_claim_count: int
    flagged_claim_count: int


def summarize_faceted(
    engine: Engine,
    *,
    question: str,
    plan: QueryPlan,
    generator: SummaryGenerator,
    model: EmbeddingModel,
    vector_store: VectorStore,
    verifier_config: VerificationConfig | None = None,
    support_scorer: SupportScorer | None = None,
    overview_requested: bool = False,
    on_stage: Callable[[str, str, int | None, bool], None] | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> SummaryPersistenceResult:
    """Broad, facet-aware synthesis. Same three-phase transaction discipline as ``summarize_scope``:
    no connection is held across the (slow) generation calls in Phase 2."""
    if on_stage is not None:
        on_stage("preparing_sources", "Preparing sources", None, False)
    with engine.begin() as conn:
        pool = _load_article_pool(conn)
        per_facet = _faceted_retrieval(conn, pool=pool, plan=plan, model=model, vector_store=vector_store)
        evidence_by_facet, retrieved_counts = _apply_hygiene_and_budget(conn, per_facet=per_facet, plan=plan)

    # Phase 2: per-facet generation (no connection held). One provider call per facet.
    if on_stage is not None:
        total_chunks = sum(len(items) for items in evidence_by_facet.values())
        on_stage("generating_synthesis", "Generating synthesis", total_chunks, True)
    facet_candidates: list[tuple[int, CandidateSummarySentence]] = []
    all_source_chunks: dict[int, SourceChunk] = {}
    for index, facet in enumerate(plan.facets):
        evidence = evidence_by_facet.get(index, [])
        if not evidence:
            continue
        for fe in evidence:
            all_source_chunks[fe.chunk.chunk_id] = fe.chunk
        scope_ref = {"query": facet.query, "facet_label": facet.label}
        try:
            produced = generator.generate(
                source_chunks=[fe.chunk for fe in evidence], scope_ref=scope_ref, engine=engine
            )
        except Exception:
            # A truncation or provider error on ONE facet must not sink the whole answer; that facet
            # simply contributes no claims and is reported by coverage (retrieved_unverified).
            produced = []
        for candidate in produced:
            facet_candidates.append((index, candidate))

    # Phase 3: ONE batched verify over ALL facets' claims, then verified-first assembly + coverage.
    candidates = [candidate for _, candidate in facet_candidates]
    with engine.begin() as conn:
        fresh_pool = _refresh_source_chunks(conn, list(all_source_chunks.values()))
        verifier = LocalCitationVerifier(
            model=model, vector_store=vector_store, config=verifier_config, support_scorer=support_scorer
        )
        if on_stage is not None:
            flat = sum(len(c.citations) for c in candidates)
            on_stage("verifying_citations", "Verifying citations", flat, False)
        verification_rows = _verify_candidates(conn, verifier=verifier, candidates=candidates, source_chunks=fresh_pool)
        if on_progress is not None:
            for i in range(1, len(candidates) + 1):
                on_progress(i, len(candidates), "Verifying claim")

        ordered_candidates, ordered_rows, coverage, responsiveness = _assemble(
            plan=plan,
            facet_candidates=facet_candidates,
            verification_rows=verification_rows,
            retrieved_counts=retrieved_counts,
        )
        extra_scope_ref = {
            "faceted": True,
            "question": question,
            "facets": [{"label": f.label, "query": f.query} for f in plan.facets],
            "coverage": [asdict(c) for c in coverage],
            # inc 582: per-claim responsiveness label (finding/descriptive/unknown), ordinal-aligned to
            # the persisted sentences below. Presentation only -- no verification status/score change.
            "responsiveness": responsiveness,
        }
        if on_stage is not None:
            on_stage("finalizing_result", "Finalizing result", len(ordered_candidates), False)
        result = _persist_verified_summary(
            conn,
            scope=SummaryScope(scope_type="query", query=question),
            candidates=ordered_candidates,
            verification_rows=ordered_rows,
            generated_by=generator.name,
            source_chunk_count=len(all_source_chunks),
            overview_requested=overview_requested,
            extra_scope_ref=extra_scope_ref,
        )
    return result


def _load_article_pool(conn: Connection) -> list[SourceChunk]:
    """Every live article-role chunk, repeated boilerplate excluded (the existing safe hard filter)."""
    live_papers = select(papers.c.id).where(papers.c.deleted_at.is_(None))
    stmt = (
        select(chunks)
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .where(chunks.c.paper_id.in_(live_papers), attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES))
        .order_by(chunks.c.id)
    )
    rows = [_source_chunk_from_row(row) for row in conn.execute(stmt).mappings()]
    return exclude_repeated_boilerplate_chunks(rows)


def _faceted_retrieval(
    conn: Connection,
    *,
    pool: list[SourceChunk],
    plan: QueryPlan,
    model: EmbeddingModel,
    vector_store: VectorStore,
) -> dict[int, list[SourceChunk]]:
    """Rank the pool per facet. ONE batched encode for all facet queries (LATENCY.md), then one
    vector search per facet over the shared candidate embedding set. Returns per-facet ranked chunks
    (already sliced to ``PER_FACET_TOP_K``)."""
    if not pool or not plan.facets:
        return {}
    current = current_chunk_embedding_ids(conn, ((chunk.chunk_id, chunk.chunk_version) for chunk in pool), model=model)
    missing = [chunk for chunk in pool if chunk.chunk_id not in current]
    if missing:
        embed_chunks(conn, model=model, vector_store=vector_store, chunk_ids=[c.chunk_id for c in missing])
        current.update(current_chunk_embedding_ids(conn, ((c.chunk_id, c.chunk_version) for c in missing), model=model))
    embedding_to_chunk = {embedding_id: chunk_id for chunk_id, embedding_id in current.items()}
    candidate_ids = set(embedding_to_chunk)
    source_by_id = {chunk.chunk_id: chunk for chunk in pool}
    facet_vectors = model.encode_texts([facet.query for facet in plan.facets])  # ONE batched encode
    out: dict[int, list[SourceChunk]] = {}
    for index, vector in enumerate(facet_vectors):
        hits = vector_store.search(
            conn,
            vector=vector,
            top_k=min(PER_FACET_TOP_K, len(candidate_ids) or 1),
            candidate_embedding_ids=candidate_ids,
        )
        out[index] = [
            source_by_id[embedding_to_chunk[hit.embedding_id]] for hit in hits if hit.embedding_id in embedding_to_chunk
        ]
    return out


def _apply_hygiene_and_budget(
    conn: Connection,
    *,
    per_facet: dict[int, list[SourceChunk]],
    plan: QueryPlan,
) -> tuple[dict[int, list[FacetEvidence]], dict[int, int]]:
    """Fetch current H1a roles ({} when absent/stale), then apply the pure hygiene + budget selection."""
    all_ids = [chunk.chunk_id for chunks_ in per_facet.values() for chunk in chunks_]
    roles = current_structure_roles(conn, all_ids)  # {} when chunk_structure is absent/stale -> no-op
    return _select_with_hygiene(per_facet=per_facet, facets=plan.facets, roles=roles)


def _select_with_hygiene(
    *,
    per_facet: dict[int, list[SourceChunk]],
    facets: tuple,
    roles: dict[int, tuple[str, str]],
) -> tuple[dict[int, list[FacetEvidence]], dict[int, int]]:
    """H1a deprioritization + dedup + per-paper/per-facet/global caps (pure -- ``roles`` injected).

    Deprioritization only: within each facet, full-priority (scientific/unknown/absent) chunks lead;
    definite bibliographic/structural chunks are kept but filled only after. A chunk retrieved by
    several facets is attributed once, to the facet where it ranked. Never deletes a chunk, so the
    seam is a safe no-op on an un-backfilled library (empty ``roles``).
    """
    selected_by_facet: dict[int, list[FacetEvidence]] = {}
    retrieved_counts: dict[int, int] = {}
    claimed_chunk_ids: set[int] = set()
    per_paper: Counter[int] = Counter()
    global_total = 0

    for index in range(len(facets)):
        ranked = per_facet.get(index, [])
        # Stable deprioritization: preserve relevance order within the two priority bands.
        full_priority = [c for c in ranked if (roles.get(c.chunk_id, (None, None))[1]) not in _DEPRIORITIZED_ROLES]
        demoted = [c for c in ranked if (roles.get(c.chunk_id, (None, None))[1]) in _DEPRIORITIZED_ROLES]
        ordered = full_priority + demoted

        facet_selected: list[FacetEvidence] = []
        facet = facets[index]
        for chunk in ordered:
            if global_total >= GLOBAL_CHUNK_CAP:
                break
            if chunk.chunk_id in claimed_chunk_ids:  # dedup across facets, attribute to first (best) facet
                continue
            if per_paper[chunk.paper_id] >= PER_PAPER_CAP:
                continue
            chunk_type, role = roles.get(chunk.chunk_id, (None, None))
            facet_selected.append(
                FacetEvidence(
                    chunk=chunk,
                    facet_index=index,
                    facet_label=facet.label,
                    evidence_role=role,
                    chunk_type=chunk_type,
                )
            )
            claimed_chunk_ids.add(chunk.chunk_id)
            per_paper[chunk.paper_id] += 1
            global_total += 1
        selected_by_facet[index] = facet_selected
        retrieved_counts[index] = len(facet_selected)
    return selected_by_facet, retrieved_counts


def _assemble(
    *,
    plan: QueryPlan,
    facet_candidates: list[tuple[int, CandidateSummarySentence]],
    verification_rows: list,
    retrieved_counts: dict[int, int],
):
    """Split each facet's claims into verified/flagged, cap them, order verified-first, build per-facet
    coverage, and attach a per-claim responsiveness label (inc 582 -- presentation only, does NOT
    reorder ordinals or touch any verification status/score). Returns
    (ordered_candidates, ordered_rows, coverage, responsiveness)."""
    by_facet: dict[int, list[tuple[CandidateSummarySentence, list]]] = defaultdict(list)
    for (facet_index, candidate), row in zip(facet_candidates, verification_rows, strict=True):
        by_facet[facet_index].append((candidate, row))

    verified_seq: list[tuple[CandidateSummarySentence, list]] = []
    flagged_seq: list[tuple[CandidateSummarySentence, list]] = []
    coverage: list[FacetCoverage] = []

    for index, facet in enumerate(plan.facets):
        items = by_facet.get(index, [])
        verified = [(c, r) for c, r in items if r and all(v.verified for v in r)]
        flagged = [(c, r) for c, r in items if not (r and all(v.verified for v in r))]
        # Keep the strongest-supported verified claims first.
        verified.sort(key=lambda cr: -min((v.support_confidence for v in cr[1]), default=0.0))
        verified = verified[:MAX_VERIFIED_PER_FACET]
        flagged = flagged[:MAX_FLAGGED_PER_FACET]
        verified_seq.extend(verified)
        flagged_seq.extend(flagged)

        retrieved = retrieved_counts.get(index, 0)
        if retrieved == 0:
            status: CoverageStatus = "no_evidence_retrieved"
        elif not verified:
            status = "retrieved_unverified"
        elif flagged:
            status = "partial"
        else:
            status = "supported"
        coverage.append(
            FacetCoverage(
                label=facet.label,
                status=status,
                retrieved_chunk_count=retrieved,
                verified_claim_count=len(verified),
                flagged_claim_count=len(flagged),
            )
        )

    ordered = verified_seq + flagged_seq  # verified first (main synthesis), flagged after (secondary)
    ordered_candidates = [c for c, _ in ordered]
    ordered_rows = [r for _, r in ordered]
    # inc 582: classify every claim's responsiveness AFTER final ordering, so the list index is exactly
    # the persisted ordinal. Claim-semantics only (evidence metadata is reserved). Never changes order,
    # status, or which claims are verified -- the UI uses it only to group verified claims into
    # findings vs study-context.
    responsiveness = [classify_responsiveness(candidate.text) for candidate in ordered_candidates]
    return ordered_candidates, ordered_rows, coverage, responsiveness
