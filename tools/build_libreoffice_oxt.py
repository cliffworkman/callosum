"""Build the callosum LibreOffice extension (.oxt) — inc 162.

An `.oxt` is just a zip. We assemble it from the source under `adapters/libreoffice/oxt/` (description.xml,
META-INF/manifest.xml, Addons.xcu) plus the macro/component files (`callosum_cite.py`, `callosum_addon.py`,
`composer.py`, `citations_panel.py`) that also serve as the by-hand macro install — so there's a single source
for both install routes. Pure stdlib (`zipfile`), so the backend can build it on demand to serve / install (no
Node, no shell). Every sibling module `callosum_cite.py` imports at runtime (currently `composer.py` and
`citations_panel.py`) must be listed in ENTRIES below, or a packaged install (unlike the by-hand macro, which
shares the same folder) 404s with "No module named '<name>'" the first time that code path runs.

    python tools/build_libreoffice_oxt.py        # → adapters/libreoffice/dist/callosum.oxt
"""

from __future__ import annotations

import zipfile
from pathlib import Path

ADAPTER_DIR = Path(__file__).resolve().parents[1] / "adapters" / "libreoffice"
OXT_SRC = ADAPTER_DIR / "oxt"
DEFAULT_DEST = ADAPTER_DIR / "dist" / "callosum.oxt"

# (path inside the .oxt, source file on disk) — the .py files live at the adapter root (also the by-hand macro).
ENTRIES: list[tuple[str, Path]] = [
    ("META-INF/manifest.xml", OXT_SRC / "META-INF" / "manifest.xml"),
    ("description.xml", OXT_SRC / "description.xml"),
    ("Addons.xcu", OXT_SRC / "Addons.xcu"),
    ("callosum_cite.py", ADAPTER_DIR / "callosum_cite.py"),
    ("callosum_addon.py", ADAPTER_DIR / "callosum_addon.py"),
    ("composer.py", ADAPTER_DIR / "composer.py"),
    ("citations_panel.py", ADAPTER_DIR / "citations_panel.py"),
]


def build_oxt(dest: Path | str | None = None) -> Path:
    """Zip the extension into `dest` (default `adapters/libreoffice/dist/callosum.oxt`). Returns the path."""
    target = Path(dest) if dest is not None else DEFAULT_DEST
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, src in ENTRIES:
            zf.write(src, arcname)
    return target


if __name__ == "__main__":
    out = build_oxt()
    print(f"Wrote {out} ({out.stat().st_size} bytes)")
