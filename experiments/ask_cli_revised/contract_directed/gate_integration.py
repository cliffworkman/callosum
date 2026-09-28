"""Offline replay/integration of the c9+c11 vertical slice's already-produced Gate 1 and Gate 2 artifacts
(2026-09-27).

**This is a REPLAY of saved stage results, not a fresh live E2E run.** No model, NLI, embedding, retrieval,
localization, or eligibility call happens anywhere in this module -- it reads `gate1_evidence_fixture.py`'s
manifest (itself read from already-frozen packet files) and a saved Gate 2 overview record, calls the existing,
unmodified `partial_answer_renderer.render_partial_slice`, and wraps the result in an inspectable receipt
naming exactly what entered, survived, or was withheld at each boundary. It creates no second renderer, no
competing status vocabulary, and does not touch `e2e.py`.
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import partial_answer_renderer as renderer

MODE = "offline_replay_integration"
EXCLUDED_CHILDREN = ("c5", "c6", "c10")


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_file_manifest(paths: dict[str, Path]) -> list[dict]:
    """``[{"label", "path", "sha256"}]`` for each named input file, in the order given. Every input this
    integration reads must be listed here -- nothing enters the receipt as evidence without a named,
    hashed source."""
    return [{"label": label, "path": str(path), "sha256": sha256_file(path)} for label, path in paths.items()]


def code_identity(repo: Path) -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False).stdout.strip()

    return {
        "sha": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty_paths": [line for line in git("status", "--porcelain").splitlines() if line.strip()],
    }


def stage_transition_receipt(manifest_rows: list[dict], classifications: list[dict]) -> list[dict]:
    """One row per unit, naming what happened at each boundary this arc's own documents already established --
    Gate 1 packet/provenance identity, the manifest status derived from it, whether the overview stage matched
    and screened a candidate, and the final rendered outcome. Never re-derives a conclusion; only restates what
    the manifest row and the classification already state, side by side."""
    by_key = {(r["child_id"], r["unit_id"]): r for r in manifest_rows}
    receipt = []
    for c in classifications:
        row = by_key[(c["child_id"], c["unit_id"])]
        screening = None
        if c["outcome"] == renderer.DISPLAYED:
            screening = {"decision": "grounded", "reasons": c["displayed_statement"].get("reasons", [])}
        elif c["withheld_candidates"]:
            screening = {"decision": "withheld", "reasons": c["withheld_candidates"][0]["reasons"]}
        receipt.append(
            {
                "child_id": c["child_id"],
                "unit_id": c["unit_id"],
                "kind": c["kind"],
                "packet_id": row.get("packet_id"),
                "closure_provenance_source": (row.get("provenance") or {}).get("closure_source"),
                "manifest_status": c["manifest_status"],
                "evidence_span_count": len(c["evidence_spans"]),
                "matched_overview_unit_ids": c["matched_overview_unit_ids"],
                "overview_screening": screening,
                "rendered_outcome": c["outcome"],
            }
        )
    return receipt


def build_integration_receipt(
    manifest_rows: list[dict],
    gate2_record: dict,
    *,
    repo: Path,
    input_files: dict[str, Path],
) -> tuple[dict, str, dict]:
    """``(receipt, markdown, detailed_audit_view)``. Calls `render_partial_slice` exactly once, unmodified;
    everything else here is bookkeeping around that single call."""
    markdown, detailed_audit_view = renderer.render_partial_slice(manifest_rows, gate2_record)
    receipt = {
        "mode": MODE,
        "not_a_live_e2e_run": True,
        "created": now(),
        "code": code_identity(repo),
        "input_files": input_file_manifest(input_files),
        "excluded_children": list(EXCLUDED_CHILDREN),
        "c6_construct_scope_decision": "unresolved -- not decided by this integration",
        "topic_anchoring_partial_facet_design": "deferred, tracked in callosum_rd_ask#19, not reopened here",
        "stage_transitions": stage_transition_receipt(manifest_rows, detailed_audit_view["classifications"]),
    }
    return receipt, markdown, detailed_audit_view
