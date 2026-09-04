"""Summary generation interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy import Engine


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: int
    paper_id: int
    attachment_id: int
    text: str
    page_start: int
    page_end: int
    chunk_version: str
    bbox_json: object | None = None
    section: str | None = None


@dataclass(frozen=True)
class CandidateCitation:
    chunk_id: int
    quote: str


@dataclass(frozen=True)
class CandidateSummarySentence:
    text: str
    citations: list[CandidateCitation]


class TruncatedGenerationError(RuntimeError):
    """The provider stopped at its output-token ceiling before the model finished answering.

    Carries the claims that WERE completed. Raised rather than returned so the partial answer cannot
    travel any further without a caller deciding what to disclose: a synthesis that is missing claims
    it meant to make must never render as a whole one (PRINCIPLES #6 -- silence is not a certificate).
    It also stops ``CachedSummaryGenerator`` storing a truncated answer under the same key a complete
    one would use, which would make one bad run permanent.
    """

    def __init__(self, *, sentences: list[CandidateSummarySentence]) -> None:
        super().__init__(f"The model's answer was cut off after {len(sentences)} complete claims.")
        self.sentences = sentences


class SummaryGenerator(Protocol):
    name: str

    def generate(
        self,
        *,
        source_chunks: list[SourceChunk],
        scope_ref: dict[str, object],
        engine: "Engine | None" = None,
    ) -> list[CandidateSummarySentence]:
        """Return candidate sentences with LLM-claimed citation hints.

        ``engine`` is an optional handle the cache wrapper uses to open its own short connections
        around the (potentially slow) call below — never held open during it (the real generators
        ignore this parameter entirely).
        """


@dataclass(frozen=True)
class FakeSummaryGenerator:
    sentences: list[CandidateSummarySentence]
    name: str = "fake-summary-generator"

    def generate(
        self,
        *,
        source_chunks: list[SourceChunk],
        scope_ref: dict[str, object],
        engine: "Engine | None" = None,
    ) -> list[CandidateSummarySentence]:
        return list(self.sentences)
