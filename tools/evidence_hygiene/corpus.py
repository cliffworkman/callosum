"""Chunk loader + per-paper geometric calibration.

Everything here is derived from columns the database already has: ``text``, ``bbox_json``,
``section``, ``page_start``, ``page_end``, ``paper_id``, ``attachment_id``, ``chunk_version``.
No PDF is opened.

Two facts drive the design:

* ``bbox_json`` stores one dict PER SPAN -- ``{page, block, line, span, x0, y0, x1, y1}``
  (``extraction.py:240-249``). Block bbox and page width/height are discarded at ingest. Line
  structure is therefore *reconstructible* by grouping spans on ``(page, block, line)``, but the
  page box has to be ESTIMATED from span extrema.
* Because the true page width is unavailable, every width feature is normalized against ``col_w``
  -- the modal width of the paper's own body prose -- not against the page. In a two-column paper
  every body chunk is "narrow" relative to the page, so a page-relative rule would fire on the
  whole corpus.

``char_start``/``char_end`` are deliberately NOT loaded; see the package docstring.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from tools.evidence_hygiene.store import library_readonly, raw_sha


@dataclass(frozen=True)
class Span:
    page: int
    block: int
    line: int
    span: int
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass
class Chunk:
    chunk_id: int
    paper_id: int
    attachment_id: int
    text: str
    section: str | None
    page_start: int | None
    page_end: int | None
    chunk_version: str
    spans: tuple[Span, ...] = field(default_factory=tuple)

    @property
    def raw_sha(self) -> str:
        return raw_sha(self.text)

    @property
    def lines(self) -> list[list[Span]]:
        """Reconstruct line structure by grouping spans on (page, block, line)."""
        grouped: dict[tuple[int, int, int], list[Span]] = defaultdict(list)
        for s in self.spans:
            grouped[(s.page, s.block, s.line)].append(s)
        return [sorted(v, key=lambda s: s.span) for _, v in sorted(grouped.items())]

    @property
    def box(self) -> tuple[float, float, float, float] | None:
        if not self.spans:
            return None
        return (
            min(s.x0 for s in self.spans),
            min(s.y0 for s in self.spans),
            max(s.x1 for s in self.spans),
            max(s.y1 for s in self.spans),
        )

    @property
    def n_lines(self) -> int:
        return len(self.lines)


@dataclass
class PaperCalibration:
    paper_id: int
    col_w: float
    page_box: tuple[float, float, float, float]
    n_columns: int
    body_median_span_h: float
    n_chunks: int
    column_centers: tuple[float, ...] = ()

    @property
    def page_h(self) -> float:
        return self.page_box[3] - self.page_box[1]

    @property
    def page_w(self) -> float:
        return self.page_box[2] - self.page_box[0]


def _parse_spans(bbox_json: str | None) -> tuple[Span, ...]:
    if not bbox_json:
        return ()
    try:
        raw = json.loads(bbox_json)
    except Exception:
        return ()
    out: list[Span] = []
    if not isinstance(raw, list):
        return ()
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                Span(
                    page=int(item["page"]),
                    block=int(item.get("block", 0)),
                    line=int(item.get("line", 0)),
                    span=int(item.get("span", 0)),
                    x0=float(item["x0"]),
                    y0=float(item["y0"]),
                    x1=float(item["x1"]),
                    y1=float(item["y1"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(out)


def load_chunks(paper_ids: list[int] | None = None) -> list[Chunk]:
    sql = (
        "SELECT c.id, c.paper_id, c.attachment_id, c.text, c.section, c.page_start, c.page_end, "
        "c.chunk_version, c.bbox_json FROM chunks c JOIN papers p ON p.id = c.paper_id "
        "WHERE p.deleted_at IS NULL"
    )
    params: list = []
    if paper_ids:
        sql += f" AND c.paper_id IN ({','.join('?' * len(paper_ids))})"
        params = list(paper_ids)
    with library_readonly() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        Chunk(
            chunk_id=int(r["id"]),
            paper_id=int(r["paper_id"]),
            attachment_id=int(r["attachment_id"]),
            text=r["text"] or "",
            section=r["section"],
            page_start=r["page_start"],
            page_end=r["page_end"],
            chunk_version=r["chunk_version"] or "",
            spans=_parse_spans(r["bbox_json"]),
        )
        for r in rows
    ]


def _modal_width(widths: list[float], bin_pt: float = 6.0) -> float | None:
    """Modal width to the nearest `bin_pt`, resolved to the bin's own median."""
    if not widths:
        return None
    bins = Counter(round(w / bin_pt) for w in widths)
    top = bins.most_common(1)[0][0]
    members = [w for w in widths if round(w / bin_pt) == top]
    return statistics.median(members)


def _column_centers(mids: list[float], page_w: float) -> tuple[int, tuple[float, ...]]:
    """1-D split into 1 or 2 columns by the largest gap, accepted only if the gap is real."""
    if len(mids) < 8:
        return 1, ()
    s = sorted(mids)
    gaps = [(s[i + 1] - s[i], i) for i in range(len(s) - 1)]
    gap, idx = max(gaps)
    # A genuine two-column split leaves a wide empty corridor between the two centre clusters.
    if gap < 0.18 * page_w:
        return 1, (statistics.median(s),)
    left, right = s[: idx + 1], s[idx + 1 :]
    if len(left) < 4 or len(right) < 4:
        return 1, (statistics.median(s),)
    return 2, (statistics.median(left), statistics.median(right))


def calibrate(chunks: list[Chunk]) -> dict[int, PaperCalibration]:
    by_paper: dict[int, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_paper[c.paper_id].append(c)

    out: dict[int, PaperCalibration] = {}
    for paper_id, cs in by_paper.items():
        spans = [s for c in cs for s in c.spans]
        if not spans:
            continue
        page_box = (
            min(s.x0 for s in spans),
            min(s.y0 for s in spans),
            max(s.x1 for s in spans),
            max(s.y1 for s in spans),
        )
        page_w = max(page_box[2] - page_box[0], 1.0)

        # Body prose defines the column width: >=40 words AND >=3 reconstructed lines.
        body = [c for c in cs if len(c.text.split()) >= 40 and c.n_lines >= 3 and c.box]
        widths = [c.box[2] - c.box[0] for c in body]  # type: ignore[index]
        col_w = _modal_width(widths)
        if col_w is None or col_w <= 1.0:
            # No body prose to calibrate from (metadata-only or heavily fragmented paper).
            # Fall back to the widest observed chunk, and record it via n_columns=0 so the
            # classifier can decline to apply width rules rather than trusting a bad estimate.
            all_w = [c.box[2] - c.box[0] for c in cs if c.box]
            col_w = max(all_w) if all_w else page_w
            n_cols, centers = 0, ()
        else:
            mids = [(c.box[0] + c.box[2]) / 2 for c in body]  # type: ignore[index]
            n_cols, centers = _column_centers(mids, page_w)

        heights = [s.height for c in body for s in c.spans]
        out[paper_id] = PaperCalibration(
            paper_id=paper_id,
            col_w=col_w,
            page_box=page_box,
            n_columns=n_cols,
            body_median_span_h=statistics.median(heights) if heights else 0.0,
            n_chunks=len(cs),
            column_centers=centers,
        )
    return out


def main() -> None:
    chunks = load_chunks()
    cal = calibrate(chunks)
    with_geom = sum(1 for c in chunks if c.spans)
    print(f"loaded {len(chunks)} chunks / {len(cal)} papers; {with_geom} have parseable geometry")
    ncol = Counter(c.n_columns for c in cal.values())
    print(f"column estimate: {dict(ncol)}  (0 = uncalibratable, width rules must be skipped)")
    widths = [c.col_w for c in cal.values() if c.n_columns]
    if widths:
        print(f"col_w across papers: median {statistics.median(widths):.0f}pt  "
              f"min {min(widths):.0f}  max {max(widths):.0f}")
    ph = [c.page_h for c in cal.values()]
    pw = [c.page_w for c in cal.values()]
    print(f"estimated page box: median {statistics.median(pw):.0f} x {statistics.median(ph):.0f} pt "
          f"(US Letter = 612x792, A4 = 595x842)")
    from tools.evidence_hygiene.store import connect

    conn = connect()
    conn.executemany(
        "INSERT OR REPLACE INTO paper_calibration VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (c.paper_id, c.col_w, *c.page_box, c.n_columns, c.body_median_span_h, c.n_chunks, None)
            for c in cal.values()
        ],
    )
    conn.commit()
    print(f"wrote {len(cal)} calibration rows to the sidecar")


if __name__ == "__main__":
    main()
