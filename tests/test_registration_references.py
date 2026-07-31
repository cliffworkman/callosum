"""Increment 426: local registration-reference extraction and manual attachment paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api import create_app
from app.backend.methods.registration_references import extract_registration_references
from app.backend.pdf_processing.extraction import extract_pdf
from app.backend.pdf_processing.ingest import attach_pdf_to_paper
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_paper, get_chunks_for_attachment
from app.backend.persistence.schema import attachments


@dataclass
class _Chunk:
    text: str
    page_start: int = 1
    attachment_id: int = 11


def _refs(text: str):
    return extract_registration_references([_Chunk(text)])


def _one_page_pdf(path: Path, text: str = "This study was preregistered.") -> Path:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), text)
    document.save(path)
    document.close()
    return path


def _hidden_link_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page()
    text = "The preregistration is available here."
    page.insert_text((72, 100), text)
    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": page.search_for("here")[0],
            "uri": "https://osf.io/ab12c/",
        }
    )
    document.save(path)
    document.close()
    return path


def test_normalizes_supported_printed_references() -> None:
    refs = _refs(
        "Preregistered at https://osf.io/Ab12C/. DOI 10.17605/OSF.IO/ZX90Q. "
        "AsPredicted https://aspredicted.org/blind.php?x=xy12. Trial NCT01234567; PROSPERO CRD42020123456."
    )
    identities = {(ref.provider, ref.external_id) for ref in refs}
    assert ("osf", "ab12c") in identities
    assert ("osf", "zx90q") in identities
    assert ("aspredicted", "xy12") in identities
    assert ("clinicaltrials.gov", "NCT01234567") in identities
    assert ("prospero", "CRD42020123456") in identities
    assert all(ref.explicitly_printed for ref in refs)


def test_osf_registry_route_requires_a_guid() -> None:
    refs = _refs("The registration is at https://osf.io/registries/ab12c/.")
    assert [(ref.provider, ref.external_id) for ref in refs] == [("osf", "ab12c")]
    assert _refs("Browse the registration index at https://osf.io/registries/.") == []


def test_generic_url_or_doi_requires_registration_context() -> None:
    assert _refs("Background source https://example.org/article and DOI 10.1234/article.5") == []
    refs = _refs("The preregistration is archived at https://example.org/plan and DOI 10.1234/PLAN.5.")
    assert {(ref.provider, ref.external_id) for ref in refs} == {
        ("url", "https://example.org/plan"),
        ("doi", "10.1234/plan.5"),
    }


def test_language_without_identifier_remains_a_signal_not_a_reference() -> None:
    assert _refs("The hypotheses and analysis plan were preregistered before data collection.") == []


def test_pdf_hidden_here_link_preserves_target_and_visible_text(tmp_path: Path) -> None:
    extraction = extract_pdf(_hidden_link_pdf(tmp_path / "hidden-link.pdf"))
    refs = extract_registration_references([], hyperlinks=extraction.links)
    assert len(refs) == 1
    ref = refs[0]
    assert ref.provider == "osf"
    assert ref.external_id == "ab12c"
    assert ref.visible_text == "here"
    assert ref.page == 1
    assert ref.extraction_method == "pdf-hyperlink"
    assert ref.evidence_class == "exact-link-target"
    assert ref.explicitly_printed is False
    assert "preregistration is available here" in (ref.evidence_snippet or "")


def test_pdf_ingest_persists_multiple_references_and_endpoint_states(temp_db_url: str, tmp_path: Path) -> None:
    pdf = _one_page_pdf(
        tmp_path / "references.pdf",
        "This study was preregistered at https://osf.io/ab12c/ and AsPredicted #98765.",
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="References", csl_json={"title": "References"})
        attach_pdf_to_paper(conn, paper_id, pdf, role="article-fulltext")
    engine.dispose()

    body = TestClient(create_app(db_url=temp_db_url)).get(f"/papers/{paper_id}/transparency").json()
    assert body["registration_reference_state"] == "multiple-references-detected"
    assert {(row["provider"], row["external_id"]) for row in body["registration_references"]} == {
        ("osf", "ab12c"),
        ("aspredicted", "98765"),
    }
    assert all(row["attachment_id"] is not None for row in body["registration_references"])


def test_manual_reference_is_local_and_idempotent(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Manual", csl_json={"title": "Manual"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    first = client.post(f"/papers/{paper_id}/registration-references", json={"value": "10.17605/OSF.IO/AB12C"})
    second = client.post(f"/papers/{paper_id}/registration-references", json={"value": "10.17605/osf.io/ab12c"})
    assert first.status_code == second.status_code == 201
    body = client.get(f"/papers/{paper_id}/transparency").json()
    assert len(body["registration_references"]) == 1
    assert body["registration_references"][0]["extraction_method"] == "manual"
    assert body["registration_references"][0]["explicitly_printed"] is False
    assert (
        client.post(f"/papers/{paper_id}/registration-references", json={"value": "not a reference"}).status_code == 422
    )


def test_attach_local_registration_pdf_chunks_only_that_attachment(temp_db_url: str, tmp_path: Path) -> None:
    pdf = _one_page_pdf(tmp_path / "local-plan.pdf", "Primary outcome: response accuracy.")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Local registration", csl_json={"title": "Local registration"})
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.post(
        f"/papers/{paper_id}/registration-attachments?filename=local-plan.pdf",
        content=pdf.read_bytes(),
        headers={"content-type": "application/pdf"},
    )
    assert response.status_code == 201, response.text
    attachment_id = response.json()["attachment_id"]
    with engine.begin() as conn:
        chunks = get_chunks_for_attachment(conn, attachment_id)
        attachment = conn.execute(select(attachments).where(attachments.c.id == attachment_id)).mappings().one()
    engine.dispose()
    assert [row["text"] for row in chunks] == ["Primary outcome: response accuracy."]
    assert attachment["role"] == "preregistration"
    assert attachment["storage_mode"] == "managed"
    assert client.get(f"/papers/{paper_id}/chunks").json() == []
    assert client.get(f"/papers/{paper_id}/transparency").json()["registration_reference_state"] == "not-detected"
    link = client.get(f"/papers/{paper_id}/registration-links").json()[0]
    assert link["provider"] == "manual-local"
    assert link["link_status"] == "confirmed"
    assert link["attachment_id"] == attachment_id


def test_local_registration_upload_rejects_non_pdf(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Bad upload", csl_json={"title": "Bad upload"})
    engine.dispose()
    response = TestClient(create_app(db_url=temp_db_url)).post(
        f"/papers/{paper_id}/registration-attachments?filename=not-a-pdf.pdf",
        content=b"plain text",
        headers={"content-type": "application/pdf"},
    )
    assert response.status_code == 422


def test_mark_existing_attachment_as_preregistration(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Existing", csl_json={"title": "Existing"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            attachment_type="pdf",
            role="other",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    response = client.patch(
        f"/papers/{paper_id}/attachments/{attachment_id}/document-role", json={"role": "preregistration"}
    )
    assert response.status_code == 200
    detail = client.get(f"/papers/{paper_id}").json()
    assert next(row for row in detail["attachments"] if row["id"] == attachment_id)["role"] == "preregistration"
    link = client.get(f"/papers/{paper_id}/registration-links").json()[0]
    assert link["attachment_id"] == attachment_id
    assert link["link_status"] == "confirmed"


def test_cannot_reclassify_another_papers_attachment(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        first = create_paper(conn, title="First", csl_json={"title": "First"})
        second = create_paper(conn, title="Second", csl_json={"title": "Second"})
        attachment_id = create_attachment(
            conn,
            paper_id=first,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            attachment_type="pdf",
            role="other",
        )
    engine.dispose()
    response = TestClient(create_app(db_url=temp_db_url)).patch(
        f"/papers/{second}/attachments/{attachment_id}/document-role", json={"role": "preregistration"}
    )
    assert response.status_code == 404
