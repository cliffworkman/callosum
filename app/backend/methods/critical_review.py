"""Cross-corpus contradiction detector — the deterministic heart of the critical-review
"weak claim" signal (backlog #12, Tier 1).

Given a paper's candidate claim sentences, retrieve semantically-related passages from the
*rest of the corpus* via the local vector store and run the existing local NLI stance
classifier with each claim as the hypothesis. A claim is "contested" when another paper's
passage takes a confident CONTRAST stance toward it — surfacing disagreement the corpus
already contains, never resolving it (the THEORY contract: "surface disagreement, do not
smooth it"). The result is a signal, not a verdict: each contested claim carries its
contradicting passage (verbatim, with the other paper's id + page), the stance, and a
visible confidence, so the human appraises.

Fully local, no network, no LLM: this module imports NOTHING from any gemini/LLM module.
Every heavy dependency (embedding model, vector store, stance scorer, chunk resolver) is
INJECTED so the detector is pure and hermetically testable.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import or_, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import VectorHit, VectorStore
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.findings_repo import get_paper_findings
from app.backend.persistence.repository import get_chunks_for_paper, get_paper
from app.backend.persistence.schema import attachments, chunks, embeddings, open_science_signals, papers
from app.backend.summarization.verification import Stance, StanceScorer, classify_critical_review_stances

CRITICAL_REVIEW_VERSION = "1"
MAX_CRITIQUE_CLAIMS = 12
MAX_CRITIQUE_CLAIM_CHARS = 1000
CRITIQUE_TOP_K = 5
CRITIQUE_CONTRADICTION_THRESHOLD = 0.55

# A bibliography is not substantive contrasting prose -- excluded from both the Tier-1 retrieval
# corpus and the Tier-2 LLM haystack. Most chunks have no detected heading at all (section IS NULL),
# which must stay eligible -- `!=` alone would silently drop them under SQL's NULL comparison rules.
_EXCLUDED_EVIDENCE_SECTIONS = {"references"}


def _not_excluded_section_clause():
    return or_(chunks.c.section.is_(None), chunks.c.section.notin_(_EXCLUDED_EVIDENCE_SECTIONS))


@dataclass(frozen=True)
class ContestedClaim:
    claim: str  # a sentence from THIS paper
    passage: str  # the contradicting passage (verbatim, from another paper)
    other_paper_id: int
    page: int | None
    stance: str  # always "contrast" here
    confidence: float
    other_paper_title: str | None = None
    attachment_id: int | None = None
    claim_page: int | None = None


@dataclass(frozen=True)
class ChunkInfo:
    paper_id: int
    text: str
    page: int | None
    title: str | None = None
    attachment_id: int | None = None


@dataclass(frozen=True)
class ClaimSentence:
    text: str
    page: int | None
    coordinate_precision: str | None


@dataclass(frozen=True)
class ContestedSearchReport:
    contested_claims: list[ContestedClaim]
    claims_considered: int
    eligible_chunk_embeddings: int
    retrieved_passages: int
    classified_passages: int
    retrieval_status: str


@dataclass(frozen=True)
class ContestedSearchScope:
    """One independently scoped Critical Read retrieval request within a shared inference batch."""

    paper_id: int | None
    claim_sentences: list[str]
    other_chunk_ids: set[int]


@dataclass(frozen=True)
class _RetrievedClaimPair:
    scope_index: int
    claim_index: int
    hit_index: int
    claim: str
    chunk: ChunkInfo


def find_contested_claims(
    conn,
    paper_id,
    *,
    embed_model: EmbeddingModel,
    vector_store: VectorStore,
    stance_scorer: StanceScorer,
    resolve_chunk: Callable[[VectorHit], ChunkInfo | None],
    claim_sentences: list[str],
    other_chunk_ids: set[int],
    contradiction_threshold: float = 0.55,
    top_k: int = 5,
    max_claims: int = 12,
    on_stage: Callable[[str, str, int | None], None] | None = None,
) -> list[ContestedClaim]:
    """Return the claims from this paper that another paper in the corpus contradicts.

    For each of up to ``max_claims`` ``claim_sentences``: embed it, retrieve the ``top_k``
    nearest passages from ``other_chunk_ids`` (the *other* papers' chunk-embeddings), resolve
    each hit to a :class:`ChunkInfo`, and classify the passage's stance toward the claim. A
    claim is kept when some passage takes a CONTRAST stance at or above
    ``contradiction_threshold``; only the single highest-confidence contradicter is recorded
    (claims with none are skipped). Support/mention/None stances never surface a claim.
    """
    return search_contested_claims(
        conn,
        paper_id,
        embed_model=embed_model,
        vector_store=vector_store,
        stance_scorer=stance_scorer,
        resolve_chunk=resolve_chunk,
        claim_sentences=claim_sentences,
        other_chunk_ids=other_chunk_ids,
        contradiction_threshold=contradiction_threshold,
        top_k=top_k,
        max_claims=max_claims,
        on_stage=on_stage,
    ).contested_claims


def search_contested_claims(
    conn,
    paper_id,
    *,
    embed_model: EmbeddingModel,
    vector_store: VectorStore,
    stance_scorer: StanceScorer,
    resolve_chunk: Callable[[VectorHit], ChunkInfo | None],
    claim_sentences: list[str],
    other_chunk_ids: set[int],
    contradiction_threshold: float = CRITIQUE_CONTRADICTION_THRESHOLD,
    top_k: int = CRITIQUE_TOP_K,
    max_claims: int = MAX_CRITIQUE_CLAIMS,
    on_stage: Callable[[str, str, int | None], None] | None = None,
) -> ContestedSearchReport:
    """Detailed form of :func:`find_contested_claims` with bounded coverage accounting.

    The report distinguishes an empty claim/corpus scope from unavailable local NLI. Query embeddings remain
    transient: this function only calls ``encode_texts`` and ``search``; it never adds an embedding.
    ``paper_id`` may be ``None`` for an unpublished WIP because the eligible-id set already defines the corpus.
    """
    [report] = search_contested_claim_scopes(
        conn,
        scopes=[ContestedSearchScope(paper_id, claim_sentences, other_chunk_ids)],
        embed_model=embed_model,
        vector_store=vector_store,
        stance_scorer=stance_scorer,
        resolve_chunk=resolve_chunk,
        contradiction_threshold=contradiction_threshold,
        top_k=top_k,
        max_claims=max_claims,
        on_stage=on_stage,
    )
    return report


def search_contested_claim_scopes(
    conn,
    *,
    scopes: list[ContestedSearchScope],
    embed_model: EmbeddingModel,
    vector_store: VectorStore,
    stance_scorer: StanceScorer,
    resolve_chunk: Callable[[VectorHit], ChunkInfo | None],
    contradiction_threshold: float = CRITIQUE_CONTRADICTION_THRESHOLD,
    top_k: int = CRITIQUE_TOP_K,
    max_claims: int = MAX_CRITIQUE_CLAIMS,
    on_stage: Callable[[str, str, int | None], None] | None = None,
) -> list[ContestedSearchReport]:
    """Search one or more scopes with one ordered embedding batch and one logical NLI inference phase.

    Retrieval remains per claim because each query has its own candidate-id scope and ``top_k`` result. Explicit
    scope/claim/hit indices carry every NLI result back to the same evidence item the sequential implementation
    evaluated. The production scorer may group multi-batch inputs by effective token length, but reconstructs every
    stance into this exact pair order before the threshold/evidence loop below; no deduplication or unordered mapping
    occurs.
    """
    bounded_claims = [scope.claim_sentences[:max_claims] for scope in scopes]
    active_claims = [
        (scope_index, claim_index, claim)
        for scope_index, (scope, claims) in enumerate(zip(scopes, bounded_claims, strict=True))
        if scope.other_chunk_ids
        for claim_index, claim in enumerate(claims)
    ]
    if on_stage is not None:
        on_stage("embedding_claims", "Embedding claims", len(active_claims))
    vectors = embed_model.encode_texts([claim for _, _, claim in active_claims]) if active_claims else []

    retrieved_counts = [0] * len(scopes)
    pairs: list[_RetrievedClaimPair] = []
    for (scope_index, claim_index, claim), vector in zip(active_claims, vectors, strict=True):
        scope = scopes[scope_index]
        hits = vector_store.search(
            conn,
            vector=vector,
            top_k=top_k,
            candidate_embedding_ids=scope.other_chunk_ids,
        )
        for hit_index, hit in enumerate(hits):
            # The SQL-selected eligible set remains authoritative even if a vector backend returns an invalid id.
            if hit.embedding_id not in scope.other_chunk_ids:
                continue
            chunk = resolve_chunk(hit)
            if chunk is None:
                continue
            retrieved_counts[scope_index] += 1
            pairs.append(_RetrievedClaimPair(scope_index, claim_index, hit_index, claim, chunk))

    if on_stage is not None:
        on_stage("evaluating_evidence", "Evaluating evidence", len(pairs))
    stances = classify_critical_review_stances(stance_scorer, [(pair.claim, pair.chunk.text) for pair in pairs])
    classified_counts = [0] * len(scopes)
    best_by_claim: list[list[ContestedClaim | None]] = [[None] * len(claims) for claims in bounded_claims]
    for pair, stance in zip(pairs, stances, strict=True):
        if stance is None:
            continue
        classified_counts[pair.scope_index] += 1
        candidate = _contested_candidate(pair, stance, contradiction_threshold)
        current = best_by_claim[pair.scope_index][pair.claim_index]
        if candidate is not None and (current is None or candidate.confidence > current.confidence):
            best_by_claim[pair.scope_index][pair.claim_index] = candidate

    reports: list[ContestedSearchReport] = []
    for scope_index, (scope, claims) in enumerate(zip(scopes, bounded_claims, strict=True)):
        retrieved = retrieved_counts[scope_index]
        classified = classified_counts[scope_index]
        status = (
            "no-claims"
            if not claims
            else "empty-library-corpus"
            if not scope.other_chunk_ids
            else "complete"
            if classified
            else "nli-unavailable"
            if retrieved
            else "no-retrievable-passages"
        )
        reports.append(
            ContestedSearchReport(
                [candidate for candidate in best_by_claim[scope_index] if candidate is not None],
                len(claims),
                len(scope.other_chunk_ids),
                retrieved,
                classified,
                status,
            )
        )
    return reports


def _contested_candidate(
    pair: _RetrievedClaimPair, stance: Stance, contradiction_threshold: float
) -> ContestedClaim | None:
    if stance.label != "contrast" or stance.confidence < contradiction_threshold:
        return None
    return ContestedClaim(
        claim=pair.claim,
        passage=pair.chunk.text,
        other_paper_id=pair.chunk.paper_id,
        page=pair.chunk.page,
        stance="contrast",
        confidence=stance.confidence,
        other_paper_title=pair.chunk.title,
        attachment_id=pair.chunk.attachment_id,
    )


# --- Tier 1: the deterministic scrutiny backbone (compose signals that already exist) ---------------------------


@dataclass(frozen=True)
class ScrutinyBackbone:
    """The deterministic Tier-1 composition for one paper: the paper's ALREADY-STORED method signals that apply +
    a citation signal (when locally computable) + the passed-in cross-corpus contested claims. It gathers what the
    local producers already persisted and INVENTS no new judgement (PRINCIPLES #4 — the deterministic substrate is
    the source of truth). Empty lists mean "these checks surfaced nothing" — the honest null result, NOT "this
    paper is clean" (silence is not a certificate; PRINCIPLES #6)."""

    method_signals: list[dict]  # each {"kind": str, "label": str, "detail": str | None, "notice_url": str | None}
    citation_signal: dict | None
    contested_claims: list[ContestedClaim]  # computed by the caller (find_contested_claims), passed in


# Human labels for the known stored-signal kinds; an unknown kind falls back to its humanized name.
_SIGNAL_LABELS = {
    "statcheck": "Statistical consistency (statcheck)",
    "retraction": "Retraction status",
    "transparency": "Transparency disclosure",
}

# A check RESULT emitted when the auditor's PRECONDITION is not met — the check does not apply to this paper, so it
# contributes nothing to the scrutiny surface (spec Tier 1: "only the auditors that apply to this paper"). Every
# other stored status — including "consistent"/"none"/"not-detected" — is surfaced verbatim (silence≠certificate).
_NOT_APPLICABLE_STATUSES = {"not-applicable"}


def _humanize(text: str | None) -> str:
    return str(text or "").replace("_", " ").strip()


def _signal_label(kind: str, source: str | None) -> str:
    base = _SIGNAL_LABELS.get(kind) or (_humanize(kind).capitalize() or kind)
    if kind == "transparency" and source:
        return f"{base}: {_humanize(source)}"
    return base


def _open_science_detail(kind: str, status: str, evidence_snippet) -> str:
    """A human detail for a stored ``open_science_signals`` row — the status, verbatim, plus statcheck's stored
    counts when present. Never re-runs the auditor; renders only what was persisted."""
    if kind == "statcheck" and evidence_snippet:
        try:
            counts = json.loads(evidence_snippet)
            return (
                f"{status}: {int(counts.get('checked', 0))} checked, "
                f"{int(counts.get('inconsistent', 0))} inconsistent, "
                f"{int(counts.get('decision_errors', 0))} decision errors"
            )
        except (ValueError, TypeError):
            return status
    return status


def _finding_detail(payload) -> str | None:
    """A human detail for a stored ``paper_findings`` FACT payload — the producer's own description when it carries
    one, else a compact composition of the retraction-style status/nature/reason fields."""
    if not isinstance(payload, dict):
        return None
    for key in ("desc", "summary", "label", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    parts = [str(payload[k]) for k in ("status", "nature", "reason") if payload.get(k)]
    return " — ".join(parts) if parts else None


def _stored_method_signals(conn, paper_id) -> list[dict]:
    """Gather the paper's already-stored deterministic signals into the flat {kind, label, detail, notice_url}
    shape: the ``open_science_signals`` check-status rows (statcheck / retraction / transparency) + the
    ``paper_findings`` FACT rows the producers persist. READS ONLY — runs no auditor, invents no judgement.
    Precondition-not-met ("not-applicable") rows are dropped; every other stored result is surfaced.
    ``notice_url`` (retraction facts only, e.g. a doi.org registry link) is passed through verbatim so the UI can
    offer the same evidence link the retired left-pane Review accordion's FactMark used to (PRINCIPLES: every
    claim carries its evidence) — never re-derived here."""
    signals: list[dict] = []
    status_rows = conn.execute(
        select(
            open_science_signals.c.signal_type,
            open_science_signals.c.source,
            open_science_signals.c.status,
            open_science_signals.c.evidence_snippet,
        )
        .where(open_science_signals.c.paper_id == paper_id)
        .order_by(open_science_signals.c.id)
    ).mappings()
    for row in status_rows:
        if row["status"] in _NOT_APPLICABLE_STATUSES:
            continue
        signals.append(
            {
                "kind": row["signal_type"],
                "label": _signal_label(row["signal_type"], row["source"]),
                "detail": _open_science_detail(row["signal_type"], row["status"], row["evidence_snippet"]),
                "notice_url": None,
            }
        )
    for fact in get_paper_findings(conn, paper_id)["facts"]:
        payload = fact["payload"] if isinstance(fact["payload"], dict) else {}
        signals.append(
            {
                "kind": fact["source"],
                "label": _signal_label(fact["source"], None),
                "detail": _finding_detail(fact["payload"]),
                "notice_url": payload.get("notice_url"),
            }
        )
    return signals


def build_scrutiny_backbone(conn, paper_id, *, contested_claims: list[ContestedClaim]) -> ScrutinyBackbone:
    """Compose the deterministic Tier-1 scrutiny surface for ``paper_id`` from what is ALREADY stored + the
    passed-in ``contested_claims`` (computed by the caller via :func:`find_contested_claims`). No auditor is run
    here and no external call is made (Tier 1 is fully local). ``citation_signal`` is ``None``: the
    citation-concentration / overlooked-work lens (inc 229/230) is network-based (OpenAlex) and is not persisted
    per-paper, so there is no local read to summarise — surfacing it would need egress, which Tier 1 forbids.
    Empty lists are the honest "nothing surfaced by these checks", not a clean bill of health."""
    return ScrutinyBackbone(
        method_signals=_stored_method_signals(conn, paper_id),
        citation_signal=None,
        contested_claims=list(contested_claims),
    )


# --- The real DB-backed retrieval helpers the router feeds into find_contested_claims -----------------------------

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_BOUNDARY.split(text.strip()) if part.strip()]


def extract_claim_sentences(conn, paper_id, *, max_claims: int = 12) -> list[str]:
    """The paper's candidate claim sentences — a bounded, deterministic heuristic (no LLM). Splits the paper's
    abstract into sentences; if there is no abstract, falls back to the paper's first stored chunk. Returns up to
    ``max_claims`` sentences (possibly empty — the honest "no claim text available for this paper")."""
    paper = get_paper(conn, paper_id)
    text = str(paper["abstract"] or "").strip()
    if not text:
        first_chunks = get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES, limit=1)
        if first_chunks:
            text = str(first_chunks[0]["text"] or "").strip()
    if not text:
        return []
    return _split_sentences(text)[:max_claims]


def extract_block_claim_sentences(blocks: list, *, has_real_pages: bool) -> list[ClaimSentence]:
    """Bounded claim candidates from an exact WIP content snapshot.

    This is deliberately a transparent sentence heuristic, not claim adjudication. Overlong fragments are skipped
    rather than truncated so every retained claim remains verbatim within the normalized extracted block. Duplicate
    sentences are retained once. Non-PDF extractors' synthetic pages are never presented as source coordinates.
    """
    claims: list[ClaimSentence] = []
    seen: set[str] = set()
    for block in blocks:
        page = getattr(block, "page_start", None) if has_real_pages else None
        for sentence in _split_sentences(str(getattr(block, "text", "") or "")):
            if not 20 <= len(sentence) <= MAX_CRITIQUE_CLAIM_CHARS or sentence in seen:
                continue
            seen.add(sentence)
            claims.append(
                ClaimSentence(
                    text=sentence,
                    page=int(page) if page is not None else None,
                    coordinate_precision="region" if page is not None else None,
                )
            )
            if len(claims) >= MAX_CRITIQUE_CLAIMS:
                return claims
    return claims


def paper_full_text(conn, paper_id) -> str:
    """The paper's full extracted text (abstract + every stored chunk, in order) — the verbatim haystack the
    Tier-2 #13 bar (``canonical_text_contains``) checks a candidate's anchor_quote against. Local, no LLM."""
    paper = get_paper(conn, paper_id)
    parts = [str(paper["abstract"] or "").strip()]
    parts += [
        str(row["text"] or "")
        for row in get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES)
        if row["section"] not in _EXCLUDED_EVIDENCE_SECTIONS
    ]
    return "\n".join(part for part in parts if part)


def other_paper_chunk_embedding_ids(
    conn,
    paper_id,
    *,
    model_name: str,
    model_version: str,
    normalization: str,
) -> set[int]:
    """The ``embeddings.id`` of every matching-model chunk-embedding belonging to a paper OTHER than ``paper_id``,
    excluding soft-deleted papers — the candidate set the contradiction detector retrieves the *rest of the corpus*
    from. Joins ``embeddings.target_id`` → ``chunks.id`` (target_type='chunk') → ``papers.id`` (deleted_at IS NULL).
    Model/version/normalization matching avoids comparing unlike vector spaces (mirrors
    ``library_article_chunk_embedding_ids``'s own filter, just scoped to "other papers" instead of "all papers")."""
    corpus = (
        embeddings.join(chunks, embeddings.c.target_id == chunks.c.id)
        .join(attachments, attachments.c.id == chunks.c.attachment_id)
        .join(papers, papers.c.id == chunks.c.paper_id)
    )
    rows = conn.execute(
        select(embeddings.c.id)
        .select_from(corpus)
        .where(
            embeddings.c.target_type == "chunk",
            embeddings.c.model_name == model_name,
            embeddings.c.model_version == model_version,
            embeddings.c.normalization == normalization,
            chunks.c.paper_id != paper_id,
            papers.c.deleted_at.is_(None),
            attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES),
            _not_excluded_section_clause(),
        )
    )
    return {int(row[0]) for row in rows}


def library_article_chunk_embedding_ids(
    conn,
    *,
    model_name: str,
    model_version: str,
    normalization: str,
) -> set[int]:
    """Matching-model article-fulltext chunk embeddings from live Library papers.

    WIP query vectors are transient and have no ``paper_id`` to exclude. Model/version/normalization matching avoids
    comparing unlike vector spaces; document-role and soft-delete predicates keep registration, supplement, and
    removed-paper text out of the eligible evidence corpus.
    """
    corpus = (
        embeddings.join(chunks, embeddings.c.target_id == chunks.c.id)
        .join(attachments, attachments.c.id == chunks.c.attachment_id)
        .join(papers, papers.c.id == chunks.c.paper_id)
    )
    rows = conn.execute(
        select(embeddings.c.id)
        .select_from(corpus)
        .where(
            embeddings.c.target_type == "chunk",
            embeddings.c.model_name == model_name,
            embeddings.c.model_version == model_version,
            embeddings.c.normalization == normalization,
            papers.c.deleted_at.is_(None),
            attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES),
            _not_excluded_section_clause(),
        )
    )
    return {int(row[0]) for row in rows}


def make_chunk_resolver(conn) -> Callable[[VectorHit], ChunkInfo | None]:
    """Return a resolver mapping a retrieval ``VectorHit`` → the :class:`ChunkInfo` (paper_id, text, page) of its
    chunk, or ``None`` when the hit's embedding is not a resolvable chunk-embedding. Mirrors the verifier's
    ``embeddings`` → ``chunks`` join (verification.py); ``page`` is the chunk's ``page_start``."""

    def resolve(hit: VectorHit) -> ChunkInfo | None:
        row = (
            conn.execute(
                select(
                    chunks.c.paper_id,
                    chunks.c.attachment_id,
                    chunks.c.text,
                    chunks.c.page_start,
                    papers.c.title,
                )
                .select_from(
                    embeddings.join(chunks, embeddings.c.target_id == chunks.c.id).join(
                        papers, papers.c.id == chunks.c.paper_id
                    )
                )
                .where(embeddings.c.id == hit.embedding_id, embeddings.c.target_type == "chunk")
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        page = row["page_start"]
        return ChunkInfo(
            paper_id=int(row["paper_id"]),
            text=str(row["text"]),
            page=int(page) if page is not None else None,
            title=str(row["title"] or "") or None,
            attachment_id=int(row["attachment_id"]),
        )

    return resolve
