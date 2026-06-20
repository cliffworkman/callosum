"""Serve-time assembly of the modular frontend into a single self-contained document.

The frontend source lives under `app/frontend/` (a shell template + one CSS file + ordered
`js/*.jsx` chunks). This assembles them into ONE document served at `/` — preserving the
project's single-file-to-the-browser, no-build-step, no-extra-file-serving-surface guarantees:
the JSX chunks are concatenated (no module boundaries) into the single `<script type="text/babel">`,
so their shared global scope is identical to the former hand-maintained `callosum-app.html`.
Only project-owned files are read; the result is cached after the first build.
"""

from __future__ import annotations

from app.backend.api.startup import PROJECT_ROOT

FRONTEND_DIR = PROJECT_ROOT / "app" / "frontend"

_cache: str | None = None


def frontend_sources_available() -> bool:
    return (FRONTEND_DIR / "index.html").is_file() and (FRONTEND_DIR / "js").is_dir()


def build_frontend_document() -> str:
    """Assemble (and cache) index.html + styles.css + ordered js/*.jsx into one HTML string."""
    global _cache
    if _cache is not None:
        return _cache
    template = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    styles = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
    # Sorted by filename so the numeric prefixes (00_, 10_, …) fix definition order: every
    # top-level const/function must be defined before App uses it (one shared script scope).
    script = "".join(path.read_text(encoding="utf-8") for path in sorted((FRONTEND_DIR / "js").glob("*.jsx")))
    _cache = template.replace("{{STYLES}}", styles).replace("{{SCRIPT}}", script)
    return _cache
