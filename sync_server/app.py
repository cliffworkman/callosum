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
from sync_server.schema import metadata
from sync_server.store import Record, pull, push

MAX_RECORDS_PER_PUSH = 1000
MAX_CIPHERTEXT_LEN = 2_000_000  # ~2 MB — these are small metadata records, not files


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


def create_server(engine, verifier: TokenVerifier | None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        metadata.create_all(engine)  # v1: create-on-start; a prod migration is a follow-on
        yield

    app = FastAPI(title="callosum sync-server", lifespan=lifespan)
    app.state.engine = engine
    app.state.verifier = verifier

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "configured": verifier is not None}

    @app.get("/sync/records", response_model=PullResponse)
    def get_records(
        request: Request, since: int = Query(0, ge=0), ident: Identity = Depends(_identity)
    ) -> PullResponse:
        with request.app.state.engine.begin() as conn:
            records, seq = pull(conn, ident.sub, since)
        return PullResponse(records=[_to_model(r) for r in records], seq=seq)

    @app.post("/sync/records", response_model=PushResponse)
    def post_records(request: Request, body: PushRequest, ident: Identity = Depends(_identity)) -> PushResponse:
        records = [_to_record(r) for r in body.records]
        with request.app.state.engine.begin() as conn:
            seq = push(conn, ident.sub, records)
        return PushResponse(seq=seq)

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
