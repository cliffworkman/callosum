"""Deterministic structural classification of extracted chunks (inc 577, H1a).

Answers "what kind of unit is this?" from signals already stored at ingest: the text itself and the
per-span geometry in ``chunks.bbox_json``. Nothing here changes retrieval, ranking, eligibility, or
any chunk's text -- the evidence-hygiene study found that NO reason code clears the >=95% held-out
precision gate, so this increment ships the classification to be observed, not obeyed.

**I/O boundary (deliberate and enforced).** This module opens no database connection, constructs no
client, performs no network call and never reads a PDF. ``classify_paper`` takes already-resolved
inputs and returns a verdict per chunk. The caller (``tools/backfill_chunk_structure.py``) owns all
resolution. That is what makes this deterministic and testable from literals -- see
``tests/test_chunk_structure.py``, which builds every case by hand.

**Calibration is per paper, never per page.** Page width and height are discarded at ingest
(``extraction.py`` keeps only per-span boxes), so widths are normalized against ``col_w`` -- the
modal width of the paper's OWN body prose. Measured: in a two-column paper every body chunk is
"narrow" relative to the page, so a page-relative rule fires on the whole corpus.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from app.backend.pdf_processing.sections import MAX_HEADING_WORDS, detect_section_heading
from app.backend.persistence.schema_chunk_structure import DERIVATION_VERSION

# --- types (mirrors of the schema's closed vocabulary) -----------------------------------------
BODY_PROSE = "body_prose"
ABSTRACT_PROSE = "abstract_prose"
CAPTION = "caption"
REFERENCE_ENTRY = "reference_entry"
RUNNING_HEAD = "running_head"
RUNNING_FOOTER = "running_footer"
TABLE_CELL_DEBRIS = "table_cell_debris"
HEADING_FRAGMENT = "heading_fragment"
PUBLICATION_METADATA = "publication_metadata"
KEYWORD_LINE = "keyword_line"
CITATION_INSTRUCTION = "citation_instruction"
MATH_OR_SYMBOL = "math_or_symbol"
UNKNOWN = "unknown"

SCIENTIFIC = "scientific"
BIBLIOGRAPHIC = "bibliographic"
STRUCTURAL = "structural"
ROLE_UNKNOWN = "unknown"

# What KIND of evidence each type is. `unknown` maps to `unknown` -- never to "not evidence":
# measured, `unknown` holds real fragmentary statistics.
_ROLE_OF = {
    BODY_PROSE: SCIENTIFIC,
    ABSTRACT_PROSE: SCIENTIFIC,
    CAPTION: SCIENTIFIC,
    REFERENCE_ENTRY: BIBLIOGRAPHIC,
    RUNNING_HEAD: STRUCTURAL,
    RUNNING_FOOTER: STRUCTURAL,
    TABLE_CELL_DEBRIS: STRUCTURAL,
    HEADING_FRAGMENT: STRUCTURAL,
    PUBLICATION_METADATA: STRUCTURAL,
    KEYWORD_LINE: STRUCTURAL,
    CITATION_INSTRUCTION: STRUCTURAL,
    MATH_OR_SYMBOL: STRUCTURAL,
    UNKNOWN: ROLE_UNKNOWN,
}

_STOPWORDS = frozenset(
    "the of and in to a is was were for with that as on by at from this these we our are be been "
    "not but or an it its than which their there have has had".split()
)
_CAPTION_OPEN = re.compile(r"^\s*(table|fig(?:ure)?\.?|figs?\.|scheme|panel|appendix)\s*[0-9ivxIVX]+\b", re.I)
_KEYWORD_LINE = re.compile(r"^\s*(key\s*words?|keywords)\s*[:.–-]", re.I)
_CITE_INSTRUCTION = re.compile(
    r"(please|how to|to)\s+cite this article|citation:\s|this is a pdf file|uncorrected proof", re.I
)
_PUBLICATION_META = re.compile(
    r"©|copyright|all rights reserved|creative\s?commons|received:.*accepted:|"
    r"article reuse guidelines|sagepub|contents lists available|sciencedirect|the author\(s\)|"
    r"downloaded from|www\.nature\.com|springernature",
    re.I,
)
_INITIALS = re.compile(r"\b[A-Z][a-z]+,\s*[A-Z]\.(?:\s*[A-Z]\.)?")
_INITIALS_VANCOUVER = re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z]{1,3}\b(?=[,;.]|\s+[A-Z][a-z])")
_ET_AL = re.compile(r"\bet\s+al\b", re.I)
_YEAR = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")
_YEAR_PAREN = re.compile(r"\((?:19|20)\d{2}[a-z]?\)")
_PAGE_RANGE = re.compile(r"\b\d+\s*[-‐-―]\s*\d+\b")
_VOLUME_ISSUE = re.compile(r"\b\d+\s*\(\d+\)\s*[,:]")
_DOI = re.compile(r"\b10\.\d{4,9}/\S+|doi\.org|doi:", re.I)
_NUMBERED_ENTRY = re.compile(r"^\s*\d{1,3}[.)]\s+[A-Z]")
# A SENTENCE that refers to a table is prose, not a caption. Adjudicated false positive F45476:
# "Table 4 below shows the number of extracted statistics..." opens exactly like a caption but is
# body prose, and excluding it would delete real evidence. A caption LABELS its object; a sentence
# predicates something ABOUT it, so a finite verb right after the label is the discriminator.
_SENTENCE_ABOUT_TABLE = re.compile(
    r"^\s*(?:table|fig(?:ure)?\.?|figs?\.)\s*[0-9ivxIVX]+\s+"
    r"(?:(?:above|below|here)\s+)?"
    r"(?:shows?|lists?|presents?|reports?|summari[sz]es?|displays?|contains?|gives?|"
    r"provides?|indicates?|illustrates?|depicts?|details?)\b",
    re.I,
)


@dataclass(frozen=True)
class ChunkInput:
    """One chunk, exactly as stored. Built by the caller; this module never queries for it."""

    chunk_id: int
    paper_id: int
    text: str
    section: str | None = None
    page_start: int | None = None
    bbox_json: object = None
    chunk_version: str = ""


@dataclass(frozen=True)
class ChunkStructure:
    chunk_id: int
    chunk_type: str
    evidence_role: str
    reason_codes: list[str]
    confidence: float
    derivation_version: str = DERIVATION_VERSION
    reference_region: bool | None = None
    reference_region_source: str | None = None
    repeated_boilerplate: bool | None = None


@dataclass
class _Span:
    page: int
    block: int
    line: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class _Geometry:
    spans: list[_Span] = field(default_factory=list)

    @property
    def n_lines(self) -> int:
        return len({(s.page, s.block, s.line) for s in self.spans})

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


def _spans(bbox_json: object) -> _Geometry:
    """Parse stored span geometry.

    chunks.bbox_json is a SQLAlchemy JSON column, so a DB read hands back an ALREADY-DECODED
    list while a fixture or a raw sqlite3 read hands back a string. Accepting both is required:
    assuming a string silently disabled every geometry rule, because json.loads(list) raises
    TypeError and the guard swallowed it.
    """
    if not bbox_json:
        return _Geometry()
    if isinstance(bbox_json, (str, bytes)):
        try:
            raw = json.loads(bbox_json)
        except (TypeError, ValueError):
            return _Geometry()
    else:
        raw = bbox_json
    out: list[_Span] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                _Span(
                    page=int(item["page"]),
                    block=int(item.get("block", 0)),
                    line=int(item.get("line", 0)),
                    x0=float(item["x0"]),
                    y0=float(item["y0"]),
                    x1=float(item["x1"]),
                    y1=float(item["y1"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return _Geometry(out)


def biblio_score(text: str) -> float:
    """Bibliographic SHAPE, deliberately independent of ``chunks.section``.

    The section label cannot be load-bearing: measured, 10 of 108 papers have no references-labeled
    chunk at all, and hundreds of labeled-references chunks are real prose, because the ingest
    tracker labels everything after the first "References" heading.
    """
    t = text or ""
    if not t.strip():
        return 0.0
    score = 1.2 * min(len(_INITIALS.findall(t)), 3) / 3
    score += 0.5 * min(len(_INITIALS_VANCOUVER.findall(t)), 3) / 3
    score += 0.8 if _ET_AL.search(t) else 0.0
    score += 1.0 * min(len(_YEAR_PAREN.findall(t)) + len(_YEAR.findall(t)), 3) / 3
    score += 0.8 if _PAGE_RANGE.search(t) else 0.0
    score += 0.8 if _VOLUME_ISSUE.search(t) else 0.0
    score += 1.0 if _DOI.search(t) else 0.0
    score += 0.6 if _NUMBERED_ENTRY.match(t) else 0.0
    words = max(len(t.split()), 1)
    score += 0.4 if (t.count(";") + t.count(".")) / words > 0.18 else 0.0
    return round(score, 3)


def _heading_prefix(text: str) -> tuple[str | None, bool]:
    """Recover a heading from a merged heading+body block.

    The ingest tracker splits on newlines, but stored chunk text has had them collapsed, so it
    cannot be re-run against the database. Scanning the leading words recovers the heading instead.
    """
    words = (text or "").split()
    if not words:
        return None, False
    for k in range(min(MAX_HEADING_WORDS, len(words)), 0, -1):
        heading = detect_section_heading(" ".join(words[:k]))
        if heading is not None:
            return heading.key, k == len(words)
    return None, False


def _is_clear_prose(text: str, score: float) -> bool:
    words = (text or "").split()
    if len(words) < 20 or not text.strip().endswith((".", "?", "!")):
        return False
    stops = sum(1 for w in words if w.lower().strip(".,;:()[]") in _STOPWORDS)
    caps = sum(1 for w in words if w[:1].isupper())
    return stops / len(words) >= 0.22 and score < 1.5 and caps / len(words) < 0.45


def calibrate_column_width(chunks: list[ChunkInput]) -> float | None:
    """Modal width of the paper's own body prose, or None when it cannot be established.

    Returning None is a real answer: without it, width-based rules are skipped rather than run
    against a guessed scale.
    """
    widths = []
    for c in chunks:
        geom = _spans(c.bbox_json)
        box = geom.box
        if box and len(c.text.split()) >= 40 and geom.n_lines >= 3:
            widths.append(box[2] - box[0])
    if not widths:
        return None
    bins = Counter(round(w / 6.0) for w in widths)
    top = bins.most_common(1)[0][0]
    return statistics.median([w for w in widths if round(w / 6.0) == top])


def _narrow(geom: _Geometry, col_w: float) -> bool:
    box = geom.box
    return bool(box) and geom.n_lines == 1 and len(geom.spans) <= 3 and (box[2] - box[0]) / col_w < 0.5


def _grid_support(geom: _Geometry, peers: list[_Geometry]) -> int:
    """Narrow peers sharing this chunk's row or column.

    Table debris arrives with siblings forming a grid; a lone narrow chunk usually is not debris.
    This gregariousness requirement is what stops the rule eating isolated short evidence such as a
    reported effect size. Counting ALL peers rather than narrow ones was measured firing on 74% of
    the corpus, because every body paragraph shares a left margin with every other one.
    """
    box = geom.box
    if not box:
        return 0
    ymid = (box[1] + box[3]) / 2
    n = 0
    for peer in peers:
        pbox = peer.box
        if not pbox or peer is geom:
            continue
        pymid = (pbox[1] + pbox[3]) / 2
        same_row = abs(pymid - ymid) <= 6.0 and abs(pbox[0] - box[0]) > 4.0
        same_col = abs(pbox[0] - box[0]) <= 2.0 and abs(pymid - ymid) > 6.0
        if same_row or same_col:
            n += 1
    return n


def classify_paper(
    chunks: list[ChunkInput],
    *,
    reference_region: set[int] | None = None,
    reference_region_source: str = "none",
    repeated: dict[int, str] | None = None,
) -> list[ChunkStructure]:
    """Classify one paper's chunks. Pure: every input is supplied by the caller.

    ``reference_region`` is the set of chunk ids the caller inferred to sit inside the bibliography;
    ``repeated`` maps a chunk id to the page band ("top"/"bottom"/"middle") of a verbatim repeat.
    Both may be omitted, in which case those signals simply do not fire.
    """
    region = reference_region or set()
    repeats = repeated or {}
    col_w = calibrate_column_width(chunks)
    geoms = {c.chunk_id: _spans(c.bbox_json) for c in chunks}
    narrow_by_page: dict[int, list[_Geometry]] = defaultdict(list)
    if col_w:
        for c in chunks:
            if c.page_start is not None and _narrow(geoms[c.chunk_id], col_w):
                narrow_by_page[int(c.page_start)].append(geoms[c.chunk_id])

    out: list[ChunkStructure] = []
    for c in chunks:
        text = (c.text or "").strip()
        geom = geoms[c.chunk_id]
        score = biblio_score(text)
        reasons: list[str] = []
        in_region = (c.chunk_id in region) if region else None

        def verdict(kind: str, confidence: float, rule: str, _c=c, _reasons=reasons, _in=in_region) -> ChunkStructure:
            _reasons.append(rule)
            return ChunkStructure(
                chunk_id=_c.chunk_id,
                chunk_type=kind,
                evidence_role=_ROLE_OF[kind],
                reason_codes=_reasons,
                confidence=confidence,
                reference_region=_in,
                reference_region_source=reference_region_source if region else None,
                repeated_boilerplate=(_c.chunk_id in repeats) if repeats else None,
            )

        band = repeats.get(c.chunk_id)
        if band == "top":
            out.append(verdict(RUNNING_HEAD, 0.95, "repeat.top_band"))
            continue
        if band == "bottom":
            out.append(verdict(RUNNING_FOOTER, 0.95, "repeat.bottom_band"))
            continue
        if band:
            out.append(verdict(UNKNOWN, 0.4, "repeat.middle_band"))
            continue
        if _CITE_INSTRUCTION.search(text):
            out.append(verdict(CITATION_INSTRUCTION, 0.95, "text.cite_instruction"))
            continue
        if _KEYWORD_LINE.match(text):
            out.append(verdict(KEYWORD_LINE, 0.95, "text.keyword_line"))
            continue
        if _PUBLICATION_META.search(text) and not _is_clear_prose(text, score):
            out.append(verdict(PUBLICATION_METADATA, 0.85, "text.publication_meta"))
            continue
        if in_region:
            # Region membership is strong structural evidence, NOT final identity: real Results
            # prose was measured inside imperfect inferred bounds, so clear prose vetoes it.
            if _is_clear_prose(text, score) and not _CAPTION_OPEN.match(text):
                out.append(verdict(BODY_PROSE, 0.6, "ref_region.prose_veto"))
                continue
            out.append(verdict(REFERENCE_ENTRY, 0.85 if score >= 2.0 else 0.6, "ref_region.member"))
            continue
        if score >= 3.0 and not _is_clear_prose(text, score):
            out.append(verdict(REFERENCE_ENTRY, 0.7, "shape.biblio_score"))
            continue
        if _CAPTION_OPEN.match(text) and len(text.split()) >= 4 and not _SENTENCE_ABOUT_TABLE.match(text):
            out.append(verdict(CAPTION, 0.85, "text.caption_prefix"))
            continue
        heading_key, heading_only = _heading_prefix(text)
        if heading_only or (heading_key and len(text.split()) <= 6 and not text.endswith((".", "?", "!"))):
            out.append(verdict(HEADING_FRAGMENT, 0.9, "text.heading_only"))
            continue
        if col_w and c.page_start is not None and _narrow(geom, col_w):
            alpha = sum(ch.isalpha() for ch in text)
            if _grid_support(geom, narrow_by_page[int(c.page_start)]) >= 3 and (
                len(text.split()) <= 4 or (alpha / max(len(text), 1)) < 0.5
            ):
                out.append(verdict(TABLE_CELL_DEBRIS, 0.8, "geom.narrow+grid"))
                continue
        alpha_ratio = sum(ch.isalpha() for ch in text) / max(len(text), 1)
        if alpha_ratio < 0.3 and len(text.split()) <= 6:
            out.append(verdict(MATH_OR_SYMBOL, 0.7, "text.low_alpha"))
            continue
        if (c.section or "") == "abstract" and len(text.split()) >= 20:
            out.append(verdict(ABSTRACT_PROSE, 0.8, "section.abstract"))
            continue
        if _is_clear_prose(text, score):
            out.append(verdict(BODY_PROSE, 0.7, "shape.clear_prose"))
            continue
        # `unknown` is a real answer and never implies ineligibility.
        out.append(verdict(UNKNOWN, 0.3, "fallthrough"))
    return out
