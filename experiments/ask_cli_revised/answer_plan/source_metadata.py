"""Deterministic source labels from library citation metadata (Phase-30 Step 2, item D). Pure apart from the optional
read-only extract step. The model never authors source identity: labels come only from stored metadata, and a paper with
no usable metadata gets a neutral label.

Label forms follow citeproc short-author-date conventions:
  narrative      "Workman et al. (2021)"    (used when a source is the grammatical subject)
  parenthetical  "(Workman & Doe, 2021)"
  list           "Workman & Doe, 2021"      (source list entries)
Two different papers whose labels would be identical receive citeproc-style year suffixes (2021a, 2021b) in paper-id order.

    python -m experiments.ask_cli_revised.answer_plan.source_metadata --db COPY.sqlite \
        --fingerprint FINGERPRINT.json --sealed 11_verified_ledger.json --out OUT.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def extract_from_library(db_path: Path, paper_ids: list[int], fingerprint_path: Path) -> dict:
    """Read-only extract of the citation fields for the given papers. Opens the library copy with mode=ro."""
    con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    try:
        records = {}
        for pid in sorted(set(paper_ids)):
            row = con.execute("select title, year, csl_json from papers where id=?", (pid,)).fetchone()
            if row is None:
                records[str(pid)] = {"authors": [], "year": None}
                continue
            _title, year_column, csl_json = row
            csl = json.loads(csl_json) if csl_json else {}
            authors = [a.get("family") for a in csl.get("author", []) if a.get("family")]
            issued = (csl.get("issued") or {}).get("date-parts") or []
            year = issued[0][0] if issued and issued[0] else year_column
            records[str(pid)] = {"authors": authors, "year": int(year) if year else None}
    finally:
        con.close()
    fingerprint = json.loads(Path(fingerprint_path).read_text(encoding="utf-8"))
    return {
        "record": "source_metadata_extract",
        "source": "library copy opened read-only; citation fields only (no titles, no text)",
        "library_fingerprint_sha256": fingerprint.get("sha256") or fingerprint.get("library_sha256"),
        "papers": records,
    }


def load_extract(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _family_phrase(authors: list[str], joiner: str) -> str:
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} {joiner} {authors[1]}"
    return f"{authors[0]} et al."


def label_for(pid: int, record: dict | None, year_suffix: str = "") -> dict:
    """The three label forms for one paper. Neutral when metadata are absent."""
    authors = [a for a in ((record or {}).get("authors") or []) if a]
    if not authors:
        neutral = f"Source {pid}"
        return {"narrative": neutral, "parenthetical": f"({neutral})", "list": neutral, "neutral": True}
    year = (record or {}).get("year")
    year_text = (str(year) if year else "n.d.") + year_suffix
    narrative_name = _family_phrase(authors, "and")
    parenthetical_name = _family_phrase(authors, "&")
    return {
        "narrative": f"{narrative_name} ({year_text})",
        "parenthetical": f"({parenthetical_name}, {year_text})",
        "list": f"{parenthetical_name}, {year_text}",
        "neutral": False,
    }


def labels_for(extract: dict | None, paper_ids: list[int]) -> dict:
    """paper id -> label record. A missing extract yields neutral labels for every paper. Colliding labels are suffixed."""
    papers = (extract or {}).get("papers") or {}
    ids = sorted(set(paper_ids))
    plain = {pid: label_for(pid, papers.get(str(pid))) for pid in ids}
    by_list: dict[str, list[int]] = {}
    for pid in ids:
        if not plain[pid]["neutral"]:
            by_list.setdefault(plain[pid]["list"], []).append(pid)
    out = dict(plain)
    for same in by_list.values():
        if len(same) < 2:
            continue
        for index, pid in enumerate(same):
            out[pid] = label_for(pid, papers.get(str(pid)), year_suffix="abcdefghijklmnopqrstuvwxyz"[index])
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--fingerprint", type=Path, required=True)
    parser.add_argument("--sealed", type=Path, required=True, help="sealed verified ledger; supplies the paper ids")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    sealed = json.loads(args.sealed.read_text(encoding="utf-8"))
    paper_ids = sorted({row["paper_id"] for row in sealed["verified_propositions"]})
    record = extract_from_library(args.db, paper_ids, args.fingerprint)
    args.out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "papers": len(record["papers"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
