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

import json
import os
import subprocess
import sys

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.backend.llm.providers import is_loopback_url

router = APIRouter()

# Mirrors adapters/libreoffice/callosum_cite.py's own sidecar-config contract exactly (its CONFIG_PATH + the
# {"base": ...} shape) — kept as a literal here rather than importing that adapter module, since the backend
# has no business depending on a specific word-processor client's file layout; the two simply must agree on
# the format, which this comment keeps visible to a future reader of either file.
_LIBREOFFICE_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".callosum", "libreoffice.json")


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


class SetServerUrlResult(BaseModel):
    base: str
    detail: str


@router.post("/integrations/libreoffice/set-server-url", response_model=SetServerUrlResult)
def set_libreoffice_server_url(request: Request) -> SetServerUrlResult:
    """Point the LibreOffice adapter at THIS running instance with one click, instead of asking the user to
    copy a port number into Writer's Callosum → Server URL… dialog by hand — real friction under the packaged
    desktop app, whose backend port isn't fixed across launches. Derives the base URL from the request's own
    Host header (exactly what the browser used to reach this endpoint, so it's always correct regardless of
    which port this launch actually picked), rejecting anything non-loopback so a call arriving through the
    Remote-Access tunnel can never repoint the adapter at a public tunnel host."""
    base = str(request.base_url).rstrip("/")
    if not is_loopback_url(base):
        raise HTTPException(
            status_code=422,
            detail="Refusing to point LibreOffice at a non-local address — open Callosum directly (not through a tunnel) and try again.",
        )
    os.makedirs(os.path.dirname(_LIBREOFFICE_CONFIG_PATH), exist_ok=True)
    with open(_LIBREOFFICE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"base": base}, f)
    return SetServerUrlResult(base=base, detail=f"LibreOffice will now reach Callosum at {base}.")
