"""Summary generation interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy import Connection


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
        conn: "Connection | None" = None,
    ) -> list[CandidateSummarySentence]:
        """Return candidate sentences with LLM-claimed citation hints.

        ``conn`` is an optional read/write handle the cache wrapper uses (the real generators ignore it).
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
        conn: "Connection | None" = None,
    ) -> list[CandidateSummarySentence]:
        return list(self.sentences)
