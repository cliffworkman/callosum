from __future__ import annotations

from types import SimpleNamespace

from app.backend.methods.evidence_anchors import anchor_evidence


def test_anchor_evidence_returns_exact_only_on_expected_page(monkeypatch):
    chunks = [
        {
            "text": "The model reported a random intercept for subject.",
            "page_start": 4,
            "page_end": 4,
            "attachment_id": 12,
            "bbox_json": [{"page": 4, "x0": 1, "y0": 2, "x1": 3, "y1": 4}],
        }
    ]

    def fake_locator(conn, attachment_id, quote):
        assert attachment_id == 12
        assert quote == "random intercept"
        return SimpleNamespace(
            found=True,
            page_start=4,
            page_end=4,
            rectangles=({"page": 4, "x0": 10, "y0": 20, "x1": 80, "y1": 34},),
        )

    monkeypatch.setattr("app.backend.methods.evidence_anchors.locate_quote_for_attachment", fake_locator)
    anchored = anchor_evidence(None, chunks, "random intercept", 4)
    assert anchored["coordinate_precision"] == "exact"
    assert anchored["bbox_json"][0]["coordinate_precision"] == "exact"
    assert anchored["bbox_json"][0]["page"] == 4


def test_anchor_evidence_falls_back_to_region_on_page_mismatch(monkeypatch):
    chunks = [
        {
            "text": "The model reported a random intercept for subject.",
            "page_start": 4,
            "page_end": 4,
            "attachment_id": 12,
            "bbox_json": [{"page": 4, "x0": 1, "y0": 2, "x1": 3, "y1": 4}],
        }
    ]

    def wrong_page_locator(conn, attachment_id, quote):
        return SimpleNamespace(
            found=True,
            page_start=2,
            page_end=2,
            rectangles=({"page": 2, "x0": 10, "y0": 20, "x1": 80, "y1": 34},),
        )

    monkeypatch.setattr("app.backend.methods.evidence_anchors.locate_quote_for_attachment", wrong_page_locator)
    anchored = anchor_evidence(None, chunks, "random intercept", 4)
    assert anchored["coordinate_precision"] == "region"
    assert anchored["bbox_json"][0]["coordinate_precision"] == "region"
    assert anchored["bbox_json"][0]["page"] == 4
