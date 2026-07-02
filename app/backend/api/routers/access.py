"""Remote-access lockout recovery endpoint (inc 254). See ``app/backend/api/access_recovery.py`` for the model.

``POST /access/recover``:
- with ``{}`` — start recovery: write a one-time code to a local file and return ONLY its path (never the code).
- with ``{"code": "..."}`` — verify the code and, on success, turn Remote access **off** (the safe local-only
  default). It never reveals the token or any library data.

Gate-exempt (the user is locked out and can't supply a token) but rate-limited by ``AccessControlMiddleware``.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.backend import app_settings
from app.backend.api import access_recovery

router = APIRouter()


class RecoverRequest(BaseModel):
    # None/absent → start recovery (mint a code); a value → verify it. Capped so an oversized body is rejected
    # at the boundary (rule #4) before any comparison.
    code: str | None = Field(default=None, max_length=access_recovery.RECOVERY_CODE_MAX_LEN)


class RecoverResponse(BaseModel):
    status: str  # "code_written" | "recovered" | "invalid"
    detail: str
    code_path: str | None = None  # where the local user reads the one-time code — NEVER the code itself


@router.post("/access/recover", response_model=RecoverResponse)
def recover_access(req: RecoverRequest) -> RecoverResponse:
    """Two-phase local-possession recovery. Phase 1 (no code) writes the code to a local file; phase 2 (code)
    verifies it and disables remote access. The only privileged effect is turning the gate OFF."""
    if not req.code:
        path = access_recovery.start_recovery()
        return RecoverResponse(
            status="code_written",
            detail=(
                "A one-time recovery code was written to the file below, on the computer running callosum. "
                "Open it, copy the code, and paste it here."
            ),
            code_path=str(path),
        )
    if access_recovery.verify_recovery(req.code):
        app_settings.set_remote_access_enabled(False)
        return RecoverResponse(
            status="recovered",
            detail="Remote access turned off. Your library is available locally again — reloading…",
        )
    return RecoverResponse(
        status="invalid",
        detail="That code didn't match (it may have expired). Start recovery again to get a fresh code.",
    )
