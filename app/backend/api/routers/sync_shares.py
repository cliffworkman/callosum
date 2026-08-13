"""SP4c (backlog #15): receive — list shares addressed to me, decrypt one with my own SP4a identity's private
key, and merge it via the already-audited B2 `import_bundle()` (unmodified except for a new `source=` kwarg
so a share-imported paper is stamped ``imported_source="share-import"``, not the file-bundle's own value).
Split from `sync.py` (which was already at a real size before this) rather than grown in place — mirrors the
`paper_enrich.py`/`methods_retraction.py` sibling-router precedent, sharing `sync.py`'s private gate helpers
via direct import (the same cross-sibling-router pattern `paper_enrich.py` already uses for `papers.py`'s
`_detail_for`) — no duplicated gating logic.

Listing needs no passphrase (sender + timestamp only, never content). Decrypting a specific share is one
explicit passphrase-gated action per share — the same "no silent/automatic ingestion" discipline
`POST /library/bundle/import` already upholds; this is that same import path, just fed by a decrypted share
instead of an uploaded file. Dismissing is local-only bookkeeping and never touches ciphertext or a passphrase.

Recipient-side trust: a listed share's `sender_sub` is the OIDC subject SP4a's fingerprint dance never itself
verifies to the *recipient* (only to the sender, when addressing a share). The honest, minimal answer is to
show `sender_sub` plainly and let the UI link to the existing Settings → Sync fingerprint-lookup tool — no new
verification mechanism, no allow-list (that's SP4d's "roles" territory).
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend import app_settings as settings
from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import (
    BundleImportSummary,
    JobProgressOut,
    _embedding_model,
    _progress_out,
    _vector_store,
)
from app.backend.api.routers.sync import _fresh_access_token, _require_egress_ready
from app.backend.embeddings.pipeline import embed_papers
from app.backend.metadata.library_bundle import BundleError, import_bundle, parse_bundle
from app.backend.persistence import received_shares_repo
from app.backend.persistence.repository import titles_for_ids
from app.backend.persistence.sqlite_retry import commit_each, run_write
from app.backend.sync.crypto import SyncCryptoError, SyncKeyring, decrypt_payload, unlock_with_passphrase
from app.backend.sync.identity import ShareIdentity, unlock_private_key
from app.backend.sync.sharing import WrappedKey, unwrap_content_key
from app.backend.sync.transport import HttpSyncTransport, ShareForbiddenError, SyncServerError

router = APIRouter()
logger = logging.getLogger("callosum")

SHARE_IMPORT_SOURCE = (
    "share-import"  # a distinct app_settings.imported_source, parallel to library_bundle.BUNDLE_SOURCE
)


class SharedShareOut(BaseModel):
    id: int
    sender_sub: str
    created_at: str
    status: str | None  # None = pending (not yet acted on); else "imported" | "dismissed"


@router.get("/sync/shares", response_model=list[SharedShareOut])
def list_shares(request: Request, conn: Connection = Depends(get_connection)) -> list[SharedShareOut]:
    if not settings.stored_share_identity():
        raise HTTPException(status_code=409, detail="set up your sharing identity before viewing shares")
    cfg = settings.stored_sync_settings()
    token = _fresh_access_token(request)
    _require_egress_ready(cfg, token)
    transport = getattr(request.app.state, "sync_transport", None) or HttpSyncTransport(cfg["server_url"], token)
    try:
        rows = transport.list_shares()
    except SyncServerError as exc:
        raise HTTPException(status_code=502, detail=f"sync server error: {exc}") from exc
    finally:
        transport.close()
    statuses = received_shares_repo.status_for_share_ids(conn, [r["id"] for r in rows])
    return [
        SharedShareOut(
            id=r["id"], sender_sub=r["sender_sub"], created_at=str(r["created_at"]), status=statuses.get(r["id"])
        )
        for r in rows
    ]


class DismissResult(BaseModel):
    dismissed: bool


@router.post("/sync/shares/{share_id}/dismiss", response_model=DismissResult)
def dismiss_share(share_id: int, request: Request) -> DismissResult:
    """Local-only bookkeeping — never touches ciphertext or asks for a passphrase. We still need to know who
    sent it for the provenance log, so this is looked up the same way `list_shares` above does (no egress
    beyond that one read, no decrypt)."""
    if not settings.stored_share_identity():
        raise HTTPException(status_code=409, detail="set up your sharing identity first")
    cfg = settings.stored_sync_settings()
    token = _fresh_access_token(request)
    _require_egress_ready(cfg, token)
    transport = getattr(request.app.state, "sync_transport", None) or HttpSyncTransport(cfg["server_url"], token)
    try:
        rows = transport.list_shares()
    except SyncServerError as exc:
        raise HTTPException(status_code=502, detail=f"sync server error: {exc}") from exc
    finally:
        transport.close()
    match = next((r for r in rows if r["id"] == share_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="no such share in your inbox")

    def op(c: Connection) -> None:
        received_shares_repo.record_dismissal(c, share_id=share_id, sender_sub=match["sender_sub"])

    try:
        run_write(request.app.state.engine, op)
    except Exception as exc:  # a duplicate dismiss/import (unique share_id) — already handled, not fatal
        logger.info("sync: dismiss for share %s no-op (%s)", share_id, exc)
    return DismissResult(dismissed=True)


class ShareImportBody(BaseModel):
    passphrase: str = Field(min_length=1, max_length=1024)


class ShareImportJobResponse(BaseModel):
    job_id: str
    status: str
    detail: str | None = None
    summary: BundleImportSummary | None = None
    progress: JobProgressOut | None = None


@router.post("/sync/shares/{share_id}/import", response_model=ShareImportJobResponse, status_code=202)
def import_share(
    share_id: int, body: ShareImportBody, background_tasks: BackgroundTasks, request: Request
) -> ShareImportJobResponse:
    if not settings.stored_share_identity():
        raise HTTPException(status_code=409, detail="set up your sharing identity before importing")
    cfg = settings.stored_sync_settings()
    token = _fresh_access_token(request)
    _require_egress_ready(cfg, token)
    keyring = settings.stored_sync_keyring()
    if keyring is None:
        raise HTTPException(status_code=409, detail="sync is not set up")
    try:
        dek = unlock_with_passphrase(SyncKeyring.from_dict(keyring), body.passphrase)
    except SyncCryptoError as exc:
        raise HTTPException(status_code=422, detail="wrong passphrase") from exc  # 422, not 401 -- see sync_run

    identity = ShareIdentity.from_dict(settings.stored_share_identity())
    own_private_key = unlock_private_key(dek, identity)  # my own identity's key, sealed under the SAME dek above

    transport = getattr(request.app.state, "sync_transport", None) or HttpSyncTransport(cfg["server_url"], token)
    try:
        try:
            row = transport.get_share(share_id)
        except ShareForbiddenError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except SyncServerError as exc:
            raise HTTPException(status_code=502, detail=f"sync server error: {exc}") from exc
        if row is None:
            raise HTTPException(status_code=404, detail="no such share")
        own_sub = (settings.stored_oauth_session() or {}).get("sub")
        if row["recipient_sub"] != own_sub:  # defense in depth -- the server already enforces this
            raise HTTPException(status_code=403, detail="this share is not addressed to you")
        try:
            wrapped = WrappedKey.from_dict(json.loads(row["wrapped_key"]))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"malformed share envelope: {exc}") from exc
        try:
            content_key = unwrap_content_key(wrapped, own_private_key)
            bundle_dict = decrypt_payload(content_key, row["ciphertext"])
        except SyncCryptoError as exc:
            raise HTTPException(status_code=502, detail=f"couldn't decrypt this share: {exc}") from exc
        try:
            bundle = parse_bundle(json.dumps(bundle_dict))  # re-runs the same shape/version/size validation
        except BundleError as exc:
            raise HTTPException(status_code=502, detail=f"this share's content is not a valid bundle: {exc}") from exc
    finally:
        transport.close()

    job_id = request.app.state.share_import_jobs.create()
    background_tasks.add_task(_run_share_import_job, request.app, job_id, share_id, row["sender_sub"], bundle)
    return ShareImportJobResponse(job_id=job_id, status="pending")


@router.get("/sync/shares/{share_id}/import/{job_id}", response_model=ShareImportJobResponse)
def share_import_status(share_id: int, job_id: str, request: Request) -> ShareImportJobResponse:
    job = request.app.state.share_import_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Share import job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return ShareImportJobResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


def _run_share_import_job(app, job_id: str, share_id: int, sender_sub: str, bundle: dict) -> None:
    """Near-verbatim copy of `library.py`'s `_run_bundle_import_job` — the only differences are the source is
    an already-decrypted share (not an uploaded file), the distinct `SHARE_IMPORT_SOURCE` provenance value, and
    a `received_shares` row written on success (the cross-user provenance log)."""
    jobs: JobStore[ShareImportJobResponse] = app.state.share_import_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        store = _vector_store(app)
        engine = app.state.engine

        result = run_write(engine, lambda conn: import_bundle(conn, bundle, source=SHARE_IMPORT_SOURCE))
        created = [int(pid) for pid in result["created"]]
        with engine.connect() as titles_conn:
            titles = titles_for_ids(titles_conn, created)
        for index, paper_id in enumerate(created, start=1):
            jobs.mark_progress(job_id, index, len(created), f"Embedding {titles.get(paper_id, 'paper')[:60]}")
            commit_each(
                engine,
                [paper_id],
                lambda conn, pid: embed_papers(conn, model=model, vector_store=store, paper_ids=[pid]),
                on_item_error="skip",
                logger=logger,
            )
        run_write(
            engine,
            lambda conn: received_shares_repo.record_import(
                conn, share_id=share_id, sender_sub=sender_sub, summary=result["summary"]
            ),
        )
        jobs.mark_done(
            job_id,
            ShareImportJobResponse(job_id=job_id, status="done", summary=BundleImportSummary(**result["summary"])),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
