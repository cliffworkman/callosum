from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class PublicationEvidenceHit:
    chunk_id: int
    attachment_id: int
    document_role: Literal["article-fulltext", "supplement"]
    text: str
    context_text: str
    section: str | None
    section_family: str
    page_start: int
    page_end: int
    bbox: Any
    similarity: float
    search_phase: Literal["expected-sections", "whole-article", "supplement"]


@dataclass(frozen=True)
class CommitmentRetrieval:
    commitment_id: int
    field_type: str
    expected_section_families: tuple[str, ...]
    sections_searched: tuple[str, ...]
    whole_article_expanded: bool
    supplements_searched: bool
    searched_chunk_ids: tuple[int, ...]
    searched_attachment_ids: tuple[int, ...]
    study_mapping: Literal["matched", "unscoped", "ambiguous"]
    study_labels_found: tuple[str, ...]
    hits: tuple[PublicationEvidenceHit, ...]
