"""Can trustworthy local reading order be reconstructed from stored geometry? (study section 6B)

This is the foundation everything else rests on: prose reunification, caption-to-table association
and multi-page table continuation all presuppose knowing what follows what.

Two things must be established before any of that, and the first is a defect:

**The stored block index is not MuPDF's block number.** `extraction.py:144` iterates
`enumerate(text_dict.get("blocks", []))` AFTER `get_text("dict", sort=True)`, so `bbox_json["block"]`
is the ordinal position in the GEOMETRICALLY SORTED list, including image blocks that are then
dropped. `quote_matching.py:102` stores MuPDF's native `word[5]` instead. The two integers are
different numbering schemes and are not comparable. Nothing joins them today, so this is latent --
but any reconstruction that assumes "block index == reading order" inherits it silently.

**`sort=True` sorts blocks only.** Ordering is by `(y1, x0)`, i.e. top-to-bottom then
left-to-right across the WHOLE page. On a two-column page that interleaves the columns, which is
exactly the failure `quote_matching.py:81-86` documents for the flat-document case.

So this module reconstructs reading order independently -- cluster columns from x-midpoints, then
order within a column by y -- and MEASURES disagreement with stored order rather than assuming
either is right. Where geometry cannot decide, it reports that instead of forcing an order.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / ".local" / "evidence-units-geom" / "h1a.sqlite"


@dataclass
class Unit:
    chunk_id: int
    paper_id: int
    page: int
    stored_block: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def xmid(self) -> float:
        return (self.x0 + self.x1) / 2


def load_page_units(conn: sqlite3.Connection) -> dict[tuple[int, int], list[Unit]]:
    rows = conn.execute(
        "SELECT id, paper_id, page_start, bbox_json, text FROM chunks WHERE bbox_json IS NOT NULL"
    ).fetchall()
    pages: dict[tuple[int, int], list[Unit]] = defaultdict(list)
    for chunk_id, paper_id, page, raw, text in rows:
        spans = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        spans = [s for s in (spans or []) if isinstance(s, dict) and "x0" in s]
        if not spans:
            continue
        pages[(paper_id, int(page or 0))].append(
            Unit(
                chunk_id=chunk_id,
                paper_id=paper_id,
                page=int(page or 0),
                stored_block=int(spans[0].get("block", 0)),
                x0=min(s["x0"] for s in spans),
                y0=min(s["y0"] for s in spans),
                x1=max(s["x1"] for s in spans),
                y1=max(s["y1"] for s in spans),
                text=text or "",
            )
        )
    return pages


def detect_columns(units: list[Unit]) -> tuple[int, list[float]]:
    """Column count and boundaries from x-midpoints. Returns (n_columns, boundaries).

    Single-column is the conservative default: a two-column verdict requires a genuinely empty
    corridor, because mis-splitting a one-column page would fabricate an interleaving that is not
    there.
    """
    body = [u for u in units if len(u.text.split()) >= 12]
    if len(body) < 6:
        return 1, []
    mids = sorted(u.xmid for u in body)
    span = mids[-1] - mids[0]
    if span <= 1:
        return 1, []
    gaps = [(mids[i + 1] - mids[i], i) for i in range(len(mids) - 1)]
    gap, idx = max(gaps)
    # A real column corridor is a large share of the horizontal spread AND splits the page into two
    # populated halves.
    if gap < 0.35 * span:
        return 1, []
    left, right = mids[: idx + 1], mids[idx + 1 :]
    if len(left) < 3 or len(right) < 3:
        return 1, []
    return 2, [(left[-1] + right[0]) / 2]


def reading_order(units: list[Unit]) -> list[Unit]:
    """Geometry-derived reading order: column-major, then top-to-bottom within a column."""
    n_cols, bounds = detect_columns(units)
    if n_cols == 1:
        return sorted(units, key=lambda u: (u.y0, u.x0))
    boundary = bounds[0]
    return sorted(units, key=lambda u: (0 if u.xmid < boundary else 1, u.y0, u.x0))


def kendall_disagreement(a: list[int], b: list[int]) -> float:
    """Fraction of ordered pairs whose relative order differs between two sequences."""
    pos_b = {v: i for i, v in enumerate(b)}
    seq = [pos_b[v] for v in a if v in pos_b]
    n = len(seq)
    if n < 2:
        return 0.0
    discordant = sum(1 for i in range(n) for j in range(i + 1, n) if seq[i] > seq[j])
    return discordant / (n * (n - 1) / 2)


def main() -> None:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    pages = load_page_units(conn)

    # Column count is a per-paper property; decide it from the paper, apply it per page.
    by_paper: dict[int, list[Unit]] = defaultdict(list)
    for (paper_id, _page), units in pages.items():
        by_paper[paper_id].extend(units)
    paper_cols = {pid: detect_columns(us)[0] for pid, us in by_paper.items()}
    print(f"papers: {len(paper_cols)}  column estimate: {dict(Counter(paper_cols.values()))}\n")

    # 1. Is the stored block index monotonic in geometry-derived reading order?
    stats: dict[int, list[float]] = {1: [], 2: []}
    big_disagreements = []
    for (paper_id, page), units in pages.items():
        if len(units) < 4:
            continue
        stored = [u.chunk_id for u in sorted(units, key=lambda u: (u.stored_block, u.y0))]
        derived = [u.chunk_id for u in reading_order(units)]
        d = kendall_disagreement(stored, derived)
        stats[paper_cols.get(paper_id, 1)].append(d)
        if d > 0.25:
            big_disagreements.append((paper_id, page, round(d, 3), len(units)))

    print("DISAGREEMENT between stored block order and geometry-derived reading order")
    print(f"  {'layout':<16}{'pages':>7}{'median':>9}{'mean':>8}{'>25% disagree':>15}")
    for cols, label in ((1, "one-column"), (2, "two-column")):
        vals = stats[cols]
        if not vals:
            continue
        bad = sum(1 for v in vals if v > 0.25)
        print(
            f"  {label:<16}{len(vals):>7}{statistics.median(vals):>9.3f}"
            f"{statistics.mean(vals):>8.3f}{bad:>13} ({100 * bad / len(vals):.0f}%)"
        )

    # 2. Where does chunk-ID order (the naive assumption) differ from geometry?
    id_vs_geom = []
    for (_paper_id, _page), units in pages.items():
        if len(units) < 4:
            continue
        by_id = [u.chunk_id for u in sorted(units, key=lambda u: u.chunk_id)]
        derived = [u.chunk_id for u in reading_order(units)]
        id_vs_geom.append(kendall_disagreement(by_id, derived))
    print(
        f"\n  chunk-ID order vs geometry: median disagreement "
        f"{statistics.median(id_vs_geom):.3f} over {len(id_vs_geom)} pages"
    )

    # 3. Adjacency: how often is the NEXT chunk by id also the next in reading order?
    agree = total = 0
    for (_paper_id, _page), units in pages.items():
        derived = reading_order(units)
        for i in range(len(derived) - 1):
            total += 1
            if derived[i + 1].chunk_id == derived[i].chunk_id + 1:
                agree += 1
    print(f"  next-by-id is also next-in-reading-order: {agree}/{total} ({100 * agree / max(total, 1):.1f}%)")

    out = ROOT / ".local" / "evidence-units-geom" / "reading_order.json"
    out.write_text(
        json.dumps(
            {
                "paper_columns": dict(Counter(paper_cols.values())),
                "stored_vs_geometry_median": {str(c): (statistics.median(v) if v else None) for c, v in stats.items()},
                "chunkid_vs_geometry_median": statistics.median(id_vs_geom),
                "adjacency_agreement": agree / max(total, 1),
                "worst_pages": sorted(big_disagreements, key=lambda r: -r[2])[:25],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {out.name}")


if __name__ == "__main__":
    main()
