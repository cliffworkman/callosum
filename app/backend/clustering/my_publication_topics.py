"""Grounded emerging citing topics for My Publications (inc 390).

Two equal three-year windows of OpenAlex citing works are compared. Each citing work contributes only its
OpenAlex primary topic and retains the exact confirmed own publications it cites. The surfaced increase is a
descriptive count over bounded retrieved records, never a forecast, importance score, or completeness claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection

from app.backend.acquisition.registry import PaperRef
from app.backend.clustering.my_publications_domains import confirmed_member_rows
from integrations.openalex.citing_topics import MAX_SOURCE_WORKS

MIN_RECENT_WORKS = 2
MAX_TOPICS = 6
MAX_TITLE_LEN = 1000
MAX_AUTHOR_LEN = 300

_COVERAGE_NOTE = (
    "Counts describe bounded OpenAlex records retrieved in two equal three-year windows. Each citing work is "
    "assigned only to its OpenAlex primary topic. A rise is a descriptive signal, not a forecast, field-wide "
    "trend, exhaustive citation count, or importance ranking."
)


@dataclass(frozen=True)
class EmergingCitingTopic:
    topic_id: str
    name: str
    subfield: str | None
    field: str | None
    domain: str | None
    recent_count: int
    previous_count: int
    increase: int
    recent_works: list[dict[str, Any]]
    previous_works: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "name": self.name,
            "subfield": self.subfield,
            "field": self.field,
            "domain": self.domain,
            "recent_count": self.recent_count,
            "previous_count": self.previous_count,
            "increase": self.increase,
            "recent_works": self.recent_works,
            "previous_works": self.previous_works,
        }


def compute_emerging_citing_topics(
    conn: Connection,
    *,
    openalex_client,
    topic_client,
    paper_ids: set[int] | frozenset[int] | None = None,
    current_year: int | None = None,
    max_topics: int = MAX_TOPICS,
) -> tuple[list[EmergingCitingTopic], dict[str, Any]]:
    """Compute evidence-carrying primary-topic increases over the last two complete three-year windows."""
    all_confirmed = confirmed_member_rows(conn)
    confirmed = (
        [row for row in all_confirmed if int(row["id"]) in paper_ids] if paper_ids is not None else all_confirmed
    )
    with_doi = [row for row in confirmed if row.get("doi")]
    scoped = with_doi[:MAX_SOURCE_WORKS]

    source_papers: dict[str, list[dict[str, Any]]] = {}
    resolved_publication_count = 0
    for row in scoped:
        try:
            work_id = openalex_client.fetch_work_id(conn, PaperRef(doi=str(row["doi"])))
        except Exception:
            continue
        if not _valid_work_id(work_id):
            continue
        resolved_publication_count += 1
        source_papers.setdefault(work_id, []).append(
            {
                "paper_id": int(row["id"]),
                "title": _bounded_text(row.get("title") or "Untitled publication", MAX_TITLE_LEN),
            }
        )
    if scoped and not source_papers:
        raise RuntimeError("No scoped publications could be resolved in OpenAlex; prior topic snapshot preserved.")

    year = int(current_year or datetime.now(timezone.utc).year)
    recent_end = year - 1
    recent_start = recent_end - 2
    previous_end = recent_start - 1
    previous_start = previous_end - 2
    source_work_ids = sorted(source_papers)
    recent_raw, recent_capped = topic_client.fetch_window(
        conn,
        source_work_ids,
        start_year=recent_start,
        end_year=recent_end,
    )
    previous_raw, previous_capped = topic_client.fetch_window(
        conn,
        source_work_ids,
        start_year=previous_start,
        end_year=previous_end,
    )

    periods = {
        "recent": _valid_window_works(recent_raw, source_papers, recent_start, recent_end),
        "previous": _valid_window_works(previous_raw, source_papers, previous_start, previous_end),
    }
    topic_rows: dict[str, dict[str, Any]] = {}
    missing_topic = 0
    for period, works in periods.items():
        for work in works:
            topic = work.get("primary_topic")
            if not _valid_topic(topic):
                missing_topic += 1
                continue
            topic_id = str(topic["id"])
            row = topic_rows.setdefault(
                topic_id,
                {
                    "topic": topic,
                    "recent": {},
                    "previous": {},
                },
            )
            row[period][work["openalex_work_id"]] = _evidence_work(work, source_papers)

    topics: list[EmergingCitingTopic] = []
    for topic_id, row in topic_rows.items():
        recent_works = sorted(row["recent"].values(), key=_work_sort_key)
        previous_works = sorted(row["previous"].values(), key=_work_sort_key)
        recent_count = len(recent_works)
        previous_count = len(previous_works)
        if recent_count < MIN_RECENT_WORKS or recent_count <= previous_count:
            continue
        topic = row["topic"]
        topics.append(
            EmergingCitingTopic(
                topic_id=topic_id,
                name=_bounded_text(topic["name"], 300),
                subfield=_bounded_optional_text(topic.get("subfield"), 300),
                field=_bounded_optional_text(topic.get("field"), 300),
                domain=_bounded_optional_text(topic.get("domain"), 300),
                recent_count=recent_count,
                previous_count=previous_count,
                increase=recent_count - previous_count,
                recent_works=recent_works,
                previous_works=previous_works,
            )
        )
    topics.sort(key=lambda topic: (-topic.increase, -topic.recent_count, topic.name.casefold(), topic.topic_id))
    coverage = {
        "checked": resolved_publication_count,
        "with_doi": len(with_doi),
        "total": len(confirmed),
        "library_total": len(all_confirmed),
        "unresolved_openalex_count": len(scoped) - resolved_publication_count,
        "recent_start_year": recent_start,
        "recent_end_year": recent_end,
        "previous_start_year": previous_start,
        "previous_end_year": previous_end,
        "recent_work_count": len(periods["recent"]),
        "previous_work_count": len(periods["previous"]),
        "missing_primary_topic_count": missing_topic,
        "publication_cap_reached": len(with_doi) > len(scoped),
        "recent_window_cap_reached": recent_capped,
        "previous_window_cap_reached": previous_capped,
        "note": _COVERAGE_NOTE,
    }
    return topics[: max(1, min(int(max_topics), MAX_TOPICS))], coverage


def _valid_window_works(
    works: list[dict[str, Any]],
    source_papers: dict[str, list[dict[str, Any]]],
    start_year: int,
    end_year: int,
) -> list[dict[str, Any]]:
    valid: dict[str, dict[str, Any]] = {}
    for work in works:
        work_id = work.get("openalex_work_id")
        year = work.get("year")
        if not _valid_work_id(work_id) or not isinstance(year, int) or not start_year <= year <= end_year:
            continue
        source_ids = [
            source_id
            for source_id in work.get("cited_source_work_ids") or []
            if _valid_work_id(source_id) and source_id in source_papers
        ]
        if not source_ids:
            continue
        valid[work_id] = {**work, "cited_source_work_ids": sorted(set(source_ids))}
    return list(valid.values())


def _evidence_work(
    work: dict[str, Any],
    source_papers: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    cited_publications = [
        paper for source_id in work["cited_source_work_ids"] for paper in source_papers.get(source_id, [])
    ]
    return {
        "openalex_work_id": work["openalex_work_id"],
        "doi": _bounded_optional_text(work.get("doi"), 255),
        "title": _bounded_optional_text(work.get("title"), MAX_TITLE_LEN),
        "year": work.get("year"),
        "authors": [
            _bounded_text(author, MAX_AUTHOR_LEN)
            for author in (work.get("authors") or [])[:8]
            if _bounded_text(author, MAX_AUTHOR_LEN)
        ],
        "cited_publications": cited_publications,
    }


def _work_sort_key(work: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(work.get("year") or 0),
        str(work.get("title") or work.get("openalex_work_id") or "").casefold(),
        str(work.get("openalex_work_id") or ""),
    )


def _valid_work_id(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"W\d+", value) is not None


def _valid_topic(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("name"), str)
        and bool(value["name"].strip())
        and isinstance(value.get("id"), str)
        and re.fullmatch(r"T\d+", value["id"]) is not None
    )


def _bounded_optional_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _bounded_text(value: Any, limit: int) -> str:
    return _bounded_optional_text(value, limit) or ""
