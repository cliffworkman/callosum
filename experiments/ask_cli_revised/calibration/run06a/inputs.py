"""Frozen Run 0.6 inputs + the local embedder loader for Run 0.6a (offline).

Loads and hashes the frozen Run 0.6 machine artifacts, exposes the per-source-unit representation pool used
for substitution, and loads ONLY the local all-MiniLM embedding model directly via the model registry (never
Qwen, never the full experiment runtime builder that would require a managed-local descriptor). No network,
no provider.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

FROZEN_ARTIFACTS = ("02_candidates.json", "03_selection.json", "04_frozen_decompositions.json")
RICH_CASES = ("q_aib", "q_depr", "q_builtenv")
STYLES = ("minimal", "relation", "multi", "baseline")


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


def load_frozen(run06_dir: str | Path) -> dict:
    root = Path(run06_dir)
    data = {name: json.loads((root / name).read_text(encoding="utf-8")) for name in FROZEN_ARTIFACTS}
    hashes = {name: sha256_file(root / name) for name in FROZEN_ARTIFACTS}
    return {"dir": str(root), "data": data, "hashes": hashes, "dir_digest": dir_digest(root)}


def load_embedder():
    """Load the local all-MiniLM embedding model directly (the runtime.py lines minus Qwen resolution)."""
    from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, DEFAULT_NORMALIZATION
    from app.backend.model_runtime import PINNED_MODEL_REVISIONS, ModelRuntimeRegistry

    registry = ModelRuntimeRegistry()
    model = registry.get_embedding_model(
        name=DEFAULT_EMBEDDING_MODEL,
        normalization=DEFAULT_NORMALIZATION,
        revision=PINNED_MODEL_REVISIONS.get(DEFAULT_EMBEDDING_MODEL),
    )
    return registry, model, f"{model.name}:{model.version}"


def _sls_map(candidate_entry: dict) -> dict[str, float]:
    return {d["item_id"]: d["source_local_similarity"] for d in candidate_entry["audit"].get("source_local_drift", [])}


def representation(frozen: dict, case: str, style: str, source_unit_id: str) -> dict | None:
    """The frozen {style} representation of one source unit: its item(s) + per-item source-local similarity.

    A representation is an ORDERED item-set (minimal/relation/baseline → 1 item; multi → a bundle of ≥1).
    """
    entry = frozen["data"]["02_candidates.json"][case]["candidates"][style]
    sls = _sls_map(entry)
    items = [dict(i) for i in entry["items"] if i["source_unit_id"] == source_unit_id]
    if not items:
        return None
    for i in items:
        i["source_local_similarity"] = sls.get(i["item_id"])
    return {"style": style, "source_unit_id": source_unit_id, "items": items}


def all_representations(frozen: dict, case: str, source_unit_id: str) -> dict[str, dict]:
    """Every frozen same-unit representation (the substitution pool for that unit)."""
    out = {}
    for style in STYLES:
        rep = representation(frozen, case, style, source_unit_id)
        if rep is not None:
            out[style] = rep
    return out


def worst_sls(representation_items: list[dict]) -> float:
    """Worst (min) source-local similarity across a representation's item(s). HIGHER is better."""
    vals = [i["source_local_similarity"] for i in representation_items if i.get("source_local_similarity") is not None]
    return min(vals) if vals else 0.0


def source_units(frozen: dict, case: str) -> list[dict]:
    return frozen["data"]["02_candidates.json"][case]["units"]


def frozen_selection(frozen: dict, case: str) -> dict:
    """The Run 0.6 H0 frozen decomposition for a case (items + selected_candidate + hash)."""
    return frozen["data"]["04_frozen_decompositions.json"][case]
