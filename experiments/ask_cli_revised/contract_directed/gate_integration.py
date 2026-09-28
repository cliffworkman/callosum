"""Replay AND live integration of the c9+c11 vertical slice's Gate 1 evidence/coverage (2026-09-27, extended
2026-09-28 for exactly one live boundary).

**Two modes, kept structurally distinct so a run can never be mislabeled:**

- `build_integration_receipt` -- the offline REPLAY path (`MODE`). Reads a SAVED Gate 2 overview record; makes
  no model, NLI, embedding, retrieval, localization, or eligibility call anywhere.
- `run_live_overview_call` / `build_live_integration_receipt` -- the LIVE path (`MODE_LIVE`). Makes exactly one
  real overview call (or, under test, a scripted one) via the existing, unmodified
  `overview.build_overview` -- never a second renderer, never a duplicated overview implementation. The
  resulting record is then handed to the SAME `build_integration_receipt` used by the replay path, so rendering
  and receipt-building logic is never duplicated between the two modes -- only how the `gate2_record` is
  obtained differs.

Neither mode touches `e2e.py`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised.contract_directed import freeze
from experiments.ask_cli_revised.contract_directed import overview_bridge as bridge
from experiments.ask_cli_revised.contract_directed import partial_answer_renderer as renderer

MODE = "offline_replay_integration"
MODE_LIVE = "live_partial_pipeline_integration"
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


def build_sealed_ledger(manifest_rows: list[dict]) -> dict:
    """The sealed-ledger shape `overview.build_overview` needs, built entirely from `manifest_rows` via the
    existing, unmodified bridge -- `overview_bridge.project_evidence`/`coverage_constraints`/
    `real_obligation_states`/`real_original_question`. Pure and offline; makes no call of any kind on its own.
    Raises if the real request contract's question hash no longer matches the frozen substrate (fails closed
    rather than silently using a drifted question)."""
    evidence_spans, verified_propositions = bridge.project_evidence(manifest_rows)
    question, question_hash = bridge.real_original_question()
    if question_hash != freeze.QUESTION_SHA256:
        raise ValueError("the real request contract's question hash no longer matches the frozen substrate")
    field_ids = tuple(sorted({row["child_id"] for row in manifest_rows}))
    obligation_states = bridge.real_obligation_states(field_ids)
    return {
        "request_contract": {"original_question": question, "question_hash": question_hash},
        "obligation_states": obligation_states,
        "evidence_spans": evidence_spans,
        "verified_propositions": verified_propositions,
    }


def sealed_ledger_hash(sealed: dict) -> str:
    return hashlib.sha256(json.dumps(sealed, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def run_live_overview_call(
    manifest_rows: list[dict],
    *,
    supervisor,
    entail,
    on_prompt_ready=None,
    on_raw_response=None,
    sealed_override: dict | None = None,
) -> tuple[dict, str, dict]:
    """``(record, reasoning, sealed)``. Makes exactly ONE call to `overview.build_overview` -- the only call
    this whole module ever makes on its own behalf. `supervisor`/`entail` decide whether that call is live or
    scripted; this function does not know or care which. `on_prompt_ready`/`on_raw_response` are threaded
    straight through to `build_overview`'s own committed hooks -- the earliest-available boundaries for
    persisting the prompt (before inference) and the raw response (immediately after, before any parsing).

    `sealed_override` exists ONLY for offline testing of this function's own crash-recovery behavior (see
    `test_gate_integration.py`) -- a caller building a real sealed ledger should never pass it; the coverage
    constraint / obligation-state contract is otherwise always the real one from `build_sealed_ledger`.
    """
    sealed = sealed_override if sealed_override is not None else build_sealed_ledger(manifest_rows)
    constraints = bridge.coverage_constraints(manifest_rows)
    record, reasoning = ov.build_overview(
        sealed,
        sealed_ledger_hash(sealed),
        supervisor=supervisor,
        entail=entail,
        coverage_constraints=constraints,
        on_prompt_ready=on_prompt_ready,
        on_raw_response=on_raw_response,
    )
    return record, reasoning, sealed


def build_live_integration_receipt(
    manifest_rows: list[dict],
    *,
    supervisor,
    entail,
    trace,
    repo: Path,
    input_files: dict[str, Path],
    sealed_override: dict | None = None,
) -> tuple[dict, str, dict, dict, str]:
    """``(receipt, markdown, detailed_audit_view, overview_record, reasoning)``. The live counterpart of
    `build_integration_receipt`: makes the one call via `run_live_overview_call` (wired to `trace.prompt_ready`/
    `trace.raw_response`), then feeds the resulting FRESH record -- never a saved one -- into the SAME
    `build_integration_receipt` the replay path uses, so rendering never duplicates logic between the two
    modes. Raises whatever `run_live_overview_call` or `build_integration_receipt` raises; callers are expected
    to wrap this in their own `try`/`except` that calls `trace.exception(exc)`, exactly like the replay path's
    established driver convention. `sealed_override` is threaded straight through to `run_live_overview_call`
    for the same offline-testing purpose only -- a real production caller never passes it.
    """
    record, reasoning, sealed = run_live_overview_call(
        manifest_rows,
        supervisor=supervisor,
        entail=entail,
        on_prompt_ready=trace.prompt_ready,
        on_raw_response=trace.raw_response,
        sealed_override=sealed_override,
    )
    trace.final_record(record, reasoning)
    receipt, markdown, detailed_audit_view = build_integration_receipt(
        manifest_rows, record, repo=repo, input_files=input_files
    )
    receipt["mode"] = MODE_LIVE
    receipt["sealed_ledger_hash"] = sealed_ledger_hash(sealed)
    return receipt, markdown, detailed_audit_view, record, reasoning
