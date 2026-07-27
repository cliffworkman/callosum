"""Save/list/delete per-paper GRIM/GRIMMER checks (inc 401).

The existing `POST /methods/grim` calculator (`methods.py`) is untouched — it stays a pure, stateless
computation. This adds a small append-only per-paper log alongside it, importing `methods.py`'s
GRIM response models directly (the `paper_enrich.py`/`_detail_for` precedent).

Principles-gate note (rule #9): the save endpoint takes only the RAW reported inputs (mean/sd/n/items)
and recomputes `grim_test`/`grimmer_test` itself, server-side, identically to `POST /methods/grim` — a
saved record can never drift from what the deterministic function actually returns for those inputs.
The frontend's already-computed verdict is never trusted or persisted verbatim; the deterministic
substrate stays the source of truth (never a client-asserted fact).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.routers.methods import GrimComputeResponse, GrimmerResultModel, GrimResultModel
from app.backend.api.routers.papers import _iso_or_none
from app.backend.methods.grim import grim_test, grimmer_test
from app.backend.persistence.grim_checks_repo import add_grim_check, delete_grim_check, list_grim_checks
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()


class GrimCheckSaveRequest(BaseModel):
    mean: str
    sd: str | None = None
    n: int
    items: int = 1
    label: str | None = Field(default=None, max_length=120)


class GrimCheckRecord(BaseModel):
    id: int
    label: str | None = None
    mean: str
    sd: str | None = None
    n: int
    items: int
    grim: GrimResultModel
    grimmer: GrimmerResultModel | None = None
    created_at: str | None = None


class GrimCheckListResponse(BaseModel):
    checks: list[GrimCheckRecord]


def _record(row) -> GrimCheckRecord:
    payload = row["result_json"]
    return GrimCheckRecord(
        id=row["id"],
        label=row["label"],
        mean=row["mean"],
        sd=row["sd"],
        n=row["n"],
        items=row["items"],
        grim=GrimResultModel(**payload["grim"]),
        grimmer=GrimmerResultModel(**payload["grimmer"]) if payload.get("grimmer") else None,
        created_at=_iso_or_none(row["created_at"]),
    )


@router.get("/papers/{paper_id}/grim-checks", response_model=GrimCheckListResponse)
def list_saved_grim_checks(paper_id: int, conn: Connection = Depends(get_connection)) -> GrimCheckListResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    return GrimCheckListResponse(checks=[_record(r) for r in list_grim_checks(conn, paper_id)])


@router.post("/papers/{paper_id}/grim-checks", response_model=GrimCheckRecord, status_code=http_status.HTTP_201_CREATED)
def save_grim_check(
    paper_id: int, payload: GrimCheckSaveRequest, engine: Engine = Depends(get_engine)
) -> GrimCheckRecord:
    def _do(conn: Connection) -> GrimCheckRecord:
        try:
            grim = grim_test(payload.mean, payload.n, payload.items)
            grimmer = grimmer_test(payload.mean, payload.sd, payload.n, payload.items) if payload.sd else None
        except (ValueError, ArithmeticError):
            raise HTTPException(
                status_code=422,
                detail="Invalid GRIM inputs: mean/SD must be numbers; n and items must be positive.",
            ) from None
        result = GrimComputeResponse(
            grim=GrimResultModel(**vars(grim)),
            grimmer=GrimmerResultModel(**vars(grimmer)) if grimmer else None,
        )
        check_id = add_grim_check(
            conn,
            paper_id,
            label=payload.label,
            mean=payload.mean.strip(),
            sd=payload.sd.strip() if payload.sd else None,
            n=payload.n,
            items=payload.items,
            result_json=result.model_dump(),
        )
        if check_id is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        row = next(r for r in list_grim_checks(conn, paper_id) if int(r["id"]) == check_id)
        return _record(row)

    return run_write(engine, _do)


@router.delete("/papers/{paper_id}/grim-checks/{check_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_saved_grim_check(paper_id: int, check_id: int, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        if not delete_grim_check(conn, paper_id, check_id):
            raise HTTPException(status_code=404, detail="Saved check not found")
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)
