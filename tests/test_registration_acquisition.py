"""Increment 428: confirmed registration acquisition, canonicalization, and version preservation."""

from __future__ import annotations

from dataclasses import replace

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.registration_links_repo import (
    set_registration_link_status,
    upsert_registration_candidates,
)
from app.backend.persistence.registration_schema import paper_registration_links, registration_document_versions
from app.backend.persistence.repository import create_paper, get_chunks_for_attachment
from app.backend.persistence.schema import attachments
from app.backend.registration_acquisition.aspredicted import AsPredictedRegistrationAcquirer
from app.backend.registration_acquisition.domain import (
    AcquiredRegistration,
    RegistrationAcquisitionError,
    RegistrationAcquisitionRegistry,
)
from app.backend.registration_acquisition.osf import OsfRegistrationAcquirer
from app.backend.registration_discovery.domain import RegistrationCandidate
from app.backend.registration_discovery.http import RegistryHttpError


def _osf_payloads(answer: str = "We will recruit 120 participants.") -> dict[str, dict]:
    schema_url = "https://api.osf.io/v2/schemas/registrations/schema1/"
    return {
        "/registrations/ab12c/": {
            "data": {
                "id": "ab12c",
                "attributes": {
                    "title": "Attention plan",
                    "date_registered": "2023-02-03T00:00:00Z",
                    "public": True,
                    "embargoed": False,
                    "withdrawn": False,
                    "registration_supplement": "OSF Preregistration",
                    "registered_meta": {"q-1": {"value": answer}},
                },
                "relationships": {"registration_schema": {"links": {"related": {"href": schema_url}}}},
            }
        },
        "/registrations/ab12c/schema_responses/": {
            "data": [
                {
                    "id": "response1",
                    "attributes": {
                        "date_modified": "2023-02-03T00:00:00Z",
                        "revision_responses": {"q-1": answer},
                        "updated_response_keys": ["q-1"],
                        "revision_justification": "",
                        "is_original_response": True,
                    },
                }
            ]
        },
        "/registrations/ab12c/contributors/?embed=users": {
            "data": [
                {
                    "attributes": {"bibliographic": True},
                    "embeds": {"users": {"data": {"id": "user1", "attributes": {"full_name": "Ada Lovelace"}}}},
                }
            ]
        },
        "/registrations/ab12c/identifiers/": {
            "data": [
                {
                    "id": "doi1",
                    "attributes": {"category": "doi", "value": "https://doi.org/10.17605/OSF.IO/AB12C"},
                }
            ]
        },
        "/registrations/ab12c/resources/": {
            "data": [{"id": "resource1", "attributes": {"resource_type": "paper", "pid": "doi:10.5555/PAPER"}}]
        },
        "/registrations/ab12c/files/": {"data": [{"id": "osfstorage", "attributes": {"name": "osfstorage"}}]},
        "/registrations/ab12c/files/osfstorage/": {
            "data": [
                {
                    "id": "file1",
                    "type": "files",
                    "attributes": {
                        "name": "analysis-plan.pdf",
                        "kind": "file",
                        "size": 2048,
                        "contentType": "application/pdf",
                    },
                    "links": {"download": "https://files.osf.io/v1/resources/ab12c/providers/osfstorage/file1"},
                }
            ]
        },
        "/schemas/registrations/schema1/": {
            "data": {
                "id": "schema1",
                "attributes": {"name": "OSF Preregistration", "schema_version": 4},
            }
        },
        "/schemas/registrations/schema1/schema_blocks/": {
            "data": [
                {
                    "id": "heading",
                    "attributes": {
                        "index": 0,
                        "block_type": "page-heading",
                        "display_text": "Sampling plan",
                    },
                },
                {
                    "id": "label1",
                    "attributes": {
                        "index": 1,
                        "block_type": "question-label",
                        "schema_block_group_key": "group1",
                        "display_text": "Planned sample size",
                    },
                },
                {
                    "id": "input1",
                    "attributes": {
                        "index": 2,
                        "block_type": "long-text-input",
                        "schema_block_group_key": "group1",
                        "registration_response_key": "q-1",
                        "required": True,
                    },
                },
            ]
        },
    }


def _osf_fetch(payloads: dict[str, dict]):
    def fetch(url: str) -> dict:
        path = url.removeprefix("https://api.osf.io/v2")
        if path not in payloads:
            raise RegistryHttpError(404, f"fixture has no {path}")
        return payloads[path]

    return fetch


def test_osf_structured_response_is_deterministic_and_preserves_question_identity() -> None:
    first = OsfRegistrationAcquirer(_osf_fetch(_osf_payloads())).acquire({"external_id": "ab12c"})
    second = OsfRegistrationAcquirer(_osf_fetch(_osf_payloads())).acquire({"external_id": "ab12c"})

    assert first.content_hash == second.content_hash
    assert first.schema_name == "OSF Preregistration"
    assert first.schema_version == "4"
    assert first.structured["questions"] == [
        {
            "response_key": "q-1",
            "question_block_id": "input1",
            "question_group_id": "group1",
            "label": "Planned sample size",
            "section": "Sampling plan",
            "answer": "We will recruit 120 participants.",
            "answer_order": 0,
            "input_type": "long-text-input",
            "required": True,
        }
    ]
    assert "# Attention plan" in first.rendered_text
    assert "## Sampling plan" in first.rendered_text
    assert "### Planned sample size" in first.rendered_text
    assert first.structured["resources"][0]["attributes"]["pid"] == "doi:10.5555/PAPER"
    assert first.structured["registration_doi"] == "10.17605/osf.io/ab12c"
    assert first.structured["publication_dois"] == ["10.5555/paper"]
    assert first.structured["files"][0]["attributes"]["name"] == "analysis-plan.pdf"
    assert first.structured["response_history"][0]["updated_response_keys"] == ["q-1"]
    assert first.source_metadata["schema_responses"]["data"][0]["attributes"]["updated_response_keys"] == ["q-1"]
    assert first.source_metadata["file_manifest"]["truncated"] is False


def test_osf_collection_pagination_preserves_later_schema_blocks_and_amendments() -> None:
    payloads = _osf_payloads()
    blocks = payloads["/schemas/registrations/schema1/schema_blocks/"]["data"]
    payloads["/schemas/registrations/schema1/schema_blocks/"] = {
        "data": blocks[:2],
        "links": {"next": "https://api.osf.io/v2/schemas/registrations/schema1/schema_blocks/?page=2"},
    }
    payloads["/schemas/registrations/schema1/schema_blocks/?page=2"] = {"data": blocks[2:]}
    original = payloads["/registrations/ab12c/schema_responses/"]["data"][0]
    payloads["/registrations/ab12c/schema_responses/"] = {
        "data": [original],
        "links": {"next": "https://api.osf.io/v2/registrations/ab12c/schema_responses/?page=2"},
    }
    payloads["/registrations/ab12c/schema_responses/?page=2"] = {
        "data": [
            {
                "id": "response2",
                "attributes": {
                    "date_modified": "2023-02-04T00:00:00Z",
                    "revision_responses": {"q-1": "We will recruit 180 participants."},
                    "updated_response_keys": ["q-1"],
                    "revision_justification": "Updated the target before recruitment.",
                    "is_original_response": False,
                },
            }
        ]
    }

    acquired = OsfRegistrationAcquirer(_osf_fetch(payloads)).acquire({"external_id": "ab12c"})

    assert acquired.structured["questions"][0]["label"] == "Planned sample size"
    assert acquired.structured["questions"][0]["answer"] == "We will recruit 180 participants."
    assert len(acquired.structured["response_history"]) == 2
    assert "Updated the target before recruitment." in acquired.rendered_text
    assert acquired.source_metadata["schema_blocks"]["callosum_collection"]["pages_retrieved"] == 2


def _aspredicted_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(
        fitz.Rect(50, 50, 550, 780),
        "#52,400 | AsPredicted\n"
        "Attention preregistration\n"
        "Pre-registered on 2020/11/17 07:15 (PT)\n"
        "1) Have any data been collected for this study already?\nNo, no data have been collected.\n"
        "2) What's the main question being asked or hypothesis being tested in this study?\nAttention improves memory.\n"
        "Version of AsPredicted Questions: 2.00",
        fontsize=10,
    )
    value = document.tobytes()
    document.close()
    return value


def test_aspredicted_legacy_verification_resolves_only_same_origin_pdf() -> None:
    pdf = _aspredicted_pdf()
    calls: list[str] = []

    def fetch(url: str, *, max_bytes: int, accepted_types: set[str]):
        calls.append(url)
        if "blind.php" in url:
            assert accepted_types == {"text/html"}
            return b'<a href="https://aspredicted.org/pf2xb.pdf">Download PDF</a>', url, "text/html"
        assert max_bytes == 80 * 1024 * 1024
        return pdf, url, "application/pdf"

    acquired = AsPredictedRegistrationAcquirer(fetch).acquire(
        {
            "external_id": "sx97w9",
            "canonical_url": "https://aspredicted.org/blind.php?x=sx97w9",
        }
    )

    assert calls == [
        "https://aspredicted.org/blind.php?x=sx97w9",
        "https://aspredicted.org/pf2xb.pdf",
    ]
    assert acquired.canonical_url == "https://aspredicted.org/pf2xb.pdf"
    assert acquired.file_bytes.startswith(b"%PDF-")
    assert acquired.structured["registered_at"] == "2020/11/17 07:15 (PT)"
    assert acquired.structured["questions"][0]["answer"] == "No, no data have been collected."


def test_aspredicted_rejects_cross_origin_verification_link() -> None:
    def fetch(url: str, *, max_bytes: int, accepted_types: set[str]):
        return b'<a href="https://internal.example/plan.pdf">PDF</a>', url, "text/html"

    try:
        AsPredictedRegistrationAcquirer(fetch).acquire(
            {"external_id": "sx97w9", "canonical_url": "https://aspredicted.org/blind.php?x=sx97w9"}
        )
    except RegistrationAcquisitionError as exc:
        assert "did not expose a public" in str(exc)
    else:
        raise AssertionError("cross-origin AsPredicted PDF was accepted")


def _candidate(status: str = "public") -> RegistrationCandidate:
    return RegistrationCandidate(
        provider="osf",
        external_id="ab12c",
        registration_doi="10.17605/osf.io/ab12c",
        canonical_url="https://osf.io/ab12c/",
        title="Attention plan",
        contributors=("Ada Lovelace",),
        registered_at="2023-02-03T00:00:00Z",
        registration_status=status,
        schema_name="OSF Preregistration",
        linkage_class="explicit-linkage",
        match_method="paper-osf-reference",
        match_evidence=({"kind": "paper-reference"},),
        source_metadata={"public": status == "public"},
    )


def _acquired(answer: str = "We will recruit 120 participants.") -> AcquiredRegistration:
    return OsfRegistrationAcquirer(_osf_fetch(_osf_payloads(answer))).acquire({"external_id": "ab12c"})


class _SequenceAcquirer:
    id = "osf"

    def __init__(self, values) -> None:
        self.values = list(values)
        self.calls = 0

    def acquire(self, link: dict) -> AcquiredRegistration:
        value = self.values[min(self.calls, len(self.values) - 1)]
        self.calls += 1
        if isinstance(value, Exception):
            raise value
        return value


def _paper_link_client(temp_db_url: str, acquirer, *, status: str = "public"):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Published paper", csl_json={"title": "Published paper"})
        link_id = upsert_registration_candidates(conn, paper_id, [_candidate(status)])[0]
        if status == "public":
            assert set_registration_link_status(conn, paper_id, link_id, "confirmed", user_confirmed=True)
    engine.dispose()
    registry = RegistrationAcquisitionRegistry().register(acquirer)
    client = TestClient(create_app(db_url=temp_db_url, registration_acquisition_registry=registry))
    return paper_id, link_id, client


def _run_acquire(client: TestClient, paper_id: int, link_id: int) -> dict:
    started = client.post(f"/papers/{paper_id}/registration-links/{link_id}/acquire")
    assert started.status_code == 202, started.text
    result = client.get(f"/registration-acquisition/{started.json()['job_id']}")
    assert result.status_code == 200
    return result.json()


def test_acquisition_requires_confirmation_and_blocks_withdrawn_candidate(temp_db_url: str) -> None:
    acquirer = _SequenceAcquirer([_acquired()])
    paper_id, link_id, client = _paper_link_client(temp_db_url, acquirer, status="withdrawn")

    assert client.post(f"/papers/{paper_id}/registration-links/{link_id}/confirm").status_code == 409
    response = client.post(f"/papers/{paper_id}/registration-links/{link_id}/acquire")
    assert response.status_code == 409
    assert acquirer.calls == 0


def test_acquisition_rechecks_provider_status_before_import(temp_db_url: str) -> None:
    acquired = replace(_acquired(), registration_status="withdrawn")
    acquirer = _SequenceAcquirer([acquired])
    paper_id, link_id, client = _paper_link_client(temp_db_url, acquirer)

    result = _run_acquire(client, paper_id, link_id)

    assert result["status"] == "error"
    assert "now reports this registration as withdrawn" in result["detail"]
    assert client.get(f"/papers/{paper_id}/registration-versions").json() == []


def test_osf_acquisition_attaches_canonical_markdown_without_article_contamination(temp_db_url: str) -> None:
    acquirer = _SequenceAcquirer([_acquired()])
    paper_id, link_id, client = _paper_link_client(temp_db_url, acquirer)

    result = _run_acquire(client, paper_id, link_id)

    assert result["status"] == "done"
    assert result["changed"] is True
    attachment_id = result["attachment_id"]
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        attachment = conn.execute(select(attachments).where(attachments.c.id == attachment_id)).mappings().one()
        chunks = get_chunks_for_attachment(conn, attachment_id)
        link = (
            conn.execute(select(paper_registration_links).where(paper_registration_links.c.id == link_id))
            .mappings()
            .one()
        )
    engine.dispose()
    assert attachment["role"] == "preregistration"
    assert attachment["storage_mode"] == "managed"
    assert attachment["attachment_type"] == "text"
    assert any("We will recruit 120 participants" in row["text"] for row in chunks)
    assert client.get(f"/papers/{paper_id}/chunks").json() == []
    assert link["attachment_id"] == attachment_id
    versions = client.get(f"/papers/{paper_id}/registration-versions").json()
    assert len(versions) == 1
    detail = client.get(f"/papers/{paper_id}/registration-versions/{versions[0]['id']}").json()
    assert detail["structured"]["questions"][0]["label"] == "Planned sample size"
    assert detail["source_metadata"]["registration"]["data"]["id"] == "ab12c"


def test_same_hash_reuses_version_and_changed_hash_preserves_prior_basis(temp_db_url: str) -> None:
    first = _acquired("We will recruit 120 participants.")
    second = _acquired("We will recruit 180 participants after an amendment.")
    acquirer = _SequenceAcquirer([first, first, second])
    paper_id, link_id, client = _paper_link_client(temp_db_url, acquirer)

    original = _run_acquire(client, paper_id, link_id)
    same = _run_acquire(client, paper_id, link_id)
    changed = _run_acquire(client, paper_id, link_id)

    assert original["changed"] is True
    assert same["changed"] is False
    assert same["version_id"] == original["version_id"]
    assert changed["changed"] is True
    assert changed["version_id"] != original["version_id"]
    versions = client.get(f"/papers/{paper_id}/registration-versions").json()
    assert {row["content_hash"] for row in versions} == {first.content_hash, second.content_hash}
    assert {row["attachment_id"] for row in versions} == {original["attachment_id"], changed["attachment_id"]}
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        assert (
            conn.scalar(
                select(func.count())
                .select_from(registration_document_versions)
                .where(registration_document_versions.c.link_id == link_id)
            )
            == 2
        )
    engine.dispose()


def test_same_hash_reacquisition_restores_a_removed_managed_attachment(temp_db_url: str) -> None:
    acquired = _acquired()
    acquirer = _SequenceAcquirer([acquired, acquired])
    paper_id, link_id, client = _paper_link_client(temp_db_url, acquirer)
    original = _run_acquire(client, paper_id, link_id)

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(delete(attachments).where(attachments.c.id == original["attachment_id"]))
    restored = _run_acquire(client, paper_id, link_id)
    with engine.connect() as conn:
        version = (
            conn.execute(
                select(registration_document_versions).where(
                    registration_document_versions.c.id == original["version_id"]
                )
            )
            .mappings()
            .one()
        )
        restored_attachment = (
            conn.execute(select(attachments).where(attachments.c.id == restored["attachment_id"])).mappings().one()
        )
        restored_chunks = get_chunks_for_attachment(conn, restored["attachment_id"])
    engine.dispose()

    assert restored["status"] == "done"
    assert restored["changed"] is True
    assert restored["version_id"] == original["version_id"]
    assert version["attachment_id"] == restored["attachment_id"]
    assert restored_attachment["role"] == "preregistration"
    assert restored_attachment["checksum"]
    assert any("We will recruit 120 participants" in row["text"] for row in restored_chunks)


def test_provider_failure_does_not_corrupt_existing_acquired_version(temp_db_url: str) -> None:
    first = _acquired()
    acquirer = _SequenceAcquirer([first, RegistrationAcquisitionError("fixture provider unavailable")])
    paper_id, link_id, client = _paper_link_client(temp_db_url, acquirer)
    original = _run_acquire(client, paper_id, link_id)

    failed = _run_acquire(client, paper_id, link_id)

    assert failed["status"] == "error"
    assert "fixture provider unavailable" in failed["detail"]
    versions = client.get(f"/papers/{paper_id}/registration-versions").json()
    assert [(row["id"], row["attachment_id"]) for row in versions] == [
        (original["version_id"], original["attachment_id"])
    ]


def test_panel_reads_versions_without_invoking_acquirer(temp_db_url: str) -> None:
    acquirer = _SequenceAcquirer([RegistrationAcquisitionError("must not run")])
    paper_id, _link_id, client = _paper_link_client(temp_db_url, acquirer)

    assert client.get(f"/papers/{paper_id}/registration-versions").json() == []
    assert client.get(f"/papers/{paper_id}/registration-links").status_code == 200
    assert acquirer.calls == 0
