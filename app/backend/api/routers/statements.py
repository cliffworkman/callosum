"""Open-science statement staging (backlog #33/#34 P2 item #21, inc 462).

Extends `credit.py`'s own "build in the web UI -> stage -> LibreOffice pulls & inserts" hand-off (inc 261) to
7 more author-asserted manuscript disclosures: data availability, code availability, preregistration, funding,
conflict of interest, ethics, and AI use. Every one of these is, like the CRediT statement itself, something
only the author can assert -- callosum never infers or verifies funding/ethics/COI/AI-use facts about the
user's own study. Deterministic formatting (the canned starting phrases) is pure client-side text; this router's
only job is the SAME transient, in-memory staging hand-off `credit.py` already established, generalized to a
dict keyed by kind so several statements can be staged at once without one clobbering another.

New router (not folded into `credit.py`, which handles a materially different content type -- the CRediT
structured author x role grid -- and stays untouched)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

MAX_STATEMENT_LEN = 4000  # generous for a single statement paragraph; matches the scale of other free-text caps

STATEMENT_KINDS = (
    "data_availability",
    "code_availability",
    "preregistration",
    "funding",
    "conflict_of_interest",
    "ethics",
    "ai_use",
)

# Single-user, single-process in-memory staging -- the credit.py precedent, generalized to a dict keyed by kind
# instead of one bare slot. No file, no persistence, no secret; evaporates on restart.
_pending_statements: dict[str, str] = {}


class PendingStatementRequest(BaseModel):
    kind: str
    text: str = Field(default="", max_length=MAX_STATEMENT_LEN)


@router.post("/statements/pending", response_model=dict[str, str])
def stage_pending_statement(payload: PendingStatementRequest) -> dict[str, str]:
    if payload.kind not in STATEMENT_KINDS:
        raise HTTPException(status_code=422, detail=f"Unknown statement kind: {payload.kind!r}")
    text = payload.text.strip()
    if text:
        _pending_statements[payload.kind] = text
    else:
        _pending_statements.pop(payload.kind, None)  # clearing the box un-stages it, keeping the picker honest
    return dict(_pending_statements)


@router.get("/statements/pending", response_model=dict[str, str])
def get_pending_statements() -> dict[str, str]:
    # The adapter pulls whatever's currently staged ({} if none). Local, in-memory, no egress.
    return dict(_pending_statements)
