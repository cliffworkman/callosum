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

from sqlalchemy import select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import VectorHit, VectorStore
from app.backend.persistence.findings_repo import get_paper_findings
from app.backend.persistence.repository import get_chunks_for_paper, get_paper
from app.backend.persistence.schema import chunks, embeddings, open_science_signals, papers
from app.backend.summarization.verification import StanceScorer


@dataclass(frozen=True)
class ContestedClaim:
    claim: str  # a sentence from THIS paper
    passage: str  # the contradicting passage (verbatim, from another paper)
    other_paper_id: int
    page: int | None
    stance: str  # always "contrast" here
    confidence: float


@dataclass(frozen=True)
class ChunkInfo:
    paper_id: int
    text: str
    page: int | None


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
) -> list[ContestedClaim]:
    """Return the claims from this paper that another paper in the corpus contradicts.

    For each of up to ``max_claims`` ``claim_sentences``: embed it, retrieve the ``top_k``
    nearest passages from ``other_chunk_ids`` (the *other* papers' chunk-embeddings), resolve
    each hit to a :class:`ChunkInfo`, and classify the passage's stance toward the claim. A
    claim is kept when some passage takes a CONTRAST stance at or above
    ``contradiction_threshold``; only the single highest-confidence contradicter is recorded
    (claims with none are skipped). Support/mention/None stances never surface a claim.
    """
    if not claim_sentences or not other_chunk_ids:
        return []

    contested: list[ContestedClaim] = []
    for claim in claim_sentences[:max_claims]:
        vector = embed_model.encode_texts([claim])[0]
        hits = vector_store.search(
            conn,
            vector=vector,
            top_k=top_k,
            candidate_embedding_ids=other_chunk_ids,
        )
        best: ContestedClaim | None = None
        for hit in hits:
            chunk = resolve_chunk(hit)
            if chunk is None:
                continue
            stance = stance_scorer.classify_stance(sentence=claim, passage=chunk.text)
            if stance is None or stance.label != "contrast":
                continue
            if stance.confidence < contradiction_threshold:
                continue
            if best is None or stance.confidence > best.confidence:
                best = ContestedClaim(
                    claim=claim,
                    passage=chunk.text,
                    other_paper_id=chunk.paper_id,
                    page=chunk.page,
                    stance="contrast",
                    confidence=stance.confidence,
                )
        if best is not None:
            contested.append(best)
    return contested


# --- Tier 1: the deterministic scrutiny backbone (compose signals that already exist) ---------------------------


@dataclass(frozen=True)
class ScrutinyBackbone:
    """The deterministic Tier-1 composition for one paper: the paper's ALREADY-STORED method signals that apply +
    a citation signal (when locally computable) + the passed-in cross-corpus contested claims. It gathers what the
    local producers already persisted and INVENTS no new judgement (PRINCIPLES #4 — the deterministic substrate is
    the source of truth). Empty lists mean "these checks surfaced nothing" — the honest null result, NOT "this
    paper is clean" (silence is not a certificate; PRINCIPLES #6)."""

    method_signals: list[dict]  # each {"kind": str, "label": str, "detail": str | None}
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
    """Gather the paper's already-stored deterministic signals into the flat {kind, label, detail} shape: the
    ``open_science_signals`` check-status rows (statcheck / retraction / transparency) + the ``paper_findings``
    FACT rows the producers persist. READS ONLY — runs no auditor, invents no judgement. Precondition-not-met
    ("not-applicable") rows are dropped; every other stored result is surfaced."""
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
            }
        )
    for fact in get_paper_findings(conn, paper_id)["facts"]:
        signals.append(
            {
                "kind": fact["source"],
                "label": _signal_label(fact["source"], None),
                "detail": _finding_detail(fact["payload"]),
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
        first_chunks = get_chunks_for_paper(conn, paper_id, limit=1)
        if first_chunks:
            text = str(first_chunks[0]["text"] or "").strip()
    if not text:
        return []
    return _split_sentences(text)[:max_claims]


def other_paper_chunk_embedding_ids(conn, paper_id) -> set[int]:
    """The ``embeddings.id`` of every chunk-embedding belonging to a paper OTHER than ``paper_id``, excluding
    soft-deleted papers — the candidate set the contradiction detector retrieves the *rest of the corpus* from.
    Joins ``embeddings.target_id`` → ``chunks.id`` (target_type='chunk') → ``papers.id`` (deleted_at IS NULL)."""
    corpus = embeddings.join(chunks, embeddings.c.target_id == chunks.c.id).join(
        papers, papers.c.id == chunks.c.paper_id
    )
    rows = conn.execute(
        select(embeddings.c.id)
        .select_from(corpus)
        .where(
            embeddings.c.target_type == "chunk",
            chunks.c.paper_id != paper_id,
            papers.c.deleted_at.is_(None),
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
                select(chunks.c.paper_id, chunks.c.text, chunks.c.page_start)
                .select_from(embeddings.join(chunks, embeddings.c.target_id == chunks.c.id))
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
        )

    return resolve
