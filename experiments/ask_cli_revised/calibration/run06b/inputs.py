"""Phase-0 freeze: hash the frozen baseline inputs and record the exact model/runtime identity.

The baseline directory and every file this experiment reads out of it are hashed BEFORE any Qwen
inference, so the report can prove the dataset was constructed only from frozen prior-run material and
never changed after inference started. The model/runtime identity receipt reads the managed-local
descriptor (the only place the GGUF revision / byte size / observed GPU execution live — they are not in
code) plus the resolved config's stable fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

# The completed revised Ask CLI AIB baseline that exposed the old select_evidence/form_claim boundary.
BASELINE_RUN_DIR = ROOT / "experiments" / "ask_cli_revised" / "runs" / "revised-20260907T211542Z"

# Fail-closed model pin (asserted at provider resolution too; recorded here for the receipt).
EXPECTED_MODEL_DIGEST = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"

# The frozen artifacts this experiment actually parses to build its dataset. Hashing exactly these (plus a
# whole-directory digest) documents the read surface without claiming to touch files it never opens.
BASELINE_FILES = (
    "00_question.json",
    "01_decomposition.json",
    "08_evidence_packets.jsonl",
    "09_propositions.jsonl",
    "10_verification.jsonl",
    "decisions.jsonl",
    "qwen_calls.jsonl",
    "15_run_manifest.json",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dir_digest(root: Path) -> str:
    """Order-stable digest over every file in a directory (name + bytes) — proves nothing changed."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def baseline_input_receipt(baseline_dir: Path | None = None) -> dict:
    """Hashes of the exact frozen files parsed, plus a whole-directory digest of the baseline run."""
    root = Path(baseline_dir) if baseline_dir is not None else BASELINE_RUN_DIR
    if not root.is_dir():
        raise FileNotFoundError(f"frozen baseline run directory not found: {root}")
    file_hashes = {name: sha256_file(root / name) for name in BASELINE_FILES if (root / name).is_file()}
    missing = [name for name in BASELINE_FILES if not (root / name).is_file()]
    return {
        "baseline_run_dir": str(root),
        "baseline_files_hashed": file_hashes,
        "baseline_files_missing": missing,
        "baseline_dir_digest": dir_digest(root),
    }


def _managed_local_descriptor() -> dict | None:
    """Read the managed-local descriptor (target.json) if CALLOSUM_APP_DATA_DIR is set and it exists.

    This is the only place the GGUF revision, byte size, and observed GPU execution are recorded; the code
    pins only the model artifact digest. Returns None if unreadable rather than failing — build_runtime has
    already fail-closed on the pin by the time this is called, so a missing descriptor here is informational.
    """
    app_data = os.environ.get("CALLOSUM_APP_DATA_DIR")
    if not app_data:
        return None
    path = Path(app_data) / "managed-local-ai" / "target.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def identity_receipt(qwen_config: object) -> dict:
    """Model/runtime identity: descriptor digest + revision/size/execution + the config's stable fingerprint.

    ``digest_ok`` records whether the descriptor's model artifact digest matches the code pin. It should
    always be True here (build_runtime fail-closes otherwise); recording it makes the receipt self-verifying.
    """
    descriptor = _managed_local_descriptor()
    fingerprint = getattr(qwen_config, "stable_identity_fingerprint", None)
    model_alias = getattr(qwen_config, "model", None)
    max_output_tokens = getattr(qwen_config, "max_output_tokens", None)
    receipt: dict = {
        "expected_model_digest": EXPECTED_MODEL_DIGEST,
        "config_model_alias": model_alias,
        "config_max_output_tokens": max_output_tokens,
        "stable_identity_fingerprint": fingerprint,
        "descriptor_present": descriptor is not None,
    }
    if descriptor is not None:
        digest = descriptor.get("model_artifact_digest")
        receipt.update(
            {
                "descriptor_model_artifact_digest": digest,
                "digest_ok": digest == EXPECTED_MODEL_DIGEST,
                "descriptor_model_artifact_revision": descriptor.get("model_artifact_revision"),
                "descriptor_model_artifact_bytes": descriptor.get("model_artifact_bytes"),
                "descriptor_context_tokens": descriptor.get("context_tokens"),
                "descriptor_output_tokens": descriptor.get("output_tokens"),
                "descriptor_temperature": descriptor.get("temperature"),
                "descriptor_seed": descriptor.get("seed"),
                "descriptor_runtime_family": descriptor.get("runtime_family"),
                "descriptor_declared_build_backend": descriptor.get("declared_build_backend"),
                "descriptor_observed_execution": descriptor.get("observed_execution"),
            }
        )
    return receipt
