from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ComparisonProposal:
    commitment_id: int | None
    field_type: str
    registration_value: dict[str, Any] | None
    registration_evidence_text: str | None
    registration_source_locator: dict[str, Any] | None
    publication_value: dict[str, Any] | None
    publication_evidence_text: str | None
    publication_source_locator: dict[str, Any] | None
    comparison_status: str
    timing_status: str | None
    explanation: str
    uncertainty: str
    search_scope: dict[str, Any]
    publication_attachment_id: int | None
    publication_attachment_checksum: str | None
