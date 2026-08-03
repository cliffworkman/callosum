"""Run the ratcheted Bandit gate with an OS-native copy of its baseline.

Bandit compares findings using the filename string verbatim. A baseline generated
on Windows therefore uses backslashes and otherwise fails to suppress the same
reviewed findings on Linux CI. Normalize only stored filenames into a temporary
baseline; findings, rules, severities, and scan targets remain unchanged.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".bandit-baseline.json"
TARGETS = ("app/backend", "integrations", "sync_server", "feedback_relay")


def _native_path(value: str) -> str:
    # Bandit preserves the target prefix exactly as passed (``app/backend``)
    # and joins only its descendants with the host separator. The committed
    # baseline already has that mixed Windows form, so Windows needs no edit.
    return value.replace("\\", "/") if os.sep == "/" else value


def normalized_baseline() -> dict:
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    for result in data.get("results", []):
        if isinstance(result.get("filename"), str):
            result["filename"] = _native_path(result["filename"])
    metrics = data.get("metrics")
    if isinstance(metrics, dict):
        data["metrics"] = {key if key == "_totals" else _native_path(key): value for key, value in metrics.items()}
    return data


def main() -> int:
    scratch = ROOT / ".local"
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="bandit-baseline-", dir=scratch) as temp_dir:
        baseline = Path(temp_dir) / "baseline.json"
        baseline.write_text(json.dumps(normalized_baseline()), encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "bandit",
            "-q",
            "-c",
            "pyproject.toml",
            "-b",
            str(baseline),
            "-r",
            *TARGETS,
        ]
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        return subprocess.run(command, cwd=ROOT, env=environment, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
