"""Fail when public-site capability claims drift outside the demo experience ledger."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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
    counts["total"] = len(claimed)
    counts["homepage_links"] = len(index_targets)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()
    counts = validate(args.ledger)
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
