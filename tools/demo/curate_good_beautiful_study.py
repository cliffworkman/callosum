"""Replace the old demo paper slot with the CC BY He et al. PsyArXiv manuscript.

The target must be a named dedicated demo database. The paper asset and bounded
Meta-Preregistration fixture are checksum/contract validated before any write.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import fitz

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.demo.curated_library import CORPUS, CORPUS_GROWN_ON  # noqa: E402

PAPER_ID = 42
ATTACHMENT_ID = 42
LINK_ID = 4201
VERSION_ID = 4201
REGISTRATION_ATTACHMENT_ID = 4201
PDF_SHA256 = "439fe3b38158f8b80b3e041223c87160efee6c883153a14d3b2fb4935fec09b6"
TITLE = (
    "What is good is beautiful (and what isn’t, isn’t): How moral character affects perceived facial attractiveness."
)
AUTHORS = ["Dexian He", "Clifford I. Workman", "Xianyou He", "Anjan Chatterjee"]
DOI = "10.1037/aca0000454"
ABSTRACT = (
    "A well-documented ‘beauty is good’ stereotype is expressed in the expectation that physically attractive "
    "people have more positive characteristics. This preregistered study tested whether complementary "
    "‘good is beautiful’ and ‘bad is ugly’ stereotypes bias aesthetic judgments across face ages and sexes."
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if set(payload) != {"schema_version", "source", "demo_mapping", "link", "version", "commitments", "license_audit"}:
        raise ValueError("registration fixture has unknown or missing top-level fields")
    if payload["schema_version"] != 1:
        raise ValueError("unsupported registration fixture schema")
    if payload["demo_mapping"] != {"paper_id": PAPER_ID, "link_id": LINK_ID, "version_id": VERSION_ID}:
        raise ValueError("registration fixture demo identifiers do not match the curated namespace")
    if payload["source"]["paper_doi"].casefold() != DOI:
        raise ValueError("registration fixture belongs to a different article")
    if len(payload["commitments"]) != 12:
        raise ValueError("registration fixture must contain the reviewed 12 commitments")
    return payload


def curate(database: Path, pdf: Path, fixture_path: Path) -> None:
    if not database.is_file():
        raise ValueError(f"dedicated demo database does not exist: {database}")
    if not pdf.is_file() or pdf.read_bytes()[:5] != b"%PDF-":
        raise ValueError(f"curated source is not a PDF: {pdf}")
    if _hash(pdf) != PDF_SHA256:
        raise ValueError("PsyArXiv PDF checksum does not match the audited OSF primary file")
    fixture = _fixture(fixture_path)
    bounded_registration = database.with_name(f"{database.stem}-bounded-registration.md")
    bounded_text = (
        "\n\n".join(f"## {item['field_type']}\n\n{item['evidence_text']}" for item in fixture["commitments"]) + "\n"
    )
    bounded_registration.write_text(bounded_text, encoding="utf-8")
    bounded_checksum = _hash(bounded_registration)
    document = fitz.open(pdf)
    replacement_pages = [(number + 1, page.get_text("text").strip()) for number, page in enumerate(document)]
    document.close()
    if len(replacement_pages) != 38 or sum(len(text) for _, text in replacement_pages) < 40_000:
        raise ValueError("curated PsyArXiv PDF yielded an unexpected page/text count")
    con = sqlite3.connect(database)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {
            "papers",
            "attachments",
            "chunks",
            "summaries",
            "paper_registration_links",
            "registration_document_versions",
            "registration_commitments",
        }
        if not required <= tables:
            raise ValueError("database is not a migrated dedicated demo fixture")
        con.execute("DELETE FROM summaries")
        for paper_id in CORPUS:
            con.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        assets = {
            42: pdf,
            **{
                paper_id: ROOT / "demo" / "documents" / item["filename"]
                for paper_id, item in CORPUS.items()
                if paper_id != 42 and item.get("bundled_material", "complete-pdf") == "complete-pdf"
            },
        }
        abstracts = {42: ABSTRACT}
        citation_keys = {
            42: "he2024good",
            67: "workman2021morality",
            88: "rasset2023only",
            89: "bilici2026changing",
            90: "workman2022evidence",
        }
        for paper_id, item in sorted(CORPUS.items()):
            has_pdf = item.get("bundled_material", "complete-pdf") == "complete-pdf"
            created_at = "2026-08-13 00:00:00" if paper_id in (42, 67, 88) else f"{CORPUS_GROWN_ON} 00:00:00"
            csl = {
                "id": f"demo-{paper_id}",
                "type": "article-journal",
                "title": item["title"],
                "author": item["csl_authors"],
                "issued": {"date-parts": [[int(part) for part in item["publication_date"].split("-")]]},
                "DOI": item["doi"],
                "URL": item.get("article_url", item["canonical_url"]),
                "container-title": item["venue"],
                "publisher": item["publisher"],
                "volume": item["volume"],
                "issue": item["issue"],
                "page": item["page"],
                "ISSN": item["issn"],
            }
            con.execute(
                """INSERT INTO papers (
                       id, title, abstract, year, doi, venue, item_type, language, publication_date,
                       first_author_family_name, imported_source, citation_key, csl_json, processing_tier,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    paper_id,
                    item["title"],
                    item.get("abstract") or abstracts.get(paper_id),
                    item["year"],
                    item["doi"],
                    item["venue"],
                    "article-journal",
                    "en",
                    item["publication_date"],
                    item["csl_authors"][0]["family"],
                    "curated-public-demo",
                    citation_keys[paper_id],
                    json.dumps(csl, ensure_ascii=False, sort_keys=True),
                    "metadata-only",
                    created_at,
                    created_at,
                ),
            )
            if not has_pdf:
                continue
            asset = assets[paper_id]
            if not asset.is_file() or asset.read_bytes()[:5] != b"%PDF-":
                raise ValueError(f"curated paper {paper_id} asset is unavailable")
            checksum = _hash(asset)
            doc = fitz.open(asset)
            article_pages = [(number + 1, page.get_text("text").strip()) for number, page in enumerate(doc)]
            doc.close()
            if not article_pages or sum(len(text) for _, text in article_pages) < 10_000:
                raise ValueError(f"curated paper {paper_id} did not yield enough public text")
            oa_color = "gold" if paper_id == 90 else "green"
            con.execute(
                """INSERT INTO attachments (
                       id, paper_id, storage_mode, availability, resolved_path, checksum, file_size,
                       content_type, import_source, attachment_type, role, oa_color, oa_version,
                       oa_source, oa_landing_page_url, oa_license, oa_bronze_unstable, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    paper_id,
                    paper_id,
                    "linked",
                    "available",
                    str(asset.resolve()),
                    checksum,
                    asset.stat().st_size,
                    "application/pdf",
                    "curated-public-demo",
                    "pdf",
                    "primary",
                    oa_color,
                    "preprint" if paper_id == 42 else "publishedVersion",
                    "PsyArXiv" if paper_id == 42 else item["publisher"],
                    item["canonical_url"],
                    item["license_name"],
                    0,
                    created_at,
                ),
            )
            for page_number, text in article_pages:
                if not text:
                    continue
                con.execute(
                    """INSERT INTO chunks (
                           id, paper_id, attachment_id, text, section, page_start, page_end, char_start,
                           char_end, bbox_json, bbox_coordinate_system, extraction_tool, extraction_version,
                           chunking_strategy, chunk_version, source_attachment_checksum, created_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        paper_id * 1000 + page_number,
                        paper_id,
                        paper_id,
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
                        f"demo-public-v1:{checksum[:16]}",
                        checksum,
                        created_at,
                    ),
                )
        link = fixture["link"]
        con.execute(
            """INSERT INTO attachments (
                   id, paper_id, storage_mode, availability, resolved_path, checksum, file_size,
                   content_type, import_source, attachment_type, role, oa_source,
                   oa_landing_page_url, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                REGISTRATION_ATTACHMENT_ID,
                PAPER_ID,
                "linked",
                "available",
                str(bounded_registration.resolve()),
                bounded_checksum,
                bounded_registration.stat().st_size,
                "text/markdown",
                "curated-public-demo",
                "document",
                "preregistration",
                "OSF",
                link["canonical_url"],
                "2026-08-13 00:00:00",
            ),
        )
        con.execute(
            """INSERT INTO paper_registration_links (
                   id, paper_id, attachment_id, provider, external_id, registration_doi, canonical_url,
                   title, contributors_json, registered_at, registration_status, schema_name, link_status,
                   linkage_class, match_method, match_evidence_json, user_confirmed, source_metadata_json,
                   content_hash, retrieved_at, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                LINK_ID,
                PAPER_ID,
                REGISTRATION_ATTACHMENT_ID,
                link["provider"],
                link["external_id"],
                link["registration_doi"],
                link["canonical_url"],
                link["title"],
                json.dumps(link["contributors"], ensure_ascii=False),
                link["registered_at"],
                link["registration_status"],
                link["schema_name"],
                "confirmed",
                link["linkage_class"],
                link["match_method"],
                json.dumps(link["match_evidence"], ensure_ascii=False),
                1,
                json.dumps({"public_fixture": "bounded-commitments-only"}),
                link["content_hash"],
                "2026-08-13 00:00:00",
                "2026-08-13 00:00:00",
                "2026-08-13 00:00:00",
            ),
        )
        version = fixture["version"]
        con.execute(
            """INSERT INTO registration_document_versions (
                   id, link_id, paper_id, attachment_id, provider, external_id, content_hash, canonical_url,
                   registered_at, registration_status, schema_name, schema_version, structured_json,
                   rendered_text, source_metadata_json, retrieved_at, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)""",
            (
                VERSION_ID,
                LINK_ID,
                PAPER_ID,
                REGISTRATION_ATTACHMENT_ID,
                version["provider"],
                version["external_id"],
                version["content_hash"],
                version["canonical_url"],
                version["registered_at"],
                version["registration_status"],
                version["schema_name"],
                version["schema_version"],
                json.dumps({"public_fixture": "bounded-commitments-only"}),
                json.dumps({"complete_registration_bundled": False}),
                "2026-08-13 00:00:00",
                "2026-08-13 00:00:00",
            ),
        )
        for index, item in enumerate(fixture["commitments"], start=1):
            registration_chunk_id = 4201000 + index
            registration_page = item["page"] or 1
            con.execute(
                """INSERT INTO chunks (
                       id, paper_id, attachment_id, text, section, page_start, page_end, char_start,
                       char_end, bbox_json, bbox_coordinate_system, extraction_tool, extraction_version,
                       chunking_strategy, chunk_version, source_attachment_checksum, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    registration_chunk_id,
                    PAPER_ID,
                    REGISTRATION_ATTACHMENT_ID,
                    item["evidence_text"],
                    item["source_section"] or item["field_type"],
                    registration_page,
                    registration_page,
                    0,
                    len(item["evidence_text"]),
                    None,
                    "text_chars",
                    "public-fixture",
                    "1",
                    "bounded-registration-commitment",
                    f"bounded-registration-v1:{bounded_checksum[:16]}",
                    bounded_checksum,
                    "2026-08-13 00:00:00",
                ),
            )
            source_locator = dict(item["source_locator"])
            source_locator.update({"attachment_id": REGISTRATION_ATTACHMENT_ID, "chunk_id": registration_chunk_id})
            con.execute(
                """INSERT INTO registration_commitments (
                       id, version_id, paper_id, link_id, attachment_id, field_type, study_label, ordinal,
                       structured_value_json, evidence_text, source_section, source_key, page, chunk_id,
                       source_locator_json, extraction_method, extraction_confidence,
                       registration_content_hash, extraction_version, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    420100 + index,
                    VERSION_ID,
                    PAPER_ID,
                    LINK_ID,
                    REGISTRATION_ATTACHMENT_ID,
                    item["field_type"],
                    item["study_label"],
                    item["ordinal"],
                    json.dumps(item["structured_value"], ensure_ascii=False),
                    item["evidence_text"],
                    item["source_section"],
                    item["source_key"],
                    item["page"],
                    registration_chunk_id,
                    json.dumps(source_locator, ensure_ascii=False),
                    item["extraction_method"],
                    item["extraction_confidence"],
                    version["content_hash"],
                    item["extraction_version"],
                    "2026-08-13 00:00:00",
                ),
            )
        con.commit()
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument(
        "--pdf",
        type=Path,
        default=ROOT / "demo" / "documents" / "he-2021-good-beautiful-preprint.pdf",
    )
    parser.add_argument(
        "--registration-fixture",
        type=Path,
        default=ROOT / "tools" / "demo" / "fixtures" / "good-beautiful-registration-public.json",
    )
    parser.add_argument("--confirm-public-demo-source", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_demo_source:
        parser.error("--confirm-public-demo-source is required; never mutate an ordinary working library")
    curate(args.source_db, args.pdf, args.registration_fixture)
    print(f"curated CC BY replacement paper and bounded OSF commitments in {args.source_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
