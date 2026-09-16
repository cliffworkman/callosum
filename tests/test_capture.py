"""The bounded browser-capture boundary (#61 Phase 1).

Covers the security boundary, the admission adapter, and the conservative attachment rule. Hermetic:
fake embedding model, in-memory vector store, injected Crossref, no network, no browser.
"""

from __future__ import annotations

import time
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.api import create_app
from app.backend.api.routers import capture as capture_router
from app.backend.capture import idempotency, pairing
from app.backend.capture.admission import CAPTURE_SOURCE
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.annotations_repo import create_annotation
from app.backend.persistence.database import make_engine
from app.backend.persistence.paper_lifecycle_repo import soft_delete_paper
from app.backend.persistence.repository import create_paper, get_attachments_for_paper
from app.backend.persistence.schema import embeddings, papers
from tests.api_helpers import ApiFakeEmbeddingModel, indexing_collaborators

CAPTURE_HEADERS = {"x-callosum-capture": "browser-capture-v1"}


class _FakeCrossref:
    """Resolves any DOI to a fixed record — the create_app(crossref_client=...) seam."""

    def __init__(self, resolved: bool = True) -> None:
        self._resolved = resolved

    def resolve_doi(self, conn, doi):
        from integrations.crossref.adapter import CrossrefResolution

        return CrossrefResolution(
            doi=doi,
            resolved=self._resolved,
            csl_json={
                "DOI": doi,
                "title": "A Captured Paper",
                "abstract": "Enough text for the paper-level embedding to be non-empty.",
                "container-title": "Journal of Capture",
                "issued": {"date-parts": [[2024]]},
                "author": [{"family": "Okafor", "given": "N"}],
            }
            if self._resolved
            else None,
        )


@pytest.fixture(autouse=True)
def _ui_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture is UI-instance only; most tests need the gate open. Role tests override this."""
    monkeypatch.setenv("CALLOSUM_INSTANCE_ROLE", "ui")
    capture_router._reset_for_tests()
    yield
    capture_router._reset_for_tests()


def _client(temp_db_url: str, *, resolved: bool = True) -> TestClient:
    return TestClient(
        create_app(
            db_url=temp_db_url,
            crossref_client=_FakeCrossref(resolved=resolved),
            embedding_model=ApiFakeEmbeddingModel(),
            vector_store=InMemoryVectorStore(),
        )
    )


def _paired(client: TestClient) -> dict[str, str]:
    """Pair + open a session, returning the headers a capture request needs."""
    secret = pairing.ensure_pairing_secret()
    response = client.post("/capture/session", json={"pairing_secret": secret})
    assert response.status_code == 200, response.text
    return {**CAPTURE_HEADERS, "Authorization": f"Bearer {response.json()['session_token']}"}


def _envelope(**overrides) -> dict:
    base = {
        "envelope_version": 1,
        "source_url": "https://example.org/article/1",
        "captured_at": "2026-09-16T10:00:00Z",
        "producer_kind": "generic",
        "title": "A Captured Paper",
        "creators": [{"family": "Okafor", "given": "N"}],
        "year": 2024,
        "identifiers": {"doi": "10.1/captured"},
        "field_provenance": {"doi": "citation_doi"},
    }
    base.update(overrides)
    return base


def _one_page_pdf(path: Path, text: str = "Captured page one.") -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 144), text)
    doc.save(str(path))
    doc.close()
    return path


# ── the instance-role gate: sibling backends must never accept capture ──────────────────────────


@pytest.mark.parametrize("role", ["word-https", "tunnel-target"])
def test_sibling_backends_refuse_capture(temp_db_url: str, monkeypatch, role: str) -> None:
    """The Word-HTTPS child runs with the Remote Access gate disabled; it must not accept capture."""
    monkeypatch.setenv("CALLOSUM_INSTANCE_ROLE", role)
    response = _client(temp_db_url).post("/capture/session", json={"pairing_secret": "anything"})
    assert response.status_code == 403


def test_undeclared_instance_refuses_capture(temp_db_url: str, monkeypatch) -> None:
    """A process that declares no role is not the UI backend — absence must never pass for `ui`."""
    monkeypatch.delenv("CALLOSUM_INSTANCE_ROLE", raising=False)
    response = _client(temp_db_url).post("/capture/session", json={"pairing_secret": "anything"})
    assert response.status_code == 403


# ── authorization ───────────────────────────────────────────────────────────────────────────────


def test_capture_requires_a_session_token(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    response = client.post("/capture/item", json=_envelope(), headers=CAPTURE_HEADERS)
    assert response.status_code == 401


def test_capture_rejects_a_wrong_token(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    pairing.ensure_pairing_secret()
    response = client.post(
        "/capture/item",
        json=_envelope(),
        headers={**CAPTURE_HEADERS, "Authorization": "Bearer not-a-real-session"},
    )
    assert response.status_code == 401


def test_capture_rejects_an_expired_session(temp_db_url: str, monkeypatch) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    # Jump past the TTL rather than sleeping — the limiter/session clock is monotonic.
    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + pairing.SESSION_TTL_S + 1)
    response = client.post("/capture/item", json=_envelope(), headers=headers)
    assert response.status_code == 401


def test_wrong_pairing_secret_yields_no_session(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    pairing.ensure_pairing_secret()
    assert client.post("/capture/session", json={"pairing_secret": "wrong"}).status_code == 401


def test_rotating_the_pairing_secret_revokes_live_sessions(temp_db_url: str) -> None:
    """Rotation is the revocation path: existing tokens stop working immediately, not at TTL."""
    client = _client(temp_db_url)
    headers = _paired(client)
    pairing.rotate_pairing_secret()
    assert client.post("/capture/item", json=_envelope(), headers=headers).status_code == 401


def test_capture_requires_the_action_header(temp_db_url: str) -> None:
    """The non-safelisted header forces a preflight the GET-only CORS policy denies to foreign origins."""
    client = _client(temp_db_url)
    headers = _paired(client)
    headers.pop("x-callosum-capture")
    assert client.post("/capture/item", json=_envelope(), headers=headers).status_code == 403


def test_capture_rejects_a_foreign_host_header(temp_db_url: str) -> None:
    """DNS-rebinding defense: a rebound name resolving to loopback is refused."""
    client = _client(temp_db_url)
    headers = _paired(client)
    response = client.post("/capture/item", json=_envelope(), headers={**headers, "host": "evil.example"})
    assert response.status_code == 403


def test_capture_rejects_a_relayed_request(temp_db_url: str) -> None:
    """A forwarded header means the request came through a relay/tunnel, never a local extension."""
    client = _client(temp_db_url)
    headers = _paired(client)
    response = client.post("/capture/item", json=_envelope(), headers={**headers, "x-forwarded-for": "8.8.8.8"})
    assert response.status_code == 403


# ── rate limiting (pure unit, injected clock — no sleeping) ──────────────────────────────────────


def test_capture_rate_limiter_is_independent_of_remote_access() -> None:
    from app.backend.api.access_control import RateLimiter

    limiter = RateLimiter(max_requests=3, window=60.0)
    assert [limiter.allow("capture", now=t) for t in (0.0, 0.1, 0.2)] == [True, True, True]
    assert limiter.allow("capture", now=0.3) is False
    assert limiter.allow("capture", now=61.0) is True


def test_capture_returns_429_when_the_budget_is_exhausted(temp_db_url: str, monkeypatch) -> None:
    monkeypatch.setattr(capture_router, "_limiter", capture_router.RateLimiter(max_requests=2, window=60.0))
    client = _client(temp_db_url)
    pairing.ensure_pairing_secret()
    codes = [client.post("/capture/session", json={"pairing_secret": "x"}).status_code for _ in range(4)]
    assert 429 in codes


# ── request-size boundary ───────────────────────────────────────────────────────────────────────


def test_oversized_envelope_is_refused_before_parsing(temp_db_url: str) -> None:
    """Per-field caps run only after a parse; the streaming cap is what actually bounds the body."""
    client = _client(temp_db_url)
    headers = _paired(client)
    huge = b"{" + b" " * (capture_router.MAX_CAPTURE_BODY_BYTES + 1024) + b"}"
    response = client.post("/capture/item", content=huge, headers={**headers, "content-type": "application/json"})
    assert response.status_code == 413


def test_envelope_rejects_unbounded_creator_cardinality(temp_db_url: str) -> None:
    """Ten thousand one-character authors pass every per-field check; cardinality is capped too."""
    client = _client(temp_db_url)
    headers = _paired(client)
    payload = _envelope(creators=[{"family": "X"} for _ in range(600)])
    assert client.post("/capture/item", json=payload, headers=headers).status_code == 422


def test_envelope_version_must_be_pinned(temp_db_url: str) -> None:
    """A future v2 producer is refused explicitly, never silently reinterpreted as v1."""
    client = _client(temp_db_url)
    headers = _paired(client)
    assert client.post("/capture/item", json=_envelope(envelope_version=2), headers=headers).status_code == 422


# ── admission ───────────────────────────────────────────────────────────────────────────────────


def test_capture_admits_a_new_paper_and_indexes_it(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    body = client.post("/capture/item", json=_envelope(), headers=headers).json()

    assert body["status"] == "added"
    assert body["created"] is True
    paper_id = body["paper_id"]

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        row = conn.execute(select(papers).where(papers.c.id == paper_id)).mappings().one()
        embedded = conn.execute(
            select(func.count())
            .select_from(embeddings)
            .where(embeddings.c.target_type == "paper", embeddings.c.target_id == paper_id)
        ).scalar_one()
    engine.dispose()

    assert row["imported_source"] == CAPTURE_SOURCE  # capture provenance, not discovery's
    assert embedded == 1, "the indexing invariant must hold for the browser front end too"


def test_capture_surfaces_an_existing_paper_without_duplicating(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    first = client.post("/capture/item", json=_envelope(), headers=headers).json()
    second = client.post("/capture/item", json=_envelope(), headers=headers).json()

    assert second["status"] == "already_present"
    assert second["paper_id"] == first["paper_id"]
    assert second["created"] is False


def test_capture_reports_a_trashed_paper_without_writing_or_restoring(temp_db_url: str) -> None:
    """Trash fails honestly: no write, no silent restore, no colliding replacement."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        trashed_id = create_paper(
            conn, title="A Captured Paper", csl_json={"title": "A Captured Paper"}, doi="10.1/captured"
        )
        soft_delete_paper(conn, trashed_id)
    engine.dispose()

    client = _client(temp_db_url)
    headers = _paired(client)
    body = client.post("/capture/item", json=_envelope(), headers=headers).json()

    assert body["status"] == "in_trash"
    assert body["paper_id"] == trashed_id

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        row = conn.execute(select(papers).where(papers.c.id == trashed_id)).mappings().one()
        live = conn.execute(select(func.count()).select_from(papers).where(papers.c.deleted_at.is_(None))).scalar_one()
    engine.dispose()

    assert row["deleted_at"] is not None, "capture must never silently restore a trashed paper"
    assert live == 0, "capture must not create a live duplicate beside the trashed row"


def test_capture_refuses_to_guess_when_identity_rests_on_non_unique_fields(temp_db_url: str) -> None:
    """No DOI + an existing title/year/author match → review, never a silent first-match write."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(
            conn,
            title="A Captured Paper",
            csl_json={"title": "A Captured Paper"},
            year=2024,
            first_author_family_name="Okafor",
        )
    engine.dispose()

    client = _client(temp_db_url)
    headers = _paired(client)
    payload = _envelope(identifiers={})
    body = client.post("/capture/item", json=payload, headers=headers).json()

    assert body["status"] == "unresolved_review_required"
    assert body["created"] is False


def test_capture_reports_unresolved_for_a_doi_crossref_cannot_resolve(temp_db_url: str) -> None:
    """An unresolvable DOI creates nothing — never an invented placeholder record."""
    client = _client(temp_db_url, resolved=False)
    headers = _paired(client)
    body = client.post("/capture/item", json=_envelope(), headers=headers).json()

    assert body["status"] == "unresolved_review_required"
    assert body["paper_id"] is None


# ── idempotency: a retry replays, it does not mutate twice ──────────────────────────────────────


def test_a_retried_capture_replays_the_original_outcome(temp_db_url: str) -> None:
    """The session token is reusable by design; THIS is what stops a duplicate admission."""
    client = _client(temp_db_url)
    headers = {**_paired(client), "Idempotency-Key": "capture-abc"}
    first = client.post("/capture/item", json=_envelope(), headers=headers).json()
    second = client.post("/capture/item", json=_envelope(), headers=headers).json()

    assert second == first
    assert second["status"] == "added", "the replay returns the ORIGINAL outcome, not 'already_present'"

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        total = conn.execute(select(func.count()).select_from(papers)).scalar_one()
    engine.dispose()
    assert total == 1


# ── the conservative Phase 1 attachment rule ────────────────────────────────────────────────────


def test_a_new_paper_accepts_captured_pdf_bytes(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    body = client.post("/capture/item", json=_envelope(pdf_bytes_from_active_tab=True), headers=headers).json()

    assert body["pdf_accepted"] is True
    pdf = _one_page_pdf(tmp_path / "captured.pdf")
    response = client.post(
        f"/capture/item/{body['capture_id']}/pdf",
        content=pdf.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    )
    assert response.status_code == 200, response.text

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        attachments = get_attachments_for_paper(conn, body["paper_id"])
        chunk_embeddings = conn.execute(
            select(func.count()).select_from(embeddings).where(embeddings.c.target_type == "chunk")
        ).scalar_one()
    engine.dispose()

    assert len(attachments) == 1
    assert attachments[0]["import_source"] == CAPTURE_SOURCE
    assert chunk_embeddings >= 1, "attaching indexes the chunks — it is a property of attaching"


def test_existing_paper_with_a_pdf_refuses_capture_bytes(temp_db_url: str, tmp_path: Path) -> None:
    """Phase 1 never overwrites, replaces or demotes an attachment — and there is no detach path."""
    from app.backend.pdf_processing.ingest import attach_pdf_to_paper

    engine = make_engine(temp_db_url)
    pdf = _one_page_pdf(tmp_path / "existing.pdf")
    with engine.begin() as conn:
        paper_id = create_paper(
            conn, title="A Captured Paper", csl_json={"title": "A Captured Paper"}, doi="10.1/captured"
        )
        attach_pdf_to_paper(conn, paper_id, pdf, **indexing_collaborators())
    engine.dispose()

    client = _client(temp_db_url)
    headers = _paired(client)
    body = client.post("/capture/item", json=_envelope(pdf_bytes_from_active_tab=True), headers=headers).json()

    assert body["status"] == "already_present"
    assert body["pdf_accepted"] is False
    assert body["pdf_reason"] == "attachment_review_required"
    assert body["capture_id"] is None, "no upload slot is offered for a refused attachment"

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert len(get_attachments_for_paper(conn, paper_id)) == 1, "existing state must be untouched"
    engine.dispose()


def test_existing_paper_with_annotations_refuses_capture_bytes(temp_db_url: str) -> None:
    """Annotations with a NULL attachment_id render over ANY PDF the paper owns — do not light them up."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn, title="A Captured Paper", csl_json={"title": "A Captured Paper"}, doi="10.1/captured"
        )
        create_annotation(
            conn,
            paper_id=paper_id,
            page=1,
            color="#ffd400",
            bboxes_json=[{"x0": 10, "y0": 20, "x1": 200, "y1": 40}],
            anchor_text="a highlight from another PDF",
            prefix=None,
            suffix=None,
            attachment_id=None,  # exactly what bundle/share import writes, by design
            source="user",
            note=None,
        )
    engine.dispose()

    client = _client(temp_db_url)
    headers = _paired(client)
    body = client.post("/capture/item", json=_envelope(pdf_bytes_from_active_tab=True), headers=headers).json()

    assert body["pdf_accepted"] is False
    assert body["pdf_reason"] == "attachment_review_required"


def test_metadata_only_existing_paper_with_no_attachments_or_annotations_accepts_pdf(
    temp_db_url: str, tmp_path: Path
) -> None:
    """The one existing-paper case Phase 1 does allow — #61's motivating scenario, safely bounded."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn, title="A Captured Paper", csl_json={"title": "A Captured Paper"}, doi="10.1/captured"
        )
    engine.dispose()

    client = _client(temp_db_url)
    headers = _paired(client)
    body = client.post("/capture/item", json=_envelope(pdf_bytes_from_active_tab=True), headers=headers).json()

    assert body["status"] == "already_present"
    assert body["pdf_accepted"] is True

    pdf = _one_page_pdf(tmp_path / "late.pdf")
    response = client.post(
        f"/capture/item/{body['capture_id']}/pdf",
        content=pdf.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    )
    assert response.status_code == 200

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert len(get_attachments_for_paper(conn, paper_id)) == 1
    engine.dispose()


# ── PDF validation ──────────────────────────────────────────────────────────────────────────────


def _capture_slot(client: TestClient, headers: dict) -> str:
    body = client.post("/capture/item", json=_envelope(pdf_bytes_from_active_tab=True), headers=headers).json()
    assert body["pdf_accepted"] is True
    return body["capture_id"]


def test_pdf_upload_rejects_bad_magic(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    capture_id = _capture_slot(client, headers)
    response = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=b"this is definitely not a pdf",
        headers={**headers, "content-type": "application/pdf"},
    )
    assert response.status_code == 422


def test_pdf_upload_rejects_a_malformed_pdf(temp_db_url: str) -> None:
    """Right magic, unparseable body — the PyMuPDF check is what catches this."""
    client = _client(temp_db_url)
    headers = _paired(client)
    capture_id = _capture_slot(client, headers)
    response = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=b"%PDF-1.7\nnot actually a pdf body",
        headers={**headers, "content-type": "application/pdf"},
    )
    assert response.status_code == 422


def test_pdf_upload_rejects_an_oversized_declared_length(temp_db_url: str) -> None:
    """The >80 MiB path the existing registration tests never covered."""
    from app.backend.acquisition.fetch import MAX_OA_PDF_BYTES

    client = _client(temp_db_url)
    headers = _paired(client)
    capture_id = _capture_slot(client, headers)
    response = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=b"%PDF-1.7 tiny",
        headers={
            **headers,
            "content-type": "application/pdf",
            "content-length": str(MAX_OA_PDF_BYTES + 1),
        },
    )
    assert response.status_code == 413


def test_failed_pdf_upload_leaves_the_admitted_paper_intact(temp_db_url: str) -> None:
    """Honest partial success: metadata really was admitted; only the bytes failed."""
    client = _client(temp_db_url)
    headers = _paired(client)
    body = client.post("/capture/item", json=_envelope(pdf_bytes_from_active_tab=True), headers=headers).json()
    client.post(
        f"/capture/item/{body['capture_id']}/pdf",
        content=b"not a pdf",
        headers={**headers, "content-type": "application/pdf"},
    )

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        row = conn.execute(select(papers).where(papers.c.id == body["paper_id"])).mappings().one()
        assert len(get_attachments_for_paper(conn, body["paper_id"])) == 0
    engine.dispose()
    assert row["deleted_at"] is None, "the paper survives a failed attachment"


def test_pdf_upload_cleans_up_its_temp_file(temp_db_url: str) -> None:
    """The temp file is removed on the failure path too, not only on success."""
    import tempfile

    client = _client(temp_db_url)
    headers = _paired(client)
    capture_id = _capture_slot(client, headers)
    before = set(Path(tempfile.gettempdir()).glob("callosum-capture-*.pdf"))
    client.post(
        f"/capture/item/{capture_id}/pdf",
        content=b"not a pdf",
        headers={**headers, "content-type": "application/pdf"},
    )
    after = set(Path(tempfile.gettempdir()).glob("callosum-capture-*.pdf"))
    assert after <= before


def test_pdf_upload_for_an_unknown_capture_is_404(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    response = client.post(
        "/capture/item/deadbeef/pdf",
        content=b"%PDF-1.7",
        headers={**headers, "content-type": "application/pdf"},
    )
    assert response.status_code == 404


# ── the pairing secret ──────────────────────────────────────────────────────────────────────────


def test_pairing_secret_lives_beside_the_settings_file(tmp_path, monkeypatch) -> None:
    """The cross-language contract: a plain file the Rust connector host can compute the path to."""
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "app-settings.json"))
    secret = pairing.ensure_pairing_secret()
    assert pairing.pairing_file_path() == tmp_path / "capture-pairing.json"
    assert pairing.pairing_file_path().is_file()
    assert pairing.read_pairing_secret() == secret
    assert pairing.ensure_pairing_secret() == secret, "ensure is idempotent"


# ── wiring the pairing secret at startup (#61 Phase 2, Part 5) ─────────────────────────────────


def _app_module():
    """The `app.backend.api.app` SUBMODULE, not the FastAPI instance.

    `app/backend/api/__init__.py` does `from app.backend.api.app import app`, which rebinds the
    `app` attribute on the `app.backend.api` package to the FastAPI instance — so both
    `from app.backend.api import app` and `import app.backend.api.app as x` resolve to the
    instance, not the module, once that package has been imported. `sys.modules` is the only
    lookup that isn't shadowed by that rebinding.
    """
    import sys

    import app.backend.api.app  # noqa: F401 - ensures it is registered in sys.modules

    return sys.modules["app.backend.api.app"]


def test_startup_mints_the_pairing_secret_for_the_ui_instance_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stage 1 left `ensure_pairing_secret()` with no production caller; this closes that gap."""
    monkeypatch.setenv("CALLOSUM_INSTANCE_ROLE", "ui")
    assert pairing.read_pairing_secret() is None
    _app_module()._ensure_capture_pairing_ready()
    assert pairing.read_pairing_secret() is not None


def test_startup_never_mints_a_pairing_secret_for_a_sibling_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    for role in ("word-https", "tunnel-target"):
        monkeypatch.setenv("CALLOSUM_INSTANCE_ROLE", role)
        _app_module()._ensure_capture_pairing_ready()
        assert pairing.read_pairing_secret() is None, f"role {role!r} must never create the pairing file"


def test_startup_pairing_failure_is_logged_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A permissions/disk-full failure must disable browser capture, never take down startup."""
    monkeypatch.setenv("CALLOSUM_INSTANCE_ROLE", "ui")

    def _boom() -> str:
        raise OSError("disk full")

    monkeypatch.setattr(pairing, "ensure_pairing_secret", _boom)
    with caplog.at_level("WARNING"):
        _app_module()._ensure_capture_pairing_ready()  # must not raise
    assert any("Browser capture is disabled" in record.message for record in caplog.records)


def test_idempotency_map_is_bounded() -> None:
    idempotency.clear()
    for index in range(idempotency.MAX_REMEMBERED + 20):
        idempotency.remember(f"key-{index}", {"status": "added"})
    assert len(idempotency._outcomes) <= idempotency.MAX_REMEMBERED
