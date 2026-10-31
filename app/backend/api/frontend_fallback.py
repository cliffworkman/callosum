"""Frontend-shell fallbacks for ``create_app``: where the served HTML comes from, and the honest page shown when it
is missing. Moved verbatim out of ``api/app.py`` (inc 615) to keep that file under the 600-line cap."""

from __future__ import annotations

import os
from html import escape
from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse

from app.backend.api.frontend import FRONTEND_DIR

FRONTEND_PATH_ENV = "CALLOSUM_FRONTEND_PATH"


def resolve_frontend_path(frontend_path: str | Path | None) -> Path | None:
    # An explicit path (arg or CALLOSUM_FRONTEND_PATH) serves a single prebuilt file;
    # None means "assemble the modular source under app/frontend/ at serve time".
    configured = frontend_path or os.environ.get(FRONTEND_PATH_ENV)
    return Path(configured) if configured else None


def assembly_unavailable_response() -> HTMLResponse:
    expected = escape(str(FRONTEND_DIR))
    env_name = escape(FRONTEND_PATH_ENV)
    return HTMLResponse(
        content=(
            "<!doctype html><html><head><title>Callosum frontend not found</title></head>"
            "<body>"
            "<h1>Callosum frontend source not found</h1>"
            f"<p>The API is running, but the frontend source was not found at <code>{expected}</code>.</p>"
            f"<p>Reinstall the app, or set <code>{env_name}</code> to a prebuilt single-file frontend.</p>"
            "</body></html>"
        ),
        status_code=200,
    )


def frontend_response(frontend_path: Path) -> FileResponse | HTMLResponse:
    if frontend_path.is_file():
        return FileResponse(frontend_path, media_type="text/html")
    expected = escape(str(frontend_path))
    env_name = escape(FRONTEND_PATH_ENV)
    return HTMLResponse(
        content=(
            "<!doctype html><html><head><title>Callosum frontend not found</title></head>"
            "<body>"
            "<h1>Callosum frontend file not found</h1>"
            f"<p>The API is running, but no frontend HTML file was found at <code>{expected}</code>.</p>"
            f"<p>Set <code>{env_name}</code> to the path of <code>callosum-app.html</code>, "
            "or place the file at the default repository-root location.</p>"
            "</body></html>"
        ),
        status_code=200,
    )
