"""Increment 429: deterministic, evidence-bearing canonical registration commitments."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.registration_schema import (
    paper_registration_links,
    registration_commitments,
    registration_document_versions,
)
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper


def _seed_version(
    conn,
    *,
    structured: dict,
    chunks: list[tuple[str, str | None, int]],
    provider: str = "osf",
) -> tuple[int, int, int]:
    paper_id = create_paper(conn, title="Published report", csl_json={"title": "Published report"})
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="managed",
        availability="available",
        content_type="text/plain" if provider == "osf" else "application/pdf",
        checksum="registration-hash",
        file_size=100,
        attachment_type="registration",
        role="preregistration",
    )
    link_id = int(
        conn.execute(
            insert(paper_registration_links).values(
                paper_id=paper_id,
                attachment_id=attachment_id,
                provider=provider,
                external_id="reg-1",
                link_status="confirmed",
                linkage_class="explicit-linkage",
                match_method="manual-confirmation",
                match_evidence_json=[],
                user_confirmed=True,
                content_hash="registration-hash",
            )
        ).inserted_primary_key[0]
    )
    version_id = int(
        conn.execute(
            insert(registration_document_versions).values(
                link_id=link_id,
                paper_id=paper_id,
                attachment_id=attachment_id,
                provider=provider,
                external_id="reg-1",
                content_hash="registration-hash",
                structured_json=structured,
                rendered_text="fixture",
                source_metadata_json={},
                retrieved_at=datetime.now(timezone.utc),
            )
        ).inserted_primary_key[0]
    )
    for text, section, page in chunks:
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text=text,
            section=section,
            page_start=page,
            page_end=page,
            bbox_coordinate_system="pdf-points",
            bbox_json={"x0": 10, "y0": 20, "x1": 100, "y1": 50},
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="fixture",
            chunk_version="1",
            source_attachment_checksum="registration-hash",
        )
    return paper_id, version_id, attachment_id


def test_structured_osf_questions_map_to_canonical_fields_with_verbatim_evidence(temp_db_url: str) -> None:
    structured = {
        "format": "callosum-registration-v1",
        "provider": "osf",
        "title": "Experiment 1 attention plan",
        "registered_at": "2023-01-02T10:00:00Z",
        "registration_status": "public",
        "questions": [
            {
                "response_key": "sample",
                "question_block_id": "block-sample",
                "question_group_id": "group-sample",
                "label": "Planned sample size",
                "section": "Sampling plan",
                "answer": "We will recruit 120 participants.",
                "answer_order": 0,
            },
            {
                "response_key": "outcome",
                "question_block_id": "block-outcome",
                "label": "Primary outcome",
                "section": "Variables",
                "answer": "The primary outcome is response accuracy.",
                "answer_order": 1,
            },
            {
                "response_key": "analysis",
                "question_block_id": "block-analysis",
                "label": "Statistical model",
                "section": "Analysis plan",
                "answer": "We will fit a logistic regression.",
                "answer_order": 2,
            },
        ],
        "response_metadata": {
            "updated_response_keys": ["analysis"],
            "revision_justification": "Clarified the model before data collection.",
        },
    }
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, version_id, attachment_id = _seed_version(
            conn,
            structured=structured,
            chunks=[
                (
                    "Planned sample size\nWe will recruit 120 participants.\nPrimary outcome\n"
                    "The primary outcome is response accuracy.",
                    "Sampling plan",
                    1,
                ),
                ("Statistical model\nWe will fit a logistic regression.", "Analysis plan", 2),
            ],
        )
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.post(f"/papers/{paper_id}/registration-versions/{version_id}/commitments/extract")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["local_only"] is True
    assert "not a judgment" in payload["note"]
    by_type = {row["field_type"]: row for row in payload["commitments"]}
    assert {
        "study-identity",
        "registration-timing",
        "sample-size-target",
        "primary-outcome",
        "statistical-model",
        "deviation-amendment-statement",
    } <= set(by_type)
    sample = by_type["sample-size-target"]
    assert sample["structured_value"]["target_n"] == 120
    assert sample["evidence_text"] == "We will recruit 120 participants."
    assert sample["attachment_id"] == attachment_id
    assert sample["page"] == 1
    assert sample["source_locator"]["question_block_id"] == "block-sample"
    assert sample["source_locator"]["registration_content_hash"] == "registration-hash"
    assert sample["extraction_method"] == "structured-osf"
    assert by_type["deviation-amendment-statement"]["evidence_text"].startswith("Clarified")

    # Re-running replaces only this extractor's proposal set and cannot duplicate evidence rows.
    second = client.post(f"/papers/{paper_id}/registration-versions/{version_id}/commitments/extract")
    assert second.status_code == 200
    assert second.json()["commitment_count"] == payload["commitment_count"]
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(registration_commitments)) == payload["commitment_count"]
    engine.dispose()


def test_aspredicted_numbered_questions_have_provider_specific_deterministic_mapping(temp_db_url: str) -> None:
    structured = {
        "provider": "aspredicted",
        "questions": [
            {
                "response_key": "aspredicted-2",
                "label": "What's the main question being asked or hypothesis being tested in this study?",
                "section": "AsPredicted questions",
                "answer": "Participants in condition A will recall more words.",
            },
            {
                "response_key": "aspredicted-7",
                "label": "How many observations will be collected or what will determine sample size?",
                "section": "AsPredicted questions",
                "answer": "We will recruit 200 participants.",
            },
        ],
    }
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, version_id, _ = _seed_version(
            conn,
            structured=structured,
            provider="aspredicted",
            chunks=[("Participants in condition A will recall more words.", "Question 2", 1)],
        )
    payload = TestClient(create_app(db_url=temp_db_url)).post(
        f"/papers/{paper_id}/registration-versions/{version_id}/commitments/extract"
    )
    assert payload.status_code == 200
    rows = {row["field_type"]: row for row in payload.json()["commitments"]}
    assert rows["hypothesis"]["extraction_confidence"] == "high"
    assert rows["sample-size-target"]["structured_value"]["target_n"] == 200
    engine.dispose()


def test_aspredicted_existing_data_answer_and_response_update_join_registration_timing(temp_db_url: str) -> None:
    structured = {
        "provider": "aspredicted",
        "registered_at": "2021/01/01",
        "questions": [
            {
                "response_key": "aspredicted-1",
                "label": "Have any data been collected for this study already?",
                "section": "AsPredicted questions",
                "answer": "Yes, some data have been collected for this study already.",
            },
            {
                "response_key": "aspredicted-2",
                "label": "What is the main hypothesis?",
                "section": "AsPredicted questions",
                "answer": "Condition A will improve recall.",
            },
        ],
        "response_history": [
            {"date_modified": "2021-01-01T00:00:00Z", "is_original_response": True},
            {"date_modified": "2021-05-01T00:00:00Z", "revision_justification": "Clarified analysis."},
        ],
    }
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, version_id, _ = _seed_version(conn, structured=structured, provider="aspredicted", chunks=[])
    payload = TestClient(create_app(db_url=temp_db_url)).post(
        f"/papers/{paper_id}/registration-versions/{version_id}/commitments/extract"
    )
    assert payload.status_code == 200
    timing = next(row for row in payload.json()["commitments"] if row["field_type"] == "registration-timing")
    assert timing["structured_value"]["existing_data_collected"] is True
    assert timing["structured_value"]["updated_at"] == "2021-05-01T00:00:00Z"
    assert "Existing-data response" in timing["evidence_text"]
    assert not any(row["source_key"] == "aspredicted-1" for row in payload.json()["commitments"])
    engine.dispose()


def test_manual_local_pdf_uses_only_exact_attachment_chunks_and_marks_text_mapping_uncertainty(
    temp_db_url: str,
) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, version_id, attachment_id = _seed_version(
            conn,
            provider="manual-local",
            structured={"provider": "manual-local", "attachment_id": 1},
            chunks=[
                ("Exclusion criteria\nParticipants failing either attention check will be excluded.", "Exclusions", 4),
                ("Administrative notes with no research plan content.", "Notes", 5),
            ],
        )
        # A paper article chunk is deliberately more tempting but must never enter registration extraction.
        article_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            content_type="application/pdf",
            checksum="article-hash",
            role="article-fulltext",
        )
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=article_id,
            text="Primary outcome: an article-only measure.",
            section="Methods",
            page_start=9,
            page_end=9,
            bbox_coordinate_system="pdf-points",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="fixture",
            chunk_version="1",
            source_attachment_checksum="article-hash",
        )
    client = TestClient(create_app(db_url=temp_db_url))
    result = client.post(f"/papers/{paper_id}/registration-versions/{version_id}/commitments/extract")
    assert result.status_code == 200
    rows = result.json()["commitments"]
    assert len(rows) == 1
    assert rows[0]["field_type"] == "exclusion-criterion"
    assert rows[0]["attachment_id"] == attachment_id
    assert rows[0]["page"] == 4
    assert rows[0]["extraction_method"] == "deterministic-local-text"
    assert rows[0]["extraction_confidence"] == "medium"
    assert "article-only" not in rows[0]["evidence_text"]
    assert client.get(f"/papers/{paper_id}/registration-versions/{version_id}/commitments").json() == rows
    engine.dispose()


def test_commitment_routes_reject_version_from_another_paper(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _, version_id, _ = _seed_version(conn, structured={"provider": "osf"}, chunks=[])
        other_id = create_paper(conn, title="Other", csl_json={"title": "Other"})
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get(f"/papers/{other_id}/registration-versions/{version_id}/commitments").status_code == 404
    assert client.post(f"/papers/{other_id}/registration-versions/{version_id}/commitments/extract").status_code == 404
    engine.dispose()
