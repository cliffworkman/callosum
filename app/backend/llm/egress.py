"""Provider-agnostic data-egress enforcement.

The single home for ``DataEgressDisabledError`` and for the egress gate the API applies at the
dependency-injection seam. The router factories wrap whatever LLM provider they resolve — the default
Gemini provider OR an instance injected via ``create_app(...)`` — so the gate is the **authoritative**
boundary protecting library text. This closes the hole where an injected provider would otherwise be
returned unchecked and protected only by the provider self-gating by convention (invariant #3).

The wrappers conform structurally to the existing provider protocols
(``app.backend.summarization.generators.SummaryGenerator`` and the ``AxisTermSuggester`` /
``AxisClusterLabeler`` Protocols in ``integrations.gemini.*``). They hold an inner instance plus the
resolved egress flag, raise ``DataEgressDisabledError`` when egress is disabled, and otherwise delegate
unchanged. The providers keep their own internal egress checks as defense-in-depth.

This module must NOT import ``integrations.gemini.*`` at runtime: ``integrations.gemini.generator``
re-exports ``DataEgressDisabledError`` from here, so a runtime import back would be circular. The
provider protocols are referenced only under ``TYPE_CHECKING``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backend.llm.providers import requires_egress
from app.backend.summarization.generators import (
    CandidateSummarySentence,
    SourceChunk,
    SummaryGenerator,
)

if TYPE_CHECKING:
    from sqlalchemy import Connection

    from app.backend.help.assistant import HelpAnswer, HelpAssistant, HelpTurn
    from app.backend.summarization.overview import OverviewGenerator, OverviewSentence
    from integrations.gemini.axis_cluster_labeler import AxisClusterLabeler
    from integrations.gemini.axis_terms import AxisTermSuggester
    from integrations.gemini.extraction_assistant import ExtractionAssistant
    from integrations.gemini.research_summary import ResearchSummaryGenerator


class DataEgressDisabledError(RuntimeError):
    """Raised when a Gemini call would send source text while egress is disabled."""


class HelpAssistantDisabledError(RuntimeError):
    """Raised when the AI help assistant is called while its OWN consent toggle is disabled.

    Independent of ``DataEgressDisabledError`` (the library data-egress gate): the help assistant sends
    only the user's question + the public help docs, so it has a separate toggle
    (``CALLOSUM_HELP_ASSISTANT_ENABLED``).
    """


@dataclass(frozen=True)
class _EgressProbe:
    """A minimal duck-typed config so the wrappers can ask ``requires_egress`` its ENDPOINT-based question
    (inc 256). Critical for custom providers: their id is a uuid, not a name in ``CLOUD_PROVIDERS``, so a
    name-only check would wrongly pass a custom CLOUD endpoint as no-egress. ``wire_format``/``base_url`` left
    None fall back to the name-based decision, so a wrapper constructed with only ``provider=`` (the existing
    tests) keeps the exact legacy truth table."""

    provider: str
    wire_format: str | None
    base_url: str | None


def _egress_needed(provider: str, wire_format: str | None, base_url: str | None) -> bool:
    """Endpoint-aware egress decision for the authoritative DI-seam gate."""
    return requires_egress(_EgressProbe(provider=provider, wire_format=wire_format, base_url=base_url))


@dataclass(frozen=True)
class EgressGatedSummaryGenerator:
    """Egress gate around a ``SummaryGenerator`` (injected or default).

    Raises ``DataEgressDisabledError`` when egress is disabled; otherwise delegates to ``inner``.
    """

    inner: SummaryGenerator
    data_egress_enabled: bool
    provider: str = "gemini"  # a loopback provider (builtin `local` or a localhost custom) needs no consent
    wire_format: str | None = None
    base_url: str | None = None

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def cache_signature(self) -> str:
        return getattr(self.inner, "cache_signature", self.inner.name)

    def generate(
        self,
        *,
        source_chunks: list[SourceChunk],
        scope_ref: dict[str, object],
        conn: "Connection | None" = None,
    ) -> list[CandidateSummarySentence]:
        # Egress is checked FIRST (outermost), before the inner cache is ever consulted, so egress-off
        # behaves exactly as before — a cache hit can never bypass the gate. A loopback endpoint keeps text on
        # the machine (egress not required), so consent-to-egress is correctly N/A.
        if _egress_needed(self.provider, self.wire_format, self.base_url) and not self.data_egress_enabled:
            raise DataEgressDisabledError("Summary generation requires explicit data-egress consent.")
        return self.inner.generate(source_chunks=source_chunks, scope_ref=scope_ref, conn=conn)


@dataclass(frozen=True)
class EgressGatedAxisTermSuggester:
    """Egress gate around an ``AxisTermSuggester`` (injected or default)."""

    inner: "AxisTermSuggester"
    data_egress_enabled: bool
    provider: str = "gemini"
    wire_format: str | None = None
    base_url: str | None = None

    def suggest(self, *, label: str, description: str | None) -> list[str]:
        if _egress_needed(self.provider, self.wire_format, self.base_url) and not self.data_egress_enabled:
            raise DataEgressDisabledError("Axis-term suggestion requires explicit data-egress consent.")
        return self.inner.suggest(label=label, description=description)


@dataclass(frozen=True)
class EgressGatedResearchSummaryGenerator:
    """Egress gate around a ``ResearchSummaryGenerator`` (injected or default) — it sends the user's own
    publication titles/abstracts (library text), so it rides the library egress gate (inc 81)."""

    inner: "ResearchSummaryGenerator"
    data_egress_enabled: bool
    provider: str = "gemini"
    wire_format: str | None = None
    base_url: str | None = None

    def generate(self, *, documents: list[dict[str, str]]) -> str:
        if _egress_needed(self.provider, self.wire_format, self.base_url) and not self.data_egress_enabled:
            raise DataEgressDisabledError("Research-summary generation requires explicit data-egress consent.")
        return self.inner.generate(documents=documents)


@dataclass(frozen=True)
class EgressGatedOverviewGenerator:
    """Egress gate around an ``OverviewGenerator`` (inc 124). It narrativizes the verified claims (library-derived
    text), so it rides the library egress gate."""

    inner: "OverviewGenerator"
    data_egress_enabled: bool
    provider: str = "gemini"
    wire_format: str | None = None
    base_url: str | None = None

    @property
    def name(self) -> str:
        return self.inner.name

    def generate(self, *, verified_claims: list[str], scope_ref: dict[str, object]) -> list["OverviewSentence"]:
        if _egress_needed(self.provider, self.wire_format, self.base_url) and not self.data_egress_enabled:
            raise DataEgressDisabledError("Overview generation requires explicit data-egress consent.")
        return self.inner.generate(verified_claims=verified_claims, scope_ref=scope_ref)


@dataclass(frozen=True)
class EgressGatedAxisClusterLabeler:
    """Egress gate around an ``AxisClusterLabeler`` (injected or default)."""

    inner: "AxisClusterLabeler"
    data_egress_enabled: bool
    provider: str = "gemini"
    wire_format: str | None = None
    base_url: str | None = None

    def label(self, *, titles: list[str], terms: list[str]) -> dict:
        if _egress_needed(self.provider, self.wire_format, self.base_url) and not self.data_egress_enabled:
            raise DataEgressDisabledError("Axis-cluster labeling requires explicit data-egress consent.")
        return self.inner.label(titles=titles, terms=terms)


@dataclass(frozen=True)
class EgressGatedExtractionAssistant:
    """SP2b funnel: gate the assisted-extraction LLM at the DI seam. A loopback/local provider is honestly no-egress;
    a non-loopback endpoint requires consent, exactly like the summary generator (invariant #3)."""

    inner: "ExtractionAssistant"
    data_egress_enabled: bool
    provider: str = "gemini"
    wire_format: str | None = None
    base_url: str | None = None

    def propose(self, *, text: str, fields: list[dict]) -> list[dict]:
        if _egress_needed(self.provider, self.wire_format, self.base_url) and not self.data_egress_enabled:
            raise DataEgressDisabledError("Assisted extraction requires explicit data-egress consent.")
        return self.inner.propose(text=text, fields=fields)


@dataclass(frozen=True)
class EgressGatedHelpAssistant:
    """Gate around a ``HelpAssistant`` (injected or default), keyed on the help assistant's **own** toggle.

    Deliberately NOT keyed on ``data_egress_enabled``: the help assistant sends only the user's question +
    the public help docs (never library text), so it is independent of the library egress gate.
    """

    inner: "HelpAssistant"
    help_assistant_enabled: bool

    def answer(self, *, message: str, history: list["HelpTurn"]) -> "HelpAnswer":
        if not self.help_assistant_enabled:
            raise HelpAssistantDisabledError("The AI help assistant requires CALLOSUM_HELP_ASSISTANT_ENABLED.")
        return self.inner.answer(message=message, history=history)
