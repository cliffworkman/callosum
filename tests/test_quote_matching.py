"""Tests for quote_matching.py: locate_quote and anchor_quote."""

from __future__ import annotations

from app.backend.pdf_processing.quote_matching import anchor_quote


def test_anchor_quote_exact_when_located_with_rectangles(tmp_path, monkeypatch):
    """Quote found + rectangles present → exact with the rectangles as bbox_json."""
    from app.backend.pdf_processing import quote_matching

    def fake_locate(pdf_path, quote):
        return quote_matching.QuoteMatch(
            found=True,
            quote=quote,
            page_start=3,
            page_end=3,
            rectangles=[{"page": 3, "x0": 10.0, "y0": 20.0, "x1": 90.0, "y1": 40.0}],
        )

    monkeypatch.setattr(quote_matching, "locate_quote", fake_locate)
    result = anchor_quote("fake.pdf", "participants were excluded if under 18")
    assert result == {
        "anchor_state": "exact",
        "page": 3,
        "bbox_json": [{"page": 3, "x0": 10.0, "y0": 20.0, "x1": 90.0, "y1": 40.0}],
        "reason": None,
    }


def test_anchor_quote_region_when_located_without_rectangles(monkeypatch):
    """Quote found but no rectangles → region with no bbox_json and reason 'no_rects'."""
    from app.backend.pdf_processing import quote_matching

    def fake_locate(pdf_path, quote):
        return quote_matching.QuoteMatch(found=True, quote=quote, page_start=5, page_end=5, rectangles=None)

    monkeypatch.setattr(quote_matching, "locate_quote", fake_locate)
    result = anchor_quote("fake.pdf", "a covariate was added")
    assert result == {
        "anchor_state": "region",
        "page": 5,
        "bbox_json": None,
        "reason": "no_rects",
    }


def test_anchor_quote_unanchored_when_not_found_falls_back_to_claimed_page(monkeypatch):
    """Quote not found → unanchored with claimed_page and reason 'quote_not_found'."""
    from app.backend.pdf_processing import quote_matching

    def fake_locate(pdf_path, quote):
        return quote_matching.QuoteMatch(found=False, quote=quote, page_start=None, page_end=None, rectangles=None)

    monkeypatch.setattr(quote_matching, "locate_quote", fake_locate)
    result = anchor_quote("fake.pdf", "not really in the paper", claimed_page=7)
    assert result == {
        "anchor_state": "unanchored",
        "page": 7,
        "bbox_json": None,
        "reason": "quote_not_found",
    }
