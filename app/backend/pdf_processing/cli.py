"""Minimal temporary CLI for ingesting one local PDF into SQLite."""

from __future__ import annotations

import argparse

from alembic import command
from alembic.config import Config
from app.backend.pdf_processing.ingest import ingest_pdf_scaffold
from app.backend.persistence.database import make_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Temporary Callosum one-PDF ingest scaffold.")
    parser.add_argument("database_url", help="SQLAlchemy database URL, e.g. sqlite:///callosum.db")
    parser.add_argument("pdf_path", help="Local PDF path to ingest")
    parser.add_argument("--title", help="Optional paper title")
    parser.add_argument("--migrate", action="store_true", help="Run Alembic upgrade head before ingest")
    args = parser.parse_args()

    if args.migrate:
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", args.database_url)
        command.upgrade(config, "head")

    engine = make_engine(args.database_url)
    with engine.begin() as conn:
        result = ingest_pdf_scaffold(conn, args.pdf_path, title=args.title)

    print(result)


if __name__ == "__main__":
    main()
