#!/usr/bin/env python3
"""Bump the desktop-shell version across the five files that must move in lockstep.

Usage:
    python tools/bump_version.py X.Y.Z            # apply the bump
    python tools/bump_version.py X.Y.Z --dry-run  # show the diff, write nothing

Background (backlog GitHub issue "release version bump", legacy #80): a release
bump touches five hand-edited files, and a naive find-and-replace is unsafe —
`package-lock.json` carries the version as *two* self-references (and a dependency
could coincidentally match it), and `Cargo.lock` has a *second* crate that happens
to sit at the same version as `callosum-shell`. This tool edits exactly the right
spots, refuses (nonzero exit, no writes) on any unexpected occurrence count or on a
result that no longer parses as JSON/TOML, and prints a unified diff.

The five files and their expected edit counts, all keyed off the *current* version
read from tauri.conf.json (the source of truth):

  app/desktop-shell/src-tauri/tauri.conf.json   1x  top-level "version"
  app/desktop-shell/package.json                1x  top-level "version"
  app/desktop-shell/src-tauri/Cargo.toml        1x  [package] version
  app/desktop-shell/package-lock.json           2x  root + packages[""] self-refs
  app/desktop-shell/src-tauri/Cargo.lock        1x  the callosum-shell stanza only

pyproject.toml is deliberately NOT touched — it is inert Python-package metadata
with its own lifecycle, unrelated to the desktop shell (see CLAUDE.md's release flow).
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "app" / "desktop-shell"
SOURCE_OF_TRUTH = DS / "src-tauri" / "tauri.conf.json"

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


@dataclass
class Rule:
    path: Path
    kind: str  # "json" | "toml" — how to validate the result
    expected: int
    pattern: re.Pattern
    repl: Callable[[re.Match], str]


def build_rules(old: str, new: str) -> list[Rule]:
    o = re.escape(old)
    ver = lambda m: f'"version": "{new}"'  # noqa: E731 (small local repl helpers)
    return [
        Rule(DS / "src-tauri" / "tauri.conf.json", "json", 1, re.compile(rf'"version": "{o}"'), ver),
        Rule(DS / "package.json", "json", 1, re.compile(rf'"version": "{o}"'), ver),
        Rule(
            DS / "src-tauri" / "Cargo.toml",
            "toml",
            1,
            re.compile(rf'(?m)^version = "{o}"'),
            lambda m: f'version = "{new}"',
        ),
        Rule(DS / "package-lock.json", "json", 2, re.compile(rf'"version": "{o}"'), ver),
        # Anchor to the callosum-shell name line so a coincidental same-version
        # dependency crate is never touched. Groups: 1=name+newline+prefix, 3=trailing quote.
        Rule(
            DS / "src-tauri" / "Cargo.lock",
            "toml",
            1,
            re.compile(rf'(name = "callosum-shell"\r?\nversion = ")({o})(")'),
            lambda m: m.group(1) + new + m.group(3),
        ),
    ]


def fail(msg: str) -> None:
    print(f"bump_version: refusing - {msg}", file=sys.stderr)
    sys.exit(1)


def read(path: Path) -> str:
    # newline="" preserves the files' CRLF endings so the diff/write stay minimal.
    # (open(), not Path.read_text(newline=...), which is Python 3.13+ only.)
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def current_version() -> str:
    try:
        data = json.loads(read(SOURCE_OF_TRUTH))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"could not read the current version from {SOURCE_OF_TRUTH.relative_to(ROOT)}: {exc}")
    ver = data.get("version")
    if not isinstance(ver, str) or not SEMVER.match(ver):
        fail(f"{SOURCE_OF_TRUTH.relative_to(ROOT)} has no valid top-level version field")
    return ver


def main() -> None:
    # Never let a stray non-cp1252 char in a printed diff line crash the tool on a
    # Windows console (the class of bug behind commit 6b4b8d9); replace, don't die.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(description="Bump the desktop-shell version in lockstep across five files.")
    ap.add_argument("version", help="the new version, e.g. 0.5.9 (optional -prerelease suffix allowed)")
    ap.add_argument("--dry-run", action="store_true", help="print the diff but write nothing")
    args = ap.parse_args()

    new = args.version.lstrip("v")
    if not SEMVER.match(new):
        fail(f"{new!r} is not a valid version (expected X.Y.Z with an optional -prerelease suffix)")

    old = current_version()
    if new == old:
        fail(f"already at {old}; nothing to do")

    # Phase 1: verify every file, compute its new content, validate it parses.
    # Nothing is written until all five pass — a partial bump is exactly the bug.
    edits: list[tuple[Rule, str, str]] = []  # (rule, old_text, new_text)
    for rule in build_rules(old, new):
        rel = rule.path.relative_to(ROOT)
        if not rule.path.exists():
            fail(f"{rel} does not exist")
        text = read(rule.path)
        found = len(rule.pattern.findall(text))
        if found != rule.expected:
            fail(
                f"{rel}: expected {rule.expected} occurrence(s) of version {old}, found {found}. "
                "The files may be inconsistent (a half-done bump?); resolve by hand."
            )
        new_text = rule.pattern.sub(rule.repl, text)
        try:
            if rule.kind == "json":
                json.loads(new_text)
            else:
                tomllib.loads(new_text)
        except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
            fail(f"{rel}: result no longer parses as {rule.kind.upper()} ({exc}); no files written")
        edits.append((rule, text, new_text))

    # Phase 2: show the diff.
    print(f"Bumping desktop-shell version: {old} -> {new}\n")
    for rule, old_text, new_text in edits:
        rel = str(rule.path.relative_to(ROOT)).replace("\\", "/")
        diff = difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
        )
        for line in diff:
            print(line)
        print()

    if args.dry_run:
        print("--dry-run: no files written.")
        return

    # Phase 3: write.
    for rule, _old_text, new_text in edits:
        with open(rule.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_text)
    print(
        f"Wrote {len(edits)} files. Next: commit, push, confirm CI is green, then tag v{new} "
        "(see CLAUDE.md's release flow)."
    )


if __name__ == "__main__":
    main()
