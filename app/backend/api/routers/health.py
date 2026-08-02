"""Health endpoint: reachability + honest at-head migration status."""

from __future__ import annotations

import functools
import os
import subprocess

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError

from alembic.runtime.migration import MigrationContext
from app.backend import app_settings
from app.backend.api.dependencies import get_connection
from app.backend.api.startup import PROJECT_ROOT, _head_revision
from app.backend.summarization.verification import VERIFICATION_VERSION

router = APIRouter()


@functools.lru_cache(maxsize=1)
def _dev_git_version() -> str | None:
    """A dev-only fallback for `app_version` when not running under the desktop shell (plain
    uvicorn, the remote-access tunnel) — a git short-SHA identifier, e.g. ``"dev-4ed3196"``,
    with a trailing ``+`` if the working tree has uncommitted changes. Deliberately prefixed
    ``dev-`` so it can never be mistaken for a real packaged release version (never invents a
    fake semver — invariant #4, evidence honestly labeled). Cached for the process's lifetime
    (this never changes without a restart); returns None if git isn't available or this isn't a
    git checkout at all (e.g. a from-scratch source tarball), same fail-quiet posture as the
    packaged-version case above."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not sha:
        return None
    try:
        dirty = (
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            ).stdout.strip()
            != ""
        )
    except (OSError, subprocess.SubprocessError):
        dirty = False
    return f"dev-{sha}" + ("+" if dirty else "")


class HealthResponse(BaseModel):
    app: str
    verification_version: str
    db_reachable: bool
    db_migrated: bool  # True only when the DB is at the latest revision (head)
    db_revision: str | None = None  # the DB's current Alembic revision (None if unstamped)
    db_head_revision: str | None = None  # the latest revision on disk (migration target)
    # B5 SP2 (inc 238): this instance is read-only (CALLOSUM_READ_ONLY=1). The frontend reads it here — /health is the
    # one endpoint forwarded over the read-only mobile tunnel AND token-exempt — to hide write controls (a clean
    # companion). It's a UX signal; the actual read-only boundary is the method gate in AccessControlMiddleware.
    read_only: bool = False
    # inc 416: has the first-run onboarding wizard been completed or explicitly skipped? Rides this same
    # unconditional launch fetch (the one App() always makes), mirroring read_only's own precedent above.
    onboarding_completed: bool = False
    # The desktop shell's own version (e.g. "0.3.2"), set via CALLOSUM_APP_VERSION when the Tauri shell
    # spawns this backend as a child process. Outside the shell (plain uvicorn/dev, the remote-access
    # tunnel) there's no packaged release version, so this falls back to a "dev-<git-sha>" identifier
    # instead (see `_dev_git_version`) — still None if that isn't available either (no git, or not a
    # checkout at all). This is deliberately NOT verification_version (the local NLI/quote-verification
    # pipeline's own internal versioning, unrelated to the app's release number) — the two were
    # previously conflated in the frontend's connection tooltip.
    app_version: str | None = None


def reported_app_version() -> str | None:
    """One release/version label shared by health and explicit low-risk feedback metadata."""
    return os.getenv("CALLOSUM_APP_VERSION") or _dev_git_version()


def _database_status(conn: Connection) -> tuple[bool, bool, str | None, str | None]:
    """(reachable, at_head, current_revision, head_revision).

    `at_head` is the honest migration check: the DB's current Alembic revision equals the
    latest revision on disk — not merely "some version is stamped".
    """
    try:
        conn.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        return False, False, None, None
    try:
        current = MigrationContext.configure(conn).get_current_revision()
    except SQLAlchemyError:
        current = None
    try:
        head = _head_revision()
    except Exception:
        head = None
    at_head = current is not None and head is not None and current == head
    return True, at_head, current, head


@router.get("/health", response_model=HealthResponse)
def health(conn: Connection = Depends(get_connection)) -> HealthResponse:
    reachable, at_head, current, head = _database_status(conn)
    return HealthResponse(
        app="callosum",
        verification_version=VERIFICATION_VERSION,
        db_reachable=reachable,
        db_migrated=at_head,
        db_revision=current,
        db_head_revision=head,
        read_only=app_settings.read_only_mode(),
        onboarding_completed=app_settings.stored_onboarding_completed(),
        app_version=reported_app_version(),
    )
