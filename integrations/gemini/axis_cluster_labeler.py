"""Gemini-backed cluster labeling for suggest-optimal-axes (egress-gated, optional polish).

Given ONE cluster's representative paper titles (+ the locally-derived candidate terms), proposes a
concise axis name + related terms. Like every Gemini path, it is gated: nothing leaves the machine
unless the user opts into data egress, and the check happens BEFORE any genai import/call. The caller
(`axis_suggestion.apply_labels`) falls back to the local label on any failure, so this is pure polish.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from app.backend.llm.usage import log_usage
from integrations.gemini.generator import DataEgressDisabledError, GeminiConfig, _strip_code_fence

MAX_LABEL_LEN = 80
MAX_TERMS = 8
MAX_TERM_LEN = 60


class AxisClusterLabeler(Protocol):
    def label(self, *, titles: list[str], terms: list[str]) -> dict:
        """Return {'label': str, 'terms': [str]} for a cluster. May raise DataEgressDisabledError."""


@dataclass(frozen=True)
class GeminiAxisClusterLabeler:
    config: GeminiConfig
    name: str = "gemini-axis-cluster-labeler"

    def label(self, *, titles: list[str], terms: list[str]) -> dict:
        from app.backend.llm.providers import complete, requires_egress

        if requires_egress(self.config) and not self.config.data_egress_enabled:
            # Bail BEFORE the network call, so egress-off never touches a cloud provider.
            raise DataEgressDisabledError("Axis-cluster labeling requires explicit data-egress consent.")
        result = complete(self.config, _prompt(titles=titles, terms=terms))
        log_usage("axis-cluster-labeler", self.config.model, result)
        return _parse_label(str(result.text or "{}"))


def _prompt(*, titles: list[str], terms: list[str]) -> str:
    return (
        "You name a conceptual 'axis' (a lens for organizing a research library) for ONE cluster of "
        'papers. Given their titles, return JSON only: {"label": <a concise 2-5 word axis name>, '
        '"terms": [<4-8 short related search terms / synonyms / acronyms for the SAME construct>]}. '
        "No commentary, no markdown. "
        f"Paper titles: {json.dumps(list(titles)[:12], ensure_ascii=True)}\n"
        f"Candidate terms: {json.dumps(list(terms)[:8], ensure_ascii=True)}"
    )


def _parse_label(text: str) -> dict:
    """Defensively parse the model's JSON object into a clean label + capped/deduped terms (untrusted)."""
    try:
        payload = json.loads(_strip_code_fence(text))
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    label = str(payload.get("label") or "").strip()[:MAX_LABEL_LEN]
    raw_terms = payload.get("terms")
    seen: set[str] = set()
    terms: list[str] = []
    if isinstance(raw_terms, list):
        for item in raw_terms:
            term = str(item).strip()
            key = term.lower()
            if not term or len(term) > MAX_TERM_LEN or key in seen:
                continue
            seen.add(key)
            terms.append(term)
            if len(terms) >= MAX_TERMS:
                break
    return {"label": label, "terms": terms}
