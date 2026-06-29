"""The opt-in sync surface (accounts SP3b) — the minimal local endpoints that make E2E sync usable: set up a vault,
toggle it on, check status, and run a sync against the reference server. Default-OFF; every precondition fails closed.

This is the egress door (the inc-198 engine pushes opaque ciphertext to the sync-server here), so it is gated:
``/sync/run`` refuses unless sync is **enabled** AND **configured** (a keyring exists) AND **signed in** (an Authentik
session, SP1) AND a **server URL** is set — and the DEK is unlocked from the passphrase **per run** (never persisted
in memory). The rich Settings → Sync UI + conflict-review screen is SP3c; this is its backend.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend import app_settings as settings
from app.backend.api.dependencies import get_connection
from app.backend.sync.crypto import SyncCryptoError, SyncKeyring, create_keyring, unlock_with_passphrase
from app.backend.sync.engine import run_sync
from app.backend.sync.transport import HttpSyncTransport, SyncServerError

router = APIRouter()  # full /sync/* paths per the house convention (the QA surface extractor reads literal paths)


def _access_token() -> str | None:
    return (settings.stored_oauth_session() or {}).get("access_token")


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
    token = _access_token()
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
        raise HTTPException(status_code=401, detail="wrong passphrase") from exc
    # an injected transport (tests bind one to the in-process server) wins; else build one per run
    transport = getattr(request.app.state, "sync_transport", None) or HttpSyncTransport(cfg["server_url"], token)
    try:
        result = run_sync(conn, dek, transport, since=settings.stored_sync_cursor())
        conn.commit()  # the dependency uses engine.connect(); a sync-server error before here → rollback (no half-apply)
    except SyncServerError as exc:
        raise HTTPException(status_code=502, detail=f"sync server error: {exc}") from exc
    finally:
        transport.close()
    settings.set_sync_cursor(result.new_cursor)
    return RunResult(pushed=result.pushed, applied=result.applied, conflicts=result.conflicts, cursor=result.new_cursor)
