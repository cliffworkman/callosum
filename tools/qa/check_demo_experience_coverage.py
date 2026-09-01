"""Fail when public-site capability claims drift outside the demo experience ledger."""

# ruff: noqa: E402 -- direct script execution needs the repository root on sys.path before the tools.qa import.

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.qa import changelog_drift

DEFAULT_LEDGER = ROOT / "demo" / "experience-coverage-v1.json"
SHOWCASE = ROOT / "www" / "showcase.html"
INDEX = ROOT / "www" / "index.html"

CAPABILITY_RE = re.compile(r'<a\s+class="cap"\s+id="(cap-[^"]+)"', re.IGNORECASE)
INDEX_TARGET_RE = re.compile(r'href="showcase\.html#(cap-[^"]+)"', re.IGNORECASE)
ALLOWED_STATUSES = {
    "saved-inspectable",
    "saved-partial",
    "browser-local",
    "visible-live-only",
    "external-surface",
    "scientifically-inapplicable",
    "missing-snapshot",
}


def _source_files() -> list[Path]:
    # The demo mirrors live backend endpoint *behavior* into a static snapshot, so its relevant
    # surface is the backend routers it captures from plus the capture scripts encoding what gets
    # captured -- deliberately not app/frontend/js/*.jsx, which check_website_coverage.py already
    # fingerprints for the shared UI layer.
    patterns = ("app/backend/api/routers/*.py", "tools/demo/*.py")
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in ROOT.glob(pattern) if path.is_file() and "__pycache__" not in path.parts)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def _source_fingerprint() -> str:
    return changelog_drift.fingerprint(_source_files())


def refresh(note: str, ledger_path: Path = DEFAULT_LEDGER) -> int:
    if not note.strip():
        raise SystemExit("--refresh requires a non-empty --note describing what was reviewed")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["review"] = {
        "reviewed_at": date.today().isoformat(),
        "reviewed_rev": changelog_drift.git_rev(),
        "reviewed_increment": changelog_drift.latest_increment_number(),
        "source_fingerprint": _source_fingerprint(),
        "note": note.strip(),
        # A real review supersedes any earlier decline -- clear it rather than leaving a now-dead
        # acknowledgment sitting in the registry looking like unfixed drift still remains.
        "declined_at": None,
        "declined_rev": None,
        "declined_increment": None,
        "decline_note": None,
    }
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"[demo] refreshed review receipt at {changelog_drift.git_rev()}")
    return 0


def decline(note: str, ledger_path: Path = DEFAULT_LEDGER) -> int:
    """Explicitly acknowledge known, unfixed demo drift instead of fixing it right now. Never a
    silent bypass: requires a reason, is stamped alongside (never instead of) the last real review,
    only covers drift up to the current increment, and is always printed while it's active."""
    if not note.strip():
        raise SystemExit("--decline requires a non-empty --note explaining why the drift is being left as-is")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    review = ledger.setdefault("review", {})
    review["declined_at"] = date.today().isoformat()
    review["declined_rev"] = changelog_drift.git_rev()
    review["declined_increment"] = changelog_drift.latest_increment_number()
    review["decline_note"] = note.strip()
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"[demo] recorded an explicit decline at increment {review['declined_increment']}")
    return 0


def validate(ledger_path: Path = DEFAULT_LEDGER) -> dict[str, int]:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("schema") != "callosum-demo-experience-coverage/1":
        raise ValueError("unsupported demo experience ledger schema")
    definitions = set(ledger.get("status_definitions") or {})
    if definitions != ALLOWED_STATUSES:
        raise ValueError("demo experience status definitions drifted")

    claimed = CAPABILITY_RE.findall(SHOWCASE.read_text(encoding="utf-8"))
    if len(claimed) != len(set(claimed)):
        raise ValueError("showcase capability ids must be unique")

    assigned: dict[str, tuple[str, str]] = {}
    counts = {status: 0 for status in ALLOWED_STATUSES}
    stages = ledger.get("stages") or {}
    for stage, groups in stages.items():
        for status, ids in groups.items():
            if status not in ALLOWED_STATUSES:
                raise ValueError(f"unknown demo experience status {status!r}")
            for capability_id in ids:
                if capability_id in assigned:
                    previous = assigned[capability_id]
                    raise ValueError(
                        f"{capability_id} is assigned twice: {previous[0]}/{previous[1]} and {stage}/{status}"
                    )
                assigned[capability_id] = (stage, status)
                counts[status] += 1

    missing = sorted(set(claimed) - set(assigned))
    stale = sorted(set(assigned) - set(claimed))
    if missing or stale:
        parts = []
        if missing:
            parts.append("unclassified website claims: " + ", ".join(missing))
        if stale:
            parts.append("stale ledger claims: " + ", ".join(stale))
        raise ValueError("; ".join(parts))

    index_targets = INDEX_TARGET_RE.findall(INDEX.read_text(encoding="utf-8"))
    bad_targets = sorted(set(index_targets) - set(assigned))
    if bad_targets:
        raise ValueError("homepage links target unclassified capabilities: " + ", ".join(bad_targets))

    # Grace-windowed increment check (not the website tool's zero-grace posture): this glob spans
    # most of app/backend/api/routers/, most of which has nothing to do with any one cap-*'s
    # demo-fitness, so an instant zero-grace gate here would fire on nearly every push.
    current_fingerprint = _source_fingerprint()
    staleness = changelog_drift.staleness_errors(
        ledger.get("review", {}), label="demo", current_fingerprint=current_fingerprint
    )
    if staleness:
        raise ValueError("; ".join(staleness))

    counts["total"] = len(claimed)
    counts["homepage_links"] = len(index_targets)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--refresh", action="store_true", help="record a completed demo-currency review")
    parser.add_argument(
        "--decline", action="store_true", help="explicitly acknowledge known drift without fixing it now"
    )
    parser.add_argument("--note", default="", help="required review note when --refresh or --decline is used")
    args = parser.parse_args()
    if args.refresh and args.decline:
        raise SystemExit("--refresh and --decline are mutually exclusive")
    if args.decline:
        return decline(args.note, args.ledger)
    if args.refresh:
        return refresh(args.note, args.ledger)
    counts = validate(args.ledger)
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    banner = changelog_drift.decline_banner(ledger.get("review", {}), label="demo")
    if banner:
        print(banner)
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
