"""Shared changelog/increment-aware staleness helpers for the website and demo QA coverage gates.

Used by ``tools/qa/check_website_coverage.py`` and ``tools/qa/check_demo_experience_coverage.py`` to
detect when relevant source has changed since the last explicit review, using callosum's own
increment numbering (not just raw file-content hashing, which both tools already do separately) as
the staleness clock. See CLAUDE.md's Increment workflow section for the ``.claude/changes.md`` and
``.claude/docs/increment-notes/`` conventions this reads.

Both callers follow the same recovery pattern for a failure this module reports:

    --refresh --note "..."   records a real review: fingerprint + reviewed_increment move together.
    --decline --note "..."   records an explicit, reasoned acknowledgment that known drift is not
                              being fixed right now. Never a silent bypass -- it only covers drift up
                              to the increment it was declined at, and a decline in effect is always
                              printed, never silently swallowed.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGES_MD = ROOT / ".claude" / "changes.md"
INCREMENT_NOTES_DIR = ROOT / ".claude" / "docs" / "increment-notes"

_CHANGES_HEADER_RE = re.compile(r"^## \d{4}-\d{2}-\d{2} — Increment (\d+):", re.MULTILINE)
_NOTES_FILENAME_RE = re.compile(r"^INCREMENT-(\d+)-NOTES\.md$")

# A push that both lands the source change AND bumps the increment counter must not fail against
# itself before a human has any chance to react -- this repo pushes straight to main with no PR
# gate, confirmed against .github/workflows/ci.yml. One increment's worth of same-session drift is
# tolerated for free; the next one on top of it is not.
DEFAULT_GRACE_INCREMENTS = 1


def _latest_from_changes_md() -> int:
    if not CHANGES_MD.is_file():
        return 0
    match = _CHANGES_HEADER_RE.search(CHANGES_MD.read_text(encoding="utf-8"))
    return int(match.group(1)) if match else 0


def _latest_from_increment_notes() -> int:
    numbers = []
    for path in INCREMENT_NOTES_DIR.glob("INCREMENT-*-NOTES.md"):
        match = _NOTES_FILENAME_RE.match(path.name)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers) if numbers else 0


def latest_increment_number() -> int:
    """The highest known increment number, cross-checked across both changelog sources.

    ``.claude/changes.md`` is confirmed to lag the actual increment count in practice (its entries
    are added on a human cadence, not mechanically every increment) -- trusting it alone would
    understate real drift, so this takes the max across both sources rather than either alone.
    """
    return max(_latest_from_changes_md(), _latest_from_increment_notes())


def git_rev() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() or "unknown"


def fingerprint(paths: Iterable[Path]) -> str:
    """A single combined SHA-256 over filename-length-prefixed-path + raw bytes of every file, sorted."""
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def decline_covers(review: dict) -> bool:
    """True if an active decline covers the current increment (drift up to that point is an
    explicit, acknowledged gap, not an unreviewed one). False once a new increment has landed
    beyond what the decline covered, or if there is no decline at all."""
    declined_increment = review.get("declined_increment")
    return declined_increment is not None and latest_increment_number() <= declined_increment


def staleness_errors(
    review: dict,
    *,
    label: str,
    current_fingerprint: str,
    grace_increments: int = DEFAULT_GRACE_INCREMENTS,
) -> list[str]:
    """[] if relevant content hasn't moved since the last review, or has but is still covered by an
    active decline or the increment-count grace window; otherwise one explanatory error string.

    This is the coarser, increment-count-based check (grace_increments tolerates that many
    increments' worth of unreviewed drift before failing). Fails closed when no
    ``reviewed_increment`` baseline exists at all -- a missing baseline is always treated as
    maximally stale, never a free pass. For a zero-tolerance "any drift fails" check (the website
    tool's existing content-fingerprint posture), callers should compare fingerprints directly and
    use ``decline_covers()`` alone rather than this function -- see check_website_coverage.check().
    """
    if current_fingerprint == review.get("source_fingerprint"):
        return []  # nothing in the relevant file set has actually changed since the last review

    reviewed_increment = review.get("reviewed_increment")
    if reviewed_increment is None:
        return [
            f"{label}: relevant source changed and no reviewed_increment baseline exists yet -- "
            'run --refresh --note "..." (or --decline --note "..." for a deliberate, acknowledged gap)'
        ]

    if decline_covers(review):
        return []  # covered by an active decline -- decline_banner() surfaces this separately

    latest = latest_increment_number()
    delta = latest - reviewed_increment
    if delta <= grace_increments:
        return []  # within the same-commit / same-session grace window

    return [
        f"{label}: relevant source changed and {delta} increments have passed since the last review "
        f"(reviewed at increment {reviewed_increment}, now at increment {latest}) -- inspect and "
        're-review with --refresh --note "..." or --decline --note "..." if this is a deliberate, '
        "acknowledged gap"
    ]


def decline_banner(review: dict, *, label: str) -> str | None:
    """A line to print whenever an active decline is the reason a check is passing.

    A decline must never go quietly missing from CI output just because it made the run green.
    Returns None once a new increment has landed beyond what the decline covers (staleness_errors
    will already be failing again by then, so there is nothing to announce).
    """
    declined_increment = review.get("declined_increment")
    if declined_increment is None:
        return None
    if latest_increment_number() > declined_increment:
        return None
    reviewed_increment = review.get("reviewed_increment", declined_increment)
    acknowledged = declined_increment - reviewed_increment
    note = review.get("decline_note", "")
    return (
        f'[{label}] drift declined at increment {declined_increment}: "{note}" -- '
        f"{acknowledged} increment(s) of acknowledged, unfixed drift remain"
    )
