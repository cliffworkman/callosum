"""Add the licensed Rasset et al. study to a dedicated public-demo fixture.

This is an explicit one-time curation command, not part of ordinary demo builds. It only accepts a named
fixture database plus a checked-in public PDF and requires the same public-source acknowledgement as the
snapshot exporter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import fitz

PAPER_ID = 88
ATTACHMENT_ID = 88
TITLE = (
    "Only human after all? a pre-registered study on gaze behavior and humanity attributions "
    "to people with facial difference"
)
AUTHORS = ["Pauline Rasset", "Benoît Montalan", "Jessica Mange"]
DOI = "10.1371/journal.pone.0295617"
ABSTRACT = (
    "People with facial difference may be dehumanized. This preregistered eye-tracking study examined "
    "visual attention and humanity attributions toward people with facial difference, including whether "
    "disgust related to altered gaze and perceived humanness."
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def curate(database: Path, pdf: Path) -> None:
    if not database.is_file():
        raise ValueError(f"dedicated demo database does not exist: {database}")
    if not pdf.is_file() or pdf.read_bytes()[:5] != b"%PDF-":
        raise ValueError(f"curated source is not a PDF: {pdf}")
    document = fitz.open(pdf)
    pages = [(number + 1, page.get_text("text").strip()) for number, page in enumerate(document)]
    document.close()
    if not pages or sum(len(text) for _, text in pages) < 10_000:
        raise ValueError("curated PDF did not yield enough public text")
    checksum = _hash(pdf)
    csl = {
        "id": "demo-88",
        "type": "article-journal",
        "title": TITLE,
        "author": [{"literal": author} for author in AUTHORS],
        "issued": {"date-parts": [[2023, 12, 12]]},
        "DOI": DOI,
        "URL": f"https://doi.org/{DOI}",
        "container-title": "PLOS ONE",
    }
    connection = sqlite3.connect(database)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"papers", "attachments", "chunks"}
        if not required <= tables:
            raise ValueError("database is not a compatible dedicated demo fixture")
        connection.execute("DELETE FROM chunks WHERE paper_id = ?", (PAPER_ID,))
        connection.execute("DELETE FROM attachments WHERE paper_id = ?", (PAPER_ID,))
        connection.execute("DELETE FROM papers WHERE id = ?", (PAPER_ID,))
        connection.execute(
            """INSERT INTO papers (
                   id, title, abstract, year, doi, venue, item_type, language, publication_date,
                   first_author_family_name, imported_source, citation_key, csl_json, processing_tier,
                   created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                PAPER_ID,
                TITLE,
                ABSTRACT,
                2023,
                DOI,
                "PLOS ONE",
                "article-journal",
                "en",
                "2023-12-12",
                "Rasset",
                "curated-public-demo",
                "rasset2023only",
                json.dumps(csl, ensure_ascii=False, sort_keys=True),
                "metadata-only",
                "2026-08-11 00:00:00",
                "2026-08-11 00:00:00",
            ),
        )
        connection.execute(
            """INSERT INTO attachments (
                   id, paper_id, storage_mode, availability, resolved_path, checksum, file_size,
                   content_type, import_source, attachment_type, role, oa_color, oa_version,
                   oa_source, oa_landing_page_url, oa_license, oa_bronze_unstable, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ATTACHMENT_ID,
                PAPER_ID,
                "linked",
                "available",
                str(pdf.resolve()),
                checksum,
                pdf.stat().st_size,
                "application/pdf",
                "curated-public-demo",
                "pdf",
                "primary",
                "gold",
                "publishedVersion",
                "PLOS ONE",
                f"https://doi.org/{DOI}",
                "CC BY 4.0",
                0,
                "2026-08-11 00:00:00",
            ),
        )
        for page_number, text in pages:
            if not text:
                continue
            connection.execute(
                """INSERT INTO chunks (
                       id, paper_id, attachment_id, text, section, page_start, page_end, char_start,
                       char_end, bbox_json, bbox_coordinate_system, extraction_tool, extraction_version,
                       chunking_strategy, chunk_version, source_attachment_checksum, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    PAPER_ID * 1000 + page_number,
                    PAPER_ID,
                    ATTACHMENT_ID,
                    text,
                    "full text",
                    page_number,
                    page_number,
                    0,
                    len(text),
                    None,
                    "pdf_points_top_left",
                    "PyMuPDF",
                    fitz.VersionBind,
                    "page",
                    "demo-v1",
                    checksum,
                    "2026-08-11 00:00:00",
                ),
            )
        connection.commit()
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "demo" / "documents" / "rasset-2023-only-human.pdf",
    )
    parser.add_argument("--confirm-public-demo-source", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_demo_source:
        raise SystemExit("refusing to curate without --confirm-public-demo-source")
    curate(args.source_db, args.pdf)
    print(f"curated public study {PAPER_ID} in {args.source_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
