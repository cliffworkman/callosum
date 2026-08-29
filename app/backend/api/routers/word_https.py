"""Local-only lifecycle API for the packaged desktop Word HTTPS companion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.backend import word_https_lifecycle
from app.backend.api.local_only import require_local_machine_action

router = APIRouter(prefix="/word-https", tags=["word"], dependencies=[Depends(require_local_machine_action)])


class WordHttpsStatusResponse(BaseModel):
    supported: bool
    enabled: bool
    certificate_ready: bool
    trusted: bool
    platform: str
    detail: str


def _response() -> WordHttpsStatusResponse:
    return WordHttpsStatusResponse(**word_https_lifecycle.status().__dict__)


@router.get("/status", response_model=WordHttpsStatusResponse)
def word_https_status() -> WordHttpsStatusResponse:
    return _response()


@router.post("/enable", response_model=WordHttpsStatusResponse)
def enable_word_https() -> WordHttpsStatusResponse:
    try:
        word_https_lifecycle.enable()
    except word_https_lifecycle.WordHttpsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _response()


@router.post("/disable", response_model=WordHttpsStatusResponse)
def disable_word_https() -> WordHttpsStatusResponse:
    try:
        word_https_lifecycle.disable()
    except word_https_lifecycle.WordHttpsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _response()
