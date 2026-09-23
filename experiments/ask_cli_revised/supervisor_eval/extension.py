"""Post-hoc, predeclared same-family scale extension to the (frozen, immutable) first tranche.

The first tranche ended "four candidates, none qualified". After observing it, one narrow follow-up was declared
before running: does more Gemma capacity (`gemma3:12b` -> `gemma3:27b`) keep 12B's recall/recovery while fixing its
discrimination failures? This module holds only what that needs, kept OUT of the frozen files on purpose:

  * the one added candidate identity (not in `models.CANDIDATES`, so the first tranche never reads as if it took part);
  * the helpers that turn what the runtime observed into a text-safe receipt block.

It defines no envelope, prompt, schema, gate or reasoning override: the candidate runs `models.ENVELOPE` and the
frozen battery exactly as `gemma3:12b` did. `extension.py` is deliberately not in `build_battery.FROZEN_CODE`.
"""

import json
from pathlib import Path

from experiments.ask_cli_revised.supervisor_eval import models

FIRST_TRANCHE_FREEZE_COMMIT = "3d12610d"
FIRST_TRANCHE_RESULTS_COMMIT = "87e3d7c3"

CANDIDATES = [
    {
        "key": "gemma3-27b",
        "tag": "gemma3:27b",
        "think_level": None,
        "size_gb": 17.4,
        "size_gb_note": "pre-run registry estimate, used only for the store-headroom check; not model metadata",
    },
]


def artifact_identity(entry):
    """Durable artifact identity = what `/api/tags` observed (digest, size). Absent, never guessed."""
    if not entry or "digest" not in entry or "size" not in entry:
        return None
    return {"digest": entry["digest"], "size_bytes": entry["size"]}


def capture_artifact(client, tag):
    entry = next((m for m in client.tags() if m["name"] in (tag, f"{tag}:latest")), None)
    return artifact_identity(entry)


def extension_block(freeze_path, artifact):
    frozen = json.loads(Path(freeze_path).read_text(encoding="utf-8"))
    return {
        "kind": "post-hoc, predeclared same-family scale extension, run after the first tranche's results were observed",
        "extension_of": "first-tranche",
        "first_tranche_freeze_commit": FIRST_TRANCHE_FREEZE_COMMIT,
        "first_tranche_results_commit": FIRST_TRANCHE_RESULTS_COMMIT,
        "freeze_sha256": frozen["freeze_sha256"],
        "battery_manifest_sha256": frozen["json"]["battery_manifest"],
        "private_battery_sha256": frozen["private_files"]["battery.private.json"],
        "envelope": dict(models.ENVELOPE),
        "artifact": artifact,
    }
