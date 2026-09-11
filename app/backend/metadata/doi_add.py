"""Add a paper to the Library by DOI — the shared identity-resolution primitive (backlog #58).

One implementation of "resolve a DOI to a real record and add it (or surface the existing one)", used by
BOTH the Library "Add with DOI…" endpoint and the MCP agent's save-reference tool, so there is no
DOI-specific metadata silo. It is metadata-only and provider-honest: an unresolvable DOI creates nothing
(never an invented placeholder record). Open-access full-text acquisition is a SEPARATE step the caller
orchestrates on the created paper — this helper never fetches a PDF, so a failed download can never
masquerade as a failed DOI import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection

from app.backend.metadata.doi import normalize_doi
from app.backend.metadata.enrichment import _paper_values_from_csl
from app.backend.persistence.repository import create_paper, find_existing_paper_by_identity


@dataclass(frozen=True)
class DoiAddResult:
    """The outcome of a DOI add. ``status`` is machine-readable:

    * ``created``  — a new metadata record was created from resolved Crossref metadata.
    * ``existing`` — a paper with this DOI is already in the Library (surfaced, never duplicated).
    * ``invalid``  — the input is not a DOI at all (nothing created).
    * ``unresolved`` — a syntactically-valid DOI that Crossref could not resolve (nothing created).
    """

    status: str
    paper_id: int | None = None
    doi: str | None = None
    title: str | None = None
    error: str | None = None


def add_paper_by_doi(
    conn: Connection, raw_doi: str, *, crossref_client: Any | None, imported_source: str
) -> DoiAddResult:
    """Normalize → duplicate check → Crossref resolve → create (or surface existing). No PDF fetch, no
    commit (the caller owns the transaction)."""
    doi = normalize_doi(raw_doi)
    if doi is None:
        return DoiAddResult(status="invalid", error="That does not look like a valid DOI.")
    existing = find_existing_paper_by_identity(conn, doi=doi)
    if existing is not None:
        row = existing[1]
        return DoiAddResult(status="existing", paper_id=int(row["id"]), doi=doi, title=row["title"])
    resolution = crossref_client.resolve_doi(conn, doi) if crossref_client is not None else None
    if resolution is None or not resolution.resolved or not resolution.csl_json:
        error = resolution.error if resolution is not None else "no metadata provider configured"
        return DoiAddResult(status="unresolved", doi=doi, error=error)
    # Build straight from the resolved CSL so the provenance stamp survives (no second enrichment pass).
    values = _paper_values_from_csl({**resolution.csl_json, "DOI": doi}, imported_source=imported_source)
    paper_id = create_paper(conn, **values)
    return DoiAddResult(status="created", paper_id=paper_id, doi=doi, title=values.get("title"))
