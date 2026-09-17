"""Read the completed local Stage-0 dossier; never research, download, or reclassify."""

from pathlib import Path

from .contracts import ContractError
from .hashing import file_hash, read_json

FILES = (
    "REPORT_STAGE0.md",
    "candidate_manifest.json",
    "future_preflight_spec.json",
    "license_matrix.json",
    "runtime_compatibility.json",
    "memory_estimates.json",
    "validation_receipt.json",
    "artifact_hashes.json",
)
EXPECTED_DISPOSITIONS = {
    "qwen25_15": "ELIGIBLE",
    "qwen3_17": "UNKNOWN_REQUIRES_PREFLIGHT",
    "qwen3_4": "UNKNOWN_REQUIRES_PREFLIGHT",
    "phi4_mini": "UNKNOWN_REQUIRES_PREFLIGHT",
    "gemma3_4": "ELIGIBLE_WITH_CONSTRAINTS",
    "llama32_3": "ELIGIBLE_WITH_CONSTRAINTS",
    "ministral3_3": "UNKNOWN_REQUIRES_PREFLIGHT",
    "qwen3_8": "ELIGIBLE_WITH_CONSTRAINTS",
    "ministral3_8": "ELIGIBLE_WITH_CONSTRAINTS",
    "qwen3_14": "ELIGIBLE_WITH_CONSTRAINTS",
    "gemma3_12": "ELIGIBLE_WITH_CONSTRAINTS",
    "phi4_14": "ELIGIBLE_WITH_CONSTRAINTS",
}


def roster(dossier):
    dossier = Path(dossier)
    validation = read_json(dossier / "validation_receipt.json")
    for name, expected in validation["generated_file_sha256"].items():
        if file_hash(dossier / name) != expected:
            raise ContractError("STAGE0_DOSSIER_HASH_MISMATCH:" + name)
    candidates = read_json(dossier / "candidate_manifest.json")["models"]
    if {m["id"]: m["stage0_verdict"] for m in candidates} != EXPECTED_DISPOSITIONS:
        raise ContractError("STAGE0_DISPOSITION_CONFLICT")
    profiles = {m["id"]: m for m in read_json(dossier / "future_preflight_spec.json")["models"]}
    licenses = {m["id"]: m for m in read_json(dossier / "license_matrix.json")["models"]}
    runtimes = {m["id"]: m for m in read_json(dossier / "runtime_compatibility.json")["models"]}
    result = []
    for candidate in candidates:
        cid = candidate["id"]
        if candidate["primary_artifact"] != profiles[cid]["artifact"]:
            raise ContractError("STAGE0_ARTIFACT_PROFILE_CONFLICT")
        result.append(
            {
                "candidate": candidate,
                "runtime_preflight_specification": profiles[cid],
                "license": licenses[cid],
                "runtime_compatibility": runtimes[cid],
                "local_weight_hash_status": "HASH_REQUIRES_PREFLIGHT_DOWNLOAD",
                "empirical_preflight_status": "NOT_RUN",
                "quantization_selection": "primary artifact from Stage-0; no semantic selection",
                "semantic_thinking_policy": "REQUIRED_FINAL_FREEZE_VALUE"
                if cid.startswith("qwen3_")
                else "NOT_APPLICABLE",
            }
        )
    return {
        "version": 1,
        "source_hashes": {name: file_hash(dossier / name) for name in FILES},
        "models": result,
        "source_status_preserved": True,
        "primary_count": 12,
        "no_paper_ineligible": True,
        "local_hashes_not_inferred_from_remote_metadata": True,
    }
