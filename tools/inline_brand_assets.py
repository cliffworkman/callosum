"""Re-embed the brand assets (app/media/{logo,favicon}.png) into the modular frontend
as base64 data: URIs.

The frontend has no asset-serving route, so the logo and favicon are inlined as
`data:image/png;base64,...` URIs in the source under `app/frontend/` (favicon in
`index.html`, logo in the JSX chunk that renders the sidebar brand). The serve-time
assembler emits them into the single document at `/`. Run this whenever you edit either
PNG, then hard-reload the page (Ctrl+Shift+R). Because a data: URI is content-addressed,
changing the bytes changes the icon's identity, which forces Firefox to drop its cached
favicon — no query-string cache-busting needed.

Usage:  python tools/inline_brand_assets.py
"""

from __future__ import annotations

import base64
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "app" / "frontend"

# (label, source PNG, regex with two capture groups around the data URI, candidate files)
TARGETS = [
    # Two media-query favicon links (inc 53): the browser swaps the tab icon to the OS color scheme.
    (
        "favicon light",
        ROOT / "app" / "media" / "favicon.png",
        re.compile(
            r'(<link rel="icon" type="image/png" href=")data:image/png;base64,[A-Za-z0-9+/=]*(" media="\(prefers-color-scheme: light\)")'
        ),
        [FRONTEND / "index.html"],
    ),
    (
        "favicon dark",
        ROOT / "app" / "media" / "favicon_dm.png",
        re.compile(
            r'(<link rel="icon" type="image/png" href=")data:image/png;base64,[A-Za-z0-9+/=]*(" media="\(prefers-color-scheme: dark\)")'
        ),
        [FRONTEND / "index.html"],
    ),
    # Logos are CSS background-image vars in styles.css (4 states: theme x connection), kept OUT of the
    # inline Babel script. Each keys on its unique --logo-* token name.
    (
        "logo light-off",
        ROOT / "app" / "media" / "logo.png",
        re.compile(r'(--logo-light-off: url\(")data:image/png;base64,[A-Za-z0-9+/=]*("\))'),
        [FRONTEND / "styles.css"],
    ),
    (
        "logo light-on",
        ROOT / "app" / "media" / "logo_on.png",
        re.compile(r'(--logo-light-on: url\(")data:image/png;base64,[A-Za-z0-9+/=]*("\))'),
        [FRONTEND / "styles.css"],
    ),
    (
        "logo dark-off",
        ROOT / "app" / "media" / "logo_dm.png",
        re.compile(r'(--logo-dark-off: url\(")data:image/png;base64,[A-Za-z0-9+/=]*("\))'),
        [FRONTEND / "styles.css"],
    ),
    (
        "logo dark-on",
        ROOT / "app" / "media" / "logo_dm_on.png",
        re.compile(r'(--logo-dark-on: url\(")data:image/png;base64,[A-Za-z0-9+/=]*("\))'),
        [FRONTEND / "styles.css"],
    ),
]


def main() -> int:
    changed = False
    for label, png, pattern, candidates in TARGETS:
        if not png.is_file():
            print(f"  {label}: SKIP — {png} not found")
            continue
        raw = png.read_bytes()
        uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        target = next((f for f in candidates if f.is_file() and pattern.search(f.read_text(encoding="utf-8"))), None)
        if target is None:
            print(f"  {label}: ERROR — no inlined data URI found under app/frontend/ (markup changed?)")
            return 1
        text = target.read_text(encoding="utf-8")
        match = pattern.search(text)
        old_uri = match.group(0)[len(match.group(1)) : -len(match.group(2))]
        new_text, n = pattern.subn(lambda m, uri=uri: m.group(1) + uri + m.group(2), text, count=1)
        if n != 1:
            print(f"  {label}: ERROR — expected exactly 1 match in {target.name}, found {n}")
            return 1
        sha = hashlib.sha256(raw).hexdigest()[:8]
        if old_uri == uri:
            print(f"  {label}: unchanged ({len(raw)} bytes, sha {sha}) in {target.name}")
        else:
            changed = True
            target.write_text(new_text, encoding="utf-8")
            print(f"  {label}: UPDATED ({len(raw)} bytes, sha {sha}) in {target.name}")

    if changed:
        print(
            "\nWrote frontend source. Restart the server (the assembled document is cached) "
            "and hard-reload the page (Ctrl+Shift+R) to see the new asset(s)."
        )
    else:
        print("\nNo changes — the inlined assets already match the PNGs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
