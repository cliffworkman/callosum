"""Formatted-citation endpoints (inc 106; document render inc 107) — the word-processor-integration spine.

`GET /citations/styles` lists the bundled CSL styles + locales; `POST /citations/render` turns selected papers
into formatted in-text citations + a bibliography in a chosen style (via the citeproc-js sidecar). Read-only,
local, no egress. Reuses `repository.get_papers_for_export` (live papers only) for the canonical `csl_json`.

`POST /citations/render-document` (inc 107) is the **word-processor adapter contract**: an adapter scans the
document for citation fields (each carrying its own embedded CSL-JSON), POSTs the clusters **in document order**,
and gets back the **position-aware** in-text per field (numeric renumbering, author-date disambiguation) + the
bibliography to write back. Self-contained — it renders from the passed payloads, no library lookup.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Connection, Engine

from app.backend.api.dependencies import get_engine
from app.backend.citations import style_store
from app.backend.citations.journal_abbreviations import DEFAULT_MODE as DEFAULT_JOURNAL_ABBREVIATION_MODE
from app.backend.citations.render import (
    DEFAULT_LOCALE,
    DEFAULT_STYLE,
    MAX_CLUSTERS,
    MAX_ITEMS_PER_CLUSTER,
    CitationEngineUnavailable,
    render_document,
    render_papers,
)
from app.backend.citations.style_manager import (
    MAX_CSL_BYTES,
    MAX_STYLE_QUERY,
    StyleRemovalRefused,
    StyleUpdateRequired,
    catalog_response,
    export_style,
    inspect_style_install,
    install_style,
    preview_style,
    remove_style,
    update_style_preferences,
)
from app.backend.citations.style_repository import (
    MAX_URL_LENGTH,
    StyleFetchError,
    install_prepared_style,
    install_repository_style,
    install_style_from_url,
    prepare_repository_style,
    prepare_style_from_url,
    search_repository_styles,
)
from app.backend.persistence.repository import get_papers_for_export
from app.backend.persistence.sqlite_retry import run_write
from app.backend.usage import record_event

router = APIRouter()


class RenderCitationsRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=1, max_length=5000)
    style: str = DEFAULT_STYLE
    locale: str = DEFAULT_LOCALE


class StylePreviewRequest(BaseModel):
    style: str = DEFAULT_STYLE
    locale: str = DEFAULT_LOCALE


class StylePreferencesRequest(BaseModel):
    style: str
    locale: str = DEFAULT_LOCALE
    favorite: bool | None = None
    set_default: bool = False
    mark_used: bool = False


class StyleInstallRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    csl: str = Field(min_length=1, max_length=MAX_CSL_BYTES + style_store.PORTABLE_MARKER_MAX_BYTES)
    replace: bool = False


class RepositoryStyleInstallRequest(BaseModel):
    repository_id: str = Field(min_length=1, max_length=200)
    replace: bool = False
    preflight_token: str | None = Field(default=None, max_length=64)


class UrlStyleInstallRequest(BaseModel):
    url: str = Field(min_length=1, max_length=MAX_URL_LENGTH)
    replace: bool = False
    preflight_token: str | None = Field(default=None, max_length=64)


# CSL's fixed locator-label vocabulary (CSL 1.0.2 term list — confirmed against the bundled locale XML; no
# "timestamp" or generic "other" exists). A `label` outside this set is rejected with a clean 422 rather than
# silently reaching citeproc-js, which would just render it oddly rather than erroring.
CSL_LOCATOR_LABELS = frozenset(
    {
        "book",
        "chapter",
        "column",
        "figure",
        "folio",
        "issue",
        "line",
        "note",
        "opus",
        "page",
        "paragraph",
        "part",
        "scene",
        "section",
        "sub-verbo",
        "supplement",
        "table",
        "verse",
        "volume",
    }
)


class CitationItem(BaseModel):
    """One item inside a citation cluster (inc TBD, P0 phase 3 — backlog #33/#34): the CSL-JSON bibliographic
    fields (title/author/issued/…) pass through untouched via ``extra="allow"``; the fields below are
    per-*occurrence* citeproc-cite properties (never written into the paper's own library record) — named after
    citeproc-js's own ``citationItems`` vocabulary so there is no translation layer between what the LibreOffice
    adapter's mark payload stores (P0 phase 1) and what actually reaches citeproc (P0 phase 3's
    ``citeproc_runner.js`` change). ``suppress_author``/``author_only`` use hyphenated wire aliases to match
    citeproc's own property names; a caller must use the hyphenated form (no ``populate_by_name`` — one wire
    shape, not two)."""

    model_config = ConfigDict(extra="allow")

    locator: str | None = Field(default=None, max_length=200)
    label: str | None = Field(default=None)
    prefix: str | None = Field(default=None, max_length=300)
    suffix: str | None = Field(default=None, max_length=300)
    suppress_author: bool = Field(default=False, alias="suppress-author")
    author_only: bool = Field(default=False, alias="author-only")

    @field_validator("label")
    @classmethod
    def _validate_label(cls, v: str | None) -> str | None:
        if v is not None and v not in CSL_LOCATOR_LABELS:
            raise ValueError(f"unknown locator label {v!r}; must be one of {sorted(CSL_LOCATOR_LABELS)}")
        return v


class CitationCluster(BaseModel):
    citationID: str | None = None
    items: list[CitationItem] = Field(min_length=1, max_length=MAX_ITEMS_PER_CLUSTER)
    # CSL note styles use the real note number for first/subsequent/ibid position state. Zero remains the
    # backwards-compatible in-text/default value for every existing adapter.
    noteIndex: int = Field(default=0, ge=0, le=MAX_CLUSTERS, strict=True)


class UncitedItem(BaseModel):
    """A bibliography-only entry (P1 item #11, backlog #33/#34) — a work with no in-text citation mark in the
    document (a "further reading" item). CSL-JSON fields pass through untouched via ``extra="allow"``, same as
    `CitationItem`; the only field this model itself cares about is `id`, matched against
    `bibliography_exclude_ids` and citeproc's own item registry."""

    model_config = ConfigDict(extra="allow")
    id: str


class RenderDocumentRequest(BaseModel):
    citations: list[CitationCluster] = Field(max_length=MAX_CLUSTERS)
    style: str = DEFAULT_STYLE
    locale: str = DEFAULT_LOCALE
    # P1 item #11 (backlog #33/#34): bibliography editing. Both additive/optional — existing callers unaffected.
    uncited_items: list[UncitedItem] = Field(default=[], max_length=MAX_ITEMS_PER_CLUSTER)
    bibliography_exclude_ids: list[str] = Field(default=[], max_length=MAX_CLUSTERS)
    journal_abbreviation_mode: Literal["library", "medline", "full"] = DEFAULT_JOURNAL_ABBREVIATION_MODE


@router.get("/citations/styles")
def citation_styles(q: str = Query(default="", max_length=MAX_STYLE_QUERY)) -> dict[str, Any]:
    try:
        return catalog_response(q)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/citations/styles/preview")
def citation_style_preview(payload: StylePreviewRequest) -> dict[str, Any]:
    try:
        return preview_style(payload.style, payload.locale)
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.put("/citations/styles/preferences")
def citation_style_preferences(payload: StylePreferencesRequest) -> dict[str, Any]:
    try:
        update_style_preferences(
            payload.style,
            payload.locale,
            favorite=payload.favorite,
            set_default=payload.set_default,
            mark_used=payload.mark_used,
        )
        return catalog_response()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/citations/styles/install")
def citation_style_install(payload: StyleInstallRequest) -> dict[str, Any]:
    try:
        result = install_style(
            payload.filename,
            payload.csl,
            replace=payload.replace,
            provenance={"source_type": "local_file", "source_name": payload.filename},
        )
        return {**catalog_response(), "install": result}
    except StyleUpdateRequired as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "update_available",
                "style_id": exc.style_id,
                "title": exc.title,
                "message": str(exc),
            },
        ) from exc
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/citations/styles/validate")
def citation_style_validate(payload: StyleInstallRequest) -> dict[str, Any]:
    try:
        return {**catalog_response(), "valid": True, "install": inspect_style_install(payload.filename, payload.csl)}
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        return {**catalog_response(), "valid": False, "error": str(exc)}


@router.get("/citations/styles/repository/search")
def citation_style_repository_search(q: str = Query(min_length=2, max_length=MAX_STYLE_QUERY)) -> dict[str, Any]:
    try:
        return search_repository_styles(q)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StyleFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _remote_style_response(result: dict[str, Any]) -> dict[str, Any]:
    return {**catalog_response(), "install": result}


def _remote_style_error(exc: Exception) -> HTTPException:
    if isinstance(exc, StyleUpdateRequired):
        return HTTPException(
            status_code=409,
            detail={
                "code": "update_available",
                "style_id": exc.style_id,
                "title": exc.title,
                "message": str(exc),
            },
        )
    if isinstance(exc, StyleFetchError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, CitationEngineUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.post("/citations/styles/repository/validate")
def citation_style_repository_validate(payload: RepositoryStyleInstallRequest) -> dict[str, Any]:
    try:
        return {**catalog_response(), "valid": True, "install": prepare_repository_style(payload.repository_id)}
    except (StyleFetchError, CitationEngineUnavailable, ValueError, RuntimeError) as exc:
        return {**catalog_response(), "valid": False, "error": str(exc)}


@router.post("/citations/styles/repository/install")
def citation_style_repository_install(payload: RepositoryStyleInstallRequest) -> dict[str, Any]:
    try:
        if payload.preflight_token:
            result = install_prepared_style(
                payload.preflight_token,
                mode="repository",
                source=payload.repository_id,
                replace=payload.replace,
            )
        else:
            result = install_repository_style(payload.repository_id, replace=payload.replace)
        return _remote_style_response(
            result,
        )
    except (StyleUpdateRequired, StyleFetchError, CitationEngineUnavailable, ValueError, RuntimeError) as exc:
        raise _remote_style_error(exc) from exc


@router.post("/citations/styles/url/validate")
def citation_style_url_validate(payload: UrlStyleInstallRequest) -> dict[str, Any]:
    try:
        return {**catalog_response(), "valid": True, "install": prepare_style_from_url(payload.url)}
    except (StyleFetchError, CitationEngineUnavailable, ValueError, RuntimeError) as exc:
        return {**catalog_response(), "valid": False, "error": str(exc)}


@router.post("/citations/styles/url/install")
def citation_style_url_install(payload: UrlStyleInstallRequest) -> dict[str, Any]:
    try:
        if payload.preflight_token:
            result = install_prepared_style(
                payload.preflight_token,
                mode="url",
                source=payload.url.strip(),
                replace=payload.replace,
            )
        else:
            result = install_style_from_url(payload.url, replace=payload.replace)
        return _remote_style_response(result)
    except (StyleUpdateRequired, StyleFetchError, CitationEngineUnavailable, ValueError, RuntimeError) as exc:
        raise _remote_style_error(exc) from exc


@router.get("/citations/styles/{style_id}/export")
def citation_style_export(style_id: str) -> Response:
    try:
        xml = export_style(style_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=422, detail="The personal citation style could not be read") from exc
    return Response(
        content=xml,
        media_type="application/vnd.citationstyles.style+xml",
        headers={"Content-Disposition": f'attachment; filename="{style_id}.csl"'},
    )


@router.delete("/citations/styles/{style_id}")
def citation_style_remove(style_id: str) -> dict[str, Any]:
    try:
        return remove_style(style_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StyleRemovalRefused as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/citations/render")
def render_citations(payload: RenderCitationsRequest, engine: Engine = Depends(get_engine)) -> dict[str, Any]:
    # Wrapped in run_write (inc 281) since it now records a usage event -- a short write, retried transaction-
    # level on a transient SQLite writer lock rather than taking a raw connection and committing directly.
    def _do(conn: Connection) -> dict[str, Any]:
        if not style_store.style_exists(payload.style):
            raise HTTPException(status_code=422, detail="Unknown citation style")
        rows = get_papers_for_export(conn, payload.paper_ids)
        if not rows:
            raise HTTPException(status_code=422, detail="No existing (non-trashed) papers to render")
        try:
            result = render_papers(rows, style=payload.style, locale=payload.locale)
        except CitationEngineUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        record_event(conn, "citation_export", count=len(rows))
        return result

    return run_write(engine, _do)


@router.post("/citations/render-document")
def render_citation_document(payload: RenderDocumentRequest) -> dict[str, Any]:
    if not style_store.style_exists(payload.style):
        raise HTTPException(status_code=422, detail="Unknown citation style")
    # by_alias=True: CitationItem's suppress_author/author_only dump as the hyphenated citeproc-cite property
    # names (P0 phase 3) — the wire shape render_document()/citeproc_runner.js expect, not the Python attribute.
    clusters = [c.model_dump(by_alias=True) for c in payload.citations]
    uncited = [u.model_dump() for u in payload.uncited_items]
    try:
        return render_document(
            clusters,
            style=payload.style,
            locale=payload.locale,
            uncited_items=uncited,
            bibliography_exclude_ids=payload.bibliography_exclude_ids,
            journal_abbreviation_mode=payload.journal_abbreviation_mode,
        )
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
