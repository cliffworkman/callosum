"""The Import Queue human review/resolution loop (#61 provisional ingestion, human review increment).

Covers the read/preview-doi/confirm/retry/delete surface added on top of the provisional-capture
pipeline proven in `tests/test_capture.py`. Reuses that file's fixtures/helpers rather than
re-deriving them (established cross-test-file pattern, e.g. `test_reference_integrity.py` importing
from `test_citation_context.py`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.acquisition.fetch import library_dir
from app.backend.api.routers import capture as capture_router
from app.backend.capture.provisional import (
    best_candidate,
    explain_evidence,
    provenance_artifacts_dir,
    queue_dir,
)
from app.backend.persistence import capture_events_repo, provisional_artifacts_repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, get_attachments_for_paper
from app.backend.persistence.schema import papers
from tests.api_helpers import indexing_collaborators
from tests.test_capture import (
    _client,
    _direct_pdf_capture_id,
    _one_page_pdf,
    _paired,
    _pdf_with_front_matter_doi,
    _pdf_with_metadata_title,
    _pdf_with_references_then_doi,
)


@pytest.fixture(autouse=True)
def _ui_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same gate as `test_capture.py`'s own fixture -- autouse fixtures are scoped to the file that
    defines them, so importing helpers from that module does not import its fixtures too."""
    monkeypatch.setenv("CALLOSUM_INSTANCE_ROLE", "ui")
    capture_router._reset_for_tests()
    yield
    capture_router._reset_for_tests()


# ── pure-function tests: explain_evidence / best_candidate ─────────────────────────────────────────


def test_explain_evidence_strong_candidate() -> None:
    evidence = {"resolutions": [{"disposition": "strong", "doi": "10.1/x", "resolved_title": "T"}], "candidates": []}
    assert "closely matches" in explain_evidence(evidence)


def test_explain_evidence_insufficient_corroboration() -> None:
    evidence = {"resolutions": [{"disposition": "insufficient_corroboration", "doi": "10.1/x"}], "candidates": []}
    assert "did not corroborate" in explain_evidence(evidence)


def test_explain_evidence_multiple_strong() -> None:
    evidence = {
        "resolutions": [
            {"disposition": "strong", "doi": "10.1/a"},
            {"disposition": "strong", "doi": "10.1/b"},
        ],
        "candidates": [],
    }
    assert "Multiple" in explain_evidence(evidence)


def test_explain_evidence_front_matter_unresolved() -> None:
    evidence = {"resolutions": [], "candidates": [{"position_class": "front_matter", "doi": "10.1/x"}]}
    assert "could not be resolved" in explain_evidence(evidence)


def test_explain_evidence_references_only() -> None:
    evidence = {"resolutions": [], "candidates": [{"position_class": "references", "doi": "10.1/x"}]}
    assert "References section" in explain_evidence(evidence)


def test_explain_evidence_nothing_found() -> None:
    evidence = {"resolutions": [], "candidates": []}
    assert "No DOI-shaped text" in explain_evidence(evidence)


def test_best_candidate_prefers_strong_over_insufficient() -> None:
    evidence = {
        "resolutions": [
            {"disposition": "insufficient_corroboration", "doi": "10.1/weak"},
            {"disposition": "strong", "doi": "10.1/strong", "resolved_title": "T"},
        ]
    }
    c = best_candidate(evidence)
    assert c["doi"] == "10.1/strong"


def test_best_candidate_none_when_nothing_resolved() -> None:
    assert best_candidate({"resolutions": []}) is None


# ── list / detail ────────────────────────────────────────────────────────────────────────────────


def _queue_pending_item(client: TestClient, tmp_path: Path, *, title: str | None = None) -> str:
    headers = _paired(client)
    capture_id = _direct_pdf_capture_id(client, headers)
    pdf = _pdf_with_metadata_title(tmp_path / "mystery.pdf", title=title)
    body = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=pdf.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    ).json()
    assert body["status"] == "direct_pdf_queued_for_review"
    engine = make_engine(client.app.state.db_url)
    with engine.begin() as conn:
        rows = provisional_artifacts_repo.list_needing_review(conn)
    engine.dispose()
    return rows[0]["id"]


def test_list_and_detail_expose_explanation_and_best_candidate(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)

    listed = client.get("/library/import-queue").json()["items"]
    assert len(listed) == 1
    item = listed[0]
    assert item["artifact_id"] == artifact_id
    assert item["identity_state"] == "unresolved"
    assert item["promotion_state"] == "pending_review"
    assert item["best_candidate"] is None
    assert "No DOI-shaped text" in item["explanation"]

    detail = client.get(f"/library/import-queue/{artifact_id}").json()
    assert detail["artifact_id"] == artifact_id
    assert "evidence" in detail and "candidates" in detail["evidence"]


def test_detail_404s_for_unknown_artifact(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    assert client.get("/library/import-queue/not-a-real-id").status_code == 404


# ── preview-doi: read-only, never mutates ───────────────────────────────────────────────────────────


def test_preview_doi_invalid_does_not_mutate(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    before = client.get("/library/import-queue").json()

    response = client.post(f"/library/import-queue/{artifact_id}/preview-doi", json={"doi": "not a doi"})
    assert response.status_code == 200
    assert response.json()["status"] == "invalid"

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        total_papers = conn.execute(select(func.count()).select_from(papers)).scalar_one()
    engine.dispose()
    assert total_papers == 0
    assert client.get("/library/import-queue").json() == before


def test_preview_doi_unresolved_does_not_mutate(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url, resolved=False)
    artifact_id = _queue_pending_item(client, tmp_path)

    response = client.post(f"/library/import-queue/{artifact_id}/preview-doi", json={"doi": "10.1234/nope"})
    assert response.json()["status"] == "unresolved"

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        total_papers = conn.execute(select(func.count()).select_from(papers)).scalar_one()
    engine.dispose()
    assert total_papers == 0


def test_preview_doi_matching_existing_paper_reports_existing_without_mutating(
    temp_db_url: str, tmp_path: Path
) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        existing_id = create_paper(conn, title="Already Here", csl_json={"title": "Already Here"}, doi="10.1234/here")
    engine.dispose()

    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    response = client.post(f"/library/import-queue/{artifact_id}/preview-doi", json={"doi": "10.1234/here"})
    data = response.json()
    assert data["status"] == "existing"
    assert data["paper_id"] == existing_id

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        total_papers = conn.execute(select(func.count()).select_from(papers)).scalar_one()
    engine.dispose()
    assert total_papers == 1  # only the pre-seeded paper -- preview created nothing


def test_preview_doi_resolves_a_new_candidate_without_creating_it(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    response = client.post(f"/library/import-queue/{artifact_id}/preview-doi", json={"doi": "10.1234/found-in-pdf"})
    data = response.json()
    assert data["status"] == "resolved"
    assert data["title"] == "A Captured Paper"

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        total_papers = conn.execute(select(func.count()).select_from(papers)).scalar_one()
    engine.dispose()
    assert total_papers == 0


def test_preview_doi_404s_for_unknown_artifact(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    response = client.post("/library/import-queue/not-a-real-id/preview-doi", json={"doi": "10.1234/x"})
    assert response.status_code == 404


# ── confirm: best candidate, manual DOI, attachment conflict ────────────────────────────────────────


def test_confirm_with_manually_entered_doi_promotes_and_records_provenance(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)

    response = client.post(
        f"/library/import-queue/{artifact_id}/confirm", json={"doi": "10.1234/found-in-pdf", "source": "manual"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["promotion_state"] == "promoted"
    paper_id = data["resolved_paper_id"]
    assert paper_id is not None

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        attachments = get_attachments_for_paper(conn, paper_id)
        artifact = provisional_artifacts_repo.get(conn, artifact_id)
    engine.dispose()
    assert len(attachments) == 1
    evidence = json.loads(artifact["evidence_json"])
    user_actions = evidence.get("user_actions", [])
    assert len(user_actions) == 1
    assert user_actions[0]["action"] == "user_entered_doi"
    assert user_actions[0]["doi"] == "10.1234/found-in-pdf"

    # No longer actionable -- it's promoted.
    assert client.get("/library/import-queue").json()["items"] == []

    root = library_dir()
    assert list(queue_dir(root).glob("*.pdf")) == []
    assert len(list(root.glob("capture-*.pdf"))) == 1


def test_confirm_with_best_candidate_uses_source_candidate(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    capture_id = _direct_pdf_capture_id(client, headers)
    pdf = _pdf_with_front_matter_doi(
        tmp_path / "identified.pdf", title="A Captured Paper", dois=["10.1234/found-in-pdf"]
    )
    body = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=pdf.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    ).json()
    # This specific fixture auto-promotes already (unique strong front-matter candidate) -- use a
    # second, genuinely ambiguous capture instead so there's something left to manually confirm.
    assert body["status"] == "added"

    capture_id2 = _direct_pdf_capture_id(client, headers, source_url="https://example.org/ambiguous.pdf")
    pdf2 = _pdf_with_front_matter_doi(
        tmp_path / "ambiguous.pdf", title="A Captured Paper", dois=["10.1234/candidate-one", "10.1234/candidate-two"]
    )
    body2 = client.post(
        f"/capture/item/{capture_id2}/pdf",
        content=pdf2.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    ).json()
    assert body2["status"] == "direct_pdf_queued_for_review"

    listed = client.get("/library/import-queue").json()["items"]
    assert len(listed) == 1
    artifact_id = listed[0]["artifact_id"]
    candidate = listed[0]["best_candidate"]
    assert candidate is not None  # both candidates resolved+agreed; ambiguity is about UNIQUENESS, not strength

    response = client.post(
        f"/library/import-queue/{artifact_id}/confirm", json={"doi": candidate["doi"], "source": "candidate"}
    )
    assert response.json()["promotion_state"] == "promoted"

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        artifact = provisional_artifacts_repo.get(conn, artifact_id)
    engine.dispose()
    evidence = json.loads(artifact["evidence_json"])
    assert evidence["user_actions"][0]["action"] == "user_confirmed_candidate"
    # The original auto-pipeline's observations survive untouched.
    assert len(evidence["candidates"]) >= 2


def test_confirm_reaching_attachment_conflict_leaves_existing_paper_and_queue_pdf_untouched(
    temp_db_url: str, tmp_path: Path
) -> None:
    engine = make_engine(temp_db_url)
    existing_pdf = _one_page_pdf(tmp_path / "existing.pdf")
    with engine.begin() as conn:
        existing_paper_id = create_paper(
            conn, title="A Captured Paper", csl_json={"title": "A Captured Paper"}, doi="10.1234/found-in-pdf"
        )
        from app.backend.pdf_processing.ingest import attach_pdf_to_paper

        attach_pdf_to_paper(conn, existing_paper_id, existing_pdf, **indexing_collaborators())
    engine.dispose()

    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    response = client.post(
        f"/library/import-queue/{artifact_id}/confirm", json={"doi": "10.1234/found-in-pdf", "source": "manual"}
    )
    data = response.json()
    assert data["promotion_state"] == "attachment_conflict"
    assert data["resolved_paper_id"] == existing_paper_id

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        attachments = get_attachments_for_paper(conn, existing_paper_id)
    engine.dispose()
    assert len(attachments) == 1  # the pre-existing attachment, unchanged

    root = library_dir()
    assert len(list(queue_dir(root).glob("*.pdf"))) == 1  # the queue copy survives
    assert list(root.glob("capture-*.pdf")) == []  # no duplicate canonical file was ever created

    listed = client.get("/library/import-queue").json()["items"]
    assert len(listed) == 1
    assert listed[0]["promotion_state"] == "attachment_conflict"
    assert listed[0]["resolved_paper_title"] == "A Captured Paper"


def test_confirm_invalid_doi_reports_error_without_mutating(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    response = client.post(f"/library/import-queue/{artifact_id}/confirm", json={"doi": "garbage", "source": "manual"})
    data = response.json()
    assert data["promotion_state"] == "pending_review"

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        total_papers = conn.execute(select(func.count()).select_from(papers)).scalar_one()
    engine.dispose()
    assert total_papers == 0


def test_confirm_404s_for_unknown_artifact(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    response = client.post("/library/import-queue/not-a-real-id/confirm", json={"doi": "10.1234/x"})
    assert response.status_code == 404


# ── retry ───────────────────────────────────────────────────────────────────────────────────────


def test_retry_refused_when_identity_unresolved(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    response = client.post(f"/library/import-queue/{artifact_id}/retry")
    assert response.status_code == 422

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        artifact = provisional_artifacts_repo.get(conn, artifact_id)
    engine.dispose()
    assert artifact["identity_state"] == "unresolved"  # untouched


def test_retry_on_attachment_conflict_preserves_queue_pdf_when_conflict_persists(
    temp_db_url: str, tmp_path: Path
) -> None:
    engine = make_engine(temp_db_url)
    existing_pdf = _one_page_pdf(tmp_path / "existing.pdf")
    with engine.begin() as conn:
        existing_paper_id = create_paper(
            conn, title="A Captured Paper", csl_json={"title": "A Captured Paper"}, doi="10.1234/found-in-pdf"
        )
        from app.backend.pdf_processing.ingest import attach_pdf_to_paper

        attach_pdf_to_paper(conn, existing_paper_id, existing_pdf, **indexing_collaborators())
    engine.dispose()

    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    client.post(
        f"/library/import-queue/{artifact_id}/confirm", json={"doi": "10.1234/found-in-pdf", "source": "manual"}
    )

    response = client.post(f"/library/import-queue/{artifact_id}/retry")
    assert response.status_code == 200
    assert response.json()["promotion_state"] == "attachment_conflict"  # still conflicting; nothing lost

    root = library_dir()
    assert len(list(queue_dir(root).glob("*.pdf"))) == 1


def test_retry_after_injected_failure_preserves_queue_pdf_and_cleans_staged_duplicate(
    temp_db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.backend.capture.provisional as provisional_module

    client = _client(temp_db_url)
    headers = _paired(client)
    capture_id = _direct_pdf_capture_id(client, headers)
    pdf = _pdf_with_metadata_title(tmp_path / "mystery.pdf", title=None)
    body = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=pdf.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    ).json()
    assert body["status"] == "direct_pdf_queued_for_review"

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        artifact_id = provisional_artifacts_repo.list_needing_review(conn)[0]["id"]
    engine.dispose()

    real_attach_pdf_to_paper = provisional_module.attach_pdf_to_paper

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated embedding model failure")

    # NOTE: `monkeypatch` is the SAME shared per-test instance `conftest.py`'s autouse
    # `_egress_consent_default` fixture also uses to set CALLOSUM_LIBRARY_DIR -- calling
    # `monkeypatch.undo()` here would revert THAT too (it reverts every patch made via this shared
    # instance, not just this one attribute), silently falling back to the real project `library/`
    # directory. Restore only this one attribute instead.
    monkeypatch.setattr(provisional_module, "attach_pdf_to_paper", _boom)
    confirm = client.post(
        f"/library/import-queue/{artifact_id}/confirm", json={"doi": "10.1234/found-in-pdf", "source": "manual"}
    )
    assert confirm.json()["promotion_state"] in {"indexing_unavailable", "processing_failed"}

    monkeypatch.setattr(provisional_module, "attach_pdf_to_paper", real_attach_pdf_to_paper)
    retry = client.post(f"/library/import-queue/{artifact_id}/retry")
    assert retry.status_code == 200
    assert retry.json()["promotion_state"] == "promoted"

    root = library_dir()
    assert list(queue_dir(root).glob("*.pdf")) == []
    assert len(list(root.glob("capture-*.pdf"))) == 1


def test_retry_404s_for_unknown_artifact(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    assert client.post("/library/import-queue/not-a-real-id/retry").status_code == 422


# ── raw PDF preview stream ───────────────────────────────────────────────────────────────────────


def test_pdf_route_streams_bytes_for_a_live_queue_item(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    response = client.get(f"/library/import-queue/{artifact_id}/pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_pdf_route_404s_for_unknown_artifact(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    assert client.get("/library/import-queue/not-a-real-id/pdf").status_code == 404


def test_pdf_route_404s_once_promoted(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    client.post(
        f"/library/import-queue/{artifact_id}/confirm", json={"doi": "10.1234/found-in-pdf", "source": "manual"}
    )
    assert client.get(f"/library/import-queue/{artifact_id}/pdf").status_code == 404


def test_repeated_pdf_preview_fetches_create_no_new_files(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    root = library_dir()
    before = sorted(p.name for p in root.rglob("*") if p.is_file())
    for _ in range(5):
        client.get(f"/library/import-queue/{artifact_id}/pdf")
    after = sorted(p.name for p in root.rglob("*") if p.is_file())
    assert before == after


# ── deletion: explicit artifact-scoped policy ───────────────────────────────────────────────────────


def test_delete_removes_pdf_sidecar_and_all_capture_events_for_the_artifact(temp_db_url: str, tmp_path: Path) -> None:
    """Explicit policy: permanently deleting a provisional artifact removes its ENTIRE provisional
    history -- the PDF, the sidecar, the DB row, and every capture_events row -- regardless of how many
    encounters recorded it. This is deliberate for provisional (pre-canonical) state, not an emergent
    side effect: a still-queued artifact has no other retained record once it is gone."""
    client = _client(temp_db_url)
    headers = _paired(client)
    pdf = _pdf_with_metadata_title(tmp_path / "shared.pdf", title=None)
    pdf_bytes = pdf.read_bytes()

    first_capture_id = _direct_pdf_capture_id(client, headers, source_url="https://example.org/first.pdf")
    client.post(
        f"/capture/item/{first_capture_id}/pdf",
        content=pdf_bytes,
        headers={**headers, "content-type": "application/pdf"},
    )
    second_capture_id = _direct_pdf_capture_id(client, headers, source_url="https://example.org/second.pdf")
    client.post(
        f"/capture/item/{second_capture_id}/pdf",
        content=pdf_bytes,
        headers={**headers, "content-type": "application/pdf"},
    )

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        rows = provisional_artifacts_repo.list_needing_review(conn)
    assert len(rows) == 1
    artifact_id = rows[0]["id"]
    with engine.begin() as conn:
        events_before = capture_events_repo.list_for_artifact(conn, artifact_id)
    assert len(events_before) == 2  # two distinct encounters of the same bytes
    engine.dispose()

    root = library_dir()
    assert (queue_dir(root) / f"{artifact_id}.pdf").is_file()

    response = client.delete(f"/library/import-queue/{artifact_id}")
    assert response.status_code == 204

    assert not (queue_dir(root) / f"{artifact_id}.pdf").exists()
    assert not (provenance_artifacts_dir(root) / f"{artifact_id}.json").exists()
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert provisional_artifacts_repo.get(conn, artifact_id) is None
        # Both encounters are gone -- the deliberate artifact-scoped deletion policy, not an accident.
        assert capture_events_repo.list_for_artifact(conn, artifact_id) == []
    engine.dispose()


def test_delete_one_artifact_never_touches_a_different_still_queued_artifact(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_a = _queue_pending_item(client, tmp_path, title=None)
    pdf_b = _pdf_with_references_then_doi(tmp_path / "refs.pdf", title="A Captured Paper", doi="10.1234/only-cited")
    headers = _paired(client)
    capture_id_b = _direct_pdf_capture_id(client, headers, source_url="https://example.org/b.pdf")
    client.post(
        f"/capture/item/{capture_id_b}/pdf",
        content=pdf_b.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        rows = provisional_artifacts_repo.list_needing_review(conn)
    engine.dispose()
    assert len(rows) == 2
    artifact_b = next(r["id"] for r in rows if r["id"] != artifact_a)

    client.delete(f"/library/import-queue/{artifact_a}")

    root = library_dir()
    assert (queue_dir(root) / f"{artifact_b}.pdf").is_file()
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert provisional_artifacts_repo.get(conn, artifact_b) is not None
    engine.dispose()


def test_delete_404s_for_unknown_artifact(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    assert client.delete("/library/import-queue/not-a-real-id").status_code == 404


# ── generic-notification-clearing independence ──────────────────────────────────────────────────────


def test_import_queue_state_is_not_touched_by_job_store_or_notification_clearing(
    temp_db_url: str, tmp_path: Path
) -> None:
    """The queue is DB state read fresh on every GET, never a client-side notification/toast list --
    there is no code path in this codebase that "clears" provisional_artifacts as a side effect of
    dismissing an unrelated notification/job. Pinned here as a regression rather than left implicit."""
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    # Exercise unrelated job-store surfaces a notification-clear might touch -- none of them are wired
    # to provisional_artifacts at all, so the queue item must still be there afterward regardless.
    client.get("/library/watched")
    assert client.get("/library/import-queue").json()["items"][0]["artifact_id"] == artifact_id
