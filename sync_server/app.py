"""The sync-server FastAPI app: two endpoints over the inc-198 ``SyncTransport`` contract, each authenticated by an
Authentik bearer token and scoped to that user. The server stores/serves OPAQUE ciphertext — it never decodes a blob
or holds a DEK.

``create_server(engine, verifier)`` is injectable (a fake verifier + a SQLite engine in tests); the module-level
``app`` is built from env for ``uvicorn sync_server.app:app`` (Postgres + Authentik in prod).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import create_engine

from sync_server.auth import Identity, InvalidToken, TokenVerifier, verifier_from_env
from sync_server.identity_store import lookup_public_key, register_public_key
from sync_server.rate_limit import RateLimiter
from sync_server.schema import ensure_updated_at_column, metadata
from sync_server.share_store import create_share
from sync_server.store import Record, pull, push

MAX_RECORDS_PER_PUSH = 1000
MAX_CIPHERTEXT_LEN = 2_000_000  # ~2 MB — these are small metadata records, not files
MAX_PUBLIC_KEY_LEN = 100  # base64 of a raw 32-byte key is ~44 chars; generous headroom, still tightly bounded
MAX_DISPLAY_NAME_LEN = 200
# SP4b: a share's ciphertext is a whole build_bundle() payload (papers + tags + annotations), so it needs the
# SAME headroom as the local library_bundle.MAX_BUNDLE_BYTES cap (~20 MB) -- duplicated as its own literal
# rather than imported, since sync_server is deliberately fenced from importing app.backend at all (tach.toml).
MAX_SHARE_CIPHERTEXT_LEN = 21_000_000
MAX_WRAPPED_KEY_LEN = 1_000  # a fixed-shape small envelope (two 32-byte fields + a nonce, base64'd), not bulk data

# backlog #15: per-user rate limiting. Generous defaults for a personal/small-team self-host (a device polling
# during active use), tunable via env without a code change. Keyed by ident.sub (see rate_limit.py) — a user's
# requests across every device they sync share one bucket, since the token carries no per-device claim.
RATE_LIMIT_WINDOW_SECONDS = float(os.getenv("CALLOSUM_SYNC_RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("CALLOSUM_SYNC_RATE_LIMIT_MAX", "60"))
# backlog #15: retention. See store.prune_tombstones's docstring for the resurrection trade-off this trades off.
RETENTION_DAYS = int(os.getenv("CALLOSUM_SYNC_RETENTION_DAYS", "90"))


class RecordModel(BaseModel):
    collection: str = Field(max_length=60)
    record_id: str = Field(max_length=200)
    version: int = Field(ge=1)
    deleted: bool = False
    ciphertext: str | None = Field(default=None, max_length=MAX_CIPHERTEXT_LEN)


class PushRequest(BaseModel):
    records: list[RecordModel] = Field(max_length=MAX_RECORDS_PER_PUSH)


class PushResponse(BaseModel):
    seq: int


class PullResponse(BaseModel):
    records: list[RecordModel]
    seq: int


class RegisterIdentityRequest(BaseModel):
    public_key: str = Field(max_length=MAX_PUBLIC_KEY_LEN)
    display_name: str | None = Field(default=None, max_length=MAX_DISPLAY_NAME_LEN)


class IdentityResponse(BaseModel):
    public_key: str
    display_name: str | None


class CreateShareRequest(BaseModel):
    recipient_sub: str = Field(max_length=255)
    wrapped_key: str = Field(max_length=MAX_WRAPPED_KEY_LEN)
    ciphertext: str = Field(max_length=MAX_SHARE_CIPHERTEXT_LEN)


class CreateShareResponse(BaseModel):
    share_id: int


def _identity(request: Request) -> Identity:
    verifier: TokenVerifier | None = request.app.state.verifier
    if verifier is None:  # unconfigured → refuse everything (default-closed)
        raise HTTPException(status_code=503, detail="sync-server not configured")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        return verifier.verify(auth[len("Bearer ") :])
    except InvalidToken as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc


def create_server(engine, verifier: TokenVerifier | None, *, rate_limiter: RateLimiter | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        metadata.create_all(engine)  # v1: create-on-start; a general prod migration TOOL is a separate follow-on
        ensure_updated_at_column(engine)  # one-time defensive ALTER for an already-deployed table (backlog #15)
        yield

    app = FastAPI(title="callosum sync-server", lifespan=lifespan)
    app.state.engine = engine
    app.state.verifier = verifier
    app.state.rate_limiter = rate_limiter or RateLimiter(RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)

    def _rate_limited(request: Request, ident: Identity = Depends(_identity)) -> Identity:
        limiter: RateLimiter = request.app.state.rate_limiter
        if not limiter.allow(ident.sub):
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(limiter.retry_after(ident.sub))},
            )
        return ident

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "configured": verifier is not None}

    @app.get("/sync/records", response_model=PullResponse)
    def get_records(
        request: Request, since: int = Query(0, ge=0), ident: Identity = Depends(_rate_limited)
    ) -> PullResponse:
        with request.app.state.engine.begin() as conn:
            records, seq = pull(conn, ident.sub, since)
        return PullResponse(records=[_to_model(r) for r in records], seq=seq)

    @app.post("/sync/records", response_model=PushResponse)
    def post_records(request: Request, body: PushRequest, ident: Identity = Depends(_rate_limited)) -> PushResponse:
        records = [_to_record(r) for r in body.records]
        with request.app.state.engine.begin() as conn:
            seq = push(conn, ident.sub, records)
        return PushResponse(seq=seq)

    # --- SP4a (backlog #15): the sharing-identity directory. `display_name` is caller-supplied and UX-only —
    # the server never verifies it against anything. Lookup is exact-`sub`-only by design (see
    # identity_store.py's own docstring) — there is no listing/search endpoint here, structurally.

    @app.post("/identity/register", status_code=204)
    def register_identity(
        request: Request, body: RegisterIdentityRequest, ident: Identity = Depends(_rate_limited)
    ) -> None:
        with request.app.state.engine.begin() as conn:
            register_public_key(conn, ident.sub, body.public_key, body.display_name)

    @app.get("/identity/lookup", response_model=IdentityResponse)
    def lookup_identity(
        request: Request, sub: str = Query(..., max_length=255), ident: Identity = Depends(_rate_limited)
    ) -> IdentityResponse:
        with request.app.state.engine.begin() as conn:
            record = lookup_public_key(conn, sub)
        if record is None:
            raise HTTPException(status_code=404, detail="no identity registered for this id")
        return IdentityResponse(public_key=record.public_key, display_name=record.display_name)

    # --- SP4b (backlog #15): create a share. `wrapped_key`/`ciphertext` are opaque to the server -- it
    # relays bytes addressed to `recipient_sub`, nothing more. `sender_sub` comes from the authenticated
    # token, never the request body. There is deliberately no read endpoint here yet (SP4c).

    @app.post("/shares", response_model=CreateShareResponse)
    def post_share(
        request: Request, body: CreateShareRequest, ident: Identity = Depends(_rate_limited)
    ) -> CreateShareResponse:
        with request.app.state.engine.begin() as conn:
            share_id = create_share(
                conn,
                sender_sub=ident.sub,
                recipient_sub=body.recipient_sub,
                wrapped_key=body.wrapped_key,
                ciphertext=body.ciphertext,
            )
        return CreateShareResponse(share_id=share_id)

    return app


def _to_record(m: RecordModel) -> Record:
    return Record(
        collection=m.collection,
        record_id=m.record_id,
        version=m.version,
        deleted=m.deleted,
        ciphertext=None if m.deleted else m.ciphertext,
    )


def _to_model(r: Record) -> RecordModel:
    return RecordModel(
        collection=r.collection,
        record_id=r.record_id,
        version=r.version,
        deleted=r.deleted,
        ciphertext=r.ciphertext,
    )


def _build_from_env() -> FastAPI:
    db_url = os.getenv("CALLOSUM_SYNC_DB_URL", "sqlite:///sync-server.sqlite")
    return create_server(create_engine(db_url), verifier_from_env())


app = _build_from_env()
