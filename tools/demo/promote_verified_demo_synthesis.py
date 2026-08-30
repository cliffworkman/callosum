"""Promote one validated sandbox synthesis into the stable public-demo summary slot.

The source must be a dedicated/disposable demo-library database, never an ordinary working
library. The target must be the dedicated curated demo database. Every citation is rechecked
against the target chunk identity before the target's single stable summary is replaced.

Any real citation status the app itself displays (verified/weak/unverified/contradicted -- see
``CITATION_MAPPING_STATUSES``) is eligible for promotion, not only "verified": an all-green demo
summary is *less* representative of the app's actual verified/flagged/contradicted behavior than
an honest mix, and the promoted citation's own status/confidence fields travel with it unchanged
-- this tool never fabricates or upgrades a status, only decides whether the real one is eligible.
Promotion always reports the exact non-verified sentence/status pairs it accepted, so choosing a
mixed-status summary is a visible, informed decision at the call site, never a silent default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.persistence.schema_base import CITATION_MAPPING_STATUSES  # noqa: E402

DEMO_SUMMARY_ID = 1
CURATED_PAPER_IDS = {42, 67, 88}
DEMO_SUMMARY_STATUSES = ("verified", "flagged")


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def promote(
    *,
    source_db: Path,
    source_summary_id: int,
    target_db: Path,
    ask_overview_path: Path,
    backup_path: Path | None = None,
) -> tuple[int, int]:
    if not source_db.is_file() or not target_db.is_file():
        raise ValueError("source and target databases must already exist")
    if source_db.resolve() == target_db.resolve():
        raise ValueError("source and target databases must be different")
    source = sqlite3.connect(f"file:{source_db.resolve().as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    target = sqlite3.connect(target_db)
    target.row_factory = sqlite3.Row
    target.execute("PRAGMA foreign_keys = ON")
    try:
        summary = source.execute("SELECT * FROM summaries WHERE id = ?", (source_summary_id,)).fetchone()
        if summary is None or summary["status"] not in DEMO_SUMMARY_STATUSES or not summary["overview_json"]:
            raise ValueError(
                f"source summary must have a real status in {DEMO_SUMMARY_STATUSES} and contain a traceable Overview"
            )
        sentences = source.execute(
            "SELECT * FROM summary_sentences WHERE summary_id = ? ORDER BY ordinal, id",
            (source_summary_id,),
        ).fetchall()
        if not 4 <= len(sentences) <= 7:
            raise ValueError("source summary must contain four to seven evidence-bearing claims")
        copied: list[tuple[sqlite3.Row, sqlite3.Row, sqlite3.Row]] = []
        paper_ids: set[int] = set()
        non_verified: list[tuple[int, str]] = []  # (ordinal, citation status) -- reported, never silent
        for sentence in sentences:
            rows = source.execute(
                """SELECT cm.*, eq.id evidence_id, eq.quote_text, eq.page_start, eq.page_end, eq.bbox_json,
                          eq.retrieval_confidence, eq.quote_confidence, eq.support_confidence,
                          eq.created_at evidence_created_at, c.paper_id, c.text chunk_text,
                          c.chunk_version source_chunk_version
                   FROM citation_mappings cm
                   JOIN evidence_quotes eq ON eq.citation_mapping_id = cm.id
                   JOIN chunks c ON c.id = cm.chunk_id
                   WHERE cm.summary_sentence_id = ? ORDER BY cm.id""",
                (sentence["id"],),
            ).fetchall()
            if not rows:
                raise ValueError(f"source claim {sentence['ordinal']} has no citation")
            for row in rows:
                if row["status"] not in CITATION_MAPPING_STATUSES:
                    raise ValueError(f"source claim {sentence['ordinal']} has an unrecognized citation status")
                if row["status"] != "verified":
                    non_verified.append((int(sentence["ordinal"]), row["status"]))
                target_chunk = target.execute(
                    "SELECT paper_id, text, chunk_version FROM chunks WHERE id = ?",
                    (row["chunk_id"],),
                ).fetchone()
                if (
                    target_chunk is None
                    or int(target_chunk["paper_id"]) != int(row["paper_id"])
                    or target_chunk["text"] != row["chunk_text"]
                    or target_chunk["chunk_version"] != row["source_chunk_version"]
                ):
                    raise ValueError(f"source citation chunk {row['chunk_id']} drifted from the curated target")
                paper_ids.add(int(row["paper_id"]))
                copied.append((sentence, row, target_chunk))
        if paper_ids != CURATED_PAPER_IDS:
            raise ValueError(
                f"source synthesis covers papers {sorted(paper_ids)}, expected {sorted(CURATED_PAPER_IDS)}"
            )
        overview = json.loads(summary["overview_json"])
        if not isinstance(overview, list) or not overview:
            raise ValueError("source Overview is malformed")
        ordinals = {int(sentence["ordinal"]) for sentence in sentences}
        flagged_ordinals = {ordinal for ordinal, _status in non_verified}
        verified_ordinals = ordinals - flagged_ordinals
        # Matches app/backend/demo_ask_overview.py's own verified_claims_sha256() exactly: the Overview
        # narrates only non-flagged (fully-verified) claims -- a flagged sentence has no business being
        # cited by the Overview's own claim trace, mixed-status summary or not.
        if any(not set(item.get("claim_ordinals") or []) <= verified_ordinals for item in overview):
            raise ValueError("source Overview references an unknown or non-verified (flagged) claim ordinal")

        if backup_path is not None:
            if backup_path.exists():
                raise ValueError(f"refusing to overwrite existing backup: {backup_path}")
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(backup_path) as backup:
                target.backup(backup)

        target.execute("DELETE FROM summaries")
        summary_values = _row_dict(summary)
        summary_values["id"] = DEMO_SUMMARY_ID
        columns = list(summary_values)
        target.execute(
            f"INSERT INTO summaries ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            tuple(summary_values[column] for column in columns),
        )
        mapping_count = 0
        for sentence in sentences:
            ordinal = int(sentence["ordinal"])
            sentence_id = 101 + ordinal
            target.execute(
                """INSERT INTO summary_sentences (id, summary_id, ordinal, text, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (sentence_id, DEMO_SUMMARY_ID, ordinal, sentence["text"], sentence["created_at"]),
            )
            source_rows = [row for source_sentence, row, _ in copied if source_sentence["id"] == sentence["id"]]
            for row in source_rows:
                mapping_count += 1
                mapping_id = 1000 + mapping_count
                evidence_id = 2000 + mapping_count
                target.execute(
                    """INSERT INTO citation_mappings (
                           id, summary_sentence_id, chunk_id, status, chunk_version_verified_against,
                           embedding_version_verified_against, verification_version, created_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        mapping_id,
                        sentence_id,
                        row["chunk_id"],
                        row["status"],
                        row["chunk_version_verified_against"],
                        row["embedding_version_verified_against"],
                        row["verification_version"],
                        row["created_at"],
                    ),
                )
                target.execute(
                    """INSERT INTO evidence_quotes (
                           id, citation_mapping_id, chunk_id, quote_text, page_start, page_end, bbox_json,
                           retrieval_confidence, quote_confidence, support_confidence, created_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        evidence_id,
                        mapping_id,
                        row["chunk_id"],
                        row["quote_text"],
                        row["page_start"],
                        row["page_end"],
                        row["bbox_json"],
                        row["retrieval_confidence"],
                        row["quote_confidence"],
                        row["support_confidence"],
                        row["evidence_created_at"],
                    ),
                )
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()

    # Fingerprint ONLY the non-flagged (fully-verified) claims -- must match
    # app/backend/demo_ask_overview.py::verified_claims_sha256()'s own `if not sentence.flagged` filter exactly,
    # or the promoted ask-overview-v1.json would carry a fingerprint the live app could never itself reproduce.
    claims = [
        {"ordinal": int(row["ordinal"]), "text": str(row["text"])}
        for row in sentences
        if int(row["ordinal"]) in verified_ordinals
    ]
    fingerprint = hashlib.sha256(
        json.dumps(claims, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    ask_overview = {
        "summary_id": DEMO_SUMMARY_ID,
        "overview": overview,
        "verified_claim_count": len(claims),
        "verified_claims_sha256": fingerprint,
        "provider_id": "gemini",
        "model_id": "gemini-3.1-flash-lite",
        "prompt_version": "overview-v1",
    }
    ask_overview_path.write_text(
        json.dumps(ask_overview, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if non_verified:
        print(
            f"NOTE: promoted a mixed-status summary -- {len(non_verified)} of {len(sentences)} sentences are "
            f"non-verified (flagged): {non_verified}. This is an intentional, disclosed choice (a demo that is "
            f"100% verified is less representative of the app's real verified/flagged behavior), not an error."
        )
    return len(sentences), mapping_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--source-summary-id", type=int, required=True)
    parser.add_argument("--target-db", type=Path, required=True)
    parser.add_argument("--ask-overview", type=Path, default=ROOT / "demo" / "ask-overview-v1.json")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--confirm-dedicated-demo-target", action="store_true")
    parser.add_argument("--confirm-public-source", action="store_true")
    args = parser.parse_args()
    if not args.confirm_dedicated_demo_target or not args.confirm_public_source:
        parser.error("both explicit target/public-source confirmations are required")
    sentence_count, citation_count = promote(
        source_db=args.source_db,
        source_summary_id=args.source_summary_id,
        target_db=args.target_db,
        ask_overview_path=args.ask_overview,
        backup_path=args.backup,
    )
    print(
        f"promoted {sentence_count} claims with {citation_count} citations into demo summary "
        f"{DEMO_SUMMARY_ID} (see any NOTE above for the real verified/flagged split)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
