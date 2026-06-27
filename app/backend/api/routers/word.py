"""Microsoft Word add-in (Office.js) — serve the task pane + manifest (inc 164, SP1).

Architecture A: callosum serves the task pane over HTTPS, **same-origin** with its API, so the add-in reaches the
local library with **no egress and no CORS change**. Desktop Word only (an Office task pane cannot fetch
``http://localhost`` and Word-on-the-web can't reach localhost at all). The add-in reuses the existing cite
contracts (``/papers``, ``/citations/render``); these routes only serve the static task-pane files + the manifest.

Local-only: every route serves a **fixed** bundled file from ``adapters/word/`` via an explicit per-filename route
(no request-derived path → no traversal). office.js loads from Microsoft's CDN (the Office platform SDK), not from
callosum — no library egress. **Gate before any hosted deployment** (same posture as the libreoffice/scan routes).
"""

from __future__ import annotations

import os
import subprocess
import sys

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.backend.api.startup import PROJECT_ROOT

router = APIRouter()

WORD_DIR = PROJECT_ROOT / "adapters" / "word"

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


@router.get("/integrations/word/manifest.xml")
def word_manifest() -> FileResponse:
    path = WORD_DIR / "manifest.xml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="application/xml", filename="callosum-word-manifest.xml")


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
