from __future__ import annotations

import pytest

from integrations.gemini.analytic_flexibility_assistant import (
    ANALYTIC_FLEXIBILITY_CATEGORIES,
    AnalyticFlexibilityAssistant,
    parse_proposals,
)


def test_categories_are_the_five_fixed_values():
    assert ANALYTIC_FLEXIBILITY_CATEGORIES == frozenset(
        {"exclusion-criteria", "covariate-choice", "test-selection", "outcome-choice", "other-branch-point"}
    )


def test_parse_proposals_accepts_well_formed_json():
    raw = (
        '[{"category": "exclusion-criteria", "quote": "participants under 18 were excluded"},'
        ' {"category": "test-selection", "quote": "we used a two-sample t-test"}]'
    )
    result = parse_proposals(raw)
    assert result == [
        {"category": "exclusion-criteria", "quote": "participants under 18 were excluded"},
        {"category": "test-selection", "quote": "we used a two-sample t-test"},
    ]


def test_parse_proposals_tolerates_markdown_fences():
    raw = '```json\n[{"category": "covariate-choice", "quote": "age was included as a covariate"}]\n```'
    assert parse_proposals(raw) == [{"category": "covariate-choice", "quote": "age was included as a covariate"}]


def test_parse_proposals_drops_invalid_category_not_raises():
    raw = (
        '[{"category": "researcher-freedom-index", "quote": "some text"},'
        ' {"category": "outcome-choice", "quote": "primary outcome was X"}]'
    )
    assert parse_proposals(raw) == [{"category": "outcome-choice", "quote": "primary outcome was X"}]


def test_parse_proposals_drops_entries_missing_a_quote():
    raw = '[{"category": "exclusion-criteria"}, {"category": "outcome-choice", "quote": "primary outcome was X"}]'
    assert parse_proposals(raw) == [{"category": "outcome-choice", "quote": "primary outcome was X"}]


def test_parse_proposals_caps_at_twelve():
    items = ", ".join(f'{{"category": "other-branch-point", "quote": "point {i}"}}' for i in range(20))
    assert len(parse_proposals(f"[{items}]")) == 12


def test_parse_proposals_never_raises_on_garbage():
    assert parse_proposals("not json at all") == []
    assert parse_proposals("") == []
    assert parse_proposals("{}") == []


def test_propose_refuses_before_any_network_call_when_egress_disabled(monkeypatch):
    from app.backend.llm.egress import DataEgressDisabledError
    from integrations.gemini.generator import GeminiConfig

    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    config = GeminiConfig(provider="gemini", model="gemini-2.5-flash-lite", api_key="fake", data_egress_enabled=False)
    assistant = AnalyticFlexibilityAssistant(config)
    with pytest.raises(DataEgressDisabledError):
        assistant.propose(text="Participants were excluded if under 18.")


def test_propose_extracts_text_from_completion_result_when_egress_not_required(monkeypatch):
    """Regression guard: complete() returns a CompletionResult (see extraction_assistant.py's real usage),
    not a bare string -- propose() must read .text before handing the raw response to parse_proposals."""
    import app.backend.llm.providers as providers
    from integrations.gemini.generator import GeminiConfig

    def fake_complete(config, prompt, *, http_client=None):
        return providers.CompletionResult(
            text='[{"category": "exclusion-criteria", "quote": "excluded if under 18"}]',
            usage_metadata=None,
        )

    monkeypatch.setattr(providers, "complete", fake_complete)
    config = GeminiConfig(
        provider="local",
        wire_format="chat_completions",
        base_url="http://127.0.0.1:11434",
        model="local-model",
        data_egress_enabled=False,
    )
    assistant = AnalyticFlexibilityAssistant(config)
    result = assistant.propose(text="Participants were excluded if under 18.")
    assert result == [{"category": "exclusion-criteria", "quote": "excluded if under 18"}]
