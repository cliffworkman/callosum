"""CLI over the source-role structure derivation (inc 577 H1a; v2 since inc 611). Read-only for the library.

    python tools/backfill_chunk_structure.py [--db-url sqlite:///...] [--paper-id N] [--limit N]
    python tools/backfill_chunk_structure.py --inspect <chunk_id>
    python tools/backfill_chunk_structure.py --summary

The derivation itself (cache-only reference resolution, per-paper committed, resumable, idempotent) lives in the
packaged application at ``app.backend.pdf_processing.structure_backfill`` since inc 613, so a desktop install can
classify its own library. This script only parses arguments and prints; see that module for the properties.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Script mode puts only this file's own directory on sys.path, not the project root, so the
# sibling `app` package is invisible without this (the same defect inc 508 found in
# run_https.py, invoked exactly as its docs said).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.backend.pdf_processing.structure_backfill import backfill, coverage
from app.backend.persistence.chunk_structure_repo import structure_for_chunk
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import chunks, papers
from app.backend.persistence.schema_chunk_structure import DERIVATION_VERSION, chunk_structure

DEFAULT_DB_URL = "sqlite:///.local/validation/validation.sqlite"


def inspect(engine, chunk_id: int) -> None:
    with engine.begin() as conn:
        row = (
            conn.execute(
                select(chunks, papers.c.title)
                .select_from(chunks.join(papers, papers.c.id == chunks.c.paper_id))
                .where(chunks.c.id == chunk_id)
            )
            .mappings()
            .first()
        )
        if row is None:
            print(f"no chunk {chunk_id}")
            return
        derived = structure_for_chunk(conn, chunk_id)

    print(f"chunk {chunk_id}  paper {row['paper_id']} ({(row['title'] or '')[:60]})")
    print(f"  attachment {row['attachment_id']}  page {row['page_start']}  section {row['section'] or 'NULL'}")
    print(f"  raw text: {' '.join((row['text'] or '').split())[:200]}")
    if row["bbox_json"]:
        try:
            spans = [s for s in json.loads(row["bbox_json"]) if isinstance(s, dict)]
            lines = {(s.get("page"), s.get("block"), s.get("line")) for s in spans}
            print(f"  geometry: {len(spans)} spans / {len(lines)} lines")
        except (TypeError, ValueError):
            print("  geometry: unparseable")
    if derived is None:
        print("  structure: NOT DERIVED (run the backfill)")
        return
    print(f"  chunk_type     : {derived.chunk_type}")
    print(f"  evidence_role  : {derived.evidence_role}")
    print(f"  reason codes   : {derived.reason_codes}")
    print(f"  confidence     : {derived.confidence}")
    print(f"  reference region: {derived.reference_region} (source {derived.reference_region_source})")
    print(f"  repeated boilerplate: {derived.repeated_boilerplate}")
    print(f"  derivation     : {derived.derivation_version}{'  [STALE]' if derived.is_stale else ''}")


def summarize(engine) -> None:
    cov = coverage(engine)
    print(f"derivation version {cov['derivation_version']}: {cov['papers_current']} of {cov['papers_with_chunks']}")
    print(f"  papers current; {cov['papers_needing_derivation']} need (re)derivation -- their rows are ignored")
    print(f"  rows by derivation version: {cov['rows_by_derivation_version']}\n")
    with engine.begin() as conn:
        rows = conn.execute(
            select(chunk_structure.c.chunk_type, chunk_structure.c.evidence_role).where(
                chunk_structure.c.derivation_version == DERIVATION_VERSION
            )
        ).fetchall()
    if not rows:
        print("no current derived rows yet")
        return
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for chunk_type, role in rows:
        counts[(chunk_type, role)] += 1
    total = len(rows)
    print(f"{total} classified chunks\n")
    print(f"  {'chunk_type':<24}{'evidence_role':<16}{'n':>7}{'share':>8}")
    for (chunk_type, role), n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {chunk_type:<24}{role:<16}{n:>7}{100 * n / total:>7.1f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", default=os.environ.get("CALLOSUM_DB_URL", DEFAULT_DB_URL))
    parser.add_argument("--paper-id", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true", help="re-derive even where rows are current")
    parser.add_argument("--inspect", type=int, metavar="CHUNK_ID")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    engine = make_engine(args.db_url)
    if args.inspect is not None:
        inspect(engine, args.inspect)
        return
    if args.summary:
        summarize(engine)
        return
    stats = backfill(engine, paper_id=args.paper_id, limit=args.limit, force=args.force)
    print(
        f"classified {stats['chunks']} chunks across {stats['papers']} papers "
        f"({stats['skipped_current']} already current, "
        f"{stats['no_reference_metadata']} without cached reference metadata)"
    )
    for doi, ids in stats["ambiguous_dois"].items():
        print(f"duplicate live papers share DOI {doi}: {ids} -- each receives that DOI's reference metadata")


if __name__ == "__main__":
    sys.exit(main())
