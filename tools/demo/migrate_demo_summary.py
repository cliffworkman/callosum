"""Migrate still-valid verified claims when a curated demo paper is replaced.

The input is a previously validated public demo snapshot. Claims are retained only when
every citation points to an unchanged allowlisted paper and each evidence quotation is
still present on the recorded page of the newly curated source. No prose, status, score,
or locator is invented; ordinals and database identifiers are deterministically remapped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUMMARY_ID = 1
UNCHANGED_PAPER_ID = 67
CURATED_PAPER_IDS = [42, 67, 88]
QUESTION = "What is the anomalous-is-bad bias?"


def _normalized(text: str) -> str:
    text = re.sub(r"(?<=\w)[\u00ad-]\s+(?=\w)", "", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def migrate(snapshot_path: Path, database: Path, ask_overview_path: Path) -> tuple[int, int]:
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    source = raw["api"]["summaries"][str(SUMMARY_ID)]
    retained = [
        sentence
        for sentence in source["sentences"]
        if sentence["citations"]
        and all(int(citation["paper_id"]) == UNCHANGED_PAPER_ID for citation in sentence["citations"])
    ]
    if len(retained) < 4 or not any(not sentence["flagged"] for sentence in retained):
        raise ValueError("too few unchanged evidence-bearing claims survived the corpus replacement")
    ordinal_map = {int(sentence["ordinal"]): ordinal for ordinal, sentence in enumerate(retained)}
    old_overview = json.loads(ask_overview_path.read_text(encoding="utf-8"))
    con = sqlite3.connect(database)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        con.execute("DELETE FROM summaries")
        con.execute(
            """INSERT INTO summaries (
                   id, scope_type, scope_ref_json, content, overview_json, generated_by,
                   chunk_version_verified_against, embedding_version_verified_against,
                   verification_version, status, created_at
               ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)""",
            (
                SUMMARY_ID,
                "query",
                json.dumps(
                    {
                        "query": QUESTION,
                        "paper_ids": CURATED_PAPER_IDS,
                        "source_chunk_count": 8,
                        "migration": "unchanged-verified-claims-only",
                    },
                    sort_keys=True,
                ),
                " ".join(sentence["text"] for sentence in retained),
                "callosum-saved-summary-claim-migration-v1",
                "demo-public-v1",
                "all-MiniLM-L6-v2",
                "local-verifier-v1",
                "flagged" if any(sentence["flagged"] for sentence in retained) else "verified",
                "2026-08-13 00:00:00",
            ),
        )
        mapping_count = 0
        for ordinal, sentence in enumerate(retained):
            sentence_id = 100 + ordinal
            con.execute(
                "INSERT INTO summary_sentences (id, summary_id, ordinal, text, created_at) VALUES (?, ?, ?, ?, ?)",
                (sentence_id, SUMMARY_ID, ordinal, sentence["text"], "2026-08-13 00:00:00"),
            )
            for citation in sentence["citations"]:
                page = int(citation["page_start"])
                chunk_id = UNCHANGED_PAPER_ID * 1000 + page
                chunk = con.execute(
                    "SELECT text, chunk_version FROM chunks WHERE id = ? AND paper_id = ?",
                    (chunk_id, UNCHANGED_PAPER_ID),
                ).fetchone()
                if chunk is None or _normalized(citation["quote"]) not in _normalized(str(chunk[0])):
                    raise ValueError(f"saved evidence no longer resolves for retained claim {sentence['ordinal']}")
                mapping_count += 1
                mapping_id = 1000 + mapping_count
                con.execute(
                    """INSERT INTO citation_mappings (
                           id, summary_sentence_id, chunk_id, status, chunk_version_verified_against,
                           embedding_version_verified_against, verification_version, created_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        mapping_id,
                        sentence_id,
                        chunk_id,
                        citation["status"],
                        str(chunk[1]),
                        "all-MiniLM-L6-v2",
                        "local-verifier-v1",
                        "2026-08-13 00:00:00",
                    ),
                )
                con.execute(
                    """INSERT INTO evidence_quotes (
                           id, citation_mapping_id, chunk_id, quote_text, page_start, page_end,
                           bbox_json, retrieval_confidence, quote_confidence, support_confidence, created_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        2000 + mapping_count,
                        mapping_id,
                        chunk_id,
                        citation["quote"],
                        citation["page_start"],
                        citation["page_end"],
                        json.dumps(citation["bbox_json"], ensure_ascii=False) if citation["bbox_json"] else None,
                        citation["retrieval_confidence"],
                        citation["quote_confidence"],
                        citation["support_confidence"],
                        "2026-08-13 00:00:00",
                    ),
                )
        con.commit()
    finally:
        con.close()
    verified = [
        {"ordinal": ordinal, "text": sentence["text"]}
        for ordinal, sentence in enumerate(retained)
        if not sentence["flagged"]
    ]
    migrated_overview = []
    for item in old_overview["overview"]:
        old_ordinals = [int(value) for value in item["claim_ordinals"]]
        if all(value in ordinal_map for value in old_ordinals):
            migrated_overview.append(
                {"text": item["text"], "claim_ordinals": sorted({ordinal_map[value] for value in old_ordinals})}
            )
    if not migrated_overview:
        raise ValueError("no traceable generated Overview sentence survived the corpus replacement")
    fingerprint = hashlib.sha256(
        json.dumps(verified, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    ask_overview_path.write_text(
        json.dumps(
            {
                "summary_id": SUMMARY_ID,
                "overview": migrated_overview,
                "verified_claim_count": len(verified),
                "verified_claims_sha256": fingerprint,
                "provider_id": old_overview["provider_id"],
                "model_id": old_overview["model_id"],
                "prompt_version": old_overview["prompt_version"],
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return len(retained), mapping_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=ROOT / "demo" / "snapshot-v1.json")
    parser.add_argument("--ask-overview", type=Path, default=ROOT / "demo" / "ask-overview-v1.json")
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--confirm-public-demo-source", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_demo_source:
        parser.error("--confirm-public-demo-source is required; never migrate an ordinary working library")
    claims, citations = migrate(args.snapshot, args.source_db, args.ask_overview)
    print(f"migrated {claims} unchanged saved claims with {citations} re-resolved citations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
