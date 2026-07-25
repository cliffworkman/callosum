"""Grounded citation-gap discovery for My Publications (inc 386).

This is deliberately different from the library gap-finder. It finds external works in the user's co-citation
neighborhood: a candidate cites at least one reference anchor shared by two or more confirmed own publications,
while none of the scanned own publications directly cites the candidate. Every candidate retains the exact shared
reference(s) and own-publication source rows that caused it to surface.

OpenAlex graph coverage is partial. Results are bounded discovery candidates, never importance rankings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection

from app.backend.acquisition.registry import PaperRef
from app.backend.clustering.my_publications_domains import confirmed_member_rows
from app.backend.persistence.repository import find_existing_paper_by_identity

MAX_SCANNED_PUBLICATIONS = 75
MIN_PUBLICATIONS_PER_ANCHOR = 2
MAX_SHARED_ANCHORS = 20
MAX_CANDIDATES = 25
MAX_AUTHORS = 20
MAX_EVIDENCE_SOURCES_PER_ANCHOR = 12
MAX_TITLE_LEN = 1000
MAX_AUTHOR_LEN = 300
MAX_DOI_LEN = 255

_COVERAGE_NOTE = (
    "OpenAlex reference and citing-work coverage is partial, and each shared-reference neighborhood is bounded. "
    "A candidate shares at least one reference cited by two or more scanned publications, and no scanned "
    "publication directly cites it. Results are discovery leads, not an exhaustive list or importance ranking."
)


@dataclass(frozen=True)
class MyPublicationCitationGap:
    openalex_work_id: str
    doi: str | None
    title: str | None
    authors: list[str]
    year: int | None
    shared_reference_count: int
    source_publication_count: int
    evidence: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "openalex_work_id": self.openalex_work_id,
            "doi": self.doi,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "shared_reference_count": self.shared_reference_count,
            "source_publication_count": self.source_publication_count,
            "evidence": self.evidence,
        }


def compute_my_publication_citation_gaps(
    conn: Connection,
    *,
    openalex_client,
    dismissed: set[str],
    max_candidates: int = MAX_CANDIDATES,
) -> tuple[list[MyPublicationCitationGap], dict[str, Any]]:
    """Compute a bounded, evidence-carrying co-citation neighborhood from confirmed own publications."""
    confirmed = confirmed_member_rows(conn)
    dismissed_keys = {str(key).strip().casefold() for key in dismissed if str(key).strip()}
    with_doi = [row for row in confirmed if row.get("doi")]
    scoped = with_doi[:MAX_SCANNED_PUBLICATIONS]
    source_papers = {
        int(row["id"]): {
            "paper_id": int(row["id"]),
            "title": _bounded_text(row.get("title") or "Untitled publication", MAX_TITLE_LEN),
        }
        for row in scoped
    }

    anchor_sources: dict[str, set[int]] = {}
    directly_cited: set[str] = set()
    own_work_ids: set[str] = set()
    for row in scoped:
        paper_id = int(row["id"])
        ref = PaperRef(doi=str(row["doi"]))
        try:
            own_id = openalex_client.fetch_work_id(conn, ref)
            references = openalex_client.fetch_referenced_works(conn, ref)
        except Exception:  # one unavailable OpenAlex record must not abort the remaining bounded scan
            continue
        if own_id and _valid_work_id(own_id):
            own_work_ids.add(own_id)
        for work_id in set(references):
            if not _valid_work_id(work_id):
                continue
            directly_cited.add(work_id)
            anchor_sources.setdefault(work_id, set()).add(paper_id)

    selected_anchor_ids = [
        work_id
        for work_id, _ in sorted(
            (
                (work_id, paper_ids)
                for work_id, paper_ids in anchor_sources.items()
                if len(paper_ids) >= MIN_PUBLICATIONS_PER_ANCHOR
            ),
            key=lambda item: (-len(item[1]), item[0]),
        )[:MAX_SHARED_ANCHORS]
    ]
    anchor_meta = {
        str(meta["openalex_work_id"]): meta
        for meta in openalex_client.fetch_works_by_ids(conn, selected_anchor_ids, with_abstract=False)
        if _valid_work_id(meta.get("openalex_work_id"))
    }

    candidate_meta: dict[str, dict[str, Any]] = {}
    candidate_anchors: dict[str, set[str]] = {}
    for anchor_id in selected_anchor_ids:
        try:
            citing_works = openalex_client.fetch_citing_works(conn, anchor_id)
        except Exception:
            continue
        for meta in citing_works:
            work_id = str(meta.get("openalex_work_id") or "")
            if (
                not _valid_work_id(work_id)
                or work_id in directly_cited
                or work_id in own_work_ids
                or work_id.casefold() in dismissed_keys
                or (meta.get("doi") and str(meta["doi"]).casefold() in dismissed_keys)
            ):
                continue
            if _already_in_library(conn, meta):
                continue
            candidate_meta.setdefault(work_id, meta)
            candidate_anchors.setdefault(work_id, set()).add(anchor_id)

    candidates: list[MyPublicationCitationGap] = []
    for work_id, shared_ids in candidate_anchors.items():
        meta = candidate_meta[work_id]
        evidence: list[dict[str, Any]] = []
        all_source_ids: set[int] = set()
        for anchor_id in sorted(shared_ids, key=lambda aid: (-len(anchor_sources.get(aid, set())), aid)):
            source_ids = sorted(anchor_sources.get(anchor_id, set()))
            all_source_ids.update(source_ids)
            reference = anchor_meta.get(anchor_id) or {}
            evidence.append(
                {
                    "reference_openalex_work_id": anchor_id,
                    "reference_title": _bounded_optional_text(reference.get("title"), MAX_TITLE_LEN),
                    "reference_doi": _bounded_optional_text(reference.get("doi"), MAX_DOI_LEN),
                    "source_papers": [
                        source_papers[paper_id]
                        for paper_id in source_ids[:MAX_EVIDENCE_SOURCES_PER_ANCHOR]
                        if paper_id in source_papers
                    ],
                }
            )
        candidates.append(
            MyPublicationCitationGap(
                openalex_work_id=work_id,
                doi=_bounded_optional_text(meta.get("doi"), MAX_DOI_LEN),
                title=_bounded_optional_text(meta.get("title"), MAX_TITLE_LEN),
                authors=[_bounded_text(author, MAX_AUTHOR_LEN) for author in (meta.get("authors") or [])[:MAX_AUTHORS]],
                year=meta.get("year"),
                shared_reference_count=len(shared_ids),
                source_publication_count=len(all_source_ids),
                evidence=evidence,
            )
        )

    candidates.sort(
        key=lambda candidate: (
            -candidate.shared_reference_count,
            -candidate.source_publication_count,
            (candidate.title or candidate.openalex_work_id).casefold(),
            candidate.openalex_work_id,
        )
    )
    coverage = {
        "checked": len(scoped),
        "with_doi": len(with_doi),
        "total": len(confirmed),
        "shared_anchor_count": len(selected_anchor_ids),
        "publication_cap_reached": len(with_doi) > len(scoped),
        "note": _COVERAGE_NOTE,
    }
    return candidates[: max(1, min(int(max_candidates), MAX_CANDIDATES))], coverage


def _already_in_library(conn: Connection, meta: dict[str, Any]) -> bool:
    authors = [str(author) for author in (meta.get("authors") or []) if str(author).strip()]
    first_family = None
    if authors:
        first_family = (
            authors[0].split(",", 1)[0].strip() if "," in authors[0] else authors[0].rsplit(" ", 1)[-1].strip()
        )
    return (
        find_existing_paper_by_identity(
            conn,
            doi=meta.get("doi"),
            openalex_work_id=meta.get("openalex_work_id"),
            title=meta.get("title"),
            year=meta.get("year"),
            first_author_family_name=first_family,
        )
        is not None
    )


def _valid_work_id(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"W\d+", value) is not None


def _bounded_optional_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _bounded_text(value: Any, limit: int) -> str:
    return _bounded_optional_text(value, limit) or ""
