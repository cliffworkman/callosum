"""A model that runs out of output room must not look like a model that returned garbage.

Vasiliki asked a broad, citation-heavy question on the managed Local AI provider and got
``JSONDecodeError: Unterminated string starting at: line 32 column 30 (char 8436)`` — roughly 2,100
tokens, i.e. the 2,048-token ``--n-predict`` ceiling. Two separate defects met there:

1. Every provider reports *why* it stopped and we discarded it, so truncation was indistinguishable
   from malformed output — we could not even tell which provider had run out of room.
2. The synthesis schema PERMITS 7 claims x 3 citations of ~80-word quotes (~3,300+ tokens) while the
   output ceiling allowed 2,048, so a citation-dense question truncated *by construction*.

These tests pin both, plus the salvage that keeps a long wait from producing nothing.
"""

from __future__ import annotations

import json

import pytest

from app.backend.llm.managed_local import (
    _PREVIEW_OUTPUT_TOKENS,
    _PRIMARY_SYNTHESIS_SCHEMA,
    _QUOTE_MAX_CHARS,
    _WORST_CASE_OUTPUT_CHARS,
)
from app.backend.llm.providers import CompletionResult, _is_truncation_reason
from app.backend.summarization.generators import TruncatedGenerationError
from integrations.gemini.generator import _parse_response_text, salvage_complete_objects

# Deliberately conservative: real JSON with quoted prose runs ~4 chars/token, so dividing by a SMALLER
# number over-estimates the token cost. If the cap covers the pessimistic estimate it covers reality.
_PESSIMISTIC_CHARS_PER_TOKEN = 3.5


def _complete_object(index: int, quote: str = "a verbatim quote") -> dict:
    return {"text": f"Claim {index}.", "citations": [{"chunk_id": index, "quote": quote}]}


def _truncated_array(complete_count: int) -> str:
    """A JSON array cut off mid-string inside the element AFTER ``complete_count`` whole ones."""
    body = ",".join(json.dumps(_complete_object(i)) for i in range(complete_count))
    return f"[{body}," + '{"text": "Claim cut off here", "citations": [{"chunk_id": 99, "quote": "the model ran ou'


def test_the_reported_failure_reproduces_and_is_now_salvaged() -> None:
    text = _truncated_array(3)
    with pytest.raises(json.JSONDecodeError, match="Unterminated string"):
        json.loads(text)  # exactly what the user saw

    salvaged = salvage_complete_objects(text)
    assert [item["text"] for item in salvaged] == ["Claim 0.", "Claim 1.", "Claim 2."]
    assert all(item["citations"][0]["quote"] for item in salvaged), "a salvaged claim keeps its evidence"


def test_salvage_never_returns_a_partial_object() -> None:
    """The half-written element must be dropped whole, never repaired into something the model
    did not say."""
    for complete_count in range(0, 5):
        salvaged = salvage_complete_objects(_truncated_array(complete_count))
        assert len(salvaged) == complete_count
        for item in salvaged:
            assert set(item) == {"text", "citations"}
            assert item["citations"][0]["chunk_id"] is not None


def test_nothing_salvageable_still_fails_rather_than_inventing_an_empty_answer() -> None:
    assert salvage_complete_objects('[{"text": "cut off before the first claim clo') == []
    assert salvage_complete_objects("not json at all") == []
    assert salvage_complete_objects("") == []


def test_a_complete_response_is_unaffected_by_the_salvage_path() -> None:
    payload = [_complete_object(i) for i in range(4)]
    text = json.dumps(payload)
    sentences = _parse_response_text(text)
    assert [s.text for s in sentences] == ["Claim 0.", "Claim 1.", "Claim 2.", "Claim 3."]
    assert [item["text"] for item in salvage_complete_objects(text)] == [s.text for s in sentences]


@pytest.mark.parametrize(
    "reason",
    [
        "length",  # chat_completions, incl. the managed Local AI path
        "max_tokens",  # anthropic
        "MAX_TOKENS",  # gemini, bare
        "FinishReason.MAX_TOKENS",  # gemini, enum repr
        "incomplete",  # responses API
    ],
)
def test_every_provider_dialect_for_running_out_of_room_is_recognised(reason: str) -> None:
    assert _is_truncation_reason(reason) is True


@pytest.mark.parametrize("reason", ["stop", "end_turn", "STOP", "completed", None, "", "content_filter"])
def test_a_normal_finish_is_not_mistaken_for_truncation(reason) -> None:
    assert _is_truncation_reason(reason) is False


def test_completion_result_defaults_to_not_truncated() -> None:
    """Every pre-existing construction site omits the field; none of them may start claiming
    truncation by accident."""
    assert CompletionResult(text="hi", usage_metadata=None).truncated is False


def test_truncation_error_carries_the_completed_claims_and_says_how_many() -> None:
    error = TruncatedGenerationError(sentences=[object(), object()])  # type: ignore[list-item]
    assert error.sentences and len(error.sentences) == 2
    assert "2 complete claims" in str(error)


def test_the_output_ceiling_covers_the_worst_answer_the_schema_permits() -> None:
    """The regression that caused the bug: the schema and the token cap contradicting each other.

    If someone loosens the schema (more claims, more citations, longer quotes) without raising the
    ceiling, this fails instead of silently truncating a real user's synthesis again.
    """
    quote_schema = _PRIMARY_SYNTHESIS_SCHEMA["items"]["properties"]["citations"]["items"]["properties"]["quote"]
    assert quote_schema["maxLength"] == _QUOTE_MAX_CHARS, "an unbounded quote can consume the whole allowance"

    max_claims = _PRIMARY_SYNTHESIS_SCHEMA["maxItems"]
    max_citations = _PRIMARY_SYNTHESIS_SCHEMA["items"]["properties"]["citations"]["maxItems"]
    # Recomputed from the schema itself, so loosening the schema moves this number.
    worst_case_chars = max_claims * (200 + max_citations * (_QUOTE_MAX_CHARS + 60)) + 64
    assert worst_case_chars <= _WORST_CASE_OUTPUT_CHARS

    worst_case_tokens = worst_case_chars / _PESSIMISTIC_CHARS_PER_TOKEN
    assert worst_case_tokens <= _PREVIEW_OUTPUT_TOKENS, (
        f"the schema permits ~{worst_case_tokens:.0f} tokens but the output cap is "
        f"{_PREVIEW_OUTPUT_TOKENS}; a citation-dense question would truncate by construction"
    )


def test_the_rust_and_python_token_contracts_cannot_drift_apart() -> None:
    """`_require(max_output_tokens == expected)` fails CLOSED, so a one-sided edit does not break a
    test — it breaks Local AI on a real machine, after a successful install, with a descriptor
    mismatch. Two constants in two languages that must move together deserve a guard that says so.
    """
    import re
    from pathlib import Path

    from app.backend.llm.managed_local import _PREVIEW_CONTEXT_TOKENS

    rust = Path("app/desktop-shell/src-tauri/src/managed_local_ai.rs").read_text(encoding="utf-8")

    def constant(name: str) -> int:
        match = re.search(rf"const {name}: u32 = ([0-9_]+);", rust)
        assert match, f"{name} not found in managed_local_ai.rs — was it renamed?"
        return int(match.group(1).replace("_", ""))

    assert constant("PREVIEW_OUTPUT_TOKENS") == _PREVIEW_OUTPUT_TOKENS
    assert constant("PREVIEW_CONTEXT_TOKENS") == _PREVIEW_CONTEXT_TOKENS


def test_the_managed_context_still_fits_prompt_plus_output() -> None:
    """Raising the output cap must not push the total past the model's context window."""
    from app.backend.llm.managed_local import _PREVIEW_CONTEXT_TOKENS
    from integrations.gemini.generator import _MANAGED_LOCAL_TOTAL_CHUNK_CHARS

    prompt_tokens = _MANAGED_LOCAL_TOTAL_CHUNK_CHARS / _PESSIMISTIC_CHARS_PER_TOKEN + 400  # + instructions
    assert prompt_tokens + _PREVIEW_OUTPUT_TOKENS < _PREVIEW_CONTEXT_TOKENS
