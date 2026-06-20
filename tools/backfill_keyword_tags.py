"""Backfill author/index keyword tags from Crossref `subject` over a Callosum SQLite database (inc 73).

For each live paper with a DOI, resolves it via Crossref — **cache-first**, only fetching from public Crossref
when no cached response exists (the "full" backfill) — and imports its subject categories as
`keyword:crossref` tags. **Tag-only:** it never updates paper metadata, so it is safe to run over a
hand-edited library; purely additive + idempotent (re-runnable). Only the DOI is sent to public Crossref
(bibliographic metadata — NOT the library-text egress gate).

    python tools/backfill_keyword_tags.py [--db-url sqlite:///...]
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy import select

from app.backend.metadata.enrichment import apply_crossref_subject_tags
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import papers
from integrations.crossref import CrossrefClient

DEFAULT_DB_URL = "sqlite:///.local/validation/validation.sqlite"


def backfill_keyword_tags(engine, client: CrossrefClient) -> dict[str, int]:
    """Tag every live DOI'd paper with its Crossref subject categories. Snapshots the work list, then commits
    per paper (resumable). Cache-first via `resolve_doi`; tag-only (never updates metadata). Returns a summary."""
    stats = {
        "with_doi": 0,
        "from_cache": 0,
        "from_network": 0,
        "unresolved": 0,
        "tagged": 0,
        "subjects": 0,
        "no_subject": 0,
    }
    with engine.begin() as conn:
        rows = [
            (int(r["id"]), str(r["doi"]))
            for r in conn.execute(
                select(papers.c.id, papers.c.doi).where(papers.c.deleted_at.is_(None), papers.c.doi.is_not(None))
            ).mappings()
        ]
    for paper_id, doi in rows:
        stats["with_doi"] += 1
        with engine.begin() as conn:
            resolution = client.resolve_doi(conn, doi)
            if not resolution.resolved or resolution.csl_json is None:
                stats["unresolved"] += 1
                continue
            stats["from_cache" if resolution.source == "cache" else "from_network"] += 1
            added = apply_crossref_subject_tags(conn, paper_id, resolution.csl_json)
            if added:
                stats["tagged"] += 1
                stats["subjects"] += len(added)
            else:
                stats["no_subject"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Crossref subject categories as keyword tags.")
    parser.add_argument("--db-url", default=os.environ.get("CALLOSUM_DB_URL", DEFAULT_DB_URL))
    args = parser.parse_args()

    engine = make_engine(args.db_url)
    try:
        stats = backfill_keyword_tags(engine, CrossrefClient())
        print(f"Papers with a DOI:        {stats['with_doi']}")
        print(f"  resolved from cache:    {stats['from_cache']}")
        print(f"  fetched from Crossref:  {stats['from_network']}")
        print(f"  unresolved / error:     {stats['unresolved']}")
        print(f"Papers with subject tags: {stats['tagged']}  (+{stats['subjects']} keyword-tag links total)")
        print(f"Resolved but no subjects: {stats['no_subject']}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
