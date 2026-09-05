"""Conservative section heading detection for PDF chunk metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_HEADING_CHARS = 90
MAX_HEADING_WORDS = 9

_NUMBERING_PREFIX_RE = re.compile(
    r"^\s*(?:(?:\d+(?:\.\d+)*)|(?:[IVXLCM]+)|(?:[A-Z]))[\.)]?\s+",
    flags=re.IGNORECASE,
)
_TRAILING_MARKS_RE = re.compile(r"[\s:;\u2013\u2014-]+$")
_MULTISPACE_RE = re.compile(r"\s+")

_SECTION_ALIASES: dict[str, set[str]] = {
    "abstract": {"abstract", "summary"},
    "introduction": {"introduction", "background"},
    "methods": {
        "data analysis",
        "materials and methods",
        "measures",
        "method",
        "methodology",
        "methods",
        "participants",
        "procedure",
        "statistical analysis",
    },
    "results": {"findings", "results"},
    "discussion": {"conclusion", "conclusions", "discussion", "limitations"},
    "data_availability": {
        "availability of data and materials",
        "data availability",
        "data availability statement",
    },
    "code_availability": {"code availability", "software availability"},
    "funding": {"funding", "funding information", "funding statement"},
    "conflict_of_interest": {
        "competing interests",
        "conflict of interest",
        "conflicts of interest",
        "declaration of competing interest",
    },
    "ethics": {"ethical approval", "ethics", "ethics statement"},
    "references": {"bibliography", "references"},
    "supplementary_material": {
        "supporting information",
        "supplementary material",
        "supplementary materials",
    },
}

_ALIAS_TO_SECTION = {alias: section for section, aliases in _SECTION_ALIASES.items() for alias in aliases}


@dataclass(frozen=True)
class SectionHeading:
    key: str
    label: str
    raw: str


class SectionTracker:
    """Track the active paper section while iterating PDF text blocks."""

    def __init__(self) -> None:
        self.current_section: str | None = None

    def observe(self, text: str) -> SectionHeading | None:
        heading = detect_section_heading(text)
        if heading is not None:
            self.current_section = heading.key
        return heading

    def observe_block(self, block_text: str) -> bool:
        """Scan a PyMuPDF text block line-by-line for a section heading.

        PyMuPDF frequently merges a heading with the following body into one block, so the whole
        block rarely has heading shape (it is long / ends with a period); the heading is usually the
        block's first line. Update the active section from the first heading line found, and report
        whether the block is *only* that heading — so the caller skips emitting a pure heading as its
        own chunk while still labeling merged heading+body blocks with the section they open.
        """
        heading, line_count = scan_block_heading(block_text)
        if heading is not None:
            self.current_section = heading.key
        return heading is not None and line_count == 1


def scan_block_heading(block_text: str) -> tuple[SectionHeading | None, int]:
    """Pure scan: the first recognized heading in a block, plus its non-blank line count.

    Shared (inc 578) by ``SectionTracker.observe_block``, which also advances section state, and by
    the H1b source-component builder, which must recognize a pure-heading block *without* mutating
    any tracker -- calling ``observe_block`` a second time over the same page would double-advance
    the section. A block is a *pure* heading iff a heading was found and it is the block's only
    non-blank line.
    """
    lines = [line for line in block_text.split("\n") if line.strip()]
    for line in lines:
        heading = detect_section_heading(line)
        if heading is not None:
            return heading, len(lines)
    return None, len(lines)


def detect_section_heading(text: str) -> SectionHeading | None:
    """Return a recognized section heading, or None for ordinary prose."""
    raw = text.strip()
    if not _has_heading_shape(raw):
        return None

    normalized = _normalize_heading(raw)
    section = _ALIAS_TO_SECTION.get(normalized)
    if section is None:
        return None
    return SectionHeading(key=section, label=normalized, raw=raw)


def _has_heading_shape(text: str) -> bool:
    if not text or len(text) > MAX_HEADING_CHARS:
        return False
    if text.count("\n") > 1:
        return False
    if text.endswith("."):
        return False
    if any(mark in text for mark in (",", "?")):
        return False
    return len(_normalize_heading(text).split()) <= MAX_HEADING_WORDS


def _normalize_heading(text: str) -> str:
    without_numbering = _NUMBERING_PREFIX_RE.sub("", text.strip())
    without_marks = _TRAILING_MARKS_RE.sub("", without_numbering)
    return _MULTISPACE_RE.sub(" ", without_marks).casefold()
