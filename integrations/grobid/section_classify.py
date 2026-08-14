"""Classifies a GROBID section's verbatim title into the SAME canonical family taxonomy chunks.section already
uses (pdf_processing/sections.py) -- deliberately not a second, GROBID-specific taxonomy, so a GROBID-tagged
chunk and a heuristic-tagged chunk are directly comparable without a translation layer."""

from __future__ import annotations

from app.backend.pdf_processing.sections import detect_section_heading


def classify_section_title(title: str) -> str | None:
    """The canonical section family for a GROBID-extracted verbatim title, or None if unrecognized. The
    verbatim title itself (paper_sections.title) is always what's shown to the user; this is a derived,
    disclosed-as-heuristic label used only for section-family matching."""
    heading = detect_section_heading(title)
    return heading.key if heading is not None else None
