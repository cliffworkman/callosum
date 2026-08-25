"""Phase 4.1 cohort adapter for the frozen synthesis Overview battery."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

frozen = importlib.import_module("tools.qualification.overview_battery")

COHORT_PATH = frozen.PROFILE_DIR / "phase4-1-candidates.json"
FREEZE_PATH = frozen.PROFILE_DIR / "phase4-1-freeze.json"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def verify_search_freeze() -> dict[str, object]:
    frozen.verify_freeze()
    freeze = _json(FREEZE_PATH)
    expected = freeze.get("files")
    if not isinstance(expected, dict):
        raise RuntimeError("invalid Phase 4.1 freeze manifest")
    actual = {relative: _sha256(frozen.ROOT / relative) for relative in expected}
    if actual != expected or _canonical_sha256(actual) != freeze.get("aggregate_sha256"):
        raise RuntimeError("Phase 4.1 search inputs differ from their frozen manifest")
    if freeze.get("base_battery_aggregate_sha256") != frozen.verify_freeze().get("aggregate_sha256"):
        raise RuntimeError("Phase 4.1 search does not identify the current frozen base battery")
    return freeze


def cohort_candidate(code: str) -> dict[str, object]:
    for candidate in _json(COHORT_PATH)["candidates"]:
        if candidate["candidate_code"] == code:
            return candidate
    raise RuntimeError(f"unknown Phase 4.1 candidate code: {code}")


def execute(candidate_code: str, stage: str, repetitions: int, output: Path) -> None:
    search_freeze = verify_search_freeze()
    candidate = cohort_candidate(candidate_code)
    original_candidate = frozen._candidate
    frozen._candidate = lambda code: candidate if code == candidate_code else original_candidate(code)
    try:
        frozen.execute(candidate_code, stage, repetitions, output)
    finally:
        frozen._candidate = original_candidate
    payload = _json(output)
    payload["extended_search"] = {
        "search_id": "synthesis-overview-phase4-1",
        "search_aggregate_sha256": search_freeze["aggregate_sha256"],
    }
    temporary = output.with_suffix(output.suffix + ".phase41.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    temporary.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("execute", choices=["execute"])
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--stage", choices=["stage1", "stage2", "holdout", "calibration"], required=True)
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.candidate, args.stage, args.repetitions, args.output)


if __name__ == "__main__":
    main()
