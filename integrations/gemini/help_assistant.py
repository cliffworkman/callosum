"""Gemini-backed help assistant (gated by its OWN consent toggle, not the library egress gate).

Answers a user's question about **using** callosum from the PUBLIC help corpus only — never library text.
Because the corpus is small, the WHOLE corpus is stuffed into the prompt each call (**NO RAG**; if the
corpus ever outgrows the context window, add retrieval here — that is the upgrade path). Conversational:
prior turns are passed in by the caller, so the server stays stateless. The model's JSON is parsed
defensively (reusing the code-fence stripper); a parse failure degrades to the raw answer text with no
references — never an exception to the endpoint.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.backend.help.assistant import HelpAnswer, HelpReference, HelpTurn
from app.backend.help.corpus import help_corpus_prompt
from app.backend.llm.egress import HelpAssistantDisabledError
from app.backend.llm.usage import log_usage
from integrations.gemini.generator import GeminiConfig, _strip_code_fence

MAX_ANSWER_LEN = 4000
MAX_REFERENCES = 6
MAX_REASON_LEN = 200
MAX_HISTORY_TURNS = 20
MAX_TURN_LEN = 4000


@dataclass(frozen=True)
class GeminiHelpAssistant:
    config: GeminiConfig
    name: str = "gemini-help-assistant"

    def answer(self, *, message: str, history: list[HelpTurn]) -> HelpAnswer:
        if not self.config.help_assistant_enabled:
            # Defense-in-depth (the seam wrapper is the authoritative gate); bail BEFORE importing genai.
            raise HelpAssistantDisabledError("The AI help assistant requires CALLOSUM_HELP_ASSISTANT_ENABLED.")

        from google import genai

        client = genai.Client(api_key=self.config.resolved_api_key())
        response = client.models.generate_content(
            model=self.config.model,
            contents=_prompt(message=message, history=history),
        )
        log_usage("help-assistant", self.config.model, response)
        return _parse_answer(str(response.text or "{}"))


def _prompt(*, message: str, history: list[HelpTurn]) -> str:
    convo = "\n".join(f"{t.role}: {t.content[:MAX_TURN_LEN]}" for t in history[-MAX_HISTORY_TURNS:])
    return (
        "You are the in-app help assistant for Callosum, a local-first reference manager. Answer the user's "
        "question about USING the app, drawing ONLY on the HELP SECTIONS below. Be concise and concrete. "
        'Return JSON only: {"answer": <a short, helpful answer>, "references": [{"section_id": <an id that '
        'appears in the sections>, "reason": <a few words on why it is relevant>}]}. Use only section_ids '
        "from the sections below; include the 1-3 most relevant. If the question is not covered by the "
        "help, say so briefly and return an empty references array. No markdown, no commentary outside the "
        "JSON.\n\n"
        f"HELP SECTIONS:\n{help_corpus_prompt()}\n\n"
        + (f"CONVERSATION SO FAR:\n{convo}\n\n" if convo else "")
        + f"USER QUESTION: {message}"
    )


def _parse_answer(text: str) -> HelpAnswer:
    """Defensively parse the model's JSON into a capped answer + deduped references (id-validation is the
    router's job). On any failure, degrade to the raw text with no references — never raise."""
    try:
        payload = json.loads(_strip_code_fence(text))
    except (json.JSONDecodeError, ValueError):
        return HelpAnswer(answer=text.strip()[:MAX_ANSWER_LEN], references=[])
    if not isinstance(payload, dict):
        return HelpAnswer(answer=str(text).strip()[:MAX_ANSWER_LEN], references=[])
    answer = str(payload.get("answer") or "").strip()[:MAX_ANSWER_LEN]
    references: list[HelpReference] = []
    seen: set[str] = set()
    raw_references = payload.get("references")
    if isinstance(raw_references, list):
        for item in raw_references:
            if not isinstance(item, dict):
                continue
            section_id = str(item.get("section_id") or "").strip()
            if not section_id or section_id in seen:
                continue
            seen.add(section_id)
            references.append(
                HelpReference(section_id=section_id, reason=str(item.get("reason") or "").strip()[:MAX_REASON_LEN])
            )
            if len(references) >= MAX_REFERENCES:
                break
    return HelpAnswer(answer=answer, references=references)
