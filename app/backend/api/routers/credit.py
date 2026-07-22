"""CRediT contribution-statement builder (CRediTer, inc 261).

`POST /credit/statement` formats an authors × CRediT-role assignment into a human-readable contributorship statement
(both by-author and by-role layouts) — **deterministic, stateless, local — no DB, no egress, no LLM.** It builds
what the human asserts; it never infers or verifies who did what (see `methods/credit.py`).

`POST /credit/pending` + `GET /credit/pending` are a transient, in-memory hand-off so the LibreOffice cite-macro can
insert a statement the user built in the web UI (single-user, single-process uvicorn — no file, no persistence, no
secret). New router (not folded into methods.py, which is at the 600-line cap).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.backend.methods.credit import (
    MAX_AUTHORS,
    MAX_NAME_LEN,
    MAX_ROLES_PER_AUTHOR,
    format_statement,
)

router = APIRouter()

# Cap the staged statement text (rule #4). Generous: 50 authors × 14 roles never approaches it.
MAX_PENDING_LEN = 20_000


class RoleAssignment(BaseModel):
    role: str = Field(max_length=64)  # validated against the allowlist in methods/credit.py
    degree: str | None = Field(default=None, max_length=16)


class AuthorRoles(BaseModel):
    name: str = Field(default="", max_length=MAX_NAME_LEN)
    roles: list[RoleAssignment] = Field(default_factory=list, max_length=MAX_ROLES_PER_AUTHOR)


class CreditStatementRequest(BaseModel):
    authors: list[AuthorRoles] = Field(default_factory=list, max_length=MAX_AUTHORS)
    use_and: bool = False  # backlog #26: opt-in Oxford "and" before the last name in by-role contributor lists


class CreditStatementResponse(BaseModel):
    by_author: list[str]
    by_role: list[str]
    roles: list[dict]


@router.post("/credit/statement", response_model=CreditStatementResponse)
def credit_statement(payload: CreditStatementRequest) -> CreditStatementResponse:
    # Deterministic, stateless, local — no DB, no egress, no LLM. Formats asserted contributions (never infers them).
    authors = [a.model_dump() for a in payload.authors]
    try:
        result = format_statement(authors, use_and=payload.use_and)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=422,
            detail="Invalid CRediT input (check the role keys and degree values).",
        ) from None
    return CreditStatementResponse(**result.to_dict())


# ── transient in-memory hand-off to the LibreOffice cite-macro (inc 261) ──
# A single-user, single-process holder: the web UI stages the built statement; the UNO macro pulls it and inserts it
# at the cursor. No file, no persistence, no secret — it evaporates on restart.
_pending_statement = {"text": ""}


class PendingRequest(BaseModel):
    text: str = Field(default="", max_length=MAX_PENDING_LEN)


class PendingResponse(BaseModel):
    text: str


@router.post("/credit/pending", response_model=PendingResponse)
def stage_pending(payload: PendingRequest) -> PendingResponse:
    # Stage the built statement for the LibreOffice macro to insert. Local, in-memory, no egress.
    _pending_statement["text"] = payload.text
    return PendingResponse(text=payload.text)


@router.get("/credit/pending", response_model=PendingResponse)
def get_pending() -> PendingResponse:
    # The macro pulls the staged statement ("" if none). Local, in-memory, no egress.
    return PendingResponse(text=_pending_statement["text"])
