"""Metadata enrichment orchestration for raw PDF scaffold papers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, select

from app.backend.metadata.doi import DoiCandidate, find_doi_in_pdf
from app.backend.persistence.repository import refresh_processing_tier, update_paper_metadata
from app.backend.persistence.schema import attachments, papers
from app.backend.persistence.tags_repo import add_tags_to_paper
from integrations.crossref import CrossrefClient

PDF_SCAFFOLD_SOURCE = "pdf-scaffold"
CROSSREF_SOURCE = "crossref"
CROSSREF_UNRESOLVED_SOURCE = "crossref-unresolved"
# Provenance for tags imported from a paper's Crossref subject categories (inc 73) — author/index keywords
# as first-order tags (the inc-72 c-TF-IDF suggester is the second-order gap-filler).
CROSSREF_KEYWORD_SOURCE = "keyword:crossref"
# Provenance for a hand-edited record (inc 49). Deliberately NOT in the
# `_can_update_from_crossref` allowlist, so the batch library enrich won't
# silently clobber a user's edits; the explicit per-paper re-resolve passes
# force=True to override this when the user asks for a fresh Crossref fetch.
USER_EDITED_SOURCE = "user-edited"


@dataclass(frozen=True)
class MetadataEnrichmentResult:
    paper_id: int
    status: str
    doi: str | None
    doi_source: str | None
    processing_tier: str
    error: str | None = None


@dataclass(frozen=True)
class MetadataEnrichmentRunResult:
    resolved: int
    unresolved: int
    skipped: int
    results: list[MetadataEnrichmentResult]


def enrich_pdf_scaffold_library(
    conn: Connection,
    *,
    crossref_client: CrossrefClient | None = None,
) -> MetadataEnrichmentRunResult:
    client = crossref_client or CrossrefClient()
    results = [
        enrich_paper_metadata_from_crossref(conn, int(row["id"]), crossref_client=client)
        for row in conn.execute(select(papers.c.id).order_by(papers.c.id)).mappings()
    ]
    return MetadataEnrichmentRunResult(
        resolved=sum(1 for result in results if result.status == "resolved"),
        unresolved=sum(1 for result in results if result.status == "unresolved"),
        skipped=sum(1 for result in results if result.status == "skipped"),
        results=results,
    )


def enrich_paper_metadata_from_crossref(
    conn: Connection,
    paper_id: int,
    *,
    crossref_client: CrossrefClient | None = None,
    force: bool = False,
) -> MetadataEnrichmentResult:
    client = crossref_client or CrossrefClient()
    paper = conn.execute(select(papers).where(papers.c.id == paper_id)).mappings().one()
    if not force and not _can_update_from_crossref(paper):
        tier = refresh_processing_tier(conn, paper_id)
        return MetadataEnrichmentResult(
            paper_id=paper_id, status="skipped", doi=paper["doi"], doi_source=None, processing_tier=tier
        )

    doi_candidate = _doi_for_paper(conn, paper_id, existing_doi=paper["doi"])
    if doi_candidate is None:
        update_paper_metadata(conn, paper_id, imported_source=CROSSREF_UNRESOLVED_SOURCE)
        tier = refresh_processing_tier(conn, paper_id)
        return MetadataEnrichmentResult(
            paper_id=paper_id, status="unresolved", doi=None, doi_source=None, processing_tier=tier
        )

    resolution = client.resolve_doi(conn, doi_candidate.doi)
    if not resolution.resolved or resolution.csl_json is None:
        update_paper_metadata(
            conn,
            paper_id,
            imported_source=CROSSREF_UNRESOLVED_SOURCE,
        )
        tier = refresh_processing_tier(conn, paper_id)
        return MetadataEnrichmentResult(
            paper_id=paper_id,
            status="unresolved",
            doi=doi_candidate.doi,
            doi_source=doi_candidate.source,
            processing_tier=tier,
            error=resolution.error,
        )

    update_paper_metadata(
        conn,
        paper_id,
        **_paper_values_from_csl(resolution.csl_json, imported_source=CROSSREF_SOURCE),
    )
    apply_crossref_subject_tags(conn, paper_id, resolution.csl_json)
    _hook_my_publications(
        conn, paper_id
    )  # inc 78: incremental My Publications add (cache-based; additive no-op when unused)
    tier = refresh_processing_tier(conn, paper_id)
    return MetadataEnrichmentResult(
        paper_id=paper_id,
        status="resolved",
        doi=doi_candidate.doi,
        doi_source=doi_candidate.source,
        processing_tier=tier,
    )


def _hook_my_publications(conn: Connection, paper_id: int) -> None:
    """Add a newly enriched paper to the My Publications axis if it matches the resolved author (cache-based,
    zero extra egress). Best-effort + lazy-imported: it must never alter or break import/enrichment behavior."""
    try:
        from app.backend.clustering.my_publications import maybe_add_to_my_publications

        maybe_add_to_my_publications(conn, paper_id)
    except Exception:
        pass


def apply_crossref_subject_tags(conn: Connection, paper_id: int, csl_json: dict[str, Any] | None) -> list[str]:
    """Import a resolved record's Crossref `subject` categories as `keyword:crossref` tags (additive,
    idempotent; never touches paper metadata, so it's safe for user-edited papers). Returns the names added.
    Reused by the per-paper re-resolve path above and the library-wide backfill tool."""
    subjects = (csl_json or {}).get("subject")
    if not isinstance(subjects, list) or not subjects:
        return []
    add_tags_to_paper(conn, paper_id, subjects, import_source=CROSSREF_KEYWORD_SOURCE)
    return [str(s).strip() for s in subjects if str(s).strip()]


def _doi_for_paper(conn: Connection, paper_id: int, *, existing_doi: str | None) -> DoiCandidate | None:
    if existing_doi:
        return DoiCandidate(doi=str(existing_doi), source="paper-doi")
    for attachment in conn.execute(
        select(attachments).where(
            attachments.c.paper_id == paper_id,
            attachments.c.content_type == "application/pdf",
            attachments.c.availability == "available",
        )
    ).mappings():
        path = attachment["resolved_path"] or attachment["original_path"]
        if not path or not Path(path).exists():
            continue
        candidate = find_doi_in_pdf(path)
        if candidate is not None:
            return candidate
    return None


def _can_update_from_crossref(paper: Any) -> bool:
    source = paper["imported_source"]
    if source in {PDF_SCAFFOLD_SOURCE, CROSSREF_SOURCE, CROSSREF_UNRESOLVED_SOURCE, None}:
        return True
    return False


def _paper_values_from_csl(csl_json: dict[str, Any], *, imported_source: str) -> dict[str, Any]:
    date_parts = _date_parts(csl_json)
    return {
        "title": str(csl_json.get("title") or csl_json.get("DOI") or "Untitled Crossref Work"),
        "abstract": csl_json.get("abstract"),
        "year": date_parts[0] if date_parts else None,
        "doi": str(csl_json.get("DOI") or csl_json.get("doi") or "").lower() or None,
        "venue": csl_json.get("container-title"),
        "item_type": csl_json.get("type"),
        "publication_date": "-".join(str(part) for part in date_parts) if date_parts else None,
        "first_author_family_name": _first_author_family(csl_json),
        "imported_source": imported_source,
        "csl_json": csl_json,
    }


def _date_parts(csl_json: dict[str, Any]) -> list[int] | None:
    issued = csl_json.get("issued")
    if not isinstance(issued, dict):
        return None
    date_parts = issued.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts:
        return None
    first = date_parts[0]
    return [int(item) for item in first] if isinstance(first, list) and first else None


def _first_author_family(csl_json: dict[str, Any]) -> str | None:
    authors = csl_json.get("author")
    if not isinstance(authors, list) or not authors:
        return None
    first = authors[0]
    if not isinstance(first, dict):
        return None
    family = first.get("family")
    return str(family) if family else None
