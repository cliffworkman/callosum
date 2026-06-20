"""Direct unit tests for the provider-agnostic egress gate (the inc-58 DI seam).

The API-level tests (test_summaries / test_axes / test_help) already exercise egress-off *through*
the routers. These pin the ``EgressGated*`` wrappers themselves — the authoritative boundary that
protects library text (invariant #3) — and assert the security-critical property the API tests can
only imply: **when egress is OFF the inner provider is never invoked**, so no library text can reach
the provider even via a cache hit or a misconfigured injection.

Each test uses a spy inner that records calls (and would return a sentinel if reached). The gate must
raise before the spy is ever touched.
"""

from __future__ import annotations

import pytest

from app.backend.llm.egress import (
    DataEgressDisabledError,
    EgressGatedAxisClusterLabeler,
    EgressGatedAxisTermSuggester,
    EgressGatedHelpAssistant,
    EgressGatedSummaryGenerator,
    HelpAssistantDisabledError,
)


class _SpySummaryGenerator:
    name = "spy-generator"
    cache_signature = "spy/sig/v1"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, *, source_chunks, scope_ref, conn=None):
        self.calls += 1
        return ["SUMMARY_SENTINEL"]


class _SpyAxisTermSuggester:
    def __init__(self) -> None:
        self.calls = 0

    def suggest(self, *, label, description):
        self.calls += 1
        return ["term-a", "term-b"]


class _SpyAxisClusterLabeler:
    def __init__(self) -> None:
        self.calls = 0

    def label(self, *, titles, terms):
        self.calls += 1
        return {"label": "Cluster", "terms": terms}


class _SpyHelpAssistant:
    def __init__(self) -> None:
        self.calls = 0

    def answer(self, *, message, history):
        self.calls += 1
        return "HELP_SENTINEL"


# --- Summary generator ------------------------------------------------------------------


def test_summary_gate_off_raises_and_never_calls_inner():
    inner = _SpySummaryGenerator()
    gate = EgressGatedSummaryGenerator(inner=inner, data_egress_enabled=False)
    with pytest.raises(DataEgressDisabledError):
        gate.generate(source_chunks=[], scope_ref={})
    assert inner.calls == 0  # the spy must never be reached when egress is off


def test_summary_gate_on_delegates_and_passes_metadata():
    inner = _SpySummaryGenerator()
    gate = EgressGatedSummaryGenerator(inner=inner, data_egress_enabled=True)
    result = gate.generate(source_chunks=[], scope_ref={"kind": "papers"})
    assert result == ["SUMMARY_SENTINEL"]
    assert inner.calls == 1
    assert gate.name == "spy-generator"
    assert gate.cache_signature == "spy/sig/v1"


# --- Axis term suggester ----------------------------------------------------------------


def test_axis_term_gate_off_raises_and_never_calls_inner():
    inner = _SpyAxisTermSuggester()
    gate = EgressGatedAxisTermSuggester(inner=inner, data_egress_enabled=False)
    with pytest.raises(DataEgressDisabledError):
        gate.suggest(label="anomaly", description="anomalous faces")
    assert inner.calls == 0


def test_axis_term_gate_on_delegates():
    inner = _SpyAxisTermSuggester()
    gate = EgressGatedAxisTermSuggester(inner=inner, data_egress_enabled=True)
    assert gate.suggest(label="anomaly", description=None) == ["term-a", "term-b"]
    assert inner.calls == 1


# --- Axis cluster labeler ---------------------------------------------------------------


def test_axis_labeler_gate_off_raises_and_never_calls_inner():
    inner = _SpyAxisClusterLabeler()
    gate = EgressGatedAxisClusterLabeler(inner=inner, data_egress_enabled=False)
    with pytest.raises(DataEgressDisabledError):
        gate.label(titles=["A title"], terms=["t1"])
    assert inner.calls == 0


def test_axis_labeler_gate_on_delegates():
    inner = _SpyAxisClusterLabeler()
    gate = EgressGatedAxisClusterLabeler(inner=inner, data_egress_enabled=True)
    assert gate.label(titles=["A title"], terms=["t1"]) == {"label": "Cluster", "terms": ["t1"]}
    assert inner.calls == 1


# --- Help assistant (independent toggle) ------------------------------------------------


def test_help_gate_off_raises_help_error_and_never_calls_inner():
    inner = _SpyHelpAssistant()
    gate = EgressGatedHelpAssistant(inner=inner, help_assistant_enabled=False)
    with pytest.raises(HelpAssistantDisabledError):
        gate.answer(message="how do tags work?", history=[])
    assert inner.calls == 0


def test_help_gate_on_delegates():
    inner = _SpyHelpAssistant()
    gate = EgressGatedHelpAssistant(inner=inner, help_assistant_enabled=True)
    assert gate.answer(message="how do tags work?", history=[]) == "HELP_SENTINEL"
    assert inner.calls == 1


def test_help_gate_is_independent_of_library_egress_flag():
    """The help wrapper is keyed ONLY on its own toggle — it has no data_egress field at all,
    so an enabled help assistant answers regardless of the library egress posture (inc 60)."""
    inner = _SpyHelpAssistant()
    gate = EgressGatedHelpAssistant(inner=inner, help_assistant_enabled=True)
    # No data_egress parameter exists on the help gate — structural independence.
    assert not hasattr(gate, "data_egress_enabled")
    assert gate.answer(message="q", history=[]) == "HELP_SENTINEL"
