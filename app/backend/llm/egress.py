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

from app.backend.summarization.generators import (
    CandidateSummarySentence,
    SourceChunk,
    SummaryGenerator,
)

if TYPE_CHECKING:
    from sqlalchemy import Connection

    from app.backend.help.assistant import HelpAnswer, HelpAssistant, HelpTurn
    from integrations.gemini.axis_cluster_labeler import AxisClusterLabeler
    from integrations.gemini.axis_terms import AxisTermSuggester


class DataEgressDisabledError(RuntimeError):
    """Raised when a Gemini call would send source text while egress is disabled."""


class HelpAssistantDisabledError(RuntimeError):
    """Raised when the AI help assistant is called while its OWN consent toggle is disabled.

    Independent of ``DataEgressDisabledError`` (the library data-egress gate): the help assistant sends
    only the user's question + the public help docs, so it has a separate toggle
    (``CALLOSUM_HELP_ASSISTANT_ENABLED``).
    """


@dataclass(frozen=True)
class EgressGatedSummaryGenerator:
    """Egress gate around a ``SummaryGenerator`` (injected or default).

    Raises ``DataEgressDisabledError`` when egress is disabled; otherwise delegates to ``inner``.
    """

    inner: SummaryGenerator
    data_egress_enabled: bool

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
        # behaves exactly as before — a cache hit can never bypass the gate.
        if not self.data_egress_enabled:
            raise DataEgressDisabledError("Gemini summary generation requires explicit data-egress consent.")
        return self.inner.generate(source_chunks=source_chunks, scope_ref=scope_ref, conn=conn)


@dataclass(frozen=True)
class EgressGatedAxisTermSuggester:
    """Egress gate around an ``AxisTermSuggester`` (injected or default)."""

    inner: "AxisTermSuggester"
    data_egress_enabled: bool

    def suggest(self, *, label: str, description: str | None) -> list[str]:
        if not self.data_egress_enabled:
            raise DataEgressDisabledError("Gemini axis-term suggestion requires explicit data-egress consent.")
        return self.inner.suggest(label=label, description=description)


@dataclass(frozen=True)
class EgressGatedAxisClusterLabeler:
    """Egress gate around an ``AxisClusterLabeler`` (injected or default)."""

    inner: "AxisClusterLabeler"
    data_egress_enabled: bool

    def label(self, *, titles: list[str], terms: list[str]) -> dict:
        if not self.data_egress_enabled:
            raise DataEgressDisabledError("Gemini axis-cluster labeling requires explicit data-egress consent.")
        return self.inner.label(titles=titles, terms=terms)


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
