"""WIP-side methods-section text assembly for analytic-flexibility surfacing (backlog #37).

A real, disclosed asymmetry (confirmed against app/backend/wip/content.py and
app/backend/document_text.py during implementation, not assumed): non-PDF WIP files carry a
per-block raw heading string in ``ContentBlock.section`` (e.g. "Methods", "3. Methods", lifted
from a JATS <title>/ODT <h>/HTML <hN> element), which ``detect_section_heading`` can classify
into a canonical section family exactly the way ``citations/section_scope.py``'s
``expected_section_family`` already classifies a LibreOffice draft's current heading. PDF WIP
files' raw_blocks always carry ``section=None`` -- PyMuPDF text blocks have no per-block heading
text to classify (unlike the Library-paper ingest pipeline, which runs a stateful
``SectionTracker`` over PDF text as it chunks). Rather than inventing a fragile per-PDF-block
heuristic to paper over that gap, this module honestly degrades to "every block, capped" and
reports ``scoped=False`` so a caller can disclose the degrade rather than silently presenting a
whole-manuscript search as equivalent to real section-scoping. The same degrade also covers a
non-PDF manuscript whose real section headings simply never match the "methods" family (an
unusual heading vocabulary) -- real section data existing does not guarantee a methods section
was found, and reporting "found nothing" would be less useful than the same disclosed degrade.
"""

from __future__ import annotations

from app.backend.pdf_processing.sections import detect_section_heading
from app.backend.wip.content import ContentBlock


def wip_methods_text(blocks: list[ContentBlock], *, max_chars: int = 20000) -> dict:
    """Assemble methods-section text from a WIP manuscript's content blocks.

    Returns ``{"text": str | None, "scoped": bool}``. ``scoped=True`` means real section-based
    scoping (matching ``ContentBlock.section`` headings against the "methods" family) produced
    the text. ``scoped=False`` with non-``None`` text means the honest whole-manuscript degrade
    was used instead -- disclosed, not silently presented as real scoping. ``text=None`` means no
    manuscript text was found at all.
    """
    if not blocks:
        return {"text": None, "scoped": False}

    methods_texts = [
        block.text for block in blocks if block.text and block.section and _is_methods_heading(block.section)
    ]
    if methods_texts:
        return {"text": "\n\n".join(methods_texts)[:max_chars], "scoped": True}

    all_text = "\n\n".join(block.text for block in blocks if block.text)
    if not all_text:
        return {"text": None, "scoped": False}
    return {"text": all_text[:max_chars], "scoped": False}


def _is_methods_heading(heading_text: str) -> bool:
    heading = detect_section_heading(heading_text)
    return heading is not None and heading.key == "methods"
