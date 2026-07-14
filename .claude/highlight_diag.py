"""Precise-highlighting diagnostic (read-only). Scratch probe for the exact-hit-rate work.

Measures, over one or more existing validation DBs, how many stored evidence quotes carry `exact` vs
`region` coordinate precision, and — for the `region` ones — confirms the quote IS a canonical substring
of its chunk text (so it *should* be locatable) yet `locate_quote_for_attachment` returns not-found. That
"matched-the-chunk-but-locator-missed" bucket is the honest improvement target. No writes to any DB.

Run from the project root:  python .claude/highlight_diag.py [db1.sqlite db2.sqlite ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from sqlalchemy import create_engine, text  # noqa: E402

from app.backend.pdf_processing.extraction import canonical_text_contains  # noqa: E402
from app.backend.pdf_processing.location import locate_quote_for_attachment  # noqa: E402

DEFAULT_DBS = [
    ".local/visual/inc124_live.sqlite",
    ".local/visual/inc124.sqlite",
    ".local/showcase/showcase.sqlite",
    ".local/nli-05-broad/validation.sqlite",
]

MISS_SAMPLE_MAX = 40


def stored_precision(bbox_json) -> str | None:
    if not bbox_json:
        return None
    rects = bbox_json
    if isinstance(rects, str):
        try:
            rects = json.loads(rects)
        except (TypeError, json.JSONDecodeError):
            return None
    if isinstance(rects, list):
        for r in rects:
            if isinstance(r, dict) and r.get("coordinate_precision"):
                return r["coordinate_precision"]
        return None
    if isinstance(rects, dict):
        return rects.get("coordinate_precision")
    return None


def run_db(db_path: str, misses: list[dict]) -> dict:
    engine = create_engine(f"sqlite:///{db_path}")
    counts = {
        "rows": 0,
        "stored_exact": 0,
        "stored_region": 0,
        "stored_none": 0,
        "pdf_missing": 0,
        "locate_found": 0,
        "locate_not_found": 0,
        "contains_true": 0,
        "bucket_matched_but_missed": 0,  # canonical_text_contains True AND locate not found
        "located_offpage": 0,  # located but not on chunk pages
    }
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    """
                SELECT eq.id, eq.quote_text, eq.bbox_json,
                       c.text AS chunk_text, c.page_start AS c_ps, c.page_end AS c_pe, c.attachment_id
                FROM evidence_quotes eq
                JOIN chunks c ON c.id = eq.chunk_id
                WHERE eq.quote_text IS NOT NULL AND c.attachment_id IS NOT NULL
                """
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            counts["rows"] += 1
            sp = stored_precision(row["bbox_json"])
            counts[f"stored_{sp or 'none'}"] = counts.get(f"stored_{sp or 'none'}", 0) + 1
            quote = row["quote_text"]
            chunk_text = row["chunk_text"] or ""
            contains = canonical_text_contains(needle=quote, haystack=chunk_text)
            if contains:
                counts["contains_true"] += 1
            try:
                match = locate_quote_for_attachment(conn, int(row["attachment_id"]), quote)
            except Exception as exc:  # noqa: BLE001
                counts["pdf_missing"] += 1
                if "no such" in str(exc).lower() or "cannot open" in str(exc).lower():
                    pass
                continue
            if match.found:
                counts["locate_found"] += 1
                c_ps, c_pe = row["c_ps"], row["c_pe"]
                if c_ps is not None and match.page_start is not None:
                    expected = set(range(int(c_ps), int(c_pe or c_ps) + 1))
                    located = set(range(int(match.page_start), int(match.page_end or match.page_start) + 1))
                    if not (expected & located):
                        counts["located_offpage"] += 1
            else:
                counts["locate_not_found"] += 1
                if contains:
                    counts["bucket_matched_but_missed"] += 1
                    if len(misses) < MISS_SAMPLE_MAX:
                        misses.append(
                            {
                                "db": Path(db_path).name,
                                "quote": quote[:240],
                                "chunk_pages": [row["c_ps"], row["c_pe"]],
                                "stored_precision": sp,
                                "chunk_excerpt": (chunk_text[:300]),
                            }
                        )
    engine.dispose()
    return counts


def main(argv: list[str]) -> int:
    dbs = argv or DEFAULT_DBS
    dbs = [d for d in dbs if Path(d).exists()]
    misses: list[dict] = []
    totals: dict = {}
    print(f"=== Precise-highlighting diagnostic over {len(dbs)} DB(s) ===\n")
    for db in dbs:
        c = run_db(db, misses)
        for k, v in c.items():
            totals[k] = totals.get(k, 0) + v
        print(f"{Path(db).name}: {c}")
    print("\n=== TOTALS ===")
    for k, v in totals.items():
        print(f"  {k:28s} {v}")
    rows = totals.get("rows", 0) or 1
    ex = totals.get("stored_exact", 0)
    rg = totals.get("stored_region", 0)
    print(f"\n  stored exact rate:  {ex}/{rows} = {100 * ex / rows:.1f}%")
    print(f"  stored region rate: {rg}/{rows} = {100 * rg / rows:.1f}%")
    print(
        f"  matched-but-missed (the target bucket): {totals.get('bucket_matched_but_missed', 0)} "
        f"(these SHOULD be locatable)"
    )
    out = Path(".local/highlight-diag")
    out.mkdir(parents=True, exist_ok=True)
    (out / "misses.json").write_text(json.dumps(misses, indent=2), encoding="utf-8")
    print(f"\n  wrote {len(misses)} miss samples -> {out / 'misses.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
