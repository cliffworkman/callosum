"""Set critical review Tier-2 (backlog #12) — egress-gated cross-paper LLM candidates through the #13 verbatim bar.

The model *proposes* concerns that SPAN the set; each is admitted only if its ``anchor_quote`` is verbatim in SOME
set paper (``canonical_text_contains``) → recorded against that paper_id. ``related_paper_ids`` is the model's
FRAMING (its named indices, validated to the set), NOT a verified link — only the anchor quote is verified. The model
output is untrusted → defensive parse yielding ZERO drafts on any failure. The LLM call rides the ``complete()``
seam; egress consent is enforced by the endpoint (invariant #3)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.backend.llm.providers import complete
from app.backend.pdf_processing.extraction import canonical_text_contains
from integrations.gemini.critical_review import candidate_signature

_MAX_DRAFTS = 8
_MAX_CONCERN = 400
_MAX_QUOTE = 400
_MAX_SET_PROMPT_CHARS = 20000


@dataclass(frozen=True)
class SetCandidateDraft:
    """What the model proposes, pre-verification: a concern + the verbatim sentence it anchors to + the bracketed
    paper indices it claims to span."""

    concern: str
    anchor_quote: str
    related_indices: list[int] = field(default_factory=list)


def _anchor_paper(quote: str, set_papers: list[dict]) -> dict | None:
    for paper in set_papers:
        if canonical_text_contains(needle=quote, haystack=paper["text"]):
            return paper
    return None


def verify_set_candidates(
    drafts: list[SetCandidateDraft],
    *,
    set_papers: list[dict],
    stance_scorer: Any,
    rejected_signatures: frozenset[str] | set[str] = frozenset(),
) -> list[dict]:
    """The #13 bar for a set. KEEP a draft only if its ``anchor_quote`` is verbatim in SOME set paper → record that
    paper as the anchor; annotate with a local NLI stance + confidence + signature; DROP ungrounded (honest shortfall),
    previously-rejected, or duplicate. ``related_paper_ids`` = the model's named indices mapped to set paper ids
    (minus the anchor) — the model's framing, not a verified link. ``set_papers`` items: {index, paper_id, text}."""
    index_to_id = {int(p["index"]): int(p["paper_id"]) for p in set_papers}
    set_ids = set(index_to_id.values())
    out: list[dict] = []
    seen: set[str] = set()
    for draft in drafts:
        concern = (draft.concern or "").strip()
        quote = (draft.anchor_quote or "").strip()
        if not concern or not quote:
            continue
        anchor = _anchor_paper(quote, set_papers)
        if anchor is None:
            continue  # not grounded verbatim in any set paper → dropped (the honest shortfall)
        anchor_id = int(anchor["paper_id"])
        signature = candidate_signature(anchor_id, concern, quote)
        if signature in rejected_signatures or signature in seen:
            continue
        seen.add(signature)
        related = sorted(
            {index_to_id[i] for i in draft.related_indices if i in index_to_id and index_to_id[i] != anchor_id}
            & set_ids
        )
        stance = stance_scorer.classify_stance(sentence=concern, passage=quote)
        out.append(
            {
                "paper_id": anchor_id,
                "concern": concern[:_MAX_CONCERN],
                "anchor_quote": quote[:_MAX_QUOTE],
                "page": None,
                "stance": stance.label if stance else None,
                "confidence": stance.confidence if stance else None,
                "signature": signature,
                "related_paper_ids": related or None,
            }
        )
    return out


def _set_prompt(set_papers: list[dict]) -> str:
    budget = max(1, _MAX_SET_PROMPT_CHARS // max(1, len(set_papers)))
    blocks = [f"[{int(p['index'])}] {str(p['text'])[:budget]}" for p in set_papers]
    return (
        "You are a skeptical methodological reviewer reading several papers a user is citing together. List up to "
        f"{_MAX_DRAFTS} specific concerns that SPAN these papers — a shared limitation, or a claim in one contradicted "
        "by another — about the CLAIMS and METHODS ONLY, never about the authors as people. For each concern, quote "
        "the EXACT sentence (verbatim) it is anchored in, and give the bracketed paper numbers it relates to. Return "
        'ONLY a JSON array of {"concern": "...", "anchor_quote": "...", "related": [1, 2]} objects, no prose.\n\n'
        + "\n\n".join(blocks)
    )


class GeminiSetCriticalReviewGenerator:
    """The real Tier-2 set generator: prompt the configured LLM for cross-paper drafts; defensive parse."""

    def __init__(self, config: Any) -> None:
        self.config = config

    def propose(self, set_papers: list[dict]) -> list[SetCandidateDraft]:
        result = complete(self.config, _set_prompt(set_papers))
        return parse_set_drafts(str(getattr(result, "text", "") or ""))


def parse_set_drafts(raw: str) -> list[SetCandidateDraft]:
    """Defensive parse of the UNTRUSTED model response → SetCandidateDrafts. Malformed entries are ignored; any parse
    failure yields []."""
    data = _loads_lenient(raw)
    if not isinstance(data, list):
        return []
    out: list[SetCandidateDraft] = []
    for item in data[:_MAX_DRAFTS]:
        if not isinstance(item, dict):
            continue
        concern = str(item.get("concern") or "").strip()
        quote = str(item.get("anchor_quote") or "").strip()
        related = [int(x) for x in (item.get("related") or []) if isinstance(x, (int, float))]
        if concern and quote:
            out.append(SetCandidateDraft(concern[:_MAX_CONCERN], quote[:_MAX_QUOTE], related))
    return out


def _loads_lenient(raw: str) -> Any:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        start, end = text.find("["), text.rfind("]")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except (ValueError, TypeError):
                return None
    return None
