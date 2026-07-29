"""In-app bug report / feature request (inc 265).

Three surfaces, all local:

- ``GET  /feedback/config``  — the destination address + **exactly** the diagnostics that would be
  attached, so the form can show the payload before anything is composed.
- ``PUT  /feedback/config``  — set/clear the destination address (blank by default; see
  ``feedback/destination.py``).
- ``POST /feedback``         — write the report bundle to ``~/.callosum/feedback/<stamp>_<kind>_<slug>/``
  and return its paths, the full report text, and a prefilled ``mailto:`` URL.

**No egress is added.** The server writes files and returns a URL; the mail client the user already
trusts does the sending, with the report visible in the draft (invariant #3, and the "inspectability
over authority" commitment — the user reads the payload before it moves).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Connection
from sqlalchemy.exc import SQLAlchemyError

from alembic.runtime.migration import MigrationContext
from app.backend.api.dependencies import get_connection
from app.backend.api.startup import _head_revision
from app.backend.feedback import bundle as bundle_mod
from app.backend.feedback import destination as destination_mod
from app.backend.feedback import diagnostics as diagnostics_mod

router = APIRouter()


class FeedbackConfig(BaseModel):
    destination_email: str = ""  # "" = unset; callosum ships with no hard-coded address
    destination_source: str | None = None  # "ui" | "env" | None
    diagnostics: dict[str, str] = {}  # exactly what POST would attach when include_diagnostics is true
    feedback_dir: str  # where bundles are written, shown in the UI so the user can find/delete them


class FeedbackConfigUpdate(BaseModel):
    set_destination_email: bool = False
    destination_email: str | None = Field(default=None, max_length=destination_mod.DESTINATION_EMAIL_MAX_LEN)


class FeedbackRequest(BaseModel):
    kind: Literal["bug", "feature"]
    title: str = Field(min_length=1, max_length=bundle_mod.TITLE_MAX_LEN)
    body: str = Field(min_length=1, max_length=bundle_mod.BODY_MAX_LEN)
    steps: str | None = Field(default=None, max_length=bundle_mod.STEPS_MAX_LEN)
    reply_to: str | None = Field(default=None, max_length=bundle_mod.REPLY_TO_MAX_LEN)
    include_diagnostics: bool = True
    client_diagnostics: dict[str, str] = {}
    screenshot: str | None = Field(default=None, max_length=bundle_mod.SCREENSHOT_B64_MAX_LEN)


class FeedbackResponse(BaseModel):
    directory: str
    report_path: str
    screenshot_path: str | None = None
    report_markdown: str  # returned verbatim so the UI can show/copy exactly what was written
    mailto_url: str | None = None  # None when no destination is set — the bundle is still on disk
    destination_email: str = ""


def _diagnostics(conn: Connection) -> dict[str, str]:
    try:
        current = MigrationContext.configure(conn).get_current_revision()
        reachable = True
    except SQLAlchemyError:
        current, reachable = None, False
    try:
        head = _head_revision()
    except Exception:
        head = None
    return diagnostics_mod.server_diagnostics(db_revision=current, db_head_revision=head, db_reachable=reachable)


@router.get("/feedback/config", response_model=FeedbackConfig)
def get_feedback_config(conn: Connection = Depends(get_connection)) -> FeedbackConfig:
    email, source = destination_mod.resolved_destination()
    return FeedbackConfig(
        destination_email=email,
        destination_source=source,
        diagnostics=_diagnostics(conn),
        feedback_dir=str(bundle_mod.feedback_root()),
    )


@router.put("/feedback/config", response_model=FeedbackConfig)
def put_feedback_config(update: FeedbackConfigUpdate, conn: Connection = Depends(get_connection)) -> FeedbackConfig:
    if update.set_destination_email:
        email = (update.destination_email or "").strip()
        if email and "@" not in email:
            raise HTTPException(status_code=422, detail="The feedback address must be a valid email address.")
        destination_mod.set_destination_email(email)
    return get_feedback_config(conn)


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
def submit_feedback(request: FeedbackRequest, conn: Connection = Depends(get_connection)) -> FeedbackResponse:
    if not request.title.strip() or not request.body.strip():
        raise HTTPException(status_code=422, detail="A title and a description are both required.")
    try:
        screenshot = bundle_mod.decode_screenshot(request.screenshot)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    report = bundle_mod.render_report(
        kind=request.kind,
        title=request.title,
        body=request.body,
        steps=request.steps,
        reply_to=request.reply_to,
        diagnostics=_diagnostics(conn) if request.include_diagnostics else None,
        client_diagnostics=(
            diagnostics_mod.clean_client_diagnostics(request.client_diagnostics)
            if request.include_diagnostics
            else None
        ),
        has_screenshot=screenshot is not None,
    )
    try:
        written = bundle_mod.write_bundle(
            kind=request.kind, title=request.title, report_markdown=report, screenshot=screenshot
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not write the report: {exc}") from exc

    email, _ = destination_mod.resolved_destination()
    return FeedbackResponse(
        directory=str(written.directory),
        report_path=str(written.report_path),
        screenshot_path=str(written.screenshot_path) if written.screenshot_path else None,
        report_markdown=written.report_markdown,
        mailto_url=bundle_mod.build_mailto_url(
            destination=email,
            kind=request.kind,
            title=request.title,
            report_markdown=report,
            directory=written.directory,
            has_screenshot=screenshot is not None,
        ),
        destination_email=email,
    )
