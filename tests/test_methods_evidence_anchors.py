from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.evidence_anchors import anchor_evidence
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper


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
    anchored = anchor_evidence(None, chunks, "random intercept", 4, pdf_attachment_ids={12})
    assert anchored["coordinate_precision"] == "exact"
    assert anchored["bbox_json"][0]["coordinate_precision"] == "exact"
    assert anchored["bbox_json"][0]["page"] == 4
    assert anchored["attachment_id"] == 12


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
    anchored = anchor_evidence(None, chunks, "random intercept", 4, pdf_attachment_ids={12})
    assert anchored["coordinate_precision"] == "region"
    assert anchored["bbox_json"][0]["coordinate_precision"] == "region"
    assert anchored["bbox_json"][0]["page"] == 4
    assert anchored["attachment_id"] == 12


def _chunk(conn, paper_id: int, attachment_id: int, text: str, page: int, ordinal: int) -> None:
    create_chunk(
        conn,
        paper_id=paper_id,
        attachment_id=attachment_id,
        text=text,
        page_start=page,
        page_end=page,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="fixture",
        extraction_version="1",
        chunking_strategy="paragraph",
        chunk_version=f"methods-attachment-{ordinal}",
        source_attachment_checksum=f"secondary-{paper_id}",
    )


def test_methods_endpoints_retain_the_secondary_pdf_attachment(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Multi-file methods", csl_json={"title": "Multi-file methods"})
        primary_id = create_attachment(
            conn,
            paper_id=paper_id,
            role="primary",
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="primary",
        )
        secondary_id = create_attachment(
            conn,
            paper_id=paper_id,
            role="supplement",
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="secondary",
        )
        _chunk(conn, paper_id, secondary_id, "The result was t(19) = 2.53, p = .02, BF10 = 2.9.", 7, 1)
        _chunk(conn, paper_id, secondary_id, "We fit a linear mixed model with y ~ x + (1 | subject).", 8, 2)
        _chunk(
            conn,
            paper_id,
            secondary_id,
            "We conducted a random-effects meta-analysis of Hedges' g; heterogeneity was I2 = 62%.",
            9,
            3,
        )
        _chunk(
            conn,
            paper_id,
            secondary_id,
            "Data availability: all data are openly available at https://osf.io/ab12c/.",
            10,
            4,
        )
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    statcheck = client.get(f"/papers/{paper_id}/statcheck").json()
    bayes = client.get(f"/papers/{paper_id}/bayes").json()
    lmm = client.get(f"/papers/{paper_id}/lmm").json()
    meta = client.get(f"/papers/{paper_id}/meta-analysis").json()
    transparency = client.get(f"/papers/{paper_id}/transparency").json()

    assert primary_id != secondary_id
    assert statcheck["results"][0]["attachment_id"] == secondary_id
    assert bayes["results"][0]["attachment_id"] == secondary_id
    assert any(check["attachment_id"] == secondary_id for check in lmm["checks"] if check["evidence"])
    assert any(check["attachment_id"] == secondary_id for check in meta["checks"] if check["evidence"])
    assert (
        next(check for check in transparency["checks"] if check["key"] == "data_availability")["attachment_id"]
        == secondary_id
    )


def test_non_pdf_methods_evidence_does_not_target_the_pdf_route(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="HTML methods", csl_json={"title": "HTML methods"})
        create_attachment(
            conn,
            paper_id=paper_id,
            role="primary",
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="primary-html-paper",
        )
        html_id = create_attachment(
            conn,
            paper_id=paper_id,
            role="supplement",
            storage_mode="linked",
            availability="available",
            content_type="text/html",
            checksum="html",
        )
        _chunk(
            conn,
            paper_id,
            html_id,
            "Data availability: all data are openly available at https://osf.io/ab12c/.",
            1,
            1,
        )
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    checks = client.get(f"/papers/{paper_id}/transparency").json()["checks"]
    evidence = next(check for check in checks if check["key"] == "data_availability")
    assert evidence["page"] == 1
    assert evidence["attachment_id"] is None
