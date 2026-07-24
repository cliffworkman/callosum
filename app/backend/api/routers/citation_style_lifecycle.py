"""Citation-style provenance lifecycle endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.backend.citations.render import CitationEngineUnavailable
from app.backend.citations.style_editor import (
    StyleEditConflict,
    save_style_edit,
    style_source,
    validate_style_edit,
)
from app.backend.citations.style_lifecycle import check_style_update, duplicate_style
from app.backend.citations.style_manager import catalog_response
from app.backend.citations.style_repository import StyleFetchError

router = APIRouter()


class DuplicateStyleRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)


class ValidateStyleEditRequest(BaseModel):
    csl: str = Field(min_length=1, max_length=1_000_000)
    locale: str = Field(default="en-US", max_length=10)


class SaveStyleEditRequest(ValidateStyleEditRequest):
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.get("/citations/styles/{style_id}/source")
def citation_style_source(style_id: str) -> dict[str, Any]:
    try:
        return style_source(style_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/citations/styles/{style_id}/source/validate")
def citation_style_source_validate(style_id: str, payload: ValidateStyleEditRequest) -> dict[str, Any]:
    try:
        return validate_style_edit(style_id, payload.csl, payload.locale)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/citations/styles/{style_id}/source")
def citation_style_source_save(style_id: str, payload: SaveStyleEditRequest) -> dict[str, Any]:
    try:
        result = save_style_edit(style_id, payload.csl, payload.expected_revision, payload.locale)
        return {**catalog_response(), "editor": result}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StyleEditConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/citations/styles/{style_id}/duplicate")
def citation_style_duplicate(style_id: str, payload: DuplicateStyleRequest) -> dict[str, Any]:
    try:
        result = duplicate_style(style_id, payload.title)
        return {**catalog_response(), "install": result}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/citations/styles/{style_id}/check-update")
def citation_style_check_update(style_id: str) -> dict[str, Any]:
    try:
        result = check_style_update(style_id)
        return {**catalog_response(), "update": result}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StyleFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
