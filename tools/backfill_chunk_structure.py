"""Derive inspectable structural metadata for chunks (inc 577, H1a). Read-only for the library.

    python tools/backfill_chunk_structure.py [--db-url sqlite:///...] [--paper-id N] [--limit N]
    python tools/backfill_chunk_structure.py --inspect <chunk_id>
    python tools/backfill_chunk_structure.py --summary

This script OWNS all I/O -- database reads and reference-metadata resolution -- and hands
already-resolved inputs to the pure classifier in
``app.backend.pdf_processing.chunk_structure``. Keeping the boundary here is what makes the
classifier deterministic and testable from literals.

Properties, all deliberate:

* **Cache-only. No network.** Reference metadata comes from what is already in
  ``external_api_cache`` and ``reference_instances``. Opening an existing library must never require
  connectivity, and a paper with no cached metadata classifies conservatively rather than guessing.
* **Additive and non-destructive.** Raw chunk text, embeddings, sections and every ingest-time
  column are untouched. Only ``chunk_structure`` is written.
* **Per-paper commit, so an interrupted run resumes** by simply re-running: a paper whose rows are
  missing or stale is re-derived, everything else is skipped.
* **Nothing on the retrieval path reads what this writes.** H1a ships the classification to be
  observed, not obeyed -- no reason code cleared the >=95% precision gate.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# Script mode puts only this file's own directory on sys.path, not the project root, so the
# sibling `app` package is invisible without this (the same defect inc 508 found in
# run_https.py, invoked exactly as its docs said).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy import text as sqltext

from app.backend.pdf_processing.chunk_structure import ChunkInput, classify_paper
from app.backend.persistence.chunk_structure_repo import (
    papers_with_current_structure,
    raw_sha,
    replace_paper_structure,
    structure_for_chunk,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.schema import attachments, chunks, papers
from app.backend.persistence.schema_chunk_structure import DERIVATION_VERSION, chunk_structure

DEFAULT_DB_URL = "sqlite:///.local/validation/validation.sqlite"

_WORD = re.compile(r"[a-z0-9]+")
_DOI_IN_TEXT = re.compile(r"10\.\d{4,9}/[^\s\"'<>,;)\]]+", re.I)
_NGRAM = 6
_MIN_TITLE_WORDS = 8
_MIN_DISTINCT_REFS = 4
_CLUSTER_GAP = 25
_REPEAT_MIN_PAGES = 3
_REPEAT_MAX_WORDS = 25


# --------------------------------------------------------------------------------------------
# Resolution (all I/O lives here, never in the classifier)
# --------------------------------------------------------------------------------------------
def _dense_key(text: str) -> str:
    """Aggressively normalized, whitespace-free comparison key. COMPARISON ONLY.

    Never stored, never quoted, never model-facing. It exists so a title split across a line break
    still matches its metadata: "Functional connectiv-\\nity in late-life depression" and
    "Functional Connectivity in Late-Life Depression" collapse to the same key, which is what took
    title matching from ~31% to ~90% of a paper's known references without needing to solve
    hyphenation first.
    """
    from app.backend.embeddings.models import normalize_text, strip_punctuation
    from app.backend.pdf_processing.extraction import _canonical_characters

    canon = normalize_text(strip_punctuation(_canonical_characters(text or "")))
    return re.sub(r"[^a-z0-9]+", "", canon)


def load_reference_metadata(conn) -> dict[int, list[dict]]:
    """{paper_id: [reference records]} from LOCAL caches only. No network, ever."""
    by_doi = {
        (r[1] or "").lower().strip(): int(r[0])
        for r in conn.execute(select(papers.c.id, papers.c.doi).where(papers.c.doi.is_not(None)))
    }
    out: dict[int, list[dict]] = defaultdict(list)
    rows = conn.execute(
        sqltext("SELECT cache_key, response_json FROM external_api_cache WHERE provider = 'crossref'")
    ).fetchall()
    for key, payload in rows:
        paper_id = by_doi.get((key or "").lower().strip())
        if paper_id is None:
            continue
        try:
            doc = json.loads(payload)
        except (TypeError, ValueError):
            continue
        message = doc.get("message", doc) if isinstance(doc, dict) else {}
        for ref in (message.get("reference") or []) if isinstance(message, dict) else []:
            if isinstance(ref, dict):
                out[paper_id].append(ref)
    # `reference_instances` is the persisted Meta-Reference product -- authoritative where present.
    try:
        for citing, title, doi in conn.execute(sqltext("SELECT citing_paper_id, title, doi FROM reference_instances")):
            out[int(citing)].append({"article-title": title, "DOI": doi})
    except Exception:  # noqa: BLE001 - an older library may predate the table
        pass
    return dict(out)


def infer_reference_region(rows: list[dict], refs: list[dict]) -> tuple[set[int], str]:
    """Locate the bibliography by finding the paper's OWN known references in its text.

    Multi-prong by necessity, not preference: measured across 31,122 cached reference entries, 89%
    carry a DOI but only 42% carry a title -- yet the DOI is frequently not PRINTED in the reference
    list (older works especially), so dense-key title matching is the strongest general signal and
    the DOI is a corroborator. The region is the densest cluster of matches, never the first match:
    a cited title can legitimately appear in the body.
    """
    if not refs:
        return set(), "none"
    doi_map: dict[str, int] = {}
    gram_map: dict[str, int] = {}
    for ordinal, ref in enumerate(refs):
        doi = ref.get("DOI")
        if isinstance(doi, str) and doi.strip():
            doi_map.setdefault(doi.strip().lower(), ordinal)
        title = ref.get("article-title") or ref.get("volume-title") or ref.get("unstructured")
        if isinstance(title, str):
            words = _WORD.findall(title.lower())
            if len(words) >= _MIN_TITLE_WORDS:
                key = _dense_key(title)
                for i in range(0, max(len(key) - 40, 1), 10):
                    gram_map.setdefault(key[i : i + 40], ordinal)
    if not doi_map and not gram_map:
        return set(), "none"

    keys = [_dense_key(r["text"]) for r in rows]
    hits: list[tuple[int, set[int]]] = []
    for i, row in enumerate(rows):
        found: set[int] = set()
        for token in {m.group(0).lower().rstrip(".") for m in _DOI_IN_TEXT.finditer(row["text"] or "")}:
            if token in doi_map:
                found.add(doi_map[token])
        window = "".join(keys[i : i + 4])
        for gram, ordinal in gram_map.items():
            if gram and gram in window:
                found.add(ordinal)
        if found:
            hits.append((i, found))
    if not hits:
        return set(), "none"

    clusters: list[list[tuple[int, set[int]]]] = [[hits[0]]]
    for hit in hits[1:]:
        if hit[0] - clusters[-1][-1][0] <= _CLUSTER_GAP:
            clusters[-1].append(hit)
        else:
            clusters.append([hit])
    n_distinct, best = max(((len({o for _, s in cl for o in s}), cl) for cl in clusters), key=lambda t: t[0])
    if n_distinct < _MIN_DISTINCT_REFS:
        return set(), "none"
    start, end = best[0][0], best[-1][0]
    while end + 1 < len(rows) and len(_WORD.findall(rows[end + 1]["text"] or "")) < _MIN_TITLE_WORDS:
        end += 1
    return {rows[i]["id"] for i in range(start, end + 1)}, "anchored"


def detect_repeats(rows: list[dict]) -> dict[int, str]:
    """Verbatim short text repeating across >=3 of a paper's pages at a stable x -> page furniture.

    Position stability is what makes this defensible rather than merely plausible; the page band
    ("top"/"bottom") is what keeps running_head and running_footer distinct.
    """
    from app.backend.summarization.chunk_filtering import _repetition_key

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = _repetition_key(row["text"] or "")
        if key and len(key.split()) <= _REPEAT_MAX_WORDS:
            groups[key].append(row)
    tops = [r["y_top"] for r in rows if r["y_top"] is not None]
    page_top = min(tops) if tops else 0.0
    page_bottom = max(tops) if tops else 1.0
    span = max(page_bottom - page_top, 1.0)

    flagged: dict[int, str] = {}
    for members in groups.values():
        pages = {m["page_start"] for m in members if m["page_start"] is not None}
        if len(pages) < _REPEAT_MIN_PAGES:
            continue
        xs = [m["x0"] for m in members if m["x0"] is not None]
        if len(xs) > 1 and (max(xs) - min(xs)) > 12.0:
            continue  # not a stable margin position
        for member in members:
            if member["y_top"] is None:
                flagged[member["id"]] = "middle"
                continue
            rel = (member["y_top"] - page_top) / span
            flagged[member["id"]] = "top" if rel < 0.12 else ("bottom" if rel > 0.85 else "middle")
    return flagged


def _paper_rows(conn, paper_id: int) -> list[dict]:
    stmt = (
        select(
            chunks.c.id,
            chunks.c.paper_id,
            chunks.c.text,
            chunks.c.section,
            chunks.c.page_start,
            chunks.c.bbox_json,
            chunks.c.chunk_version,
        )
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .where(chunks.c.paper_id == paper_id, attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES))
        .order_by(chunks.c.id)
    )
    rows = []
    for row in conn.execute(stmt).mappings():
        record = dict(row)
        x0 = y_top = None
        if record["bbox_json"]:
            try:
                raw = record["bbox_json"]
                # A JSON column read hands back a decoded list; only a string needs loads().
                spans = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                boxes = [s for s in spans if isinstance(s, dict) and "x0" in s]
                if boxes:
                    x0 = min(float(s["x0"]) for s in boxes)
                    y_top = min(float(s["y0"]) for s in boxes)
            except (TypeError, ValueError):
                pass
        record["x0"], record["y_top"] = x0, y_top
        rows.append(record)
    return rows


def backfill(engine, *, paper_id: int | None = None, limit: int | None = None, force: bool = False) -> dict:
    stats = {"papers": 0, "chunks": 0, "skipped_current": 0, "no_reference_metadata": 0}
    with engine.begin() as conn:
        targets = (
            [paper_id]
            if paper_id
            else [int(r[0]) for r in conn.execute(select(papers.c.id).where(papers.c.deleted_at.is_(None)))]
        )
        done = set() if force else papers_with_current_structure(conn, DERIVATION_VERSION)
        references = load_reference_metadata(conn)

    for pid in targets:
        if pid in done:
            stats["skipped_current"] += 1
            continue
        if limit is not None and stats["papers"] >= limit:
            break
        with engine.begin() as conn:  # per-paper commit: an interrupted run simply resumes
            rows = _paper_rows(conn, pid)
            if not rows:
                continue
            refs = references.get(pid, [])
            if not refs:
                stats["no_reference_metadata"] += 1
            region, source = infer_reference_region(rows, refs)
            repeats = detect_repeats(rows)
            results = classify_paper(
                [
                    ChunkInput(
                        chunk_id=int(r["id"]),
                        paper_id=int(r["paper_id"]),
                        text=r["text"] or "",
                        section=r["section"],
                        page_start=r["page_start"],
                        bbox_json=r["bbox_json"],
                        chunk_version=r["chunk_version"] or "",
                    )
                    for r in rows
                ],
                reference_region=region,
                reference_region_source=source,
                repeated=repeats,
            )
            written = replace_paper_structure(
                conn,
                paper_id=pid,
                results=results,
                source={int(r["id"]): (raw_sha(r["text"] or ""), r["chunk_version"] or "") for r in rows},
            )
            stats["papers"] += 1
            stats["chunks"] += written
    return stats


def inspect(engine, chunk_id: int) -> None:
    with engine.begin() as conn:
        row = (
            conn.execute(
                select(chunks, papers.c.title)
                .select_from(chunks.join(papers, papers.c.id == chunks.c.paper_id))
                .where(chunks.c.id == chunk_id)
            )
            .mappings()
            .first()
        )
        if row is None:
            print(f"no chunk {chunk_id}")
            return
        derived = structure_for_chunk(conn, chunk_id)

    print(f"chunk {chunk_id}  paper {row['paper_id']} ({(row['title'] or '')[:60]})")
    print(f"  attachment {row['attachment_id']}  page {row['page_start']}  section {row['section'] or 'NULL'}")
    print(f"  raw text: {' '.join((row['text'] or '').split())[:200]}")
    if row["bbox_json"]:
        try:
            spans = [s for s in json.loads(row["bbox_json"]) if isinstance(s, dict)]
            lines = {(s.get("page"), s.get("block"), s.get("line")) for s in spans}
            print(f"  geometry: {len(spans)} spans / {len(lines)} lines")
        except (TypeError, ValueError):
            print("  geometry: unparseable")
    if derived is None:
        print("  structure: NOT DERIVED (run the backfill)")
        return
    print(f"  chunk_type     : {derived.chunk_type}")
    print(f"  evidence_role  : {derived.evidence_role}")
    print(f"  reason codes   : {derived.reason_codes}")
    print(f"  confidence     : {derived.confidence}")
    print(f"  reference region: {derived.reference_region} (source {derived.reference_region_source})")
    print(f"  repeated boilerplate: {derived.repeated_boilerplate}")
    print(f"  derivation     : {derived.derivation_version}{'  [STALE]' if derived.is_stale else ''}")


def summarize(engine) -> None:
    with engine.begin() as conn:
        rows = conn.execute(select(chunk_structure.c.chunk_type, chunk_structure.c.evidence_role)).fetchall()
    if not rows:
        print("no derived rows yet")
        return
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for chunk_type, role in rows:
        counts[(chunk_type, role)] += 1
    total = len(rows)
    print(f"{total} classified chunks\n")
    print(f"  {'chunk_type':<24}{'evidence_role':<16}{'n':>7}{'share':>8}")
    for (chunk_type, role), n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {chunk_type:<24}{role:<16}{n:>7}{100 * n / total:>7.1f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", default=os.environ.get("CALLOSUM_DB_URL", DEFAULT_DB_URL))
    parser.add_argument("--paper-id", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true", help="re-derive even where rows are current")
    parser.add_argument("--inspect", type=int, metavar="CHUNK_ID")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    engine = make_engine(args.db_url)
    if args.inspect is not None:
        inspect(engine, args.inspect)
        return
    if args.summary:
        summarize(engine)
        return
    stats = backfill(engine, paper_id=args.paper_id, limit=args.limit, force=args.force)
    print(
        f"classified {stats['chunks']} chunks across {stats['papers']} papers "
        f"({stats['skipped_current']} already current, "
        f"{stats['no_reference_metadata']} without cached reference metadata)"
    )


if __name__ == "__main__":
    sys.exit(main())
