"""Metadata enrichment orchestration for raw PDF scaffold papers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, select

from app.backend.metadata.doi import DoiCandidate, find_doi_in_pdf
from app.backend.metadata.enrich_sources import EnrichmentRegistry, EnrichRef, build_default_enrich_registry
from app.backend.persistence.repository import (
    find_existing_paper_by_identity,
    refresh_processing_tier,
    update_paper_metadata,
)
from app.backend.persistence.schema import attachments, papers
from app.backend.persistence.tags_repo import add_tags_to_paper, suppressed_tag_names
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
# Provenance for a record produced by merging duplicate papers (inc 161). Like USER_EDITED_SOURCE, kept OUT of
# the `_can_update_from_crossref` allowlist so a batch enrich won't clobber the user's curated merge.
MERGED_SOURCE = "merged"
# Provenance for anything an MCP agent wrote (B1 SP2). Kept OUT of the `_can_update_from_crossref` allowlist (a
# batch enrich won't clobber it) AND makes agent-origin visible/filterable (the inc-100 tag-source styling).
AI_AGENT_SOURCE = "ai-agent"


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
    suppressed = suppressed_tag_names(conn, paper_id)  # inc 143: don't re-add a keyword the librarian deleted
    keep = [s for s in subjects if str(s).strip() and str(s).strip() not in suppressed]
    add_tags_to_paper(conn, paper_id, keep, import_source=CROSSREF_KEYWORD_SOURCE)
    return [str(s).strip() for s in keep]


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


# --- Multi-pass, gap-filling enrichment (inc 217) -------------------------------------------------------------
# A SEPARATE path from `enrich_paper_metadata_from_crossref` (wholesale overwrite, left unchanged for the
# re-resolve / scan / OA-acquire / my-pubs callers). This one recovers a missing DOI then fills ONLY a paper's
# empty fields from a source cascade — never overwriting a value already present, never downgrading the
# provenance of a hand-edited / merged / agent record (so it's safe to run library-wide over every paper).


@dataclass(frozen=True)
class MultiEnrichResult:
    paper_id: int
    doi: str | None
    doi_recovered: bool
    filled_fields: tuple[str, ...]
    still_missing_doi: bool


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def gap_merge(existing: dict[str, Any], fragments: list[dict[str, Any]]) -> dict[str, Any]:
    """Fill only the keys absent/empty in `existing` from the CSL fragments, in order (the `Item.merged_with`
    self.x-or-other.x pattern, generalized to a dict). Never overwrites a populated key. `DOI` is handled by the
    caller (the UNIQUE column + the duplicate guard), so it's left out of the merge."""
    merged = dict(existing or {})
    for fragment in fragments:
        for key, value in fragment.items():
            if key == "DOI":
                continue
            if _is_empty(merged.get(key)) and not _is_empty(value):
                merged[key] = value
    return merged


def _gap_fill_columns(paper: Any, merged: dict[str, Any]) -> dict[str, Any]:
    """Project `merged` CSL → scalar columns, returning ONLY columns currently empty on the paper (gap-fill).
    Excludes `doi` + `imported_source` (the orchestrator handles those); `title` is NOT NULL so it never fills."""
    date_parts = _date_parts(merged)
    candidates = {
        "abstract": merged.get("abstract"),
        "year": date_parts[0] if date_parts else None,
        "venue": merged.get("container-title"),
        "item_type": merged.get("type"),
        "publication_date": "-".join(str(part) for part in date_parts) if date_parts else None,
        "first_author_family_name": _first_author_family(merged),
    }
    return {col: val for col, val in candidates.items() if _is_empty(paper[col]) and not _is_empty(val)}


def _titles_match(a: str | None, b: str | None) -> bool:
    """Conservative match for DOI recovery: normalized-title equality, else token-Jaccard >= 0.7."""
    from app.backend.discovery.providers import normalized_title

    na, nb = normalized_title(a), normalized_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.7


def _years_compatible(a: int | None, b: int | None) -> bool:
    return a is None or b is None or int(a) == int(b)


def _pmid_from_csl(csl_json: dict[str, Any]) -> str | None:
    pmid = csl_json.get("PMID") if isinstance(csl_json, dict) else None
    if not pmid:
        return None
    return "".join(ch for ch in str(pmid) if ch.isdigit()) or None


def enrich_paper_metadata_multi(
    conn: Connection,
    paper_id: int,
    *,
    registry: EnrichmentRegistry | None = None,
    search_provider: Any | None = None,
) -> MultiEnrichResult:
    """Multi-pass, GAP-FILLING enrichment of one paper (inc 217). See the module note above for the contract."""
    if registry is None:
        registry = build_default_enrich_registry()
    if search_provider is None:
        from app.backend.discovery.crossref_provider import CrossrefSearchProvider

        search_provider = CrossrefSearchProvider()

    paper = conn.execute(select(papers).where(papers.c.id == paper_id)).mappings().one()
    existing_csl = dict(paper["csl_json"] or {})
    title = paper["title"]
    paper_year = paper["year"]

    # Pass 0 — recover a missing DOI (PDF scan → Crossref title-search; a recovered DOI that belongs to a
    # DIFFERENT paper is left for dedup, honoring the papers.doi UNIQUE constraint).
    doi = str(paper["doi"]) if paper["doi"] else None
    pmid = _pmid_from_csl(existing_csl)
    doi_recovered = False
    if not doi:
        candidate = _doi_for_paper(conn, paper_id, existing_doi=None)
        recovered = candidate.doi if candidate else None
        if not recovered and title:
            try:
                items = search_provider.search(title, 5)
            except Exception:
                items = []
            for item in items:
                if item.doi and _titles_match(title, item.title) and _years_compatible(paper_year, item.year):
                    recovered = item.doi
                    pmid = pmid or item.pmid
                    break
        if recovered:
            hit = find_existing_paper_by_identity(conn, doi=recovered)
            if hit is None or int(hit[1]["id"]) == paper_id:
                doi = recovered.strip().lower()
                doi_recovered = True

    # Cascade — gap-fill from each source, in order.
    fragments = registry.fetch_all(conn, EnrichRef(doi=doi, pmid=pmid, title=title, year=paper_year))
    merged = gap_merge(existing_csl, fragments)
    if doi:
        merged["DOI"] = doi  # the guarded effective DOI; a fragment's DOI never sets this

    gap_cols = _gap_fill_columns(paper, merged)
    updates: dict[str, Any] = {"csl_json": merged, **gap_cols}
    filled = list(gap_cols.keys())
    if doi and _is_empty(paper["doi"]):
        updates["doi"] = doi
        filled.append("doi")

    # Provenance — never downgrade a curated record; mark a freshly-enriched scaffold.
    source = paper["imported_source"]
    if source not in {USER_EDITED_SOURCE, MERGED_SOURCE, AI_AGENT_SOURCE}:
        if doi or filled:
            updates["imported_source"] = CROSSREF_SOURCE
        elif source in {PDF_SCAFFOLD_SOURCE, None}:
            updates["imported_source"] = CROSSREF_UNRESOLVED_SOURCE

    update_paper_metadata(conn, paper_id, **updates)
    apply_crossref_subject_tags(conn, paper_id, merged)
    _hook_my_publications(conn, paper_id)
    refresh_processing_tier(conn, paper_id)
    return MultiEnrichResult(
        paper_id=paper_id,
        doi=doi,
        doi_recovered=doi_recovered,
        filled_fields=tuple(filled),
        still_missing_doi=doi is None,
    )
