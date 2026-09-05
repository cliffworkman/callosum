"""Deterministic per-chunk features: geometry from stored spans, shape from text.

No PDF is opened and no model is called. Every value is derived from columns the database already
has. Geometry and text features are computed in one pass because they share the loaded record.
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, asdict

from app.backend.pdf_processing.sections import (
    MAX_HEADING_WORDS,
    detect_section_heading,
)
from tools.evidence_hygiene.corpus import Chunk, PaperCalibration

_STOPWORDS = {
    "the", "of", "and", "in", "to", "a", "is", "was", "were", "for", "with", "that", "as", "on",
    "by", "at", "from", "this", "these", "we", "our", "are", "be", "been", "not", "but", "or",
    "an", "it", "its", "than", "which", "their", "there", "have", "has", "had",
}

_CAPTION = re.compile(r"^\s*(table|fig(?:ure)?\.?|figs?\.|scheme|panel|appendix)\s*[0-9ivxIVX]+\b", re.I)
_INITIALS = re.compile(r"\b[A-Z][a-z]+,\s*[A-Z]\.(?:\s*[A-Z]\.)?")
# Vancouver style prints "Zapatero ZD, Workman CI" with no comma before the initials, so the
# author pattern above misses it entirely -- which stopped a reference-region shape extension
# mid-list. Measured on this library the pattern alone also fires on 10% of body prose, so it
# carries a deliberately small weight and cannot make a chunk bibliographic on its own.
_INITIALS_VANCOUVER = re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z]{1,3}\b(?=[,;.]|\s+[A-Z][a-z])")
_ET_AL = re.compile(r"\bet\s+al\b", re.I)
_YEAR_PAREN = re.compile(r"\((?:19|20)\d{2}[a-z]?\)")
_YEAR = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")
_PAGE_RANGE = re.compile(r"\b\d+\s*[-‐-―]\s*\d+\b")
_VOLUME_ISSUE = re.compile(r"\b\d+\s*\(\d+\)\s*[,:]")
_DOI = re.compile(r"\b10\.\d{4,9}/\S+|doi\.org|doi:", re.I)
_NUMBERED_ENTRY = re.compile(r"^\s*\d{1,3}[\.\)]\s+[A-Z]")
_URL = re.compile(r"https?://|www\.", re.I)

# Front-matter subtypes. Amendment 3: front matter is NOT one undifferentiated class -- substantive
# abstract prose must not be treated like a keyword line or a publisher instruction.
_KEYWORD_LINE = re.compile(r"^\s*(key\s*words?|keywords)\s*[:.–-]", re.I)
_CITE_INSTRUCTION = re.compile(
    r"please cite this article|to cite this article|citation:\s|this is a pdf file|"
    r"uncorrected proof|accepted manuscript",
    re.I,
)
_PUBLICATION_META = re.compile(
    r"©|\(c\)\s|copyright|all rights reserved|creativecommons|creative commons|"
    r"received:.*accepted:|article reuse guidelines|sagepub|contents lists available|"
    r"sciencedirect|the author\(s\)|downloaded from|www\.nature\.com|springernature",
    re.I,
)


@dataclass
class Features:
    chunk_id: int
    raw_sha: str
    paper_id: int
    # geometry
    n_spans: int
    n_lines: int
    x0: float | None
    y0: float | None
    x1: float | None
    y1: float | None
    width_ratio: float | None
    line_fill: float | None
    y_top_frac: float | None
    y_bot_frac: float | None
    mean_span_h: float | None
    grid_support: int
    col_index: int
    # shape
    n_words: int
    n_chars: int
    alpha_ratio: float
    digit_ratio: float
    punct_ratio: float
    terminal_punct: bool
    caps_frac: float
    stop_frac: float
    biblio_score: float
    caption_match: bool
    heading_prefix_key: str | None
    heading_only: bool
    keyword_line: bool
    cite_instruction: bool
    publication_meta: bool
    contamination_ratio: float = 0.0

    def as_row(self) -> dict:
        return asdict(self)


def _biblio_score(text: str) -> float:
    """Weighted bibliographic shape. Deliberately independent of `chunks.section`.

    The section label cannot be load-bearing here: 10 of 108 papers have no references-labeled chunk
    at all, and 360 labeled-references chunks are real prose. The label is a corroborating feature
    added later by the classifier, never the detector itself.
    """
    t = text or ""
    if not t.strip():
        return 0.0
    score = 0.0
    score += 1.2 * min(len(_INITIALS.findall(t)), 3) / 3
    score += 0.5 * min(len(_INITIALS_VANCOUVER.findall(t)), 3) / 3
    score += 0.8 if _ET_AL.search(t) else 0.0
    score += 1.0 * min(len(_YEAR_PAREN.findall(t)) + len(_YEAR.findall(t)), 3) / 3
    score += 0.8 if _PAGE_RANGE.search(t) else 0.0
    score += 0.8 if _VOLUME_ISSUE.search(t) else 0.0
    score += 1.0 if _DOI.search(t) else 0.0
    score += 0.6 if _NUMBERED_ENTRY.match(t) else 0.0
    # Reference lists are semicolon/period dense relative to prose of the same length.
    words = max(len(t.split()), 1)
    score += 0.4 if (t.count(";") + t.count(".")) / words > 0.18 else 0.0
    return round(score, 3)


def _heading_prefix(text: str) -> tuple[str | None, bool]:
    """Recover a heading from a merged heading+body block.

    `SectionTracker.observe_block` splits on "\\n", but stored chunk text has had newlines collapsed
    by `_normalize_space`, so the production tracker cannot be re-run against the database. Scanning
    the first k words instead recovers the heading AND gives a stateless cross-check of the stateful
    tracker's labels.
    """
    words = (text or "").split()
    if not words:
        return None, False
    for k in range(min(MAX_HEADING_WORDS, len(words)), 0, -1):
        heading = detect_section_heading(" ".join(words[:k]))
        if heading is not None:
            return heading.key, k == len(words)
    return None, False


def _is_narrow_fragment(chunk: Chunk, col_w: float) -> bool:
    """A one-line, few-span chunk materially narrower than the paper's own text column."""
    box = chunk.box
    if not box or not col_w:
        return False
    return len(chunk.lines) == 1 and len(chunk.spans) <= 3 and (box[2] - box[0]) / col_w < 0.5


def _grid_support(chunk: Chunk, narrow_peers: list[Chunk], line_h: float) -> int:
    """How many NARROW peers on the same page share this chunk's row or column.

    Table-cell debris arrives with siblings forming a grid; a lone narrow chunk usually is not
    debris. This gregariousness requirement is what stops the rule eating isolated short evidence
    such as a reported effect size.

    Counting *all* peers rather than narrow ones was measured at 74% of the corpus -- every body
    paragraph shares a left margin with every other body paragraph, so left-edge alignment alone is
    not a table signal. Only narrow fragments can be a cell's siblings.
    """
    box = chunk.box
    if not box:
        return 0
    x0, y0, x1, y1 = box
    ymid = (y0 + y1) / 2
    tol_y = max(0.6 * line_h, 2.0)
    n = 0
    for peer in narrow_peers:
        if peer.chunk_id == chunk.chunk_id:
            continue
        pbox = peer.box
        if not pbox:
            continue
        pymid = (pbox[1] + pbox[3]) / 2
        same_row = abs(pymid - ymid) <= tol_y and abs(pbox[0] - x0) > 4.0
        same_col = abs(pbox[0] - x0) <= 2.0 and abs(pymid - ymid) > tol_y
        if same_row or same_col:
            n += 1
    return n


def compute(chunks: list[Chunk], cal: dict[int, PaperCalibration]) -> list[Features]:
    # Only NARROW fragments can be a table cell's siblings, so the per-page peer index holds only
    # those. See `_grid_support`.
    by_page: dict[tuple[int, int], list[Chunk]] = defaultdict(list)
    for c in chunks:
        pc0 = cal.get(c.paper_id)
        if c.page_start is not None and pc0 and pc0.n_columns and _is_narrow_fragment(c, pc0.col_w):
            by_page[(c.paper_id, int(c.page_start))].append(c)

    out: list[Features] = []
    for c in chunks:
        pc = cal.get(c.paper_id)
        box = c.box
        lines = c.lines
        line_h = pc.body_median_span_h if pc and pc.body_median_span_h else 10.0

        width_ratio = line_fill = y_top = y_bot = mean_h = None
        col_index = 0
        if box and pc:
            w = box[2] - box[0]
            # Width rules are only meaningful where a body-prose column could be calibrated.
            if pc.n_columns:
                width_ratio = round(w / pc.col_w, 4) if pc.col_w else None
                if lines:
                    lw = [max(s.x1 for s in ln) - min(s.x0 for s in ln) for ln in lines]
                    line_fill = round(statistics.mean(lw) / pc.col_w, 4) if pc.col_w else None
            page_h = max(pc.page_h, 1.0)
            y_top = round((box[1] - pc.page_box[1]) / page_h, 4)
            y_bot = round((box[3] - pc.page_box[1]) / page_h, 4)
            if pc.column_centers:
                mid = (box[0] + box[2]) / 2
                col_index = min(
                    range(len(pc.column_centers)),
                    key=lambda i: abs(pc.column_centers[i] - mid),
                )
        if c.spans:
            mean_h = round(statistics.mean(s.height for s in c.spans), 3)

        t = c.text or ""
        stripped = t.strip()
        chars = len(stripped)
        words = stripped.split()
        alpha = sum(ch.isalpha() for ch in stripped)
        digit = sum(ch.isdigit() for ch in stripped)
        punct = sum((not ch.isalnum()) and (not ch.isspace()) for ch in stripped)
        caps = sum(1 for w in words if w[:1].isupper())
        stops = sum(1 for w in words if w.lower().strip(".,;:()[]") in _STOPWORDS)
        hkey, honly = _heading_prefix(stripped)

        peers = by_page.get((c.paper_id, int(c.page_start))) if c.page_start is not None else None
        out.append(
            Features(
                chunk_id=c.chunk_id,
                raw_sha=c.raw_sha,
                paper_id=c.paper_id,
                n_spans=len(c.spans),
                n_lines=len(lines),
                x0=box[0] if box else None,
                y0=box[1] if box else None,
                x1=box[2] if box else None,
                y1=box[3] if box else None,
                width_ratio=width_ratio,
                line_fill=line_fill,
                y_top_frac=y_top,
                y_bot_frac=y_bot,
                mean_span_h=mean_h,
                grid_support=_grid_support(c, peers, line_h) if peers else 0,
                col_index=col_index,
                n_words=len(words),
                n_chars=chars,
                alpha_ratio=round(alpha / chars, 4) if chars else 0.0,
                digit_ratio=round(digit / chars, 4) if chars else 0.0,
                punct_ratio=round(punct / chars, 4) if chars else 0.0,
                terminal_punct=stripped.endswith((".", "?", "!")),
                caps_frac=round(caps / len(words), 4) if words else 0.0,
                stop_frac=round(stops / len(words), 4) if words else 0.0,
                biblio_score=_biblio_score(stripped),
                caption_match=bool(_CAPTION.match(stripped)),
                heading_prefix_key=hkey,
                heading_only=honly,
                keyword_line=bool(_KEYWORD_LINE.match(stripped)),
                cite_instruction=bool(_CITE_INSTRUCTION.search(stripped)),
                publication_meta=bool(_PUBLICATION_META.search(stripped)),
            )
        )
    return out


def main() -> None:
    from tools.evidence_hygiene.corpus import calibrate, load_chunks
    from tools.evidence_hygiene.store import connect

    chunks = load_chunks()
    cal = calibrate(chunks)
    feats = compute(chunks, cal)
    conn = connect()
    conn.executemany(
        "INSERT OR REPLACE INTO chunk_geom VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (f.chunk_id, f.raw_sha, f.n_spans, f.n_lines, f.x0, f.y0, f.x1, f.y1,
             f.width_ratio, f.line_fill, f.y_top_frac, f.y_bot_frac, f.mean_span_h,
             f.grid_support, f.col_index)
            for f in feats
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO chunk_shape VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (f.chunk_id, f.raw_sha, f.n_words, f.n_chars, f.alpha_ratio, f.digit_ratio,
             f.punct_ratio, int(f.terminal_punct), f.caps_frac, f.stop_frac, f.biblio_score,
             int(f.caption_match), f.heading_prefix_key, f.contamination_ratio)
            for f in feats
        ],
    )
    conn.commit()
    print(f"computed features for {len(feats)} chunks")
    print(f"  caption_match      {sum(f.caption_match for f in feats):>6}")
    print(f"  heading_prefix     {sum(f.heading_prefix_key is not None for f in feats):>6} "
          f"(heading-only {sum(f.heading_only for f in feats)})")
    print(f"  keyword_line       {sum(f.keyword_line for f in feats):>6}")
    print(f"  cite_instruction   {sum(f.cite_instruction for f in feats):>6}")
    print(f"  publication_meta   {sum(f.publication_meta for f in feats):>6}")
    print(f"  biblio_score>=2.5  {sum(f.biblio_score >= 2.5 for f in feats):>6}")
    print(f"  grid_support>=3    {sum(f.grid_support >= 3 for f in feats):>6}")


if __name__ == "__main__":
    main()
