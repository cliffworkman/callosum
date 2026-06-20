"""Rebuild the single-file frontend (callosum-app.html) from the modular source.

The source of truth is `app/frontend/` (`index.html` shell + `styles.css` + ordered
`js/*.jsx`). The running server assembles those on the fly, but this writes the assembled
result to `callosum-app.html` at the project root as well — a generated artifact that keeps
file-based frontend testing (which expects that particular file) working, and that the server
serves by default when present.

Run this after editing anything under `app/frontend/`:

    python tools/build_frontend.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api.frontend import (  # noqa: E402  (after sys.path setup)
    build_frontend_document,
    frontend_sources_available,
)

OUT = ROOT / "callosum-app.html"


def main() -> int:
    if not frontend_sources_available():
        print("ERROR: frontend source not found under app/frontend/")
        return 1
    document = build_frontend_document()
    OUT.write_text(document, encoding="utf-8")
    print(f"Wrote {OUT} ({document.count(chr(10)) + 1} lines, {len(document)} bytes) from app/frontend/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
