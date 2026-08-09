"""Save/list/delete per-paper DEBIT checks (inc 467). Mirrors methods_grim_saved.py's shape exactly.

The existing `POST /methods/debit` calculator (`methods.py`) is untouched — it stays a pure, stateless
computation. This adds a small append-only per-paper log alongside it, importing `methods.py`'s DEBIT
response models directly (the `paper_enrich.py`/`_detail_for` precedent, also used by
methods_grim_saved.py).

Principles-gate note (rule #9): the save endpoint takes only the RAW reported inputs (mean/sd/n) and
recomputes `debit_test` itself, server-side, identically to `POST /methods/debit` — a saved record can
never drift from what the deterministic function actually returns for those inputs. The frontend's
already-computed verdict is never trusted or persisted verbatim; the deterministic substrate stays the
source of truth (never a client-asserted fact).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.routers.methods import DebitComputeResponse, DebitResultModel
from app.backend.api.routers.papers import _iso_or_none
from app.backend.methods.grim import debit_test
from app.backend.persistence.debit_checks_repo import add_debit_check, delete_debit_check, list_debit_checks
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()


class DebitCheckSaveRequest(BaseModel):
    mean: str
    sd: str
    n: int
    label: str | None = Field(default=None, max_length=120)


class DebitCheckRecord(BaseModel):
    id: int
    label: str | None = None
    mean: str
    sd: str
    n: int
    debit: DebitResultModel
    created_at: str | None = None


class DebitCheckListResponse(BaseModel):
    checks: list[DebitCheckRecord]


def _record(row) -> DebitCheckRecord:
    payload = row["result_json"]
    return DebitCheckRecord(
        id=row["id"],
        label=row["label"],
        mean=row["mean"],
        sd=row["sd"],
        n=row["n"],
        debit=DebitResultModel(**payload["debit"]),
        created_at=_iso_or_none(row["created_at"]),
    )


@router.get("/papers/{paper_id}/debit-checks", response_model=DebitCheckListResponse)
def list_saved_debit_checks(paper_id: int, conn: Connection = Depends(get_connection)) -> DebitCheckListResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    return DebitCheckListResponse(checks=[_record(r) for r in list_debit_checks(conn, paper_id)])


@router.post(
    "/papers/{paper_id}/debit-checks", response_model=DebitCheckRecord, status_code=http_status.HTTP_201_CREATED
)
def save_debit_check(
    paper_id: int, payload: DebitCheckSaveRequest, engine: Engine = Depends(get_engine)
) -> DebitCheckRecord:
    def _do(conn: Connection) -> DebitCheckRecord:
        try:
            debit = debit_test(payload.mean, payload.sd, payload.n)
        except (ValueError, ArithmeticError):
            raise HTTPException(
                status_code=422,
                detail="Invalid DEBIT inputs: mean/SD must be numbers; n must be at least 2.",
            ) from None
        result = DebitComputeResponse(debit=DebitResultModel(**vars(debit)))
        check_id = add_debit_check(
            conn,
            paper_id,
            label=payload.label,
            mean=payload.mean.strip(),
            sd=payload.sd.strip(),
            n=payload.n,
            result_json=result.model_dump(),
        )
        if check_id is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        row = next(r for r in list_debit_checks(conn, paper_id) if int(r["id"]) == check_id)
        return _record(row)

    return run_write(engine, _do)


@router.delete("/papers/{paper_id}/debit-checks/{check_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_saved_debit_check(paper_id: int, check_id: int, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        if not delete_debit_check(conn, paper_id, check_id):
            raise HTTPException(status_code=404, detail="Saved check not found")
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)
