"""Gemini-backed Overview generation (inc 124), egress-gated.

Narrativizes the verified claims of a synthesis into a short Overview, returning per-sentence claim references
(an evidence trace). Sends library-derived text (the verified claims), so — like summary/research-summary
generation — it is gated at the inc-58 seam and only runs with explicit data-egress consent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.backend.llm.usage import log_usage
from app.backend.summarization.overview import OverviewSentence
from integrations.gemini.generator import DataEgressDisabledError, GeminiConfig

# Versioned for a future cache key (cf. SUMMARY_PROMPT_VERSION); nothing cached yet.
OVERVIEW_PROMPT_VERSION = "overview-v1"
MAX_CLAIMS = 40  # cap how many verified claims we send
MAX_CLAIM_CHARS = 400  # truncate each claim
MAX_OVERVIEW_SENTENCES = 6  # defensively cap returned sentences (untrusted output)
MAX_SENTENCE_CHARS = 400


@dataclass(frozen=True)
class GeminiOverviewGenerator:
    config: GeminiConfig
    name: str = "gemini-overview-generator"

    def generate(self, *, verified_claims: list[str], scope_ref: dict[str, object]) -> list[OverviewSentence]:
        if not self.config.data_egress_enabled:
            # Check (and bail) BEFORE importing/calling genai, so egress-off never touches the network.
            raise DataEgressDisabledError("Gemini overview generation requires explicit data-egress consent.")

        from google import genai

        client = genai.Client(api_key=self.config.resolved_api_key())
        response = client.models.generate_content(model=self.config.model, contents=_prompt(verified_claims))
        log_usage("overview", self.config.model, response)
        return _parse_overview_response(str(response.text or "[]"))


def _prompt(verified_claims: list[str]) -> str:
    items = [
        {"index": i, "claim": str(c).strip()[:MAX_CLAIM_CHARS]}
        for i, c in enumerate(verified_claims[:MAX_CLAIMS])
        if str(c).strip()
    ]
    return (
        "You are given NUMBERED claims that have ALREADY been verified against source papers. Write a brief "
        "overview (2-4 sentences) synthesizing them for a reader. Return JSON ONLY: an array of objects "
        '{"text": <sentence>, "claim_indices": [<the index numbers of the claims that sentence restates>]}. '
        "Use ONLY information in the listed claims; introduce NO new facts, numbers, names, or citations. Every "
        "sentence must restate one or more of the numbered claims and list their indices.\n"
        f"Claims (JSON): {json.dumps(items, ensure_ascii=True)}"
    )


def _parse_overview_response(text: str) -> list[OverviewSentence]:
    payload = json.loads(_strip_code_fence(text))
    out: list[OverviewSentence] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        sentence = str(item.get("text") or "").strip()[:MAX_SENTENCE_CHARS]
        refs = item.get("claim_indices")
        if not sentence or not isinstance(refs, list):
            continue
        # bool is an int subclass — exclude JSON true/false from claim indices.
        indices = [int(r) for r in refs if isinstance(r, int) and not isinstance(r, bool)]
        out.append(OverviewSentence(text=sentence, claim_indices=indices))
    return out[:MAX_OVERVIEW_SENTENCES]


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped
