from __future__ import annotations

from app.backend.wip.analytic_flexibility_text import wip_methods_text
from app.backend.wip.content import ContentBlock


def test_non_pdf_blocks_are_scoped_to_the_methods_section():
    blocks = [
        ContentBlock(text="Intro text.", section="Introduction", page_start=1, page_end=1),
        ContentBlock(text="Methods part one.", section="Methods", page_start=2, page_end=2),
        ContentBlock(text="Methods part two.", section="3. Methods", page_start=2, page_end=2),
        ContentBlock(text="Results text.", section="Results", page_start=3, page_end=3),
    ]
    result = wip_methods_text(blocks)
    assert result == {"text": "Methods part one.\n\nMethods part two.", "scoped": True}


def test_pdf_blocks_have_no_section_and_degrade_to_all_blocks_disclosed():
    blocks = [
        ContentBlock(text="Whatever text is on page one.", section=None, page_start=1, page_end=1),
        ContentBlock(text="Whatever text is on page two.", section=None, page_start=2, page_end=2),
    ]
    result = wip_methods_text(blocks)
    assert result == {
        "text": "Whatever text is on page one.\n\nWhatever text is on page two.",
        "scoped": False,
    }


def test_no_blocks_at_all_returns_none():
    assert wip_methods_text([]) == {"text": None, "scoped": False}


def test_max_chars_caps_the_degraded_all_blocks_path():
    blocks = [ContentBlock(text="x" * 100, section=None, page_start=1, page_end=1)]
    result = wip_methods_text(blocks, max_chars=10)
    assert result["text"] is not None and len(result["text"]) == 10


def test_sectioned_blocks_with_no_methods_match_degrade_to_all_blocks():
    """Real section data is present, but none of it classifies as "methods" -- rather than
    silently reporting nothing found, this degrades to the same honest whole-manuscript path
    used when there is no section data at all (e.g. an unusual heading vocabulary)."""
    blocks = [
        ContentBlock(text="Intro text.", section="Introduction", page_start=1, page_end=1),
        ContentBlock(text="Results text.", section="Results", page_start=2, page_end=2),
    ]
    result = wip_methods_text(blocks)
    assert result == {"text": "Intro text.\n\nResults text.", "scoped": False}


def test_blocks_with_no_text_are_skipped_in_the_scoped_path():
    blocks = [
        ContentBlock(text="Methods part one.", section="Methods", page_start=1, page_end=1),
        ContentBlock(text="", section="Methods", page_start=1, page_end=1),
    ]
    result = wip_methods_text(blocks)
    assert result == {"text": "Methods part one.", "scoped": True}
