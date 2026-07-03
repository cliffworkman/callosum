"""Gemini-backed axis synonym / related-term suggestion (egress-gated, human-curated).

Proposes related terms for a user-defined axis so the user can curate them and fold the chosen
ones into the axis description, broadening semantic matching. Like summary generation, this is the
ONLY place axis text leaves the machine, and only with explicit data-egress consent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from app.backend.llm.usage import log_usage
from integrations.gemini.generator import DataEgressDisabledError, GeminiConfig, _strip_code_fence

MAX_TERMS = 12
MAX_TERM_LEN = 60


class AxisTermSuggester(Protocol):
    def suggest(self, *, label: str, description: str | None) -> list[str]:
        """Return related terms/synonyms for an axis. May raise DataEgressDisabledError."""


@dataclass(frozen=True)
class GeminiAxisTermSuggester:
    config: GeminiConfig
    name: str = "gemini-axis-term-suggester"

    def suggest(self, *, label: str, description: str | None) -> list[str]:
        from app.backend.llm.providers import complete, requires_egress

        if requires_egress(self.config) and not self.config.data_egress_enabled:
            # Bail BEFORE the network call, so egress-off never touches a cloud provider.
            raise DataEgressDisabledError("Axis-term suggestion requires explicit data-egress consent.")
        result = complete(self.config, _prompt(label=label, description=description))
        log_usage("axis-terms", self.config.model, result)
        return _parse_terms(str(result.text or "[]"), label=label, description=description)


def _prompt(*, label: str, description: str | None) -> str:
    return (
        "You expand a conceptual 'axis' (a lens for organizing a research library) into related search "
        "terms to broaden semantic matching. Return JSON only: an array of 8-12 short related terms, "
        "synonyms, or alternate phrasings (including acronyms and their expansions) that capture the "
        "SAME construct. No commentary, no duplicates. "
        f"Axis label: {json.dumps(label, ensure_ascii=True)}\n"
        f"Axis description: {json.dumps(description or '', ensure_ascii=True)}"
    )


def _parse_terms(text: str, *, label: str, description: str | None) -> list[str]:
    """Defensively parse the model's JSON array into clean, deduped, capped terms (untrusted output)."""
    try:
        payload = json.loads(_strip_code_fence(text))
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    existing_words = {word.lower() for word in (label + " " + (description or "")).split()}
    seen: set[str] = set()
    terms: list[str] = []
    for item in payload:
        term = str(item).strip()
        key = term.lower()
        if not term or len(term) > MAX_TERM_LEN or key in seen or key in existing_words:
            continue
        seen.add(key)
        terms.append(term)
        if len(terms) >= MAX_TERMS:
            break
    return terms
