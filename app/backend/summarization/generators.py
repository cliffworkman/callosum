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
