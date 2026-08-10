"""The opt-in sync surface (accounts SP3b) — the minimal local endpoints that make E2E sync usable: set up a vault,
toggle it on, check status, and run a sync against the reference server. Default-OFF; every precondition fails closed.

This is the egress door (the inc-198 engine pushes opaque ciphertext to the sync-server here), so it is gated:
``/sync/run`` refuses unless sync is **enabled** AND **configured** (a keyring exists) AND **signed in** (an Authentik
session, SP1) AND a **server URL** is set — and the DEK is unlocked from the passphrase **per run** (never persisted
in memory). The rich Settings → Sync UI + conflict-review screen is SP3c; this is its backend.
"""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection
from sqlalchemy.exc import OperationalError

from app.backend import app_settings as settings
from app.backend.api.auth import oidc as oidc_mod
from app.backend.api.dependencies import get_connection
from app.backend.persistence import sync_conflicts_repo
from app.backend.persistence.sqlite_retry import is_sqlite_locked, run_write
from app.backend.sync.changeset import SYNCABLE, collect_local
from app.backend.sync.crypto import SyncCryptoError, SyncKeyring, create_keyring, unlock_with_passphrase
from app.backend.sync.engine import run_sync
from app.backend.sync.identity import ShareIdentity, create_identity
from app.backend.sync.identity import fingerprint as identity_fingerprint
from app.backend.sync.transport import HttpSyncTransport, SyncServerError

router = APIRouter()  # full /sync/* paths per the house convention (the QA surface extractor reads literal paths)
logger = logging.getLogger("callosum")

_REFRESH_MARGIN_SECONDS = 30  # refresh a little before actual expiry, not exactly at the edge


def _access_token() -> str | None:
    return (settings.stored_oauth_session() or {}).get("access_token")


def _fresh_access_token(request: Request) -> str | None:
    """The stored access token, refreshed first via the stored refresh_token if it's near/past expiry — Authentik's
    access tokens are short-lived, and a sync run can easily happen well after the original sign-in. Falls back to
    whatever's stored on any refresh problem; sync_run's existing 401->502 handling is the fail-closed backstop."""
    session = settings.stored_oauth_session()
    if not session or not session.get("access_token"):
        return None
    expires_at, refresh_token = session.get("expires_at"), session.get("refresh_token")
    if not refresh_token or expires_at is None or expires_at > time.time() + _REFRESH_MARGIN_SECONDS:
        logger.info(
            "sync: skipping token refresh (expires_at=%s, now=%s, has_refresh_token=%s)",
            expires_at,
            int(time.time()),
            bool(refresh_token),
        )
        return session["access_token"]  # still comfortably valid, or nothing/no way to refresh
    client = getattr(request.app.state, "oidc_client", None)
    if client is None:
        logger.warning("sync: near-expiry token but no oidc_client available to refresh it")
        return session["access_token"]
    try:
        tokens = client.refresh_access_token(refresh_token)
    except oidc_mod.OidcError as exc:
        logger.warning("sync: token refresh failed, falling back to the stale token: %s", exc)
        return session["access_token"]
    logger.info("sync: token refreshed successfully")
    session = {**session, **{k: tokens[k] for k in ("access_token", "refresh_token", "id_token") if k in tokens}}
    if "expires_in" in tokens:
        session["expires_at"] = int(time.time()) + int(tokens["expires_in"])
    settings.set_oauth_session(session)
    return session["access_token"]


class SyncStatus(BaseModel):
    enabled: bool
    configured: bool  # a keyring exists (setup done)
    signed_in: bool
    server_url: str | None
    last_cursor: int


def _status() -> SyncStatus:
    cfg = settings.stored_sync_settings()
    return SyncStatus(
        enabled=cfg["enabled"],
        configured=settings.sync_configured(),
        signed_in=bool(_access_token()),
        server_url=cfg["server_url"],
        last_cursor=settings.stored_sync_cursor(),
    )


@router.get("/sync/status", response_model=SyncStatus)
def sync_status() -> SyncStatus:
    return _status()


class SyncSettingsBody(BaseModel):
    enabled: bool
    server_url: str | None = Field(default=None, max_length=2000)


@router.put("/sync/settings", response_model=SyncStatus)
def put_sync_settings(body: SyncSettingsBody) -> SyncStatus:
    if body.enabled:  # lockout-safe: can't enable a half-configured sync (mirrors the inc-168 remote-access toggle)
        if not settings.sync_configured():
            raise HTTPException(status_code=422, detail="set up sync (choose a passphrase) before enabling")
        if not _access_token():
            raise HTTPException(status_code=422, detail="sign in before enabling sync")
        if not (body.server_url or "").strip():
            raise HTTPException(status_code=422, detail="a sync server URL is required to enable")
    settings.set_sync_settings(enabled=body.enabled, server_url=body.server_url)
    return _status()


class SetupBody(BaseModel):
    passphrase: str = Field(min_length=1, max_length=1024)


class SetupResult(BaseModel):
    recovery_code: str  # shown ONCE — never returned by /status


@router.post("/sync/setup", response_model=SetupResult)
def sync_setup(body: SetupBody) -> SetupResult:
    if settings.sync_configured():
        raise HTTPException(status_code=409, detail="sync is already set up")  # don't silently re-key existing data
    try:
        keyring, recovery = create_keyring(body.passphrase)
    except SyncCryptoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    settings.set_sync_keyring(keyring.to_dict())
    return SetupResult(recovery_code=recovery)


class RunBody(BaseModel):
    passphrase: str = Field(min_length=1, max_length=1024)


class RunResult(BaseModel):
    pushed: int
    applied: int
    conflicts: int
    cursor: int


@router.post("/sync/run", response_model=RunResult)
def sync_run(request: Request, body: RunBody, conn: Connection = Depends(get_connection)) -> RunResult:
    cfg = settings.stored_sync_settings()
    keyring = settings.stored_sync_keyring()
    token = _fresh_access_token(request)
    if not cfg["enabled"]:
        raise HTTPException(status_code=409, detail="sync is off")
    if keyring is None:
        raise HTTPException(status_code=409, detail="sync is not set up")
    if not token:
        raise HTTPException(status_code=409, detail="sign in to sync")
    if not cfg["server_url"]:
        raise HTTPException(status_code=409, detail="no sync server URL is set")
    try:
        dek = unlock_with_passphrase(SyncKeyring.from_dict(keyring), body.passphrase)
    except SyncCryptoError as exc:
        # 422 (not 401), matching sync_setup's own SyncCryptoError handling above: every api* fetch helper in the
        # frontend treats ANY 401 as "the remote-access bearer token is invalid" and fires the app-wide
        # AccessLockOverlay lockout-recovery flow (inc 254) — a wrong LOCAL sync passphrase is a different kind of
        # failure entirely and must not trip that unrelated global recovery UI.
        raise HTTPException(status_code=422, detail="wrong passphrase") from exc
    # an injected transport (tests bind one to the in-process server) wins; else build one per run
    transport = getattr(request.app.state, "sync_transport", None) or HttpSyncTransport(cfg["server_url"], token)
    try:
        result = run_sync(conn, dek, transport, since=settings.stored_sync_cursor())
        conn.commit()  # the dependency uses engine.connect(); a sync-server error before here → rollback (no half-apply)
    except SyncServerError as exc:
        raise HTTPException(status_code=502, detail=f"sync server error: {exc}") from exc
    except OperationalError as exc:
        # A short, local SQLite write-lock collision (e.g. a concurrent watched-folder rescan holding the writer
        # lock) — deliberately NOT auto-retried here (unlike the run_write short-write sweep, inc 281): retrying
        # a mixed local+egress run risks re-pushing to the sync server. Give an honest, actionable message instead
        # of letting a raw 500/traceback surface — the user's own retry (a fresh /sync/run) is the safe recovery.
        if is_sqlite_locked(exc):
            raise HTTPException(
                status_code=503,
                detail="Sync couldn't get a database write lock just now (another operation is "
                "writing) — try running sync again in a moment.",
            ) from exc
        raise
    finally:
        transport.close()
    settings.set_sync_cursor(result.new_cursor)
    return RunResult(pushed=result.pushed, applied=result.applied, conflicts=result.conflicts, cursor=result.new_cursor)


# --- SP4a (backlog #15): sharing identity — a per-account keypair + a server-side public-key directory. No
# record is shared here (SP4b+ add the actual share); this only makes "who is this collaborator,
# cryptographically" answerable. Registering/looking up rides the SAME egress gate as a sync run — real network
# egress to the sync server, never bypassing it — plus its own explicit setup action (the passphrase entry
# below), since sharing your identity is a materially different consent event than syncing your own devices.


def _require_egress_ready(cfg: dict, token: str | None) -> None:
    if not cfg["enabled"]:
        raise HTTPException(status_code=409, detail="sync is off")
    if not settings.sync_configured():
        raise HTTPException(status_code=409, detail="sync is not set up")
    if not token:
        raise HTTPException(status_code=409, detail="sign in to sync")
    if not cfg["server_url"]:
        raise HTTPException(status_code=409, detail="no sync server URL is set")


class IdentityStatus(BaseModel):
    has_identity: bool
    fingerprint: str | None
    own_sub: str | None


@router.get("/sync/identity/status", response_model=IdentityStatus)
def sync_identity_status() -> IdentityStatus:
    stored = settings.stored_share_identity()
    own_sub = (settings.stored_oauth_session() or {}).get("sub")
    if stored is None:
        return IdentityStatus(has_identity=False, fingerprint=None, own_sub=own_sub)
    identity = ShareIdentity.from_dict(stored)
    return IdentityStatus(has_identity=True, fingerprint=identity_fingerprint(identity.public_key), own_sub=own_sub)


class IdentitySetupBody(BaseModel):
    passphrase: str = Field(min_length=1, max_length=1024)


class IdentitySetupResult(BaseModel):
    fingerprint: str
    own_sub: str | None


@router.post("/sync/identity/setup", response_model=IdentitySetupResult)
def sync_identity_setup(request: Request, body: IdentitySetupBody) -> IdentitySetupResult:
    if settings.stored_share_identity() is not None:
        raise HTTPException(status_code=409, detail="a sharing identity is already set up")  # no silent re-key
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
    identity = create_identity(dek)
    encoded = identity.to_dict()
    own = settings.stored_oauth_session() or {}
    transport = getattr(request.app.state, "sync_transport", None) or HttpSyncTransport(cfg["server_url"], token)
    try:
        transport.register_identity(encoded["public_key"], own.get("display_name"))
    except SyncServerError as exc:
        raise HTTPException(status_code=502, detail=f"sync server error: {exc}") from exc
    finally:
        transport.close()
    settings.set_share_identity(encoded)  # only stored locally once the server registration actually succeeded
    return IdentitySetupResult(fingerprint=identity_fingerprint(identity.public_key), own_sub=own.get("sub"))


class IdentityLookupResult(BaseModel):
    public_key: str
    display_name: str | None
    fingerprint: str


@router.get("/sync/identity/lookup", response_model=IdentityLookupResult)
def sync_identity_lookup(request: Request, sub: str = Query(..., max_length=255)) -> IdentityLookupResult:
    """A thin authenticated proxy to the sync-server's own exact-id-only `/identity/lookup` -- the frontend
    never talks to `sync_server` directly (matching every other sync surface). The fingerprint is computed
    LOCALLY from the raw key bytes, never trusted as a value the server itself asserts."""
    cfg = settings.stored_sync_settings()
    token = _fresh_access_token(request)
    _require_egress_ready(cfg, token)
    transport = getattr(request.app.state, "sync_transport", None) or HttpSyncTransport(cfg["server_url"], token)
    try:
        result = transport.lookup_identity(sub)
    except SyncServerError as exc:
        raise HTTPException(status_code=502, detail=f"sync server error: {exc}") from exc
    finally:
        transport.close()
    if result is None:
        raise HTTPException(status_code=404, detail="no sharing identity registered for that id")
    try:
        fp = identity_fingerprint(base64.b64decode(result["public_key"]))
    except (SyncCryptoError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail=f"sync server returned a malformed identity: {exc}") from exc
    return IdentityLookupResult(
        public_key=result["public_key"], display_name=result.get("display_name"), fingerprint=fp
    )


# --- SP3c: conflict review (read `sync_conflicts`, pick a side) ------------------------------------------------
# Deliberately NOT gated on enabled/signed-in/configured — a conflict is local data from a past sync run; the user
# can review and resolve one whether or not sync happens to be on right now.


class ConflictOut(BaseModel):
    id: int
    collection: str
    record_id: str
    losing_version: int | None
    losing_payload: dict | None  # "mine" — the local side that lost the last-write-wins merge
    detected_at: datetime
    current: dict | None  # "theirs" — the live domain value, for a mine-vs-current diff (None if since deleted)


@router.get("/sync/conflicts", response_model=list[ConflictOut])
def list_sync_conflicts(conn: Connection = Depends(get_connection)) -> list[ConflictOut]:
    rows = sync_conflicts_repo.list_unresolved_conflicts(conn)
    by_name = {c.name: c for c in SYNCABLE}
    current_by_collection: dict[str, dict] = {}
    out: list[ConflictOut] = []
    for row in rows:
        coll = row["collection"]
        if coll not in current_by_collection:
            c = by_name.get(coll)
            current_by_collection[coll] = collect_local(conn, (c,)) if c is not None else {}
        current = current_by_collection[coll].get((coll, row["record_id"]))
        out.append(ConflictOut(**row, current=current))
    return out


class ResolveConflictBody(BaseModel):
    side: Literal["mine", "theirs"]


@router.post("/sync/conflicts/{conflict_id}/resolve")
def resolve_sync_conflict(conflict_id: int, body: ResolveConflictBody, request: Request) -> dict:
    def op(c: Connection) -> None:
        if not sync_conflicts_repo.resolve_conflict(c, conflict_id, body.side):
            # un-retried (HTTPException propagates immediately, run_write only retries a lock error) — and
            # nothing was written yet: resolve_conflict's False-paths are read-checks, no execute() before them.
            raise HTTPException(status_code=409, detail="conflict not found, already resolved, or could not be applied")

    run_write(request.app.state.engine, op)  # a short local write — inc 281's run_write sweep, not a raw commit
    return {"resolved": True}
