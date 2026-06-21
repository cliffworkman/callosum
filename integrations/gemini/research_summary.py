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


class ResearchSummaryGenerator(Protocol):
    def generate(self, *, documents: list[dict[str, str]]) -> str:
        """Return a one-paragraph research summary from the user's publications. May raise DataEgressDisabledError."""


@dataclass(frozen=True)
class GeminiResearchSummaryGenerator:
    config: GeminiConfig
    name: str = "gemini-research-summary"

    def generate(self, *, documents: list[dict[str, str]]) -> str:
        if not self.config.data_egress_enabled:
            # Check (and bail) BEFORE importing/calling genai, so egress-off never touches the network.
            raise DataEgressDisabledError("Gemini research-summary generation requires explicit data-egress consent.")

        from google import genai

        client = genai.Client(api_key=self.config.resolved_api_key())
        response = client.models.generate_content(model=self.config.model, contents=_prompt(documents))
        log_usage("research-summary", self.config.model, response)
        return _clean(str(response.text or ""))


def _prompt(documents: list[dict[str, str]]) -> str:
    items: list[dict[str, str]] = []
    for doc in documents[:MAX_DOCUMENTS]:
        title = str(doc.get("title") or "").strip()
        if not title:
            continue
        items.append({"title": title, "abstract": str(doc.get("abstract") or "").strip()[:MAX_ABSTRACT_CHARS]})
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
