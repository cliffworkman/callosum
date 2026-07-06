"""Rule #1 enforcer — the 600-line hard cap on application source.

Fails (exit 1) if any application-source file exceeds the cap, printing the offenders. "Application source" =
`.py` under `app/` or `integrations/`, and the `.jsx` frontend chunks under `app/frontend/` (the frontend chunks
count too — they live under `app/`). Exempt by rule #1: `tests/`, `tools/`, and non-code (Markdown/SQL/config/CSS)
— none of which are under `app/`/`integrations/` anyway, so the walk simply never reaches them.

Threshold: a file is a violation when it is **> 600 lines** (601+). The project holds files at "599/600" as
"at cap"; crossing the cap (601+) is the violation the historical splits (inc 91/137/214/220/226/256/262 …) all
cleared. Run standalone or from the pre-commit hook (`tools/git-hooks/pre-commit`).

Usage:  python tools/check_line_budget.py            # check, exit 1 on any violation
        python tools/check_line_budget.py --list     # also print the 10 closest-to-cap files (a watch list)
"""

from __future__ import annotations

import sys
from pathlib import Path

CAP = 600
ROOTS = (Path("app"), Path("integrations"))
SUFFIXES = (".py", ".jsx")


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def collect() -> list[tuple[int, Path]]:
    """(line_count, path) for every application-source file, largest first."""
    sizes: list[tuple[int, Path]] = []
    for root in ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix in SUFFIXES and path.is_file():
                sizes.append((_line_count(path), path))
    sizes.sort(key=lambda t: t[0], reverse=True)
    return sizes


def main(argv: list[str]) -> int:
    sizes = collect()
    violations = [(n, p) for n, p in sizes if n > CAP]
    if violations:
        print(f"[line-budget] RULE #1 VIOLATION — {len(violations)} file(s) over the {CAP}-line cap:")
        for n, p in violations:
            print(f"  {n:>4}  {p.as_posix()}")
        print("Split by concern before committing (see CLAUDE.md rule #1). Emergency bypass: git commit --no-verify.")
        return 1
    if "--list" in argv:
        print(f"[line-budget] OK — all {len(sizes)} application-source files ≤ {CAP}. Closest to the cap:")
        for n, p in sizes[:10]:
            print(f"  {n:>4}  {p.as_posix()}")
    else:
        print(f"[line-budget] OK — all {len(sizes)} application-source files within the {CAP}-line cap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
