"""Critical-review Tier-2 — egress-gated LLM candidate critiques through the #13 verbatim bar (backlog #12 t5).

The model *proposes* concerns as CANDIDATES; each is admitted only if its ``anchor_quote`` is found **verbatim**
in the paper (``canonical_text_contains``) — the #13 auditability bar — then annotated with a local NLI stance +
confidence + a stable signature, and dropped if it was previously rejected. Ungrounded drafts are dropped (honest
shortfall). The model output is **untrusted** (a user may point the roster at an arbitrary endpoint) → parsing is
defensive and yields ZERO drafts on any failure, never a crash. The LLM call rides the existing ``complete()``
seam; egress consent is enforced by the endpoint (invariant #3).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.backend.llm.providers import complete
from app.backend.pdf_processing.extraction import canonical_text_contains
from app.backend.summarization.verification import classify_stances

_MAX_DRAFTS = 8
_MAX_CONCERN = 400
_MAX_QUOTE = 400
_MAX_PROMPT_CHARS = 20000


@dataclass(frozen=True)
class CandidateDraft:
    """What the model proposes, pre-verification: a concern + the sentence it claims to be about."""

    concern: str
    anchor_quote: str


class CriticalReviewCandidateGenerator(Protocol):
    def propose(self, *, paper_text: str) -> list[CandidateDraft]: ...


def candidate_signature(paper_id: int, concern: str, anchor_quote: str) -> str:
    """A stable per-paper hash of (normalized concern + quote) so a rejected candidate is never re-proposed."""
    norm = lambda s: re.sub(r"\s+", " ", (s or "").strip().lower())  # noqa: E731
    raw = f"{int(paper_id)}|{norm(concern)}|{norm(anchor_quote)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()  # 64 hex chars ≤ String(80)


def verify_candidates(
    drafts: list[CandidateDraft],
    *,
    paper_id: int,
    paper_text: str,
    stance_scorer: Any,
    rejected_signatures: frozenset[str] | set[str] = frozenset(),
) -> list[dict]:
    """The #13 bar. KEEP a draft only if its ``anchor_quote`` is verbatim in ``paper_text``; annotate it with a
    local NLI stance + confidence + signature; DROP an ungrounded draft (honest shortfall) or a previously-rejected
    (or duplicate) signature. Returns repo-shaped dicts (concern, anchor_quote, page, stance, confidence, signature).
    """
    eligible: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for draft in drafts:
        concern = (draft.concern or "").strip()
        quote = (draft.anchor_quote or "").strip()
        if not concern or not quote:
            continue
        if not canonical_text_contains(needle=quote, haystack=paper_text):
            continue  # not grounded verbatim in the source → dropped (the honest shortfall)
        signature = candidate_signature(paper_id, concern, quote)
        if signature in rejected_signatures or signature in seen:
            continue
        seen.add(signature)
        eligible.append((concern, quote, signature))

    stances = classify_stances(stance_scorer, [(concern, quote) for concern, quote, _ in eligible])
    out: list[dict] = []
    for (concern, quote, signature), stance in zip(eligible, stances, strict=True):
        out.append(
            {
                "concern": concern[:_MAX_CONCERN],
                "anchor_quote": quote[:_MAX_QUOTE],
                "page": None,
                "stance": stance.label if stance else None,
                "confidence": stance.confidence if stance else None,
                "signature": signature,
            }
        )
    return out


class GeminiCriticalReviewGenerator:
    """The real Tier-2 generator: prompt the configured LLM for {concern, anchor_quote} pairs; defensive parse."""

    def __init__(self, config: Any) -> None:
        self.config = config

    def propose(self, *, paper_text: str) -> list[CandidateDraft]:
        result = complete(self.config, _prompt(paper_text))
        return parse_drafts(str(getattr(result, "text", "") or ""))


def _prompt(paper_text: str) -> str:
    return (
        "You are a skeptical methodological reviewer. Read the paper text and list up to "
        f"{_MAX_DRAFTS} specific concerns a careful reader should CHECK — about the CLAIMS and METHODS ONLY, "
        "never about the authors as people. For each concern, quote the EXACT sentence from the paper it refers "
        'to, copied verbatim. Return ONLY a JSON array of {"concern": "...", "anchor_quote": "..."} objects, no '
        "prose.\n\nPaper text:\n" + paper_text[:_MAX_PROMPT_CHARS]
    )


def parse_drafts(raw: str) -> list[CandidateDraft]:
    """Defensive parse of the UNTRUSTED model response → CandidateDrafts. Any malformed entry is ignored; any
    parse failure yields []."""
    data = _loads_lenient(raw)
    if not isinstance(data, list):
        return []
    out: list[CandidateDraft] = []
    for item in data[:_MAX_DRAFTS]:
        if not isinstance(item, dict):
            continue
        concern = str(item.get("concern") or "").strip()
        quote = str(item.get("anchor_quote") or "").strip()
        if concern and quote:
            out.append(CandidateDraft(concern=concern[:_MAX_CONCERN], anchor_quote=quote[:_MAX_QUOTE]))
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
