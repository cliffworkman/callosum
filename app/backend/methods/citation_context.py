"""Citation-context classifier — "how this paper is cited" (B4 SP1, inc 232; the scite analogue).

Given the citing sentences a paper received (from Semantic Scholar) + the focal paper's own claim, classify each
citation's stance **locally** with our NLI (support / contrast / mention) and aggregate honest **counts**. Pure +
local + no-I/O (takes already-fetched ``CitingContext``s + an injected ``StanceScorer``).

Honesty (the Principles gate — a claim/signal feature): each citation carries its **real citing sentence** as the
evidence (#4); the stance is a **labeled signal, not a verdict** (#2 — an NLI over the citing sentence vs the focal
claim, shown with its confidence); the aggregate is **counts, never a composite "score"** (#7); a sentence-less or
unclassifiable citation is **counted as such, never guessed** (#6). A "contrast" label describes the rhetorical
relationship *in that shown sentence*, never an accusation of an author (A-A).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.backend.summarization.verification import StanceScorer, classify_stances

CONTEXT_MAX = 1000  # chars of joined citing sentences fed to the NLI per citation (bound; rule #4)
MAX_ITEMS = 500  # cap on citations classified per run (matches the S2 fetch cap; rule #4)
STANCE_KEYS = ("support", "contrast", "mention")


@dataclass(frozen=True)
class ClassifiedCitation:
    citing_title: str | None
    citing_year: int | None
    citing_authors: list[str]
    citing_doi: str | None
    sentence: str  # the citing sentence(s) shown as the evidence ("" if S2 had none)
    stance: str | None  # support | contrast | mention — None when unclassifiable (never guessed)
    confidence: float | None
    is_influential: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "citing_title": self.citing_title,
            "citing_year": self.citing_year,
            "citing_authors": self.citing_authors,
            "citing_doi": self.citing_doi,
            "sentence": self.sentence,
            "stance": self.stance,
            "confidence": self.confidence,
            "is_influential": self.is_influential,
        }


@dataclass(frozen=True)
class CitationContextReport:
    total_citations: int  # citing papers Semantic Scholar returned (capped)
    with_context: int  # how many had a citing sentence we could read
    classified: int  # how many got a stance (≤ with_context)
    counts: dict[str, int]  # {"support": .., "contrast": .., "mention": ..} — counts, NEVER a composite score
    items: list[ClassifiedCitation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_citations": self.total_citations,
            "with_context": self.with_context,
            "classified": self.classified,
            "counts": self.counts,
            "items": [i.to_dict() for i in self.items],
        }


def classify_citation_contexts(
    *,
    contexts: list[Any],
    focal_claim: str,
    stance_scorer: StanceScorer | None,
    max_items: int = MAX_ITEMS,
) -> CitationContextReport:
    """Classify each citing sentence's stance toward ``focal_claim`` (the focal paper's abstract, else its title) via
    the local NLI. Counts by stance; keeps every citation's evidence. No composite score; unclassifiable → counted."""
    claim = (focal_claim or "").strip()
    counts = {k: 0 for k in STANCE_KEYS}
    with_context = 0

    rows: list[dict[str, Any]] = []
    for ctx in contexts[:max_items]:
        sentences = list(getattr(ctx, "sentences", []) or [])
        sentence = " ".join(s.strip() for s in sentences if s.strip()).strip()[:CONTEXT_MAX]
        # The hypothesis is the *cited* paper's own claim per-item (SP2, references) if present, else the constant
        # focal-paper claim (SP1, citations). The citing sentence is always the premise/evidence.
        hypothesis = (getattr(ctx, "claim", None) or claim).strip()
        if sentence:
            with_context += 1
        rows.append({"ctx": ctx, "sentence": sentence, "hypothesis": hypothesis})

    # Batched: one NLI call for every scoreable citation instead of one per citation (LATENCY.md).
    scoreable_indices = [i for i, row in enumerate(rows) if row["sentence"] and row["hypothesis"]]
    results_by_index: dict[int, Any] = {}
    if stance_scorer is not None and scoreable_indices:
        pairs = [(rows[i]["hypothesis"], rows[i]["sentence"]) for i in scoreable_indices]
        stances = classify_stances(stance_scorer, pairs)
        results_by_index = dict(zip(scoreable_indices, stances, strict=True))

    items: list[ClassifiedCitation] = []
    for i, row in enumerate(rows):
        ctx = row["ctx"]
        sentence = row["sentence"]
        stance: str | None = None
        confidence: float | None = None
        result = results_by_index.get(i)
        if result is not None and result.label in counts:
            stance = result.label
            confidence = round(float(result.confidence), 3)
            counts[stance] += 1
        items.append(
            ClassifiedCitation(
                citing_title=getattr(ctx, "citing_title", None),
                citing_year=getattr(ctx, "citing_year", None),
                citing_authors=list(getattr(ctx, "citing_authors", []) or []),
                citing_doi=getattr(ctx, "citing_doi", None),
                sentence=sentence,
                stance=stance,
                confidence=confidence,
                is_influential=bool(getattr(ctx, "is_influential", False)),
            )
        )
    return CitationContextReport(
        total_citations=len(contexts),
        with_context=with_context,
        classified=sum(counts.values()),
        counts=counts,
        items=items,
    )
