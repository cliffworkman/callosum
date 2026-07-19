"""Discovery search + save (backlog #28, inc 183). `run_search` fans out to the registry, dedups across providers,
and marks `in_library`. `save_item` creates a metadata-only library paper (deduped) — **no PDF fetch** (acquisition
stays the OA lane). The complete result list is returned (no filtering — relevance highlight is SP1b)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy import Connection

from app.backend.discovery.providers import Item, SourceRegistry
from app.backend.persistence.repository import create_paper, find_existing_paper_by_identity

DISCOVERY_SOURCE = "discovery-import"  # kept out of enrichment's crossref-update allowlist (like user-edited)


def _first_family(authors: tuple[str, ...]) -> str | None:
    if not authors:
        return None
    return authors[0].split(",")[0].strip() or None


def _csl_author(name: str) -> dict[str, str]:
    if "," in name:
        family, _, given = name.partition(",")
        return {"family": family.strip(), "given": given.strip()}
    return {"family": name.strip()}


def run_search(
    conn: Connection, registry: SourceRegistry, query: str, limit: int = 25, source: str | None = None
) -> list[Item]:
    """Fan out, or query one selected provider, then dedup + mark `in_library`. Order preserved."""
    merged: dict[str, Item] = {}
    order: list[str] = []
    source_name = (source or "").strip().lower()
    try:
        found = registry.search_one(source_name, query, limit) if source_name else registry.search_all(query, limit)
    except KeyError as exc:
        raise ValueError(f"Unknown discovery source: {source_name}") from exc
    for item in found:
        key = item.dedup_key
        if key in merged:
            merged[key] = merged[key].merged_with(item)
        else:
            merged[key] = item
            order.append(key)
    items = [merged[k] for k in order][:limit]
    out: list[Item] = []
    for item in items:
        existing = find_existing_paper_by_identity(
            conn, doi=item.doi, title=item.title, year=item.year, first_author_family_name=_first_family(item.authors)
        )
        out.append(replace(item, in_library=existing is not None))
    return out


def save_item(
    conn: Connection,
    *,
    title: str,
    doi: str | None = None,
    pmid: str | None = None,
    abstract: str | None = None,
    authors: list[str] | None = None,
    journal: str | None = None,
    year: int | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Create a metadata-only library paper from a discovery item (deduped). Returns {paper_id, created}.
    A `pmid` (inc 307) is stored in the CSL so a later/background enrich can drive PubMed MeSH keyword tags."""
    author_tuple = tuple(authors or ())
    first_family = _first_family(author_tuple)
    existing = find_existing_paper_by_identity(
        conn, doi=doi, title=title, year=year, first_author_family_name=first_family
    )
    if existing is not None:
        return {"paper_id": int(existing[1]["id"]), "created": False}
    clean_pmid = "".join(ch for ch in str(pmid or "") if ch.isdigit()) or None
    csl: dict[str, Any] = {
        "type": "article-journal",
        "title": title,
        "author": [_csl_author(a) for a in author_tuple],
        "container-title": journal,
        "DOI": doi,
        "PMID": clean_pmid,
        "URL": url,
    }
    if year:
        csl["issued"] = {"date-parts": [[year]]}
    csl = {k: v for k, v in csl.items() if v}
    paper_id = create_paper(
        conn,
        title=title,
        csl_json=csl,
        abstract=abstract,
        year=year,
        doi=doi,
        venue=journal,
        item_type="article-journal",
        first_author_family_name=first_family,
        imported_source=DISCOVERY_SOURCE,
    )
    return {"paper_id": int(paper_id), "created": True}
