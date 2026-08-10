"""Repeated-values checker: compute + paper-aware save (inc 469). Lives entirely in its own router — unlike
GRIM/DEBIT's calculator endpoints, this doesn't share space in methods.py (already at the 600-line cap by the
time this shipped) — so both `POST /methods/duplicate-values` and the saved-checks CRUD live here together.

Principles-gate note (rule #9): the save endpoint takes only the RAW entered values and recomputes
`count_repeated_values` itself, server-side, identically to the calculator endpoint — a saved record can never
drift from what the deterministic function actually returns, same posture as GRIM/DEBIT's save endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.routers.papers import _iso_or_none
from app.backend.methods.duplicate_values import count_repeated_values
from app.backend.persistence.duplicate_value_checks_repo import (
    add_duplicate_value_check,
    delete_duplicate_value_check,
    list_duplicate_value_checks,
)
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()


class RepeatedValuesRequest(BaseModel):
    values: list[str]


class RepeatedValueEntry(BaseModel):
    value: str
    count: int


class RepeatedValuesResultModel(BaseModel):
    total: int
    distinct: int
    repeats: list[RepeatedValueEntry]
    note: str


class DuplicateValuesComputeResponse(BaseModel):
    duplicate_values: RepeatedValuesResultModel


def _compute(values: list[str]) -> DuplicateValuesComputeResponse:
    try:
        r = count_repeated_values(values)
    except (ValueError, ArithmeticError):
        raise HTTPException(
            status_code=422,
            detail="Invalid input: enter between 1 and 500 non-empty values.",
        ) from None
    return DuplicateValuesComputeResponse(duplicate_values=RepeatedValuesResultModel(**vars(r)))


@router.post("/methods/duplicate-values", response_model=DuplicateValuesComputeResponse)
def duplicate_values_compute(payload: RepeatedValuesRequest) -> DuplicateValuesComputeResponse:
    return _compute(payload.values)


class DuplicateValuesCheckSaveRequest(BaseModel):
    values: list[str]
    label: str | None = Field(default=None, max_length=120)


class DuplicateValuesCheckRecord(BaseModel):
    id: int
    label: str | None = None
    values: list[str]
    duplicate_values: RepeatedValuesResultModel
    created_at: str | None = None


class DuplicateValuesCheckListResponse(BaseModel):
    checks: list[DuplicateValuesCheckRecord]


def _record(row) -> DuplicateValuesCheckRecord:
    payload = row["result_json"]
    return DuplicateValuesCheckRecord(
        id=row["id"],
        label=row["label"],
        values=row["values_json"],
        duplicate_values=RepeatedValuesResultModel(**payload["duplicate_values"]),
        created_at=_iso_or_none(row["created_at"]),
    )


@router.get("/papers/{paper_id}/duplicate-value-checks", response_model=DuplicateValuesCheckListResponse)
def list_saved_duplicate_value_checks(
    paper_id: int, conn: Connection = Depends(get_connection)
) -> DuplicateValuesCheckListResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    return DuplicateValuesCheckListResponse(checks=[_record(r) for r in list_duplicate_value_checks(conn, paper_id)])


@router.post(
    "/papers/{paper_id}/duplicate-value-checks",
    response_model=DuplicateValuesCheckRecord,
    status_code=http_status.HTTP_201_CREATED,
)
def save_duplicate_value_check(
    paper_id: int, payload: DuplicateValuesCheckSaveRequest, engine: Engine = Depends(get_engine)
) -> DuplicateValuesCheckRecord:
    def _do(conn: Connection) -> DuplicateValuesCheckRecord:
        result = _compute(payload.values)
        check_id = add_duplicate_value_check(
            conn,
            paper_id,
            label=payload.label,
            values=[v.strip() for v in payload.values if v.strip()],
            result_json=result.model_dump(),
        )
        if check_id is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        row = next(r for r in list_duplicate_value_checks(conn, paper_id) if int(r["id"]) == check_id)
        return _record(row)

    return run_write(engine, _do)


@router.delete("/papers/{paper_id}/duplicate-value-checks/{check_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_saved_duplicate_value_check(paper_id: int, check_id: int, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        if not delete_duplicate_value_check(conn, paper_id, check_id):
            raise HTTPException(status_code=404, detail="Saved check not found")
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)
