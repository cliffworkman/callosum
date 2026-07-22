"""One-shot tombstone-retention pruning (backlog #15) — run this from your OWN cron/systemd timer, not
auto-scheduled inside the FastAPI process. Keeping this a plain CLI script (rather than an in-process
background task) means the request-serving process stays simple and this can be run, retried, or paused
independently of the server's own uptime — the same reasoning `sync_server/OPERATIONS.md` documents.

    python -m sync_server.prune_tombstones [--older-than-days N] [--dry-run]

Reads `CALLOSUM_SYNC_DB_URL` the same way the server itself does (default `sqlite:///sync-server.sqlite`).
See `store.prune_tombstones`'s docstring for the retention trade-off this makes.
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, func, select

from sync_server.schema import ensure_updated_at_column, sync_records
from sync_server.store import prune_tombstones


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=int(os.getenv("CALLOSUM_SYNC_RETENTION_DAYS", "90")),
        help="tombstones older than this many days are eligible for removal (default: env or 90)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would be removed without deleting")
    args = parser.parse_args(argv)

    db_url = os.getenv("CALLOSUM_SYNC_DB_URL", "sqlite:///sync-server.sqlite")
    engine = create_engine(db_url)
    ensure_updated_at_column(engine)

    if args.dry_run:
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than_days)
        with engine.connect() as conn:
            count = conn.execute(
                select(func.count())
                .select_from(sync_records)
                .where(sync_records.c.deleted == 1, sync_records.c.updated_at < cutoff)
            ).scalar_one()
        print(f"dry-run: {count} tombstone(s) older than {args.older_than_days} days would be removed")
        return 0

    with engine.begin() as conn:
        removed = prune_tombstones(conn, older_than_days=args.older_than_days)
    print(f"removed {removed} tombstone(s) older than {args.older_than_days} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
