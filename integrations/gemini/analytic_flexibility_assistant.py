"""Propose analytic-flexibility decision-point candidates from methods-section text (backlog #37).

Mirrors integrations/gemini/extraction_assistant.py's shape exactly: the model PROPOSES structured
candidates -- never a location, page, or confidence -- and every quote is anchored afterward,
deterministically and locally, by app.backend.pdf_processing.quote_matching.anchor_quote (Task 1), never
by the model. AI funnel, human filter (PRINCIPLES.md): a candidate is not a finding until a human reviews
it against its independently-anchored source text.

The model response is UNTRUSTED (a user can point the roster at an arbitrary endpoint) -> parse_proposals
is defensive: it tolerates markdown fences + surrounding junk, drops malformed entries and any category
outside the fixed taxonomy, caps quote length, and yields ZERO proposals on any parse failure -- never a
crash.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.backend.llm.egress import DataEgressDisabledError
from app.backend.llm.usage import log_usage
from integrations.gemini.generator import GeminiConfig

ANALYTIC_FLEXIBILITY_CATEGORIES = frozenset(
    {"exclusion-criteria", "covariate-choice", "test-selection", "outcome-choice", "other-branch-point"}
)
MAX_CANDIDATES = 12
MAX_QUOTE_CHARS = 4000


@dataclass(frozen=True)
class AnalyticFlexibilityAssistant:
    config: GeminiConfig
    name: str = "gemini-analytic-flexibility-assistant"

    def propose(self, *, text: str) -> list[dict]:
        from app.backend.llm.providers import complete, requires_egress

        if requires_egress(self.config) and not self.config.data_egress_enabled:
            # Bail BEFORE the network call, so egress-off never touches a cloud provider.
            raise DataEgressDisabledError("Analytic-flexibility surfacing requires explicit data-egress consent.")
        result = complete(self.config, _prompt(text))
        log_usage("analytic-flexibility-assist", self.config.model, result)
        return parse_proposals(str(result.text or ""))


def _prompt(text: str) -> str:
    categories = ", ".join(sorted(ANALYTIC_FLEXIBILITY_CATEGORIES))
    return (
        "You are identifying specific, disclosed analytic decision points in a methods section -- the "
        "exclusion criteria, covariate/control choices, statistical test/model selections, outcome/measure "
        "choices, and other reported branch points. Return JSON only: an array of objects with keys "
        '"category" and "quote". Each "category" MUST be exactly one of: ' + categories + '. Each "quote" '
        "MUST be a verbatim span copied from the supplied text -- never paraphrase, never invent. Omit "
        "anything not clearly evidenced in the text. Do not return a count, ranking, weighting, or overall "
        f"assessment -- only the list of candidates, at most {MAX_CANDIDATES}.\n\nText:\n{text}"
    )


def parse_proposals(raw: str) -> list[dict]:
    """Defensive parse of the UNTRUSTED model response -> [{category, quote}]. Malformed entries, invalid
    categories, and non-string/blank quotes are dropped silently; any parse failure yields []. Quotes are
    length-capped and the list capped at MAX_CANDIDATES."""
    data = _loads_lenient(raw)
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        category = item.get("category")
        quote = item.get("quote")
        if category not in ANALYTIC_FLEXIBILITY_CATEGORIES:
            continue
        if not isinstance(quote, str) or not quote.strip():
            continue
        out.append({"category": category, "quote": quote.strip()[:MAX_QUOTE_CHARS]})
        if len(out) >= MAX_CANDIDATES:
            break
    return out


def _loads_lenient(raw: str):
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    # tolerate surrounding prose: parse the outermost [...] span, if any
    start, end = text.find("["), text.rfind("]")
    if 0 <= start < end:
        try:
            return json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
    return None
