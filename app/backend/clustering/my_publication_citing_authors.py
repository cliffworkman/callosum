"""Grounded authors-citing-your-work evidence for My Publications (inc 391).

Candidates are stable OpenAlex author identities who appear on at least two bounded citing works that, together,
cite at least two confirmed own publications. The user's OpenAlex identity and coauthors found on the checked own
works are excluded. This is an inspectable reading lead, never a compatibility or collaboration verdict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection

from app.backend.acquisition.registry import PaperRef
from app.backend.clustering.my_publications_domains import confirmed_member_rows
from app.backend.persistence.profile_repo import get_profile
from integrations.openalex.citing_topics import MAX_AUTHOR_RECORDS, MAX_SOURCE_WORKS

MIN_CITING_WORKS = 2
MIN_CITED_PUBLICATIONS = 2
MAX_CITING_AUTHORS = 12
MAX_TITLE_LEN = 1000
MAX_AUTHOR_NAME_LEN = 300

_COVERAGE_NOTE = (
    "This private index describes authorships on bounded OpenAlex records from the last six complete years. "
    "It surfaces repeated citation connections, not collaboration fit, availability, endorsement, or a "
    "recommendation. 'No coauthorship found' applies only to the checked OpenAlex authorships and is not proof "
    "that two people have never worked together."
)


@dataclass(frozen=True)
class CitingAuthor:
    author_id: str
    name: str
    citing_work_count: int
    cited_publication_count: int
    latest_year: int
    citing_works: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "author_id": self.author_id,
            "name": self.name,
            "citing_work_count": self.citing_work_count,
            "cited_publication_count": self.cited_publication_count,
            "latest_year": self.latest_year,
            "citing_works": self.citing_works,
        }


def compute_citing_authors(
    conn: Connection,
    *,
    openalex_client,
    citing_client,
    paper_ids: set[int] | frozenset[int] | None = None,
    current_year: int | None = None,
    max_authors: int = MAX_CITING_AUTHORS,
) -> tuple[list[CitingAuthor], dict[str, Any]]:
    """Compute evidence-carrying repeated citation connections over two equal three-year windows."""
    profile = get_profile(conn) or {}
    self_author_id = str(profile.get("openalex_author_id") or "").rsplit("/", 1)[-1]
    if not _valid_author_id(self_author_id):
        raise RuntimeError("Resolve your OpenAlex author profile before scanning citing authors.")

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
        raise RuntimeError("No scoped publications could be resolved in OpenAlex; prior author snapshot preserved.")

    year = int(current_year or datetime.now(timezone.utc).year)
    recent_end = year - 1
    recent_start = recent_end - 2
    earlier_end = recent_start - 1
    earlier_start = earlier_end - 2
    source_work_ids = sorted(source_papers)
    recent_raw, recent_capped = citing_client.fetch_window(
        conn,
        source_work_ids,
        start_year=recent_start,
        end_year=recent_end,
    )
    earlier_raw, earlier_capped = citing_client.fetch_window(
        conn,
        source_work_ids,
        start_year=earlier_start,
        end_year=earlier_end,
    )
    source_authorships = citing_client.fetch_source_authorships(conn, source_work_ids)

    coauthor_ids: set[str] = set()
    source_authorship_cap_count = 0
    for source in source_authorships.values():
        if source.get("authorship_cap_reached"):
            source_authorship_cap_count += 1
        for author in source.get("authors") or []:
            author_id = author.get("id")
            if _valid_author_id(author_id) and author_id != self_author_id:
                coauthor_ids.add(author_id)

    works = _valid_window_works(recent_raw, source_papers, recent_start, recent_end)
    works.extend(_valid_window_works(earlier_raw, source_papers, earlier_start, earlier_end))
    candidates: dict[str, dict[str, Any]] = {}
    missing_author_id_count = 0
    citing_authorship_cap_count = 0
    for work in works:
        author_records = work.get("author_records") or []
        authorship_count = _bounded_nonnegative_int(work.get("authorship_count"), 100)
        missing_author_id_count += max(0, authorship_count - len(author_records))
        if authorship_count > MAX_AUTHOR_RECORDS:
            citing_authorship_cap_count += 1
        evidence = _evidence_work(work, source_papers)
        for author in author_records:
            author_id = author.get("id")
            if not _valid_author_id(author_id) or author_id == self_author_id or author_id in coauthor_ids:
                continue
            row = candidates.setdefault(
                author_id,
                {
                    "name": _bounded_text(author.get("name"), MAX_AUTHOR_NAME_LEN),
                    "works": {},
                },
            )
            if not row["name"]:
                row["name"] = author_id
            row["works"][work["openalex_work_id"]] = evidence

    surfaced: list[CitingAuthor] = []
    for author_id, row in candidates.items():
        citing_works = sorted(row["works"].values(), key=_work_sort_key)
        cited_publications = {int(source["paper_id"]) for work in citing_works for source in work["cited_publications"]}
        if len(citing_works) < MIN_CITING_WORKS or len(cited_publications) < MIN_CITED_PUBLICATIONS:
            continue
        surfaced.append(
            CitingAuthor(
                author_id=author_id,
                name=row["name"],
                citing_work_count=len(citing_works),
                cited_publication_count=len(cited_publications),
                latest_year=max(int(work["year"]) for work in citing_works),
                citing_works=citing_works,
            )
        )
    surfaced.sort(
        key=lambda author: (
            -author.cited_publication_count,
            -author.citing_work_count,
            author.name.casefold(),
            author.author_id,
        )
    )
    coverage = {
        "checked": resolved_publication_count,
        "with_doi": len(with_doi),
        "total": len(confirmed),
        "library_total": len(all_confirmed),
        "unresolved_openalex_count": len(scoped) - resolved_publication_count,
        "start_year": earlier_start,
        "end_year": recent_end,
        "citing_work_count": len(works),
        "coauthor_checked_publication_count": len(source_authorships),
        "coauthor_unresolved_publication_count": len(source_work_ids) - len(source_authorships),
        "excluded_coauthor_count": len(coauthor_ids),
        "missing_author_id_count": missing_author_id_count,
        "source_authorship_cap_count": source_authorship_cap_count,
        "citing_authorship_cap_count": citing_authorship_cap_count,
        "publication_cap_reached": len(with_doi) > len(scoped),
        "citing_window_cap_reached": recent_capped or earlier_capped,
        "note": _COVERAGE_NOTE,
    }
    return surfaced[: max(1, min(int(max_authors), MAX_CITING_AUTHORS))], coverage


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
        source_ids = sorted(
            {
                source_id
                for source_id in work.get("cited_source_work_ids") or []
                if _valid_work_id(source_id) and source_id in source_papers
            }
        )
        if not source_ids:
            continue
        valid[work_id] = {**work, "cited_source_work_ids": source_ids}
    return list(valid.values())


def _evidence_work(
    work: dict[str, Any],
    source_papers: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    cited_publications = {
        int(paper["paper_id"]): paper
        for source_id in work["cited_source_work_ids"]
        for paper in source_papers.get(source_id, [])
    }
    return {
        "openalex_work_id": work["openalex_work_id"],
        "doi": _bounded_optional_text(work.get("doi"), 255),
        "title": _bounded_optional_text(work.get("title"), MAX_TITLE_LEN),
        "year": int(work["year"]),
        "cited_publications": sorted(
            cited_publications.values(),
            key=lambda paper: (paper["title"].casefold(), paper["paper_id"]),
        ),
    }


def _work_sort_key(work: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(work.get("year") or 0),
        str(work.get("title") or work.get("openalex_work_id") or "").casefold(),
        str(work.get("openalex_work_id") or ""),
    )


def _valid_work_id(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"W\d+", value) is not None


def _valid_author_id(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"A\d+", value) is not None


def _bounded_nonnegative_int(value: Any, limit: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(parsed, limit))


def _bounded_optional_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _bounded_text(value: Any, limit: int) -> str:
    return _bounded_optional_text(value, limit) or ""
