"""Local-only WIP watch-root discovery and manuscript metadata API."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.backend.api.job_store import JobStore
from app.backend.api.wip_security import require_local_wip
from app.backend.persistence.sqlite_retry import run_write
from app.backend.persistence.wip_repo import (
    create_watch_root,
    delete_watch_root,
    get_file,
    get_manuscript,
    get_watch_root,
    list_activity,
    list_files,
    list_manuscripts,
    list_watch_roots,
    reconcile_watch_root,
    update_file,
    update_manuscript,
    update_watch_root,
)
from app.backend.wip.discovery import inspect_watch_root
from app.backend.wip.paths import path_key, trusted_child

router = APIRouter(prefix="/wip", dependencies=[Depends(require_local_wip)])


class WatchRootCreate(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    discovery_mode: Literal["folder", "children"]
    excluded_children: list[str] = Field(default_factory=list, max_length=200)


class WatchRootPatch(BaseModel):
    enabled: bool | None = None
    discovery_mode: Literal["folder", "children"] | None = None
    excluded_children: list[str] | None = Field(default=None, max_length=200)


class ManuscriptPatch(BaseModel):
    title_override: str | None = Field(default=None, max_length=500)
    state: Literal["active", "paused", "archived", "missing"] | None = None
    manuscript_type: str | None = Field(default=None, max_length=50)
    stage: str | None = Field(default=None, max_length=50)
    target_journal: str | None = Field(default=None, max_length=500)
    deadline: date | None = None
    notes: str | None = Field(default=None, max_length=20_000)


class FilePatch(BaseModel):
    role: (
        Literal[
            "primary-manuscript",
            "manuscript-candidate",
            "supplement",
            "cover-letter",
            "response-to-reviewers",
            "reporting-checklist",
            "figure",
            "table",
            "analysis-output",
            "other",
        ]
        | None
    ) = None
    is_primary: bool | None = None


class ScanResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: dict[str, int] | None = None


def _clean_exclusions(values: list[str]) -> list[str]:
    clean = sorted({value.strip() for value in values if value.strip()}, key=str.casefold)
    if any("/" in value or "\\" in value or value in {".", ".."} for value in clean):
        raise HTTPException(status_code=422, detail="Excluded children must be immediate folder names.")
    return clean


@router.get("/watch-roots")
def roots_list(request: Request) -> list[dict]:
    with request.app.state.engine.connect() as conn:
        return list_watch_roots(conn)


@router.post("/watch-roots", status_code=201)
def roots_create(payload: WatchRootCreate, request: Request) -> dict:
    folder = Path(payload.path).expanduser()
    if not folder.is_dir():
        raise HTTPException(status_code=422, detail="Folder not found — enter an existing directory path.")
    resolved = str(folder.resolve(strict=False))
    return run_write(
        request.app.state.engine,
        lambda conn: create_watch_root(
            conn,
            path=resolved,
            path_key=path_key(resolved),
            discovery_mode=payload.discovery_mode,
            excluded_children=_clean_exclusions(payload.excluded_children),
        ),
    )


@router.patch("/watch-roots/{root_id}")
def roots_patch(root_id: int, payload: WatchRootPatch, request: Request) -> dict:
    values = payload.model_dump(exclude_unset=True)
    if "excluded_children" in values:
        values["excluded_children_json"] = _clean_exclusions(values.pop("excluded_children"))
    result = run_write(request.app.state.engine, lambda conn: update_watch_root(conn, root_id, values))
    if result is None:
        raise HTTPException(status_code=404, detail="WIP watch root not found")
    return result


@router.delete("/watch-roots/{root_id}", status_code=204)
def roots_delete(root_id: int, request: Request) -> Response:
    deleted = run_write(request.app.state.engine, lambda conn: delete_watch_root(conn, root_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="WIP watch root not found")
    return Response(status_code=204)


@router.post("/watch-roots/{root_id}/scan", response_model=ScanResponse, status_code=202)
def root_scan(root_id: int, background_tasks: BackgroundTasks, request: Request) -> ScanResponse:
    with request.app.state.engine.connect() as conn:
        root = get_watch_root(conn, root_id)
    if root is None:
        raise HTTPException(status_code=404, detail="WIP watch root not found")
    if not root["enabled"]:
        raise HTTPException(status_code=409, detail="This WIP watch root is paused.")
    return _start_scan(request, background_tasks, [root_id])


@router.post("/rescan", response_model=ScanResponse, status_code=202)
def roots_rescan(background_tasks: BackgroundTasks, request: Request) -> ScanResponse:
    with request.app.state.engine.connect() as conn:
        ids = [int(root["id"]) for root in list_watch_roots(conn) if root["enabled"]]
    return _start_scan(request, background_tasks, ids)


@router.get("/scan/{job_id}", response_model=ScanResponse)
def scan_status(job_id: str, request: Request) -> ScanResponse:
    job = request.app.state.wip_scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="WIP scan job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return ScanResponse(job_id=job_id, status=job.status, detail=job.detail)


def _start_scan(request: Request, background_tasks: BackgroundTasks, root_ids: list[int]) -> ScanResponse:
    app = request.app
    jobs: JobStore[ScanResponse] = app.state.wip_scan_jobs
    lock: Lock = app.state.wip_scan_singleflight_lock
    with lock:
        active_id = app.state.active_wip_scan_job_id
        if active_id:
            active = jobs.get(active_id)
            if active and active.status in {"pending", "running"}:
                return ScanResponse(job_id=active_id, status=active.status, detail="A WIP scan is already running.")
        job_id = jobs.create()
        app.state.active_wip_scan_job_id = job_id
        background_tasks.add_task(_run_scan, app, job_id, root_ids)
    return ScanResponse(job_id=job_id, status="pending")


def _run_scan(app, job_id: str, root_ids: list[int]) -> None:
    jobs: JobStore[ScanResponse] = app.state.wip_scan_jobs
    jobs.mark_running(job_id)
    total = {"added": 0, "restored": 0, "missing": 0, "files_added": 0, "files_missing": 0, "errors": 0}
    try:
        for root_id in root_ids:
            with app.state.engine.connect() as conn:
                root = get_watch_root(conn, root_id)
            if root is None or not root["enabled"]:
                continue
            inspection = inspect_watch_root(root)
            result = run_write(
                app.state.engine,
                lambda conn, r=root, i=inspection: reconcile_watch_root(conn, r, i),
            )
            for key in total:
                total[key] += result[key]
        response = ScanResponse(job_id=job_id, status="done", summary=total)
        jobs.mark_done(job_id, response)
    except Exception as exc:  # noqa: BLE001 - job boundary records a bounded error for the UI
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        with app.state.wip_scan_singleflight_lock:
            if app.state.active_wip_scan_job_id == job_id:
                app.state.active_wip_scan_job_id = None


@router.get("/manuscripts")
def manuscripts_list(
    request: Request,
    query: str = "",
    state: Literal["active", "paused", "archived", "missing"] | None = None,
    stage: str | None = None,
    sort: Literal["activity", "title", "created", "deadline", "stage"] = "activity",
) -> list[dict]:
    with request.app.state.engine.connect() as conn:
        return list_manuscripts(conn, query=query, state=state, stage=stage, sort=sort)


@router.get("/manuscripts/{manuscript_id}")
def manuscript_get(manuscript_id: int, request: Request) -> dict:
    with request.app.state.engine.connect() as conn:
        manuscript = get_manuscript(conn, manuscript_id)
    if manuscript is None:
        raise HTTPException(status_code=404, detail="WIP manuscript not found")
    return manuscript


@router.patch("/manuscripts/{manuscript_id}")
def manuscript_patch(manuscript_id: int, payload: ManuscriptPatch, request: Request) -> dict:
    values = payload.model_dump(exclude_unset=True)
    result = run_write(
        request.app.state.engine,
        lambda conn: update_manuscript(conn, manuscript_id, values),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="WIP manuscript not found")
    return result


@router.get("/manuscripts/{manuscript_id}/files")
def manuscript_files(manuscript_id: int, request: Request) -> list[dict]:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
        return list_files(conn, manuscript_id)


@router.patch("/manuscripts/{manuscript_id}/files/{file_id}")
def manuscript_file_patch(manuscript_id: int, file_id: int, payload: FilePatch, request: Request) -> dict:
    values = payload.model_dump(exclude_unset=True)
    if values.get("is_primary"):
        values["role"] = "primary-manuscript"
    result = run_write(
        request.app.state.engine,
        lambda conn: update_file(conn, manuscript_id, file_id, values),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="WIP file not found")
    return result


def _file_path(request: Request, manuscript_id: int, file_id: int) -> tuple[Path, Path]:
    with request.app.state.engine.connect() as conn:
        manuscript = get_manuscript(conn, manuscript_id)
        file = get_file(conn, manuscript_id, file_id)
    if manuscript is None or file is None:
        raise HTTPException(status_code=404, detail="WIP file not found")
    path = trusted_child(manuscript["root_path"], file["relative_path"])
    if not path.is_file():
        raise HTTPException(status_code=409, detail="WIP file is unavailable")
    return Path(manuscript["root_path"]), path


def _open_local(path: Path, *, reveal: bool) -> None:
    if sys.platform == "win32":
        command = ["explorer.exe", f"/select,{path}"] if reveal else None
        if command:
            subprocess.Popen(command)  # noqa: S603
        else:
            os.startfile(path)  # type: ignore[attr-defined] # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if reveal else ["open", str(path)])  # noqa: S603,S607
    else:
        subprocess.Popen(["xdg-open", str(path.parent if reveal else path)])  # noqa: S603,S607


@router.post("/manuscripts/{manuscript_id}/files/{file_id}/open", status_code=204)
def manuscript_file_open(manuscript_id: int, file_id: int, request: Request) -> Response:
    _, path = _file_path(request, manuscript_id, file_id)
    opener = getattr(request.app.state, "wip_path_opener", None)
    (opener or _open_local)(path, reveal=False)
    return Response(status_code=204)


@router.post("/manuscripts/{manuscript_id}/files/{file_id}/reveal", status_code=204)
def manuscript_file_reveal(manuscript_id: int, file_id: int, request: Request) -> Response:
    _, path = _file_path(request, manuscript_id, file_id)
    opener = getattr(request.app.state, "wip_path_opener", None)
    (opener or _open_local)(path, reveal=True)
    return Response(status_code=204)


@router.get("/manuscripts/{manuscript_id}/activity")
def manuscript_activity(manuscript_id: int, request: Request, limit: int = 100) -> list[dict]:
    bounded = max(1, min(limit, 500))
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
        return list_activity(conn, manuscript_id, limit=bounded)
