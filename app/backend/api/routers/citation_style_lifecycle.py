"""Citation-style provenance lifecycle endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.backend.citations.render import CitationEngineUnavailable
from app.backend.citations.style_lifecycle import check_style_update, duplicate_style
from app.backend.citations.style_manager import catalog_response
from app.backend.citations.style_repository import StyleFetchError

router = APIRouter()


class DuplicateStyleRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)


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
