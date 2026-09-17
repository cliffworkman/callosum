"""Bounded browser-capture intake (#61 Phase 1) — separately authorized, UI-instance only.

The browser extension's one job is to observe a page the user explicitly clicked on and hand Callosum
a ``CaptureEnvelope``. Every consequential decision — is this the same work, may it be written, does
it get indexed — belongs to the canonical admission substrate, not to this router and never to the
extension.

Why this is its own boundary rather than a reuse of an existing endpoint
-----------------------------------------------------------------------
``/capture/*`` is reachable by a program the user installed into their browser. That is a genuinely
different trust posture from the app's own UI calling its own loopback API, so it gets:

* its own credential (NOT the Remote Access token, which gates the whole API and rides the cloudflared
  tunnel — conflating them would turn a capture compromise into a remote-access compromise);
* its own rate limit, active even when Remote Access is off (the global limiter is not);
* an explicit instance-role gate, so a sibling backend can never accept capture — including the Word
  HTTPS child, which deliberately runs with the Remote Access gate disabled;
* Host/forwarded-header validation, closing the DNS-rebinding gap that exists outside ``local_only``.

Origin is checked as defense in depth where present, but is **never** the trust boundary: an MV3
service worker's fetch does not carry the same Origin semantics as a page's, and a header is not a
credential.

The two-call protocol
---------------------
One capture may carry metadata *and* bytes. Multipart is used nowhere in this codebase and
base64-in-JSON would hold 80 MiB in memory, so:

1. ``POST /capture/session`` — the connector host exchanges the pairing secret for a session token.
2. ``POST /capture/item`` — the envelope. Identity, admission, **and the attachment decision** all
   happen here, so a refusal is known before any bytes move and nothing is partially mutated to
   discover it. Returns ``capture_id`` + ``pdf_accepted``.
3. ``POST /capture/item/{capture_id}/pdf`` — raw body, only when ``pdf_accepted``.

If step 3 fails after step 2 succeeded, the paper exists with no attachment and the extension reports
"Added — no PDF captured". That is honest partial success: the metadata admission really did happen.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import fitz
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import Engine

from app.backend.acquisition.fetch import MAX_OA_PDF_BYTES, library_dir
from app.backend.api.access_control import RateLimiter, _bearer
from app.backend.api.dependencies import get_engine
from app.backend.api.local_only import _require_local
from app.backend.api.routers.health import UI_ROLE, reported_instance_role
from app.backend.api.routers.library import _embedding_model, _vector_store
from app.backend.capture import idempotency, pairing
from app.backend.capture.admission import (
    CAPTURE_SOURCE,
    PDF_OK,
    AdmissionOutcome,
    admit,
)
from app.backend.capture.envelope import CaptureEnvelope
from app.backend.embeddings.admission import ensure_paper_indexed
from app.backend.pdf_processing.ingest import attach_pdf_to_paper
from app.backend.persistence.sqlite_retry import run_write
from integrations.crossref import CrossrefClient

router = APIRouter()

# The envelope is metadata only — generous for a long abstract and 500 authors, far below anything
# that makes parsing expensive. Enforced by STREAMING (see `_read_bounded_body`), not by trusting a
# client-supplied Content-Length: per-field Pydantic caps are checked only after a body is read and
# parsed, so they are the second line of defense, not the first.
MAX_CAPTURE_BODY_BYTES = 256 * 1024  # 256 KiB

# Capture gets its own budget. The global limiter in AccessControlMiddleware only engages when Remote
# Access is ON, so relying on it would leave the default local install unlimited.
CAPTURE_RATE_LIMIT_WINDOW = 60.0
CAPTURE_RATE_LIMIT_MAX = 60  # a human clicking capture; generous, bounded

# A non-safelisted header forces a CORS preflight, which the GET-only localhost policy then denies to
# every foreign origin. Defense in depth behind the session token, exactly the `local_only` idiom.
CAPTURE_ACTION_HEADER = "x-callosum-capture"
CAPTURE_ACTION_VALUE = "browser-capture-v1"

_limiter = RateLimiter(max_requests=CAPTURE_RATE_LIMIT_MAX, window=CAPTURE_RATE_LIMIT_WINDOW)

# Captures awaiting their optional PDF step: {capture_id: _PendingCapture}. In-process and bounded —
# a restart simply means the extension's PDF POST 404s and it reports "no PDF captured", which is the
# honest partial-success state rather than a silent failure.
_pending: dict[str, "_PendingCapture"] = {}
MAX_PENDING_CAPTURES = 64


@dataclass
class _PendingCapture:
    paper_id: int
    created: bool
    status: str
    attached: bool = False


class CaptureSessionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    pairing_secret: str = Field(min_length=1, max_length=pairing.PAIRING_SECRET_MAX_LEN)


class CaptureSessionResponse(BaseModel):
    session_token: str
    expires_in_s: float


class CaptureResult(BaseModel):
    """The machine-readable outcome. The extension owns the human wording."""

    status: str
    capture_id: str | None = None
    paper_id: int | None = None
    created: bool = False
    pdf_accepted: bool = False
    pdf_reason: str
    title: str | None = None
    detail: str | None = None


def require_capture_boundary(request: Request) -> None:
    """Every non-credential gate, applied before any capture route body runs.

    Ordered cheapest-first, and each one fails closed on its own.
    """
    # 1. Only the canonical UI backend may accept capture. A sibling (the Word HTTPS child with its
    #    auth gate disabled, or the tunnel target) and an undeclared process are all refused. This is
    #    the eligibility rule `reported_instance_role`'s docstring deliberately leaves to the consumer.
    if reported_instance_role() != UI_ROLE:
        raise HTTPException(status_code=403, detail="Browser capture is not available on this Callosum instance.")

    # 2. Host header + forwarded-header validation: a rebound DNS name or a relayed/tunnelled request
    #    is rejected before anything else looks at the payload.
    _require_local(request, "Browser capture is available only on this machine.")

    # 3. Independent rate limit — active regardless of the Remote Access setting.
    if not _limiter.allow("capture"):
        raise HTTPException(
            status_code=429,
            detail="Too many capture requests — slow down.",
            headers={"Retry-After": str(int(CAPTURE_RATE_LIMIT_WINDOW))},
        )


def require_capture_session(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """A live capture session token, plus the non-safelisted action header.

    The token is a bearer credential and is INTENTIONALLY reusable until it expires; preventing a
    duplicate mutation is the idempotency key's job, not this one's. See the audit.
    """
    if request.headers.get(CAPTURE_ACTION_HEADER) != CAPTURE_ACTION_VALUE:
        raise HTTPException(status_code=403, detail="Missing the browser-capture action header.")
    if not pairing.session_is_valid(_bearer(authorization)):
        raise HTTPException(status_code=401, detail="Browser capture requires a valid capture session.")


@router.post("/capture/session", response_model=CaptureSessionResponse)
def open_capture_session(
    payload: CaptureSessionRequest,
    _boundary: None = Depends(require_capture_boundary),
) -> CaptureSessionResponse:
    """Exchange the per-install pairing secret for a short-lived session token (connector host only).

    The pairing secret lives in an owner-only file only a local process can read, so a hostile webpage
    cannot reach this even knowing the port.
    """
    token = pairing.issue_session(payload.pairing_secret)
    if token is None:
        raise HTTPException(status_code=401, detail="Capture pairing failed.")
    return CaptureSessionResponse(session_token=token, expires_in_s=pairing.SESSION_TTL_S)


@router.post("/capture/item", response_model=CaptureResult)
async def capture_item(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    engine: Engine = Depends(get_engine),
    _boundary: None = Depends(require_capture_boundary),
    _session: None = Depends(require_capture_session),
) -> CaptureResult:
    """Admit one captured page. Metadata only — bytes, if any, follow on the PDF route."""
    if idempotency_key and len(idempotency_key) > idempotency.IDEMPOTENCY_KEY_MAX_LEN:
        raise HTTPException(status_code=422, detail="Idempotency-Key is too long.")
    remembered = idempotency.remembered(idempotency_key)
    if remembered is not None:
        return CaptureResult(**remembered)  # a retry after a lost response replays, never re-mutates

    raw = await _read_bounded_body(request, MAX_CAPTURE_BODY_BYTES, "capture envelope")
    try:
        envelope = CaptureEnvelope.model_validate_json(raw)
    except ValidationError as exc:
        # The count, never the messages: validation errors echo submitted values, and an ordinary user
        # gets stable text rather than a parser dump.
        raise HTTPException(
            status_code=422, detail=f"Capture envelope is not valid: {exc.error_count()} problem(s)"
        ) from None
    except ValueError:
        raise HTTPException(status_code=422, detail="Capture envelope is not valid JSON.") from None

    # Fall back to a default CrossrefClient when app.state has none (it is only set when injected —
    # e.g. in tests); mirrors acquisition.py's add_paper_by_doi_endpoint and paper_enrich._crossref.
    # Without this, the running app's app.state.crossref_client is None and every DOI-bearing capture
    # reports "unresolved_review_required" even though Crossref is reachable -- confirmed via a real
    # Edge click-through acceptance run against a real DOI on a real page: metadata extraction and
    # native-messaging both worked, but admission always fell straight into the no-resolver path.
    crossref_client = request.app.state.crossref_client or CrossrefClient()
    outcome: AdmissionOutcome = run_write(engine, lambda conn: admit(conn, envelope, crossref_client=crossref_client))

    # Post-admission indexing invariant: a captured paper is searchable like any other admission, and
    # an embedding failure never fails an honest metadata import.
    if outcome.created and outcome.paper_id is not None:
        ensure_paper_indexed(
            engine,
            outcome.paper_id,
            model=_embedding_model(request.app),
            vector_store=_vector_store(request.app),
        )

    capture_id: str | None = None
    if outcome.pdf_accepted and outcome.paper_id is not None:
        capture_id = uuid4().hex
        _remember_pending(capture_id, _PendingCapture(outcome.paper_id, outcome.created, outcome.status))

    result = CaptureResult(capture_id=capture_id, **outcome.as_dict())
    idempotency.remember(idempotency_key, result.model_dump())
    return result


@router.post("/capture/item/{capture_id}/pdf", response_model=CaptureResult)
async def capture_pdf(
    capture_id: str,
    request: Request,
    engine: Engine = Depends(get_engine),
    _boundary: None = Depends(require_capture_boundary),
    _session: None = Depends(require_capture_session),
) -> CaptureResult:
    """Attach bytes the user had already opened in the active tab, to the paper just admitted.

    Validation mirrors the registration-upload path exactly: declared-length precheck, a cap enforced
    mid-stream (so a lying Content-Length does not help), ``%PDF-`` magic, and a real PyMuPDF parse
    with at least one page. The temp file is removed on every exit path.

    Eligibility was already decided at ``/capture/item``; this route only honors it. Re-posting for a
    capture that already attached replays the outcome rather than attaching twice.
    """
    pending = _pending.get(capture_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="Unknown or expired capture.")
    if pending.attached:
        return CaptureResult(
            status=pending.status,
            capture_id=capture_id,
            paper_id=pending.paper_id,
            created=pending.created,
            pdf_accepted=True,
            pdf_reason=PDF_OK,
        )

    temp_path = Path(tempfile.gettempdir()) / f"callosum-capture-{uuid4().hex}.pdf"
    try:
        total = await _stream_to_file(request, temp_path, MAX_OA_PDF_BYTES, "Captured PDF")
        # Validate from BYTES, never by handing PyMuPDF the path — the same way `download_oa_pdf`
        # does it. On Windows, `fitz.open(path)` on a malformed file leaves the OS handle open even
        # though the call raises, so the `finally` cleanup below then dies with PermissionError and
        # leaks the temp file. Reading is bounded by the same cap the transfer already enforced.
        # Found by `test_pdf_upload_rejects_a_malformed_pdf`.
        data = temp_path.read_bytes()
        if total < 5 or not data.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="The captured bytes are not a PDF.")
        try:
            document = fitz.open(stream=data, filetype="pdf")
            page_count = document.page_count
            document.close()
        except Exception:
            raise HTTPException(status_code=422, detail="The captured PDF could not be opened.") from None
        if page_count < 1:
            raise HTTPException(status_code=422, detail="The captured PDF has no pages.")

        managed_root = library_dir()
        managed_root.mkdir(parents=True, exist_ok=True)
        managed_path = managed_root / f"capture-{capture_id}.pdf"  # name from OUR id, never client input
        import shutil

        shutil.move(str(temp_path), str(managed_path))
        try:
            run_write(
                engine,
                lambda conn: attach_pdf_to_paper(
                    conn,
                    pending.paper_id,
                    managed_path,
                    storage_mode="managed",
                    original_path=str(managed_path),
                    import_source=CAPTURE_SOURCE,
                    vector_store=_vector_store(request.app),
                    embedding_model=_embedding_model(request.app),
                ),
            )
        except Exception:
            managed_path.unlink(missing_ok=True)
            raise
        pending.attached = True
        return CaptureResult(
            status=pending.status,
            capture_id=capture_id,
            paper_id=pending.paper_id,
            created=pending.created,
            pdf_accepted=True,
            pdf_reason=PDF_OK,
        )
    finally:
        temp_path.unlink(missing_ok=True)


async def _read_bounded_body(request: Request, cap: int, label: str) -> bytes:
    """Read a request body with a hard cap, refusing oversize BEFORE parsing.

    Content-Length is only a hint — it can be absent (chunked) or simply wrong — so the running total
    is what actually enforces the bound. The cheap declared-length check just rejects earlier.
    """
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > cap:
                raise HTTPException(status_code=413, detail=f"The {label} is too large.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from None
    chunks: list[bytes] = []
    total = 0
    async for block in request.stream():
        total += len(block)
        if total > cap:
            raise HTTPException(status_code=413, detail=f"The {label} is too large.")
        chunks.append(block)
    return b"".join(chunks)


async def _stream_to_file(request: Request, path: Path, cap: int, label: str) -> int:
    """Stream a request body to disk under a hard cap. Returns the byte count."""
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > cap:
                raise HTTPException(status_code=413, detail=f"{label} exceeds the {cap // (1024 * 1024)} MiB limit.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from None
    total = 0
    with path.open("wb") as handle:
        async for block in request.stream():
            total += len(block)
            if total > cap:
                raise HTTPException(status_code=413, detail=f"{label} exceeds the {cap // (1024 * 1024)} MiB limit.")
            handle.write(block)
    return total


def _remember_pending(capture_id: str, pending: _PendingCapture) -> None:
    if len(_pending) >= MAX_PENDING_CAPTURES:
        _pending.pop(next(iter(_pending)), None)  # bounded; the evicted capture simply cannot attach
    _pending[capture_id] = pending


def _reset_for_tests() -> None:
    """Drop in-process capture state (sessions, idempotency, pending, rate limit). Tests only."""
    _pending.clear()
    pairing.clear_sessions()
    idempotency.clear()
    _limiter.reset()
