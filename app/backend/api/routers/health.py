"""Health endpoint: reachability + honest at-head migration status."""

from __future__ import annotations

import functools
import logging
import os
import subprocess
from typing import Literal

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

_log = logging.getLogger(__name__)

# Which Callosum backend process this is (browser-capture prerequisite, #61). The desktop shell spawns
# several children that all serve THIS SAME FastAPI app, so port and version cannot tell them apart —
# and one of them, the Word HTTPS companion, deliberately runs with the Remote Access gate disabled
# (`CALLOSUM_DISABLE_REMOTE_ACCESS=1`). A future browser connector host must be able to identify the
# one canonical UI backend rather than whichever sibling happens to answer.
#
# The role is set EXPLICITLY by each launcher (`CALLOSUM_INSTANCE_ROLE`), never inferred here from
# port, version, `CALLOSUM_DISABLE_REMOTE_ACCESS`, `CALLOSUM_TUNNEL_TARGET`, or whether a companion
# feature happens to be enabled. Those remain independent controls; this is identity.
InstanceRole = Literal["ui", "word-https", "tunnel-target"]
INSTANCE_ROLE_ENV = "CALLOSUM_INSTANCE_ROLE"
UI_ROLE: InstanceRole = "ui"
WORD_HTTPS_ROLE: InstanceRole = "word-https"
TUNNEL_TARGET_ROLE: InstanceRole = "tunnel-target"
INSTANCE_ROLES: tuple[InstanceRole, ...] = (UI_ROLE, WORD_HTTPS_ROLE, TUNNEL_TARGET_ROLE)


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
    onboarding_version: int = 0
    onboarding_current_version: int = app_settings.ONBOARDING_CURRENT_VERSION
    # The desktop shell's own version (e.g. "0.3.2"), set via CALLOSUM_APP_VERSION when the Tauri shell
    # spawns this backend as a child process. Outside the shell (plain uvicorn/dev, the remote-access
    # tunnel) there's no packaged release version, so this falls back to a "dev-<git-sha>" identifier
    # instead (see `_dev_git_version`) — still None if that isn't available either (no git, or not a
    # checkout at all). This is deliberately NOT verification_version (the local NLI/quote-verification
    # pipeline's own internal versioning, unrelated to the app's release number) — the two were
    # previously conflated in the frontend's connection tooltip.
    app_version: str | None = None
    # Which backend process this is (browser-capture prerequisite, #61) — "ui" / "word-https" /
    # "tunnel-target", or null when no launcher declared one. Independent of app_version: role is
    # process identity, app_version is build identity. See `reported_instance_role`.
    instance_role: InstanceRole | None = None


def reported_app_version() -> str | None:
    """One release/version label shared by health and explicit low-risk feedback metadata."""
    return os.getenv("CALLOSUM_APP_VERSION") or _dev_git_version()


@functools.lru_cache(maxsize=1)
def _warn_invalid_instance_role_once(raw: str) -> None:
    """Warn ONCE per process about an out-of-vocabulary role (a connector may poll /health often)."""
    _log.warning(
        "Ignoring unrecognized %s=%r; expected one of %s. This process reports no instance role.",
        INSTANCE_ROLE_ENV,
        raw,
        ", ".join(INSTANCE_ROLES),
    )


def reported_instance_role() -> InstanceRole | None:
    """Which backend process this is, or ``None`` when no launcher declared one.

    ``None`` is the deliberate fail-safe for both an unset and an unrecognized value: a bare
    ``uvicorn``, an older packaged build, or a future launch path that forgets. A consumer must
    require a specific role explicitly, so an unknown process can never pass for the canonical UI
    backend. An unrecognized value additionally warns (once — see above), so a typo in a launcher is
    visible without a bad env var bricking a user's install.

    This reports the PROCESS's identity only. It deliberately says nothing about whether the build is
    a packaged release or a dev checkout — that is ``app_version``'s separate axis, and the two stay
    independent so ``"ui"`` means exactly the same thing in both. Composing them into an eligibility
    rule is the consumer's job: a production connector would require this role AND an approved
    packaged identity, while an explicitly development connector may accept this role with a dev
    identity. Encoding either policy here would make dev unable to emulate the product contract, or
    would weaken production.
    """
    raw = (os.getenv(INSTANCE_ROLE_ENV) or "").strip()
    if not raw:
        return None
    if raw not in INSTANCE_ROLES:
        _warn_invalid_instance_role_once(raw)
        return None
    return raw  # type: ignore[return-value]  # membership check above narrows this to InstanceRole


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
        onboarding_version=app_settings.stored_onboarding_version(),
        app_version=reported_app_version(),
        instance_role=reported_instance_role(),
    )
