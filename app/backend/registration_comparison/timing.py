from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from app.backend.registration_retrieval.domain import PublicationEvidenceHit

_DATE = re.compile(r"\b(19|20)\d{2}(?:[-/][01]\d[-/][0-3]\d)?\b")


def compare_timing(
    registration_value: Mapping[str, Any],
    publication_chunks: Sequence[Mapping],
) -> tuple[str, str, str, PublicationEvidenceHit | None]:
    registered = _parse_date(str(registration_value.get("registered_at") or ""))
    updated = _parse_date(str(registration_value.get("updated_at") or ""))
    dates = _publication_dates(publication_chunks)
    if registered is None:
        return "not-comparable", "timing-unclear", "The registration timestamp could not be parsed.", None
    if registration_value.get("existing_data_collected") is True:
        return (
            "potentially-changed",
            "registration-appears-after-data-collection-began",
            "The registration's own existing-data response indicates that data collection had already begun; "
            "inspect timing and scope.",
            None,
        )
    if not dates:
        return (
            "not-comparable",
            "insufficient-dates-to-compare",
            "No bounded recruitment, data-collection, or analysis date was located in the publication text.",
            None,
        )
    analysis = [item for item in dates if item[0] == "analysis"]
    ended = [item for item in dates if item[0] == "ended"]
    began = [item for item in dates if item[0] == "began"]
    analysis_event = min(analysis, key=lambda item: item[1], default=None)
    ended_event = min(ended, key=lambda item: item[1], default=None)
    began_event = min(began, key=lambda item: item[1], default=None)
    effective = updated if updated is not None and updated > registered else registered
    subject = "The latest recorded registration update" if effective != registered else "The registration timestamp"
    if analysis_event and effective > analysis_event[1]:
        return (
            "potentially-changed",
            "registration-appears-after-analysis",
            f"{subject} appears later than a reported analysis date.",
            _hit_from_chunk(analysis_event[2]),
        )
    if ended_event and effective > ended_event[1]:
        return (
            "potentially-changed",
            "registration-appears-after-data-collection-ended",
            f"{subject} appears later than a reported data-collection end date.",
            _hit_from_chunk(ended_event[2]),
        )
    if began_event and effective > began_event[1]:
        return (
            "potentially-changed",
            "registration-appears-after-data-collection-began",
            f"{subject} appears later than a reported data-collection start date.",
            _hit_from_chunk(began_event[2]),
        )
    first_activity = min(dates, key=lambda item: item[1])
    return (
        "aligned",
        "prospective-timing-supported",
        "The registration timestamp precedes the reported dated research activity in the located passage.",
        _hit_from_chunk(first_activity[2]),
    )


def _publication_dates(chunks: Sequence[Mapping]) -> list[tuple[str, datetime, Mapping]]:
    result = []
    for chunk in chunks:
        text = str(chunk.get("text") or "")
        dates = [_parse_date(match.group(0)) for match in _DATE.finditer(text)]
        dates = [value for value in dates if value is not None]
        if not dates:
            continue
        lowered = text.casefold()
        kind = None
        if "analy" in lowered:
            kind = "analysis"
        elif any(term in lowered for term in ("ended", "completed", "data collection through", "recruited through")):
            kind = "ended"
        elif any(term in lowered for term in ("began", "started", "recruit", "data collection from")):
            kind = "began"
        if kind:
            result.extend((kind, value, chunk) for value in dates)
    return result


def _hit_from_chunk(chunk: Mapping) -> PublicationEvidenceHit:
    return PublicationEvidenceHit(
        chunk_id=int(chunk["id"]),
        attachment_id=int(chunk["attachment_id"]),
        document_role="supplement" if chunk.get("document_role") == "supplement" else "article-fulltext",
        text=str(chunk.get("text") or ""),
        context_text=str(chunk.get("text") or ""),
        section=chunk.get("section"),
        section_family=str(chunk.get("section") or "unknown").casefold(),
        page_start=int(chunk["page_start"]),
        page_end=int(chunk["page_end"]),
        bbox=chunk.get("bbox_json"),
        similarity=1.0,
        search_phase="expected-sections",
    )


def _parse_date(value: str) -> datetime | None:
    match = _DATE.search(value)
    if not match:
        return None
    token = match.group(0).replace("/", "-")
    try:
        return datetime.fromisoformat(token if "-" in token else f"{token}-01-01")
    except ValueError:
        return None
