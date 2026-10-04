"""The replay-only, hash-bound decomposition overlay (Phase-30 D2). Pure loader and validator.

The overlay is the ONLY source of visible labels, literal confirmed wording, facet/role display phrases, and requested
construct terms. The answer layer never derives a question from runtime logic. Validation refuses any overlay that does
not cover exactly the children present in the preserved sufficiency map, or that cites a human-review obligation the
frozen contract does not record as human-review.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

OVERLAY_STATUS = "REPLAY_ONLY_OFFLINE_OVERLAY"
DEFAULT_OVERLAY_PATH = Path(__file__).parent / "overlays" / "phase30_replay_decomposition_overlay.json"


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_obj(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_overlay(path: Path = DEFAULT_OVERLAY_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def overlay_sha256(overlay: dict) -> str:
    return sha256_obj(overlay)


def validate_overlay(overlay: dict, smap: dict, frozen_contract: dict) -> list[str]:
    """Every problem found, as human-readable strings. Empty list means the overlay is usable."""
    problems: list[str] = []
    if overlay.get("status") != OVERLAY_STATUS:
        problems.append("overlay status must be REPLAY_ONLY_OFFLINE_OVERLAY")
    if overlay.get("postdates_phase28_attempt2_live_run") is not True:
        problems.append("overlay must record that its confirmation postdates the Phase-28 Attempt-2 live run")
    nodes = overlay.get("nodes") or []
    labels = [node.get("label") for node in nodes]
    if not nodes or len(set(labels)) != len(labels):
        problems.append("nodes must be non-empty with unique labels")
    owned: dict[str, str] = {}
    for node in nodes:
        label = node.get("label")
        if not str(node.get("literal_text") or "").strip():
            problems.append(f"node {label}: literal confirmed wording is empty")
        if node.get("parent") is not None and node["parent"] not in labels:
            problems.append(f"node {label}: parent {node['parent']!r} is not a node")
        for child in node.get("owning_child_ids") or []:
            if child not in smap:
                problems.append(f"node {label}: child {child} is not in the sufficiency map")
            if child in owned:
                problems.append(f"child {child} is owned by both {owned[child]} and {label}")
            owned[child] = label
        for obligation in node.get("human_review_obligations") or []:
            entry = (frozen_contract.get("requirements") or {}).get(obligation)
            if entry is None or entry.get("class") != "human_review_meaning":
                problems.append(f"node {label}: obligation {obligation} is not a recorded human-review meaning")
    for child in smap:
        if child not in owned and child not in {
            c for kids in (overlay.get("folded_child_ids") or {}).values() for c in kids
        }:
            problems.append(f"child {child} is in the sufficiency map but owned by no node and not folded")
    facet_phrases = overlay.get("facet_phrases") or {}
    role_phrases = overlay.get("role_phrases") or {}
    for child in owned:
        for requirement in smap[child]["requirements"]:
            if requirement["id"] not in facet_phrases:
                problems.append(f"no facet phrase for {requirement['id']}")
            for role in requirement["role_completion"]["required_roles"]:
                if role not in role_phrases:
                    problems.append(f"no role phrase for {role}")
    if not overlay.get("requested_construct_terms"):
        problems.append("requested construct terms are required (Phase-30 D7)")
    return problems


def node_owning(overlay: dict) -> dict[str, dict]:
    """child id -> the overlay node that owns it."""
    out: dict[str, dict] = {}
    for node in overlay["nodes"]:
        for child in node["owning_child_ids"]:
            out[child] = node
    return out
