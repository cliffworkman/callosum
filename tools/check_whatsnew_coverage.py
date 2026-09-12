#!/usr/bin/env python3
"""Release ↔ in-app "what's new" banner drift gate (#43).

Every shipped desktop-shell version must EITHER have a what's-new banner entry (announcing its user-facing
change) OR an explicit, reasoned no-banner decline — so a release can never silently drift from the banner that
tells users what changed. Mirrors the demo/website drift-gate idiom (an explicit `--decline --note`, never a
silent bypass).

Normal (read-only, CI-safe)::

    python tools/check_whatsnew_coverage.py

Add a banner entry for a release by editing `app/frontend/whatsnew.json`'s `entries` (version → headline +
optional typed actionKind). A patch release with nothing worth announcing records an explicit silence instead::

    python tools/check_whatsnew_coverage.py --decline --note "Bug-fix release; nothing user-facing to announce."

The current desktop-shell version is read from `app/desktop-shell/src-tauri/tauri.conf.json`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHATSNEW = ROOT / "app" / "frontend" / "whatsnew.json"
TAURI_CONF = ROOT / "app" / "desktop-shell" / "src-tauri" / "tauri.conf.json"

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _current_version() -> str:
    data = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
    version = str(data.get("version", "")).strip()
    if not _SEMVER.match(version):
        raise SystemExit(f"[whatsnew] tauri.conf.json version is not a clean semver: {version!r}")
    return version


def _load() -> dict:
    return json.loads(WHATSNEW.read_text(encoding="utf-8"))


def _valid_entry(entry: object) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("headline"), str)
        and bool(entry["headline"].strip())
        and (entry.get("actionKind") is None or isinstance(entry.get("actionKind"), str))
    )


def check() -> int:
    version = _current_version()
    data = _load()
    entries = data.get("entries", {})
    no_banner = data.get("no_banner", {})

    # A malformed entry for the CURRENT version is a hard failure (the banner would silently do nothing).
    if version in entries:
        if not _valid_entry(entries[version]):
            print(f"[whatsnew] FAIL — the entry for {version} is malformed (needs a non-empty headline).")
            return 1
        print(f"[whatsnew] OK — {version} has a what's-new banner entry.")
        return 0
    if version in no_banner:
        note = (no_banner[version] or {}).get("note", "").strip()
        print(f'[whatsnew] OK — {version} explicitly ships no banner: "{note}"')
        return 0

    try:
        registry_label = str(WHATSNEW.relative_to(ROOT))
    except ValueError:  # a test may point WHATSNEW outside the repo root
        registry_label = str(WHATSNEW)
    print(
        f"[whatsnew] FAIL — desktop-shell version {version} has neither a what's-new banner entry nor a "
        f"no-banner decline.\n"
        f'  Add an entry to {registry_label} ("entries": {{"{version}": '
        f'{{"headline": "…", "actionKind": null}}}}),\n'
        f'  or record an explicit silence: python tools/check_whatsnew_coverage.py --decline --note "why".'
    )
    return 1


def decline(note: str) -> int:
    if not note.strip():
        raise SystemExit("[whatsnew] --decline requires a non-empty --note explaining the deliberate silence.")
    version = _current_version()
    data = _load()
    data.setdefault("no_banner", {})[version] = {"note": note.strip(), "at": date.today().isoformat()}
    WHATSNEW.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[whatsnew] recorded a no-banner decline for {version}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="What's-new banner release drift gate (#43).")
    parser.add_argument("--decline", action="store_true", help="Record that this version deliberately ships no banner.")
    parser.add_argument("--note", default="", help="Required with --decline: why this version ships no banner.")
    args = parser.parse_args()
    if args.decline:
        return decline(args.note)
    return check()


if __name__ == "__main__":
    sys.exit(main())
