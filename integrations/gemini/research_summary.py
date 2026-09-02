"""Gemini-backed research-summary generation for the My Publications dashboard (inc 81), egress-gated.

Generates ONE editable paragraph describing the user's body of work, from their OWN publication titles +
abstracts. This sends library text, so — like summary generation and axis-term suggestion — it is the ONLY
place that text leaves the machine, and only with explicit data-egress consent. The output is a
non-load-bearing draft the user edits ("reads true to me"); it is never treated as a verified claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from app.backend.llm.usage import log_usage
from integrations.gemini.generator import DataEgressDisabledError, GeminiConfig

MAX_DOCUMENTS = 60  # cap how many of the user's publications we send
MAX_ABSTRACT_CHARS = 600  # truncate each abstract
MAX_SUMMARY_CHARS = 2000  # defensively cap the returned paragraph (untrusted output)
# 60 docs x 600-char abstracts is up to 36,000 chars of abstracts alone; measured real worst-case input was
# 56,397 chars -- well past the managed Local AI preview's ~10,240-token (~30-40k character) budget. Fewer
# documents, each more tightly truncated, when the active provider is managed_local. See
# app/backend/llm/prompt_budget.py.
MAX_DOCUMENTS_MANAGED_LOCAL = 20
MAX_ABSTRACT_CHARS_MANAGED_LOCAL = 250


class ResearchSummaryGenerator(Protocol):
    def generate(self, *, documents: list[dict[str, str]]) -> str:
        """Return a one-paragraph research summary from the user's publications. May raise DataEgressDisabledError."""


@dataclass(frozen=True)
class GeminiResearchSummaryGenerator:
    config: GeminiConfig
    name: str = "gemini-research-summary"

    def generate(self, *, documents: list[dict[str, str]]) -> str:
        from app.backend.llm.providers import complete, requires_egress

        if requires_egress(self.config) and not self.config.data_egress_enabled:
            raise DataEgressDisabledError("Research-summary generation requires explicit data-egress consent.")
        result = complete(self.config, _prompt(documents, provider=self.config.provider))
        log_usage("research-summary", self.config.model, result)
        return _clean(str(result.text or ""))


def _prompt(documents: list[dict[str, str]], *, provider: str | None = None) -> str:
    managed_local = provider == "managed_local"
    max_documents = MAX_DOCUMENTS_MANAGED_LOCAL if managed_local else MAX_DOCUMENTS
    max_abstract_chars = MAX_ABSTRACT_CHARS_MANAGED_LOCAL if managed_local else MAX_ABSTRACT_CHARS
    items: list[dict[str, str]] = []
    for doc in documents[:max_documents]:
        title = str(doc.get("title") or "").strip()
        if not title:
            continue
        items.append({"title": title, "abstract": str(doc.get("abstract") or "").strip()[:max_abstract_chars]})
    return (
        "You write a concise research summary of a single researcher's body of work, for the overview of their "
        "personal publications dashboard. Given the researcher's OWN publication titles and abstracts below, "
        "write ONE paragraph (3-5 sentences) describing the themes, methods, and through-lines of their "
        "research. Be specific and grounded ONLY in the listed work; do not invent awards, affiliations, "
        "metrics, or any claim the titles/abstracts do not support. Plain prose only — no preamble, no "
        "markdown, no bullet points.\n\n"
        f"Publications (JSON): {json.dumps(items, ensure_ascii=True)}"
    )


def _clean(text: str) -> str:
    """Collapse whitespace + cap length (untrusted model output)."""
    return " ".join(text.split()).strip()[:MAX_SUMMARY_CHARS]
