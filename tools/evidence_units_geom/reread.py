"""What does rereading the PDF recover that stored data cannot? (study sections 6D/6E/7)

One pass per PDF answers four questions that all need the same file open:

1. **Reading-order ground truth.** `page.get_text("words")` returns MuPDF's native
   `(block_no, line_no, word_no)`. `quote_matching.py:81-86` records that using this native order
   rather than geometric `sort=True` lifted exact-highlight hit-rate from ~53% to ~96% on this very
   library -- so native order is the closest thing to ground truth available without human reading.
   Stored `bbox_json["block"]` is a post-sort `enumerate` index and is NOT the same integer, so this
   measures how far the stored order actually is from the real one.

2. **Table structure.** `page.find_tables()` -- already used in production by
   `app/backend/document_tables.py:104`, which returns rows, cells, headers and per-row bboxes in
   callosum's own coordinate idiom, but only ephemerally and never for captions on the PDF path.

3. **Caption-to-table association**, the grey zone: a caption naming what values mean, and the
   values themselves, currently live in unrelated chunks. Association here is by GEOMETRY ONLY --
   nearest caption-shaped text directly above or below a table bbox on the same page.

4. **What the discarded fields are worth**: block bbox and page dimensions, both computed at
   extraction and thrown away.

No model is used anywhere. Where geometry does not justify an association, none is asserted.
"""

from __future__ import annotations

import json
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DB = ROOT / ".local" / "evidence-units-geom" / "h1a.sqlite"
OUT = ROOT / ".local" / "evidence-units-geom"

CAPTION_OPEN = re.compile(r"^\s*(table|fig(?:ure)?\.?|figs?\.|scheme|panel)\s*[0-9ivxIVX]+\b", re.I)
CAPTION_GAP_PT = 90.0  # how far above/below a table a caption may sit and still be associated


def native_reading_order(page) -> list[tuple[int, int, int, float, float, str]]:
    """MuPDF native (block, line, word) order -- the reading-order reference."""
    words = page.get_text("words")  # x0,y0,x1,y1,word,block_no,line_no,word_no
    return sorted(
        ((int(w[5]), int(w[6]), int(w[7]), float(w[0]), float(w[1]), str(w[4])) for w in words),
        key=lambda t: (t[0], t[1], t[2]),
    )


def analyse_pdf(path: Path, stored_pages: dict[int, list[dict]]) -> dict:
    import pymupdf

    result = {
        "pages": 0,
        "page_dims": [],
        "tables": 0,
        "table_rows": 0,
        "tables_with_header": 0,
        "tables_with_caption": 0,
        "caption_gaps": [],
        "order_pages_compared": 0,
        "order_disagreement": [],
        "image_blocks": 0,
    }
    with pymupdf.open(path) as doc:
        for pno, page in enumerate(doc, start=1):
            result["pages"] += 1
            result["page_dims"].append((round(page.rect.width, 1), round(page.rect.height, 1)))

            raw = page.get_text("dict", sort=False)
            result["image_blocks"] += sum(1 for b in raw.get("blocks", []) if b.get("type") != 0)

            # --- reading-order ground truth vs stored order -------------------------------------
            stored = stored_pages.get(pno)
            if stored:
                native = native_reading_order(page)
                if native:
                    # Rank each stored chunk by where its first word appears in native order.
                    word_rank = {}
                    for rank, (_b, _l, _w, x0, y0, _text) in enumerate(native):
                        word_rank.setdefault((round(x0), round(y0)), rank)
                    ranked = []
                    for chunk in stored:
                        key = (round(chunk["x0"]), round(chunk["y0"]))
                        best = word_rank.get(key)
                        if best is None:  # nearest word start within a small radius
                            cands = [
                                r
                                for (wx, wy), r in word_rank.items()
                                if abs(wx - chunk["x0"]) < 6 and abs(wy - chunk["y0"]) < 6
                            ]
                            best = min(cands) if cands else None
                        if best is not None:
                            ranked.append((chunk["stored_block"], best, chunk["chunk_id"]))
                    if len(ranked) >= 4:
                        result["order_pages_compared"] += 1
                        by_stored = [c for _s, _n, c in sorted(ranked, key=lambda r: r[0])]
                        by_native = [c for _s, _n, c in sorted(ranked, key=lambda r: r[1])]
                        pos = {v: i for i, v in enumerate(by_native)}
                        seq = [pos[v] for v in by_stored]
                        n = len(seq)
                        disc = sum(1 for i in range(n) for j in range(i + 1, n) if seq[i] > seq[j])
                        result["order_disagreement"].append(disc / (n * (n - 1) / 2))

            # --- tables --------------------------------------------------------------------------
            try:
                finder = page.find_tables()
            except Exception:  # noqa: BLE001 - a detector failure is data, not a crash
                continue
            page_captions = [
                (b["bbox"], " ".join(s["text"] for line in b.get("lines", []) for s in line.get("spans", [])))
                for b in raw.get("blocks", [])
                if b.get("type") == 0
            ]
            page_captions = [(bb, txt) for bb, txt in page_captions if CAPTION_OPEN.match(txt.strip())]

            for table in finder.tables:
                result["tables"] += 1
                rows = table.rows or []
                result["table_rows"] += len(rows)
                if table.header is not None and getattr(table.header, "names", None):
                    result["tables_with_header"] += 1
                tb = table.bbox
                # Nearest caption-shaped block directly above or below, same page, within the gap.
                best = None
                for bb, txt in page_captions:
                    above = tb[1] - bb[3]
                    below = bb[1] - tb[3]
                    gap = above if above >= 0 else (below if below >= 0 else None)
                    if gap is not None and gap <= CAPTION_GAP_PT:
                        if best is None or gap < best[0]:
                            best = (gap, txt)
                if best:
                    result["tables_with_caption"] += 1
                    result["caption_gaps"].append(round(best[0], 1))
    return result


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    attachments = conn.execute(
        "SELECT id, paper_id, COALESCE(resolved_path, original_path) FROM attachments"
    ).fetchall()

    stored: dict[int, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for chunk_id, att_id, page, raw in conn.execute(
        "SELECT id, attachment_id, page_start, bbox_json FROM chunks WHERE bbox_json IS NOT NULL"
    ):
        spans = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        spans = [s for s in (spans or []) if isinstance(s, dict) and "x0" in s]
        if spans:
            stored[att_id][int(page or 0)].append(
                {
                    "chunk_id": chunk_id,
                    "stored_block": int(spans[0].get("block", 0)),
                    "x0": min(s["x0"] for s in spans),
                    "y0": min(s["y0"] for s in spans),
                }
            )

    totals = Counter()
    order_all: list[float] = []
    gaps_all: list[float] = []
    dims: Counter = Counter()
    per_paper = []
    processed = 0
    for att_id, paper_id, path in attachments:
        if not path or not Path(path).is_file():
            continue
        if limit and processed >= limit:
            break
        try:
            res = analyse_pdf(Path(path), stored.get(att_id, {}))
        except Exception:  # noqa: BLE001
            totals["failed"] += 1
            continue
        processed += 1
        for key in ("pages", "tables", "table_rows", "tables_with_header", "tables_with_caption", "image_blocks"):
            totals[key] += res[key]
        totals["order_pages"] += res["order_pages_compared"]
        order_all.extend(res["order_disagreement"])
        gaps_all.extend(res["caption_gaps"])
        for d in res["page_dims"]:
            dims[d] += 1
        per_paper.append(
            {
                "attachment_id": att_id,
                "paper_id": paper_id,
                **{k: res[k] for k in ("pages", "tables", "table_rows", "tables_with_caption")},
            }
        )

    print(f"PDFs analysed: {processed} ({totals['failed']} failed)\n")
    print(f"pages                         : {totals['pages']}")
    print(f"image blocks dropped at ingest: {totals['image_blocks']}")
    print(f"distinct page sizes           : {len(dims)}  most common {dims.most_common(3)}")
    print()
    print("TABLES via find_tables()")
    print(f"  tables detected             : {totals['tables']}")
    print(f"  table rows                  : {totals['table_rows']}")
    print(
        f"  with a detected header row  : {totals['tables_with_header']} "
        f"({100 * totals['tables_with_header'] / max(totals['tables'], 1):.0f}%)"
    )
    print(
        f"  with a caption associable   : {totals['tables_with_caption']} "
        f"({100 * totals['tables_with_caption'] / max(totals['tables'], 1):.0f}%)"
    )
    if gaps_all:
        print(f"  caption gap (pt)            : median {statistics.median(gaps_all):.1f}  max {max(gaps_all):.1f}")
    print()
    print("READING ORDER: stored block index vs MuPDF native order")
    if order_all:
        print(f"  pages compared              : {len(order_all)}")
        print(f"  median pair disagreement    : {statistics.median(order_all):.3f}")
        print(f"  mean                        : {statistics.mean(order_all):.3f}")
        print(
            f"  pages >25% disagreement     : {sum(1 for v in order_all if v > 0.25)} "
            f"({100 * sum(1 for v in order_all if v > 0.25) / len(order_all):.0f}%)"
        )
        print(
            f"  pages perfectly ordered     : {sum(1 for v in order_all if v == 0)} "
            f"({100 * sum(1 for v in order_all if v == 0) / len(order_all):.0f}%)"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "reread.json").write_text(
        json.dumps(
            {
                "pdfs": processed,
                "totals": dict(totals),
                "page_sizes": {str(k): v for k, v in dims.most_common(10)},
                "order_median": statistics.median(order_all) if order_all else None,
                "order_perfect_fraction": (sum(1 for v in order_all if v == 0) / len(order_all) if order_all else None),
                "caption_gap_median": statistics.median(gaps_all) if gaps_all else None,
                "per_paper": per_paper,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print("\nwrote reread.json")


if __name__ == "__main__":
    main()
