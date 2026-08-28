"""GROBID Docker lifecycle endpoints (backlog #58) — the API surface around ``grobid_lifecycle.py``.

New sibling router (the ``paper_enrich.py``/``methods_retraction.py``/``grobid.py`` itself precedent) — this is
a distinct concern (infra lifecycle management) from ``grobid.py``'s own settings/parse endpoints, sharing
``request.app.state`` the same way those siblings do. A callosum-managed instance is always bound to
``127.0.0.1``, so it automatically satisfies the existing loopback-vs-egress-gate distinction
(``llm.providers.is_loopback_url``) with zero special-casing — nothing here needs its own egress gate; pulling
callosum's own tooling dependency from Docker Hub sends no library content anywhere (see the security audit
and CLAUDE.md's Principles-gate note for the full reasoning).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.backend import app_settings, grobid_lifecycle
from app.backend.api.job_store import JobStore

router = APIRouter(tags=["grobid"])


class GrobidDockerStatusResponse(BaseModel):
    docker_installed: bool
    docker_daemon_running: bool
    container_state: Literal["absent", "running", "stopped"]
    managed_url: str | None = None  # set only when container_state == "running" AND grobid_url matches it


def _managed_status() -> GrobidDockerStatusResponse:
    installed, running = grobid_lifecycle.docker_available()
    state = grobid_lifecycle.container_state()
    managed_url = None
    if state == "running":
        stored = app_settings.stored_grobid_url()
        if stored:
            managed_url = stored
    return GrobidDockerStatusResponse(
        docker_installed=installed, docker_daemon_running=running, container_state=state, managed_url=managed_url
    )


@router.get("/grobid/docker/status", response_model=GrobidDockerStatusResponse)
def docker_status() -> GrobidDockerStatusResponse:
    return _managed_status()


class GrobidInstallResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    url: str | None = None


@router.post("/grobid/docker/install", response_model=GrobidInstallResponse, status_code=202)
def start_install(background_tasks: BackgroundTasks, request: Request) -> GrobidInstallResponse:
    installed, running = grobid_lifecycle.docker_available()
    if not installed:
        raise HTTPException(status_code=409, detail="Docker is not installed. Install Docker Desktop, then try again.")
    if not running:
        raise HTTPException(
            status_code=409, detail="Docker is installed but not running. Start Docker Desktop, then try again."
        )
    jobs: JobStore[GrobidInstallResponse] = request.app.state.grobid_lifecycle_jobs
    for _job_id, job in jobs.list_all():
        if job.status in ("pending", "running"):
            raise HTTPException(status_code=409, detail="An install is already in progress.")
    job_id = jobs.create()
    background_tasks.add_task(_run_install_job, request.app, job_id)
    return GrobidInstallResponse(job_id=job_id, status="pending")


@router.get("/grobid/docker/install/{job_id}", response_model=GrobidInstallResponse)
def install_status(job_id: str, request: Request) -> GrobidInstallResponse:
    jobs: JobStore[GrobidInstallResponse] = request.app.state.grobid_lifecycle_jobs
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Install job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return GrobidInstallResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_install_job(app: FastAPI, job_id: str) -> None:
    # No mark_progress()/mark_stage() calls -- matches the existing precedent for every other "download a
    # public artifact" job (Retraction Watch/TOP Factor/AJOL mirrors), which all go straight running -> done
    # with a single static frontend label rather than a fabricated determinate progress bar (grobid_lifecycle's
    # own on_progress hook exists for pure-function testability, not for wiring into JobProgress here).
    jobs: JobStore[GrobidInstallResponse] = app.state.grobid_lifecycle_jobs
    jobs.mark_running(job_id)
    try:
        url = grobid_lifecycle.install_and_start()
    except grobid_lifecycle.GrobidInstallError as exc:
        jobs.mark_error(job_id, str(exc))
        return
    except Exception as exc:  # noqa: BLE001 -- any other failure becomes a graceful job error, never a crash
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
        return
    app_settings.set_grobid_url(url)
    jobs.mark_done(job_id, GrobidInstallResponse(job_id=job_id, status="done", url=url))


class GrobidStopResponse(BaseModel):
    container_state: Literal["absent", "running", "stopped"]


@router.post("/grobid/docker/stop", response_model=GrobidStopResponse)
def stop_managed_instance() -> GrobidStopResponse:
    grobid_lifecycle.stop_and_remove()
    return GrobidStopResponse(container_state=grobid_lifecycle.container_state())
