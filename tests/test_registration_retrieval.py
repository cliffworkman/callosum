"""Increment 430: section/study-aware publication evidence retrieval."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.registration_schema import (
    paper_registration_links,
    registration_commitments,
    registration_document_versions,
)
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.registration_commitments import EXTRACTION_VERSION
from app.backend.registration_retrieval import retrieve_publication_evidence


class KeywordEmbeddingModel:
    name = "keyword-fixture"
    version = "1"
    dimension = 9
    normalization = "none"
    terms = ("hypoth", "sample", "outcome", "exclu", "regression", "attention", "study 1", "study 2", "date")

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            normalized = " ".join(text.casefold().split())
            vectors.append([float(len(re.findall(re.escape(term), normalized))) for term in self.terms])
        return vectors


def _chunk(conn, paper_id: int, attachment_id: int, text: str, section: str, page: int) -> int:
    return create_chunk(
        conn,
        paper_id=paper_id,
        attachment_id=attachment_id,
        text=text,
        section=section,
        page_start=page,
        page_end=page,
        bbox_coordinate_system="pdf-points",
        bbox_json={"x0": 10, "y0": 20, "x1": 300, "y1": 60},
        extraction_tool="fixture",
        extraction_version="1",
        chunking_strategy="fixture",
        chunk_version="1",
        source_attachment_checksum=f"attachment-{attachment_id}",
    )


def _seed(conn) -> tuple[int, int, dict[str, int], int, int, int, int]:
    paper_id = create_paper(conn, title="Published report", csl_json={"title": "Published report"})
    article_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="managed",
        availability="available",
        content_type="application/pdf",
        checksum="article-hash",
        role="article-fulltext",
    )
    supplement_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="managed",
        availability="available",
        content_type="application/pdf",
        checksum="supplement-hash",
        role="supplement",
    )
    registration_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="managed",
        availability="available",
        content_type="application/pdf",
        checksum="registration-hash",
        role="preregistration",
    )
    _chunk(conn, paper_id, article_id, "Study 1 hypotheses predicted an attention benefit.", "Introduction", 1)
    _chunk(conn, paper_id, article_id, "Context immediately before the sample report.", "Methods", 2)
    sample_chunk = _chunk(
        conn, paper_id, article_id, "Study 1 recruited a final sample of 118 participants.", "Participants", 3
    )
    _chunk(conn, paper_id, article_id, "Context immediately after the sample report.", "Procedure", 4)
    outcome_chunk = _chunk(conn, paper_id, article_id, "The primary outcome was response accuracy.", "Results", 5)
    regression_chunk = _chunk(
        conn, paper_id, article_id, "A logistic regression was reported as an additional analysis.", "Discussion", 6
    )
    _chunk(conn, paper_id, supplement_id, "The supplement defines the primary outcome as recall score.", "Appendix", 1)
    # A perfect-looking registration chunk must be structurally unavailable to publication retrieval.
    _chunk(conn, paper_id, registration_id, "Primary outcome sample regression Study 1.", "Plan", 1)

    link_id = int(
        conn.execute(
            insert(paper_registration_links).values(
                paper_id=paper_id,
                attachment_id=registration_id,
                provider="manual-local",
                external_id=f"attachment:{registration_id}",
                link_status="confirmed",
                linkage_class="explicit-linkage",
                match_method="manual-attachment",
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
                attachment_id=registration_id,
                provider="manual-local",
                external_id=f"attachment:{registration_id}",
                content_hash="registration-hash",
                structured_json={"provider": "manual-local"},
                source_metadata_json={},
                retrieved_at=datetime.now(timezone.utc),
            )
        ).inserted_primary_key[0]
    )
    commitments = {}
    for ordinal, (field_type, evidence, study_label) in enumerate(
        [
            ("sample-size-target", "We will recruit a sample of 120 participants.", "Study 1"),
            ("primary-outcome", "The primary outcome is response accuracy.", None),
            ("statistical-model", "We will fit a logistic regression.", None),
        ]
    ):
        commitments[field_type] = int(
            conn.execute(
                insert(registration_commitments).values(
                    version_id=version_id,
                    paper_id=paper_id,
                    link_id=link_id,
                    attachment_id=registration_id,
                    field_type=field_type,
                    study_label=study_label,
                    ordinal=ordinal,
                    structured_value_json={"text": evidence},
                    evidence_text=evidence,
                    source_section="Plan",
                    source_key=f"fixture:{ordinal}",
                    source_locator_json={"attachment_id": registration_id},
                    extraction_method="fixture",
                    extraction_confidence="high",
                    registration_content_hash="registration-hash",
                    extraction_version=EXTRACTION_VERSION,
                )
            ).inserted_primary_key[0]
        )
    return paper_id, version_id, commitments, sample_chunk, outcome_chunk, regression_chunk, registration_id


def test_retrieval_starts_in_compatible_sections_then_expands_and_excludes_registration_chunks(
    temp_db_url: str,
) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, version_id, _, sample_chunk, outcome_chunk, regression_chunk, registration_id = _seed(conn)
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=KeywordEmbeddingModel()))
    response = client.post(
        f"/papers/{paper_id}/registration-evidence/retrieve",
        json={"version_id": version_id, "include_supplements": False},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["local_only"] is True
    by_type = {row["field_type"]: row for row in payload["results"]}

    sample = by_type["sample-size-target"]
    assert sample["whole_article_expanded"] is False
    assert sample["study_mapping"] == "matched"
    assert sample["hits"][0]["chunk_id"] == sample_chunk
    assert sample["hits"][0]["search_phase"] == "expected-sections"
    assert sample_chunk in sample["searched_chunk_ids"]
    assert sample["searched_attachment_ids"] == [sample["hits"][0]["attachment_id"]]
    assert "Context immediately before" in sample["hits"][0]["context_text"]
    assert "Context immediately after" in sample["hits"][0]["context_text"]

    outcome = by_type["primary-outcome"]
    assert outcome["hits"][0]["chunk_id"] == outcome_chunk
    assert outcome["whole_article_expanded"] is False
    assert outcome["supplements_searched"] is False

    model = by_type["statistical-model"]
    assert model["whole_article_expanded"] is True
    assert model["hits"][0]["chunk_id"] == regression_chunk
    assert model["hits"][0]["search_phase"] == "whole-article"
    assert "discussion" in model["sections_searched"]
    assert regression_chunk in model["searched_chunk_ids"]

    assert registration_id not in {hit["attachment_id"] for row in payload["results"] for hit in row["hits"]}
    assert all("not proof" in row["non_detection_note"] for row in payload["results"])
    engine.dispose()


class _RaisingEmbeddingModel:
    """A stand-in for a broken/cold local embedding model (corrupted cache, OOM, offline first-use download)."""

    name = "raising"
    version = "1"
    dimension = 9
    normalization = "none"

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("local model failed to load")


def test_retrieval_endpoint_returns_clean_error_when_local_model_fails(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, version_id, *_ = _seed(conn)
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_RaisingEmbeddingModel()))

    response = client.post(
        f"/papers/{paper_id}/registration-evidence/retrieve",
        json={"version_id": version_id, "include_supplements": False},
    )

    assert response.status_code == 503
    assert "could not complete" in response.json()["detail"]
    assert "RuntimeError" in response.json()["detail"]  # invariant #4: the real error stays inspectable
    engine.dispose()


def test_supplements_are_searched_only_when_explicitly_requested(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, version_id, _, _, _, _, _ = _seed(conn)
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=KeywordEmbeddingModel()))
    without = client.post(
        f"/papers/{paper_id}/registration-evidence/retrieve",
        json={"version_id": version_id, "include_supplements": False},
    ).json()
    with_supplement = client.post(
        f"/papers/{paper_id}/registration-evidence/retrieve",
        json={"version_id": version_id, "include_supplements": True},
    ).json()
    assert all(hit["document_role"] == "article-fulltext" for row in without["results"] for hit in row["hits"])
    primary = next(row for row in with_supplement["results"] if row["field_type"] == "primary-outcome")
    sampling = next(row for row in with_supplement["results"] if row["field_type"] == "sample-size-target")
    assert primary["supplements_searched"] is True
    assert sampling["supplements_searched"] is False
    assert any(hit["document_role"] == "supplement" for hit in primary["hits"])
    assert "supplement" in primary["sections_searched"]
    assert len(primary["searched_attachment_ids"]) == 2
    engine.dispose()


def test_multi_study_scope_preserves_labels_and_marks_unresolved_mapping() -> None:
    chunks = [
        {
            "id": 1,
            "attachment_id": 10,
            "text": "Study 1 used response accuracy as the primary outcome.",
            "section": "Results",
            "page_start": 1,
            "page_end": 1,
            "bbox_json": None,
        },
        {
            "id": 2,
            "attachment_id": 10,
            "text": "Study 2 used recall as the primary outcome.",
            "section": "Results",
            "page_start": 2,
            "page_end": 2,
            "bbox_json": None,
        },
    ]
    commitments = [
        {
            "id": 101,
            "field_type": "primary-outcome",
            "study_label": "Study 1",
            "structured_value_json": {"text": "Study 1 primary outcome response accuracy"},
        },
        {
            "id": 102,
            "field_type": "primary-outcome",
            "study_label": None,
            "structured_value_json": {"text": "primary outcome response accuracy"},
        },
        {
            "id": 103,
            "field_type": "primary-outcome",
            "study_label": "Study 3",
            "structured_value_json": {"text": "Study 3 primary outcome"},
        },
    ]
    rows = retrieve_publication_evidence(commitments, chunks, [], model=KeywordEmbeddingModel(), top_k=2)
    assert rows[0].study_mapping == "matched"
    assert rows[0].hits[0].chunk_id == 1
    assert rows[1].study_mapping == "ambiguous"
    assert rows[1].study_labels_found == ("Study 1", "Study 2")
    assert rows[2].study_mapping == "ambiguous"


def test_retrieval_requires_extracted_commitments(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, version_id, _, _, _, _, _ = _seed(conn)
        conn.execute(registration_commitments.delete())
    response = TestClient(create_app(db_url=temp_db_url, embedding_model=KeywordEmbeddingModel())).post(
        f"/papers/{paper_id}/registration-evidence/retrieve", json={"version_id": version_id}
    )
    assert response.status_code == 409
    assert "Extract canonical" in response.json()["detail"]
    engine.dispose()
