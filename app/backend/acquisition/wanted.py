"""The OA wanted-list re-check service (inc 76) — runs the resolver cascade over open wants and auto-acquires.

Kept out of the router so it is directly testable (inject a fake registry + fake download/import). The bright
line is structural and free: it resolves only through the ``ResolverRegistry``, which can return only an
``OaLocation`` (database-asserted OA, https) — there is no path here to fetch a non-OA / arbitrary URL.

Per item: build a ``PaperRef`` (library want → the paper's own doi/pmid/title; external want → its doi/pmid,
**required** — a title-only external want is skipped as ``needs-id`` so we never mint a paper from a fuzzy
title match), resolve, and on a hit download (outside any txn) then import — library wants fill the existing
paper; external wants create a paper first, then import (which enriches from Crossref). One item's failure
never aborts the run.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy import Engine

from app.backend.acquisition.fetch import download_oa_pdf, import_oa_pdf
from app.backend.acquisition.registry import OaLocation, PaperRef, ResolverRegistry
from app.backend.persistence import wanted_repo
from app.backend.persistence.repository import create_paper

logger = logging.getLogger("callosum.acquisition.wanted")

MAX_RECHECK_PER_RUN = 200  # politeness/resource cap; logged (never silent) if it truncates a run


def run_recheck(
    engine: Engine,
    registry: ResolverRegistry,
    *,
    crossref_client: Any | None = None,
    download: Callable[[OaLocation], Any] = download_oa_pdf,
    import_: Callable[..., dict[str, Any]] = import_oa_pdf,
) -> dict[str, Any]:
    """Re-check every open wanted row, auto-acquiring authorized OA copies. Returns a summary dict."""
    with engine.connect() as conn:
        rows = wanted_repo.list_open(conn)
    truncated = len(rows) > MAX_RECHECK_PER_RUN
    if truncated:
        logger.warning(
            "wanted re-check: %d open items exceeds the per-run cap %d; processing the first %d",
            len(rows),
            MAX_RECHECK_PER_RUN,
            MAX_RECHECK_PER_RUN,
        )
        rows = rows[:MAX_RECHECK_PER_RUN]

    summary: dict[str, Any] = {
        "checked": 0,
        "acquired": [],
        "still_wanted": 0,
        "skipped": 0,
        "errors": 0,
        "truncated": truncated,
    }

    for row in rows:
        summary["checked"] += 1
        ref = _ref_for_row(row)
        if ref is None:
            with engine.begin() as conn:
                wanted_repo.mark_checked(conn, row["id"], result="needs-id")
            summary["skipped"] += 1
            continue
        try:
            with engine.begin() as conn:  # resolve writes the per-source external_api_cache
                location = registry.resolve(conn, ref)
            if location is None:
                with engine.begin() as conn:
                    wanted_repo.mark_checked(conn, row["id"], result="none")
                summary["still_wanted"] += 1
                continue
            temp_path = download(location)  # network — outside any DB transaction
            with engine.begin() as conn:
                paper_id = row["paper_id"] if row["paper_id"] is not None else _create_paper_for_wanted(conn, row)
                import_(conn, location, temp_path, paper_id=paper_id, crossref_client=crossref_client)
                wanted_repo.mark_fulfilled(
                    conn, row["id"], paper_id=paper_id, result=f"{location.oa_color}/{location.version}"
                )
            summary["acquired"].append(
                {
                    "wanted_id": row["id"],
                    "paper_id": paper_id,
                    "oa_color": location.oa_color,
                    "oa_version": location.version,
                    "oa_source": location.source,
                }
            )
        except Exception as exc:  # per-item; one bad item never aborts the run
            with engine.begin() as conn:
                wanted_repo.mark_checked(conn, row["id"], result=f"error: {type(exc).__name__}")
            summary["errors"] += 1
    return summary


def _ref_for_row(row: dict[str, Any]) -> PaperRef | None:
    """A library want resolves on the paper's own doi/pmid/title (title allowed, like per-paper acquire). An
    external want requires a doi or pmid (title-only → None → skipped as needs-id)."""
    if row["paper_id"] is not None:
        csl = row.get("paper_csl_json") or {}
        pmid = csl.get("PMID") or csl.get("pmid")
        try:
            return PaperRef(doi=row.get("paper_doi"), pmid=str(pmid) if pmid else None, title=row.get("paper_title"))
        except ValueError:
            return None
    if not (row.get("doi") or row.get("pmid")):
        return None  # external title-only → needs an identifier; we never mint a paper from a fuzzy match
    try:
        return PaperRef(doi=row.get("doi"), pmid=str(row["pmid"]) if row.get("pmid") else None, title=row.get("title"))
    except ValueError:
        return None


def _create_paper_for_wanted(conn, row: dict[str, Any]) -> int:
    """Create a paper for a fulfilled external want; ``import_oa_pdf`` then enriches it from Crossref."""
    title = (row.get("title") or row.get("doi") or "Untitled").strip() or "Untitled"
    doi = row.get("doi")
    csl: dict[str, Any] = {"id": doi or f"wanted-{row['id']}", "type": "document", "title": title}
    if doi:
        csl["DOI"] = doi
    return create_paper(conn, title=title, csl_json=csl, doi=doi, imported_source="wanted-oa")
