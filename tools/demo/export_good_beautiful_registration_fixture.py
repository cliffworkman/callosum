"""Export a bounded, public Meta-Preregistration fixture from an existing Callosum run.

This is an explicit curation command. It reads one named working database as an intermediate,
selects only public registration-link metadata and the commitments used by the saved comparison,
remaps identifiers into the dedicated demo namespace, and rejects paths, credentials, or unknown
registration content. It never exports the complete OSF registration or working-library notes.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PAPER_ID = 25
SOURCE_VERSION_ID = 2
DEMO_PAPER_ID = 42
DEMO_LINK_ID = 4201
DEMO_VERSION_ID = 4201
SCHEMA_VERSION = 1

FORBIDDEN = (
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)"),
    re.compile(r"(?i)(?:[a-z]:\\|/users/|/home/|127\.0\.0\.1|localhost)"),
)


def _json(value: Any, *, expected: type) -> Any:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, expected):
        raise ValueError(f"expected {expected.__name__}, got {type(parsed).__name__}")
    return parsed


def export_fixture(source_db: Path, output: Path) -> dict[str, Any]:
    if not source_db.is_file():
        raise ValueError(f"working source database does not exist: {source_db}")
    uri = f"file:{source_db.resolve().as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        paper = con.execute(
            "SELECT id, title, doi FROM papers WHERE id = ?",
            (SOURCE_PAPER_ID,),
        ).fetchone()
        link = con.execute(
            """SELECT provider, external_id, registration_doi, canonical_url, title,
                      contributors_json, registered_at, registration_status, schema_name,
                      link_status, linkage_class, match_method, match_evidence_json,
                      user_confirmed, content_hash
               FROM paper_registration_links
               WHERE paper_id = ? AND id = ?""",
            (SOURCE_PAPER_ID, SOURCE_VERSION_ID),
        ).fetchone()
        version = con.execute(
            """SELECT provider, external_id, content_hash, canonical_url, registered_at,
                      registration_status, schema_name, schema_version
               FROM registration_document_versions
               WHERE paper_id = ? AND id = ?""",
            (SOURCE_PAPER_ID, SOURCE_VERSION_ID),
        ).fetchone()
        commitments = con.execute(
            """SELECT field_type, study_label, ordinal, structured_value_json, evidence_text,
                      source_section, source_key, page, extraction_method, extraction_confidence,
                      registration_content_hash, extraction_version
               FROM registration_commitments
               WHERE paper_id = ? AND version_id = ?
               ORDER BY ordinal, id""",
            (SOURCE_PAPER_ID, SOURCE_VERSION_ID),
        ).fetchall()
    finally:
        con.close()
    if paper is None or link is None or version is None:
        raise ValueError("the expected article, confirmed OSF link, or acquired version is missing")
    if str(paper["doi"]).casefold() != "10.1037/aca0000454":
        raise ValueError("source paper DOI does not match the curated article")
    if len(commitments) != 12:
        raise ValueError(f"expected the reviewed 12-commitment run, found {len(commitments)}")
    if link["link_status"] != "confirmed" or not bool(link["user_confirmed"]):
        raise ValueError("the OSF match is not confirmed")
    if link["content_hash"] != version["content_hash"]:
        raise ValueError("link/version content hashes disagree")

    canonical_url = str(link["canonical_url"])
    external_id = str(link["external_id"])
    content_hash = str(version["content_hash"])
    fixture = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "paper_id": SOURCE_PAPER_ID,
            "paper_title": str(paper["title"]),
            "paper_doi": str(paper["doi"]),
            "comparison_run_id": 2,
            "curation_note": (
                "Explicit whitelist export from the completed local comparison; the complete OSF "
                "registration and working-library state are not included."
            ),
        },
        "demo_mapping": {
            "paper_id": DEMO_PAPER_ID,
            "link_id": DEMO_LINK_ID,
            "version_id": DEMO_VERSION_ID,
        },
        "link": {
            "provider": str(link["provider"]),
            "external_id": external_id,
            "registration_doi": link["registration_doi"],
            "canonical_url": canonical_url,
            "title": link["title"],
            "contributors": _json(link["contributors_json"], expected=list),
            "registered_at": link["registered_at"],
            "registration_status": link["registration_status"],
            "schema_name": link["schema_name"],
            "link_status": "confirmed",
            "linkage_class": link["linkage_class"],
            "match_method": link["match_method"],
            "match_evidence": _json(link["match_evidence_json"], expected=list),
            "user_confirmed": True,
            "content_hash": content_hash,
        },
        "version": {
            "provider": str(version["provider"]),
            "external_id": external_id,
            "content_hash": content_hash,
            "canonical_url": canonical_url,
            "registered_at": version["registered_at"],
            "registration_status": version["registration_status"],
            "schema_name": version["schema_name"],
            "schema_version": version["schema_version"],
        },
        "commitments": [
            {
                "field_type": str(row["field_type"]),
                "study_label": row["study_label"],
                "ordinal": int(row["ordinal"]),
                "structured_value": _json(row["structured_value_json"], expected=dict),
                "evidence_text": str(row["evidence_text"]),
                "source_section": row["source_section"],
                "source_key": str(row["source_key"]),
                "page": int(row["page"]) if row["page"] is not None else None,
                "source_locator": {
                    "provider": str(version["provider"]),
                    "external_id": external_id,
                    "canonical_url": canonical_url,
                    "registration_version_id": DEMO_VERSION_ID,
                    "registration_content_hash": content_hash,
                    "source_key": str(row["source_key"]),
                    "page_start": int(row["page"]) if row["page"] is not None else None,
                    "page_end": int(row["page"]) if row["page"] is not None else None,
                },
                "extraction_method": str(row["extraction_method"]),
                "extraction_confidence": str(row["extraction_confidence"]),
                "extraction_version": str(row["extraction_version"]),
            }
            for row in commitments
        ],
        "license_audit": {
            "provider": "OSF",
            "external_id": external_id,
            "canonical_url": canonical_url,
            "license_name": "No explicit reuse license recorded",
            "redistribution": "metadata-and-bounded-evidence-only",
            "verified_via": "OSF registration metadata and DataCite linkage",
            "verified_on": "2026-08-13",
            "notice": (
                "The complete registration is not bundled. The demo stores public metadata and the "
                "12 bounded commitment excerpts used by the saved comparison; the canonical OSF record "
                "remains the authoritative source."
            ),
        },
    }
    encoded = json.dumps(fixture, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    for pattern in FORBIDDEN:
        if pattern.search(encoded):
            raise ValueError(f"public fixture rejected by forbidden-data pattern: {pattern.pattern}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8")
    return fixture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tools" / "demo" / "fixtures" / "good-beautiful-registration-public.json",
    )
    parser.add_argument("--confirm-working-source-intermediate", action="store_true")
    parser.add_argument("--confirm-public-fields", action="store_true")
    args = parser.parse_args()
    if not args.confirm_working_source_intermediate or not args.confirm_public_fields:
        parser.error("both explicit source/public-field confirmations are required")
    fixture = export_fixture(args.source_db, args.output)
    print(f"exported {len(fixture['commitments'])} bounded public commitments: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
