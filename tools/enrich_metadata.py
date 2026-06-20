"""Run Crossref DOI metadata enrichment over a Callosum SQLite database."""

from __future__ import annotations

import argparse
import os

from app.backend.metadata import enrich_pdf_scaffold_library
from app.backend.persistence.database import make_engine

DEFAULT_DB_URL = "sqlite:///.local/validation/validation.sqlite"


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich raw PDF scaffold papers with Crossref DOI metadata.")
    parser.add_argument("--db-url", default=os.environ.get("CALLOSUM_DB_URL", DEFAULT_DB_URL))
    args = parser.parse_args()

    engine = make_engine(args.db_url)
    try:
        with engine.begin() as conn:
            result = enrich_pdf_scaffold_library(conn)
        print(f"Resolved: {result.resolved}")
        print(f"Unresolved: {result.unresolved}")
        print(f"Skipped: {result.skipped}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
