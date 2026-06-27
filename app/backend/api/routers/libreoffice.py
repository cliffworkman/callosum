"""LibreOffice plugin install/download endpoints (inc 162).

Makes the LibreOffice citation extension installable from callosum's own Settings (like Zotero/Mendeley install
their word-processor plugin from the desktop app), so the user never hunts through Tools → Macros. Two routes:

  * ``GET  /integrations/libreoffice/plugin.oxt`` — builds the `.oxt` on demand and serves it as a download.
  * ``POST /integrations/libreoffice/install``   — builds it and opens it with the OS handler, so LibreOffice's
    Extension Manager pops up for the user to confirm + restart Writer.

Local-only: the server (127.0.0.1, the user's machine) opens a FIXED bundled artifact — no request input reaches
the path, so there is no traversal/injection. **Gate before any hosted deployment** (a server that launches a
desktop app or serves files is fine on localhost, dangerous when remote). No egress; no secrets.
"""

from __future__ import annotations

import os
import subprocess
import sys

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()


def _build_oxt() -> str:
    # tools/ is a build helper, imported lazily so app startup never depends on it.
    from tools.build_libreoffice_oxt import build_oxt

    return str(build_oxt())


def _open_with_os(path: str) -> None:
    """Open `path` with the OS's default handler (a fixed .oxt → LibreOffice's Extension Manager). Monkeypatched
    in tests so no real process/GUI launches."""
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606  (fixed bundled artifact path; 127.0.0.1-local only)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class InstallResult(BaseModel):
    opened: bool
    detail: str


@router.get("/integrations/libreoffice/plugin.oxt")
def download_plugin() -> FileResponse:
    path = _build_oxt()
    return FileResponse(path, media_type="application/vnd.sun.star.package-bundle", filename="callosum.oxt")


@router.post("/integrations/libreoffice/install", response_model=InstallResult)
def install_plugin() -> InstallResult:
    path = _build_oxt()
    try:
        _open_with_os(path)
    except Exception as exc:  # no handler / headless → degrade to the download route, never 500
        return InstallResult(
            opened=False,
            detail=f"Couldn't open it automatically ({type(exc).__name__}). Use “Download .oxt” and double-click it.",
        )
    return InstallResult(
        opened=True,
        detail="Opening LibreOffice's Extension Manager — click Install, then restart Writer.",
    )
