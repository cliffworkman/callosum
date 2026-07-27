"""Stage the real callosum source tree into app/desktop-shell/resources/callosum-src/ for bundling.

Run this AFTER `npm install && python tools/build_frontend.py` at the project root, so the shipped
bundle carries the prebuilt `callosum-app.html` and never needs Node at runtime (the same
"server stays Python-only" convention the dev app already follows).

Usage: python app/desktop-shell/packaging/stage_source.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEST = PROJECT_ROOT / "app" / "desktop-shell" / "resources" / "callosum-src"

# Top-level packages app/backend actually imports at runtime (confirmed by grepping for
# `from <pkg>.` across app/backend + integrations — only `integrations` turned up; adapters/
# mcp_server/ops/research/sync_server/www are dev/adapter-only and never imported from here).
# A real run against a packaged build caught `integrations` missing on the first try
# (ModuleNotFoundError at import time) — this list is verification-derived, not a guess.
TOP_LEVEL_DIRS = ["app/backend", "alembic", "integrations"]
FILES = ["alembic.ini", "callosum-app.html"]


def _copy_dir(rel: str) -> None:
    src = PROJECT_ROOT / rel
    dest = DEST / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def main() -> None:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    # app/__init__.py alongside app/backend/ — mirror the real package layout exactly.
    (DEST / "app").mkdir(exist_ok=True)
    app_init = PROJECT_ROOT / "app" / "__init__.py"
    if app_init.exists():
        shutil.copy2(app_init, DEST / "app" / "__init__.py")

    for rel in TOP_LEVEL_DIRS:
        _copy_dir(rel)

    for rel in FILES:
        src = PROJECT_ROOT / rel
        if not src.is_file():
            raise SystemExit(
                f"missing {rel} — run `npm install && python tools/build_frontend.py` first"
                if rel == "callosum-app.html"
                else f"missing required file: {rel}"
            )
        shutil.copy2(src, DEST / rel)

    print(f"staged callosum source into {DEST}")


if __name__ == "__main__":
    main()
