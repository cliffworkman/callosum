"""Increment 431: evidence-bound registration comparison, persistence, review, and staleness."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import insert, update

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.registration_schema import (
    paper_registration_links,
    registration_commitments,
    registration_document_versions,
)
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.registration_commitments import EXTRACTION_VERSION
from app.backend.registration_comparison import compare_registration_to_publication
from app.backend.registration_retrieval.domain import CommitmentRetrieval, PublicationEvidenceHit


class ComparisonEmbeddingModel:
    name = "comparison-fixture"
    version = "1"
    dimension = 4
    normalization = "none"
    terms = ("sample", "exclu", "outcome", "regression")

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(term in text.casefold()) for term in self.terms] for text in texts]


def _commitment(
    commitment_id: int,
    field_type: str,
    evidence: str,
    *,
    value: dict | None = None,
    confidence: str = "high",
) -> dict:
    return {
        "id": commitment_id,
        "field_type": field_type,
        "evidence_text": evidence,
        "structured_value_json": value or {"text": evidence},
        "source_locator_json": {"attachment_id": 90, "page_start": 1},
        "extraction_confidence": confidence,
    }


def _hit(text: str, *, chunk_id: int = 1, attachment_id: int = 10, page: int = 2) -> PublicationEvidenceHit:
    return PublicationEvidenceHit(
        chunk_id=chunk_id,
        attachment_id=attachment_id,
        document_role="article-fulltext",
        text=text,
        context_text=text,
        section="methods",
        section_family="methods",
        page_start=page,
        page_end=page,
        bbox={"x0": 1, "y0": 2, "x1": 3, "y1": 4},
        similarity=0.9,
        search_phase="expected-sections",
    )


def _retrieval(commitment_id: int, hits=(), *, study_mapping: str = "unscoped") -> CommitmentRetrieval:
    return CommitmentRetrieval(
        commitment_id=commitment_id,
        field_type="fixture",
        expected_section_families=("methods",),
        sections_searched=("methods",),
        whole_article_expanded=False,
        supplements_searched=False,
        study_mapping=study_mapping,
        study_labels_found=(),
        hits=tuple(hits),
    )


def _compare(commitments, retrievals, chunks=()):
    return compare_registration_to_publication(
        commitments,
        retrievals,
        chunks,
        attachment_checksums={10: "article-hash"},
        registration_version_id=7,
        registration_content_hash="registration-hash",
    )


def test_deterministic_numeric_threshold_outcome_and_model_comparisons() -> None:
    commitments = [
        _commitment(1, "sample-size-target", "We will recruit 120 participants.", value={"text": "x", "target_n": 120}),
        _commitment(2, "exclusion-criterion", "Failing either attention check leads to exclusion."),
        _commitment(3, "primary-outcome", "The primary outcome is response accuracy."),
        _commitment(4, "statistical-model", "We will fit a logistic regression."),
    ]
    retrievals = [
        _retrieval(1, [_hit("The final sample of 118 participants was analyzed.", chunk_id=1)]),
        _retrieval(2, [_hit("Participants failing both attention checks were excluded.", chunk_id=2)]),
        _retrieval(3, [_hit("The primary outcome was recall score.", chunk_id=3)]),
        _retrieval(4, [_hit("We fitted a linear regression.", chunk_id=4)]),
    ]
    rows = _compare(commitments, retrievals)
    by_type = {row.field_type: row for row in rows}
    assert by_type["sample-size-target"].comparison_status == "potentially-changed"
    assert by_type["sample-size-target"].publication_value["reported_n"] == 118
    assert "120" in by_type["sample-size-target"].explanation
    assert "either versus both" in by_type["exclusion-criterion"].explanation
    assert by_type["primary-outcome"].comparison_status == "potentially-changed"
    assert by_type["statistical-model"].comparison_status == "potentially-changed"
    assert all(row.registration_evidence_text and row.publication_evidence_text for row in rows)
    assert all("incorrect registration match" in row.uncertainty for row in rows)


def test_aligned_disclosed_not_located_ambiguous_and_uncertain_are_bounded_statuses() -> None:
    commitments = [
        _commitment(1, "sample-size-target", "Target sample size 120.", value={"text": "x", "target_n": 120}),
        _commitment(2, "exclusion-criterion", "Participants failing either attention check will be excluded."),
        _commitment(3, "stopping-rule", "Data collection stops after 120 participants."),
        _commitment(4, "hypothesis", "Study 1 accuracy will be higher."),
        _commitment(5, "covariate", "Age will be included as a covariate.", confidence="low"),
    ]
    retrievals = [
        _retrieval(1, [_hit("The final sample of 120 participants was analyzed.")]),
        _retrieval(2, [_hit("We deviated from the registered exclusion rule and explain why.")]),
        _retrieval(3, []),
        _retrieval(4, [_hit("Study 2 reports accuracy.")], study_mapping="ambiguous"),
        _retrieval(5, [_hit("Age was included as a covariate.")]),
    ]
    statuses = [row.comparison_status for row in _compare(commitments, retrievals)]
    assert statuses == [
        "aligned",
        "disclosed-deviation",
        "planned-item-not-located-in-publication",
        "ambiguous-study-mapping",
        "extraction-uncertain",
    ]


def test_reported_primary_outcome_without_extracted_registration_field_is_surfaced_with_one_sided_evidence() -> None:
    chunks = [
        {
            "id": 50,
            "attachment_id": 10,
            "text": "The primary outcome was response accuracy.",
            "section": "Results",
            "page_start": 8,
            "page_end": 8,
            "bbox_json": None,
            "document_role": "article-fulltext",
        }
    ]
    rows = _compare([_commitment(1, "sample-size-target", "Target sample size 120.")], [_retrieval(1, [])], chunks)
    reported = next(row for row in rows if row.comparison_status == "reported-item-not-located-in-registration")
    assert reported.field_type == "primary-outcome"
    assert reported.registration_evidence_text is None
    assert reported.registration_source_locator["searched_canonical_field"] == "primary-outcome"
    assert reported.publication_evidence_text == chunks[0]["text"]
    assert "not absence" in reported.explanation.casefold()


def test_registration_timing_is_first_class_and_uses_cautious_status_language() -> None:
    commitment = _commitment(
        1,
        "registration-timing",
        "2021-06-01",
        value={"registered_at": "2021-06-01", "registration_status": "public"},
    )
    chunk = {
        "id": 60,
        "attachment_id": 10,
        "text": "Data collection began on 2020-01-10.",
        "section": "Methods",
        "page_start": 3,
        "page_end": 3,
        "bbox_json": None,
        "document_role": "article-fulltext",
    }
    row = _compare([commitment], [_retrieval(1)], [chunk])[0]
    assert row.comparison_status == "potentially-changed"
    assert row.timing_status == "registration-appears-after-data-collection-began"
    assert "appears" in row.explanation
    assert row.publication_evidence_text == chunk["text"]


def test_underspecified_and_semantically_unresolved_rows_are_not_forced_into_difference_verdicts() -> None:
    commitments = [
        _commitment(1, "stopping-rule", "To be determined."),
        _commitment(2, "missing-data-procedure", "We will use multiple imputation with twenty datasets."),
        _commitment(3, "robustness-sensitivity-analysis", "We will inspect robustness across specifications."),
    ]
    retrievals = [
        _retrieval(1, [_hit("Data collection stopped after the semester.")]),
        _retrieval(2, [_hit("Missing data were handled as appropriate.")]),
        _retrieval(3, [_hit("Several alternative analyses are reported.")]),
    ]
    rows = _compare(commitments, retrievals)
    assert [row.comparison_status for row in rows] == [
        "underspecified-in-registration",
        "underspecified-in-publication",
        "not-comparable",
    ]
    assert "human semantic interpretation" in rows[2].explanation


def test_timing_can_support_prospective_order_or_remain_insufficient_without_certifying_compliance() -> None:
    commitment = _commitment(
        1,
        "registration-timing",
        "2019-06-01",
        value={"registered_at": "2019-06-01", "registration_status": "public"},
    )
    dated_chunk = {
        "id": 61,
        "attachment_id": 10,
        "text": "Recruitment began in 2020-01-10.",
        "section": "Methods",
        "page_start": 3,
        "page_end": 3,
        "bbox_json": None,
        "document_role": "article-fulltext",
    }
    prospective = _compare([commitment], [_retrieval(1)], [dated_chunk])[0]
    assert prospective.comparison_status == "aligned"
    assert prospective.timing_status == "prospective-timing-supported"
    assert "compliance" not in prospective.explanation.casefold()
    insufficient = _compare(
        [commitment], [_retrieval(1)], [dict(dated_chunk, text="Recruitment dates were reported.")]
    )[0]
    assert insufficient.comparison_status == "not-comparable"
    assert insufficient.timing_status == "insufficient-dates-to-compare"


def _seed_api_comparison(conn) -> tuple[int, int, int, int]:
    paper_id = create_paper(conn, title="API comparison", csl_json={"title": "API comparison"})
    article_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="managed",
        availability="available",
        content_type="application/pdf",
        checksum="article-hash",
        role="article-fulltext",
    )
    registration_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="managed",
        availability="available",
        content_type="text/plain",
        checksum="registration-hash",
        role="preregistration",
    )
    create_chunk(
        conn,
        paper_id=paper_id,
        attachment_id=article_id,
        text="The final sample of 118 participants was analyzed.",
        section="Participants",
        page_start=2,
        page_end=2,
        bbox_coordinate_system="pdf-points",
        extraction_tool="fixture",
        extraction_version="1",
        chunking_strategy="fixture",
        chunk_version="1",
        source_attachment_checksum="article-hash",
    )
    link_id = int(
        conn.execute(
            insert(paper_registration_links).values(
                paper_id=paper_id,
                attachment_id=registration_id,
                provider="osf",
                external_id="api-reg",
                link_status="confirmed",
                linkage_class="explicit-linkage",
                match_method="fixture",
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
                provider="osf",
                external_id="api-reg",
                content_hash="registration-hash",
                structured_json={"provider": "osf"},
                source_metadata_json={},
                retrieved_at=datetime.now(timezone.utc),
            )
        ).inserted_primary_key[0]
    )
    conn.execute(
        insert(registration_commitments).values(
            version_id=version_id,
            paper_id=paper_id,
            link_id=link_id,
            attachment_id=registration_id,
            field_type="sample-size-target",
            ordinal=0,
            structured_value_json={"text": "We will recruit 120 participants.", "target_n": 120},
            evidence_text="We will recruit 120 participants.",
            source_section="Sampling plan",
            source_key="sample",
            source_locator_json={"attachment_id": registration_id, "response_key": "sample"},
            extraction_method="structured-osf",
            extraction_confidence="high",
            registration_content_hash="registration-hash",
            extraction_version=EXTRACTION_VERSION,
        )
    )
    return paper_id, version_id, link_id, article_id


def test_comparison_api_persists_evidence_review_state_and_detects_document_staleness(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, version_id, link_id, article_id = _seed_api_comparison(conn)
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=ComparisonEmbeddingModel()))
    started = client.post(
        f"/papers/{paper_id}/registration-comparisons",
        json={"version_id": version_id, "include_supplements": False},
    )
    assert started.status_code == 202, started.text
    job = client.get(f"/registration-comparisons/jobs/{started.json()['job_id']}").json()
    assert job["status"] == "done"
    detail = client.get(f"/papers/{paper_id}/registration-comparisons/{job['run_id']}").json()
    assert detail["status"] == "completed"
    assert "not a compliance" in detail["framing"]
    assert detail["row_count"] == 1
    row = detail["rows"][0]
    assert row["comparison_status"] == "potentially-changed"
    assert row["registration_evidence_text"] == "We will recruit 120 participants."
    assert row["publication_evidence_text"].startswith("The final sample")
    assert row["registration_content_hash"] == "registration-hash"
    assert row["publication_attachment_checksum"] == "article-hash"
    assert row["search_scope"]["supplements_searched"] is False

    reviewed = client.post(
        f"/registration-comparison-rows/{row['id']}/review",
        json={"review_state": "reviewed", "note": "Checked both source passages."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["note"] == "Checked both source passages."

    with engine.begin() as conn:
        conn.execute(
            update(paper_registration_links)
            .where(paper_registration_links.c.id == link_id)
            .values(content_hash="new-hash", link_status="rejected", user_confirmed=False)
        )
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=article_id,
            text="A newly extracted article passage.",
            section="Methods",
            page_start=3,
            page_end=3,
            bbox_coordinate_system="pdf-points",
            extraction_tool="fixture",
            extraction_version="2",
            chunking_strategy="fixture",
            chunk_version="2",
            source_attachment_checksum="article-hash",
        )
    stale = client.get(f"/papers/{paper_id}/registration-comparisons/{job['run_id']}").json()
    assert stale["status"] == "stale"
    assert "registration-content-changed" in stale["stale_reasons"]
    assert "confirmed-registration-changed" in stale["stale_reasons"]
    assert "article-attachment-or-extraction-changed" in stale["stale_reasons"]
    assert stale["rows"][0]["review_state"] == "reviewed"
    assert (
        client.post(f"/papers/{paper_id}/registration-comparisons", json={"version_id": version_id}).status_code == 409
    )
    rejected = client.get(f"/papers/{paper_id}/registration-links?include_rejected=true").json()
    assert rejected[0]["link_status"] == "rejected"
    engine.dispose()
