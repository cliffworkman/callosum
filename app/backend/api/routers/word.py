"""Microsoft Word add-in (Office.js) — serve the task pane + manifest (inc 164, SP1).

Architecture A: callosum serves the task pane over HTTPS, **same-origin** with its API, so the add-in reaches the
local library with **no egress and no CORS change**. Desktop Word only (an Office task pane cannot fetch
``http://localhost`` and Word-on-the-web can't reach localhost at all). The add-in reuses the existing cite
contracts (``/papers``, ``/citations/render``); this router primarily serves the task-pane files + manifests.

**SP4 — Word on the web**: since Word-on-the-web genuinely cannot reach ``localhost``, ``manifest-web.xml`` points
the SAME task-pane files instead at callosum's existing cloudflared cite-only relay (the one the Google Docs
add-on already uses, ``adapters/googledocs/cloudflared-config.yml``, extended to also forward the 5 task-pane
GET routes). Increment 529 adds one token-gated, GET-only, privacy-minimized saved-highlight projection because
the tunnel path matcher cannot expose the existing annotations GET without also exposing POST at that path.
The task-pane JS (``taskpane.js``) detects which origin it loaded from and, only when tunneled,
attaches the Remote-access Bearer token to every fetch -- these routes themselves are unchanged either way,
since they still just serve fixed local files.

Static assets remain fixed bundled files from ``adapters/word/`` via explicit per-filename routes (no request-
derived path → no traversal). The evidence route accepts only a FastAPI integer id and returns four allowlisted
fields. office.js loads from Microsoft's CDN (the Office platform SDK), not from callosum.
**Gate before any hosted deployment** (same posture as the libreoffice/scan routes).
"""

from __future__ import annotations

import os
import subprocess
import sys

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.startup import PROJECT_ROOT
from app.backend.persistence.annotations_repo import list_annotations_for_paper
from app.backend.persistence.repository import get_paper

router = APIRouter()

WORD_DIR = PROJECT_ROOT / "adapters" / "word"
WORD_EVIDENCE_MAX = 200
WORD_EVIDENCE_QUOTE_MAX = 20_000
WORD_EVIDENCE_NOTE_MAX = 4_000

# Fixed filename → media-type allowlist. No request input reaches the path (each route passes a constant name),
# so there is no traversal surface; the allowlist is belt-and-suspenders + sets the content type Word expects.
_FILES = {
    "taskpane.html": "text/html; charset=utf-8",
    "taskpane.js": "application/javascript; charset=utf-8",
    "taskpane_core.js": "application/javascript; charset=utf-8",
    "taskpane.css": "text/css; charset=utf-8",
    "icon.png": "image/png",
}


def _serve(name: str) -> FileResponse:
    media = _FILES.get(name)
    path = WORD_DIR / name
    if media is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type=media)


def _open_with_os(path: str) -> None:
    """Open `path` (the fixed add-in folder) with the OS handler. Monkeypatched in tests — no real GUI launches."""
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606  (constant WORD_DIR; 127.0.0.1-local only)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


@router.get("/integrations/word/taskpane.html")
def word_taskpane_html() -> FileResponse:
    return _serve("taskpane.html")


@router.get("/integrations/word/taskpane.js")
def word_taskpane_js() -> FileResponse:
    return _serve("taskpane.js")


@router.get("/integrations/word/taskpane_core.js")
def word_taskpane_core_js() -> FileResponse:
    return _serve("taskpane_core.js")


@router.get("/integrations/word/taskpane.css")
def word_taskpane_css() -> FileResponse:
    return _serve("taskpane.css")


@router.get("/integrations/word/icon.png")
def word_icon() -> FileResponse:
    return _serve("icon.png")


class WordEvidenceAnnotation(BaseModel):
    """Privacy-minimized saved-highlight shape for Word's read-only evidence picker."""

    id: int
    page: int | None = None
    anchor_text: str
    note: str | None = None


@router.get("/integrations/word/evidence/{paper_id}", response_model=list[WordEvidenceAnnotation])
def word_evidence(paper_id: int, conn: Connection = Depends(get_connection)) -> list[WordEvidenceAnnotation]:
    """List author-saved evidence without exposing the annotations endpoint's write-capable tunnel path."""
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    rows = list_annotations_for_paper(conn, paper_id)
    if len(rows) > WORD_EVIDENCE_MAX:
        raise HTTPException(status_code=422, detail=f"At most {WORD_EVIDENCE_MAX} saved highlights can be listed")
    if any(
        len(row["anchor_text"] or "") > WORD_EVIDENCE_QUOTE_MAX or len(row["note"] or "") > WORD_EVIDENCE_NOTE_MAX
        for row in rows
    ):
        raise HTTPException(status_code=422, detail="A saved highlight exceeds Word's evidence display limits")
    return [
        WordEvidenceAnnotation(
            id=row["id"],
            page=row["page"],
            anchor_text=row["anchor_text"] or "",
            note=row["note"],
        )
        for row in rows
        if row["anchor_text"]
    ]


@router.get("/integrations/word/manifest.xml")
def word_manifest() -> FileResponse:
    path = WORD_DIR / "manifest.xml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="application/xml", filename="callosum-word-manifest.xml")


@router.get("/integrations/word/manifest-web.xml")
def word_manifest_web() -> FileResponse:
    # SP4: the Word-on-the-web variant, pointed at the cloudflared relay instead of localhost:8443. Fixed
    # bundled file, same allowlist-of-one shape as word_manifest above -- no request-derived path.
    path = WORD_DIR / "manifest.web.xml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="application/xml", filename="callosum-word-manifest-web.xml")


class InstallResult(BaseModel):
    opened: bool
    detail: str


@router.post("/integrations/word/install", response_model=InstallResult)
def word_install() -> InstallResult:
    # Desktop Word sideloading can't be automated, so "install" opens the folder holding manifest.xml; the user
    # registers it as a trusted catalog (Windows) / drops it in the wef folder (Mac). See adapters/word/README.md.
    folder = str(WORD_DIR)
    try:
        _open_with_os(folder)
    except Exception as exc:  # no handler / headless → degrade gracefully, never 500
        return InstallResult(
            opened=False,
            detail=f"Couldn't open the folder ({type(exc).__name__}). Use “Download manifest” and sideload it (see the README).",
        )
    return InstallResult(
        opened=True,
        detail="Opened the add-in folder — sideload manifest.xml into Word (see the setup steps in Settings / the README).",
    )
