from __future__ import annotations

from app.backend.pdf_processing.sections import detect_section_heading
from integrations.grobid.section_classify import classify_section_title


def test_classify_section_title_matches_sections_py_exactly():
    """No taxonomy drift: this module must classify a heading identically to the heuristic's own function."""
    cases = ["1. Introduction", "Materials and Methods", "Results", "Discussion", "Data Availability Statement"]
    for title in cases:
        expected = detect_section_heading(title)
        expected_key = expected.key if expected is not None else None
        assert classify_section_title(title) == expected_key


def test_classify_section_title_unrecognized_returns_none():
    assert classify_section_title("A Whimsical Chapter Nobody Would Title A Real Paper") is None
