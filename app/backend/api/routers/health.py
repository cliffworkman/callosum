"""Health endpoint: reachability + honest at-head migration status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError

from alembic.runtime.migration import MigrationContext
from app.backend.api.dependencies import get_connection
from app.backend.api.startup import _head_revision
from app.backend.summarization.verification import VERIFICATION_VERSION

router = APIRouter()


class HealthResponse(BaseModel):
    app: str
    verification_version: str
    db_reachable: bool
    db_migrated: bool  # True only when the DB is at the latest revision (head)
    db_revision: str | None = None  # the DB's current Alembic revision (None if unstamped)
    db_head_revision: str | None = None  # the latest revision on disk (migration target)


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
    )
