"""Phase 15 -- ONE live target-scoped semantic-consumption experiment.

Tests whether newly-recovered evidence (Phase 13's c4 recovery) can reach and be considered by
EXACTLY the one model-assisted role it was recovered for (`c4#suff:specific-region` /
`named_brain_region_or_network`), while every OTHER model-assisted role across the whole
hierarchy is held fixed at its established Phase-5 value -- never re-attempted, never silently
re-derived. Phase 14 designed this architecture (a role-scoped model-client wrapper); this module
implements the SPECIFIC refinement Cliff required over that sketch: a CONTROL map (Phase-5
recorded behavior, held fixed, over the broadened post-recovery ledger) compared against an
EXPERIMENTAL map (the same ledger, but c4's own target role gets ONE fresh live nomination) --
never a deterministic-only baseline, which would conflate "no model opinion at all" with "the
established model opinion, re-affirmed."

DISCLOSED DEVIATION (same one Phase 13 disclosed, re-verified, not re-decided here):
`hierarchy_contract.load_contract_for_live` still fails pin verification (confirmed: only
`hierarchy_contract.py`'s own code hash drifted, the hierarchy data and the other two code
inputs are unchanged -- the same condition Phase 13 found). This module uses
`load_contract(question, pins=None)` again. Re-freezing pins remains Cliff's own separate,
later, reviewed decision -- not performed here, not bundled into this module.

NO RETRY on a scientifically disappointing-but-valid result. A retry is permitted only for a
genuine mechanical failure producing no valid observation, and must be documented as such.

----------------------------------------------------------------------------------------------
WHY THIS MODULE REPLICATES `sufficiency_diagnostic.compute_diagnostic_sufficiency_map`'S OWN
PER-CHILD LOOP RATHER THAN CALLING IT DIRECTLY
----------------------------------------------------------------------------------------------
`compute_diagnostic_sufficiency_map(sealed, contract_by_child, parent_of, *, model_client=None)`
takes exactly ONE `model_client`, applied uniformly to every `model_nomination_only` role across
EVERY child in one call -- there is no per-child or per-role scoping parameter. The experimental
design this phase requires (one child's one role forwarded live, every other child's role held
fixed to history) is therefore not expressible by passing a single client into that function.
This module reuses its exact per-child topological-order logic verbatim (parent-less children
first, `sm.map_any_requirement` / `sd._stamp_model_dependency_origins` / `se.new_contract`, all
unmodified, imported directly) but swaps in a FRESH, per-child-scoped client inside the loop --
production code is not changed, duplicated into a parallel maintained copy, or forked; this is a
diagnostic-only caller composing existing primitives differently, exactly the posture
`sufficiency_phase5_replay.py` and `phase13_c4_recovery_experiment.py` already established for
offline/isolated experimentation.

----------------------------------------------------------------------------------------------
CONTROL-MAP PREFLIGHT FINDING (Section C of the brief) -- read before running anything live
----------------------------------------------------------------------------------------------
Rebuilding the post-recovery sealed ledger and the CONTROL map entirely offline (zero live
calls -- see `reconstruct_post_recovery_sealed`, which replays the actually-recorded W2/C2 raw
outputs, not a guess) found:

1. The post-recovery C2 coverage-sealing call (a genuine fresh live phi4:14b call Phase 13 had to
   make to seal the new evidence into one ledger) reassigned `responsive_obligation_ids` for SOME
   pre-existing propositions differently than the ORIGINAL run did -- confirmed by diffing the
   real recorded raw outputs of both calls (`run/12_coverage_audit.json` vs this run's own
   `qwen_calls.jsonl` row 16), not inferred. Concretely: p3 is now also attached to c2 (it
   wasn't before); p16 moved from c3 to being c5-only. This is a REAL mechanical side effect of
   re-sealing, unrelated to the recovered RTPJ evidence (p27), which is attached to c4 only.
2. Candidate-pool impact: c2's own `behavior_or_behavioral_measure` role (model_nomination_only)
   gained 5 propositions it didn't have before (p3, p7, p14, p17, p26 -- all via shared-unit
   dedup with other now-differently-tagged propositions). c4's own target role gained exactly the
   one new proposition (p27), as intended.
3. A naive "recorded client for every role, offered pool as-is" CONTROL map therefore raises
   `RecordedNominationReplayError` for TWO roles, not one: c4's own target role (expected -- this
   is exactly what the recovery was for) AND c2's `behavior_or_behavioral_measure` role
   (unexpected -- unrelated drift from the re-sealing side effect, not from the recovery).
4. "Held every prior model nomination fixed" (Section B's own words) is operationalized here as:
   before delegating to the Phase-5 recorded+adjudicated client, filter the offered candidates
   down to EXACTLY the proposition ids that child's role originally saw in the pre-recovery
   ledger. Verified this makes BOTH misses resolve to their exact historical answers -- c4's own
   role reproduces "the specific amygdala response" / p11 verbatim, and c2's role reproduces its
   exact historical 3-nomination answer -- with ZERO other child's requirement STATE or role
   bindings differing from the Phase-5 with-model baseline.
5. Comparing the full CONTROL map against the Phase-5 with-model baseline (both built fresh,
   offline) finds exactly THREE children whose output differs: c5, c6, and c12 -- but in every
   case the difference is confined to `direction`/`effectiveness` (a SEPARATE, deterministic,
   model-client-INDEPENDENT pass, `compute_direction_and_effectiveness`, which scans the full,
   now-broadened per-child candidate pool for a direction/outcome word and returns the FIRST
   match it finds in pool order) -- never to requirement `state`, `instances[].state`, or any
   role_binding. No sufficiency-completion semantics changed for any unrelated child.
6. This IS genuine "unrelated semantic drift caused by the replay/control mechanism itself"
   (Section C's own named stop condition) -- confirmed, not a false alarm. BUT it is structurally
   IDENTICAL between the CONTROL and EXPERIMENTAL maps (both are built from the exact same
   post-recovery `sealed`, and `compute_direction_and_effectiveness` never reads `model_client` at
   all), so it cancels out of the one comparison this experiment is actually testing (CONTROL vs
   EXPERIMENTAL, Section L) -- it would only ever show up as a false "unrelated isolation
   failure" if compared against the WRONG baseline (Phase-5's pre-recovery with-model state,
   which Section L explicitly says NOT to use as the primary comparison).

Per Section C's own literal instruction ("If the control map shows unrelated semantic drift...
STOP before the live call"), this module stops here: `build_state()` performs every offline step
through this preflight and raises nothing, but `run_live()` is NOT invoked by `main()` without an
explicit `--live` flag AND a fresh go-ahead from Cliff specifically informed of this finding --
the brief's own stop condition fired, and a stop condition firing is reported, not silently
reasoned past, regardless of the offline analysis above concluding the drift looks contained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from experiments.ask_cli_revised import __main__ as cli
from experiments.ask_cli_revised import backends, e2e_contracts, library_copy
from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import sufficiency_phase5_replay as replay_mod
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.qwen import QwenTasks
from experiments.ask_cli_revised.sufficiency_model_nomination_diagnostic import (
    _load_children_by_id,
    _parent_of,
    load_frozen_contract,
)
from experiments.ask_cli_revised.supervisor_eval.ollama_client import OllamaClient

EXPECTED_HEAD = "dc5f968b17a7bda35038e49eeb63697053a90361"
EXPECTED_V9_HASH = "9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586"

TARGET_CHILD = "c4"
TARGET_REQUIREMENT_ID = "c4#suff:specific-region"
TARGET_ROLE = "named_brain_region_or_network"
TARGET_CATEGORY_DESCRIPTION = "a specific NAMED brain area"  # verified globally unique, Phase 14

_PRESERVED_RUN_DIR = (
    Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930"
)
_ORIGINAL_LEDGER = _PRESERVED_RUN_DIR / "run" / "11_verified_ledger.json"
_LIBRARY_COPY = _PRESERVED_RUN_DIR / "library_copy.sqlite"
_LIBRARY_FINGERPRINT = _PRESERVED_RUN_DIR / "library_copy.sqlite.fingerprint.json"

_PHASE13_DIR = Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "phase13-c4-recovery-experiment"
_PHASE13_RESULT = _PHASE13_DIR / "phase13_result.json"
_PHASE13_QWEN_CALLS = _PHASE13_DIR / "qwen_calls.jsonl"

_T5 = topo.WAVE1["T5"]
_W_MODEL = _T5.W.model  # "qwen3.5:9b"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------------------------------------
# Step 1: deterministic, offline reconstruction of the exact Phase-13 post-recovery sealed
# ledger from already-recorded artifacts -- zero live calls, zero guessing. Verified (see
# `_verify_reconstruction_against_phase13`) to byte-for-byte reproduce Phase 13's own saved
# deterministic-only mapped_after_c4/mapped_after_c6.
# ---------------------------------------------------------------------------------------------


def reconstruct_post_recovery_sealed(*, gates: list[dict] | None = None) -> dict:
    def gate(name: str, ok: bool, detail=None) -> None:
        if gates is not None:
            gates.append({"gate": name, "ok": bool(ok), "detail": detail})
        if not ok:
            raise AssertionError(f"MECHANICAL GATE FAILED: {name} -- {detail}")

    original_ledger = json.loads(_ORIGINAL_LEDGER.read_text(encoding="utf-8"))
    phase13_result = json.loads(_PHASE13_RESULT.read_text(encoding="utf-8"))
    qwen_calls = [
        json.loads(line) for line in _PHASE13_QWEN_CALLS.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    coverage_calls = [r for r in qwen_calls if r.get("task") == "coverage_audit"]
    gate("exactly_one_recorded_coverage_audit_call", len(coverage_calls) == 1, len(coverage_calls))
    coverage_raw = json.loads(coverage_calls[0]["raw_output"])

    original_props = original_ledger["verified_propositions"]
    gate("original_ledger_has_26_propositions", len(original_props) == 26, len(original_props))

    new_ev = phase13_result["newly_verified_evidence"]
    gate("exactly_one_newly_verified_proposition", len(new_ev) == 1, len(new_ev))
    new_ev = new_ev[0]
    new_prop = {
        "proposition_id": "p27",
        "paper_id": new_ev["paper_id"],
        "subquestion_id": new_ev["subquestion_id"],
        "mapping_state": new_ev["mapping_state"],
        "proposition_text": new_ev["proposition_text"],
        "quote": new_ev["quote"],
        "provenance": new_ev["provenance"],
        "verification": new_ev["verification"],
        "evidence_anchor_chunk_id": new_ev["evidence_anchor_chunk_id"],
        "evidence_span_id": new_ev["evidence_span_id"],
        "obligation_ids": new_ev["obligation_ids"],
    }
    all_props = [dict(p) for p in original_props] + [new_prop]
    for i, p in enumerate(all_props, start=1):
        gate(f"proposition_order_p{i}", p["proposition_id"] == f"p{i}", p["proposition_id"])

    attached: dict[str, list[str]] = {}
    for field_id, entry in coverage_raw["coverage"].items():
        for pid in entry["supporting_proposition_ids"]:
            attached.setdefault(pid, []).append(field_id)
    gate("c4_gained_p27_in_coverage", "c4" in attached.get("p27", []), attached.get("p27"))
    gate("c4_retains_p11_in_coverage", "c4" in attached.get("p11", []), attached.get("p11"))

    verified = [{**p, "responsive_obligation_ids": attached.get(p["proposition_id"], [])} for p in all_props]
    evidence_spans = list(original_ledger["evidence_spans"]) + [
        {
            "paper_id": new_ev["paper_id"],
            "chunk_id": new_ev["evidence_anchor_chunk_id"],
            "span_id": new_ev["evidence_span_id"],
            "text": new_ev["quote"],
        }
    ]
    sealed = {
        "request_contract": original_ledger["request_contract"],
        "subquestions": original_ledger["subquestions"],
        "verified_propositions": verified,
        "evidence_spans": evidence_spans,
    }
    _verify_reconstruction_against_phase13(sealed, phase13_result, gate)
    return sealed


def _verify_reconstruction_against_phase13(sealed: dict, phase13_result: dict, gate) -> None:
    """Deterministic-only (no model) recompute; must byte-for-byte match Phase 13's own saved
    mapped_after_c4/mapped_after_c6 -- the proof that this reconstruction is faithful, not a
    plausible-looking guess."""
    _frozen, contract_by_child = load_frozen_contract()
    children_by_id = _load_children_by_id(_PRESERVED_RUN_DIR / "run")
    parent_of = _parent_of(children_by_id)
    mapped = sd.compute_diagnostic_sufficiency_map(sealed, contract_by_child, parent_of)
    sd.compute_direction_and_effectiveness(sealed, mapped)

    def req_by_id(mapped_, child_id, req_id):
        for r in mapped_[child_id]["requirements"]:
            if r["id"] == req_id:
                return r
        raise KeyError(req_id)

    c4_recon = req_by_id(mapped, "c4", "c4#suff:specific-region")
    c4_saved = phase13_result["mapped_after_c4"]["requirements"][0]
    gate("reconstruction_matches_phase13_saved_c4", c4_recon == c4_saved, None)

    for idx, req_id in enumerate(("c6#suff:brain-attitude", "c6#suff:implicit-explicit-coverage")):
        recon = req_by_id(mapped, "c6", req_id)
        saved = phase13_result["mapped_after_c6"]["requirements"][idx]
        gate(f"reconstruction_matches_phase13_saved_c6_{idx}", recon == saved, None)


# ---------------------------------------------------------------------------------------------
# Step 2: per-child "held fixed" replay client -- filters the offered candidates down to exactly
# the proposition ids that child's own role saw BEFORE recovery, then delegates to the Phase-5
# recorded+adjudicated client. By construction (verified offline above) this always finds a
# historical match for every child except the recovery's own target, c4.
# ---------------------------------------------------------------------------------------------


def _original_pool_by_child(contract_by_child: dict) -> dict[str, set]:
    original_ledger = json.loads(_ORIGINAL_LEDGER.read_text(encoding="utf-8"))
    original_sealed = {
        "request_contract": original_ledger["request_contract"],
        "subquestions": original_ledger["subquestions"],
        "verified_propositions": original_ledger["verified_propositions"],
        "evidence_spans": original_ledger["evidence_spans"],
    }
    by_child = sd.units_by_child(original_sealed)
    return {
        child_id: {pid for u in by_child.get(child_id, []) for pid in u["proposition_ids"]}
        for child_id in contract_by_child
    }


class HeldFixedClient:
    """Per-child-scoped: filters candidates to the pre-recovery pool before delegating to the
    Phase-5 recorded+adjudicated client. Never used for the target child/role (see
    `build_map`'s own dispatch, which constructs a different client for TARGET_CHILD)."""

    def __init__(self, child_id: str, allowed_propositions: set, validator, calls_log: list):
        self.model_name = validator.model_name
        self._child_id = child_id
        self._allowed = allowed_propositions
        self._validator = validator
        self._calls_log = calls_log

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        filtered = [c for c in candidates if c["proposition_id"] in self._allowed]
        result = self._validator.nominate_sufficiency_role(
            category_description=category_description, candidates=filtered
        )
        self._calls_log.append(
            {
                "child_id": self._child_id,
                "mode": "held_fixed",
                "category_description": category_description,
                "offered_proposition_ids": sorted(c["proposition_id"] for c in candidates),
                "filtered_to_historical_proposition_ids": sorted(c["proposition_id"] for c in filtered),
                "live_call_made": False,
                "result": result,
            }
        )
        return result


class LiveTargetClient:
    """The ONE client used for TARGET_CHILD's own target role. Forwards the FULL current
    candidate pool (including any newly recovered evidence) to a real `QwenTasks`-shaped object,
    exactly as `nominate_with_model` already does for any live model_client -- this class adds no
    new model-facing behavior, injects no prior-answer steering (there is no such parameter on
    `nominate_sufficiency_role`), and does not filter anything out."""

    def __init__(self, live_tasks, model_name: str, calls_log: list):
        self.model_name = model_name
        self._tasks = live_tasks
        self._calls_log = calls_log
        self.live_call_count = 0

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        self.live_call_count += 1
        result = self._tasks.nominate_sufficiency_role(category_description=category_description, candidates=candidates)
        self._calls_log.append(
            {
                "child_id": TARGET_CHILD,
                "mode": "live",
                "category_description": category_description,
                "offered_proposition_ids": sorted(c["proposition_id"] for c in candidates),
                "filtered_to_historical_proposition_ids": None,
                "live_call_made": True,
                "result": result,
            }
        )
        return result


class _DryRunTargetClient:
    """Dry-run stand-in for LiveTargetClient: records that it WOULD have been called, exactly
    once, with exactly these candidates -- never touches a network/model. Used by the E-section
    ("exactly one live call") mechanical proof before any real call is authorized."""

    model_name = "DRY_RUN_NO_LIVE_CALL"

    def __init__(self, calls_log: list):
        self._calls_log = calls_log
        self.would_call_count = 0

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        self.would_call_count += 1
        self._calls_log.append(
            {
                "child_id": TARGET_CHILD,
                "mode": "dry_run_would_be_live",
                "category_description": category_description,
                "offered_proposition_ids": sorted(c["proposition_id"] for c in candidates),
                "live_call_made": False,
            }
        )
        return []  # dry run only -- never a real nomination


def build_map(sealed: dict, contract_by_child: dict, parent_of: dict, *, target_client_factory) -> tuple[dict, list]:
    """Replicates `compute_diagnostic_sufficiency_map`'s own per-child topological loop verbatim
    (parent-less children first), swapping in a FRESH client per child: `target_client_factory()`
    for TARGET_CHILD, a `HeldFixedClient` for every other child. Returns (mapped, calls_log)."""
    validator = replay_mod._Phase5AdjudicationValidator(
        replay_mod._RecordedV9NominationClient(replay_mod._DEFAULT_TRACE)
    )
    original_pools = _original_pool_by_child(contract_by_child)
    calls_log: list = []

    by_child_units = sd.units_by_child(sealed)
    child_ids = list(contract_by_child)
    no_parent_context = [
        cid for cid in child_ids if not any(r["parent_context_roles"] for r in contract_by_child[cid]["requirements"])
    ]
    with_parent_context = [cid for cid in child_ids if cid not in no_parent_context]

    mapped: dict = {}
    for child_id in no_parent_context + with_parent_context:
        contract = contract_by_child[child_id]
        candidate_units = by_child_units.get(child_id, [])
        client = (
            target_client_factory(calls_log)
            if child_id == TARGET_CHILD
            else HeldFixedClient(child_id, original_pools.get(child_id, set()), validator, calls_log)
        )
        new_requirements = []
        for req in contract["requirements"]:
            parent_requirement = None
            if req["parent_context_roles"]:
                role = req["parent_context_roles"][0]
                parent_child_id = parent_of.get(child_id)
                parent_contract = mapped.get(parent_child_id) if parent_child_id else None
                if parent_contract is not None:
                    parent_requirement = next(
                        (r for r in parent_contract["requirements"] if role in r["role_specs"]), None
                    )
            mapped_req = sm.map_any_requirement(
                req, candidate_units, parent_requirement=parent_requirement, model_client=client
            )
            new_requirements.append(sd._stamp_model_dependency_origins(mapped_req, child_id))
        mapped[child_id] = se.new_contract(child_id, new_requirements)
    sd.compute_direction_and_effectiveness(sealed, mapped)
    si.stamp_map(mapped)  # Phase 32 / I1c: same stamping path as production
    return mapped, calls_log


def build_control_map(sealed: dict, contract_by_child: dict, parent_of: dict) -> tuple[dict, list]:
    """CONTROL: even TARGET_CHILD's own role is held fixed (filtered to its pre-recovery pool,
    i.e. {p11, p2} -- p27 is excluded -- then answered from Phase-5's history). Reproduces 'the
    specific amygdala response' / p11 verbatim; see the module docstring's preflight finding."""
    validator = replay_mod._Phase5AdjudicationValidator(
        replay_mod._RecordedV9NominationClient(replay_mod._DEFAULT_TRACE)
    )
    original_pools = _original_pool_by_child(contract_by_child)

    def factory(calls_log):
        return HeldFixedClient(TARGET_CHILD, original_pools.get(TARGET_CHILD, set()), validator, calls_log)

    return build_map(sealed, contract_by_child, parent_of, target_client_factory=factory)


# ---------------------------------------------------------------------------------------------
# Section D: candidate-visibility gate
# ---------------------------------------------------------------------------------------------


def _target_and_descendants(contract_by_child: dict, parent_of: dict) -> set[str]:
    """TARGET_CHILD plus every child whose requirement declares TARGET_ROLE among its own
    `parent_context_roles` AND whose hierarchy parent is TARGET_CHILD -- i.e. every child that
    structurally INHERITS c4's own target-role binding, not just the one (c6) the brief names by
    example. A real, confirmed finding from the live run: c5 shares this exact relationship with
    c6 (both declare `parent_context_roles=["named_brain_region_or_network"]` with `parent_of`
    pointing at c4) and is therefore expected to change too -- its top-level requirement `state`/
    `reason` stayed identical (c5's OTHER required role is independently missing either way), but
    its inherited region binding's `exact_text`/`proposition_id`/`provenance` legitimately
    changed from the amygdala to the RTPJ, exactly mirroring c6's own change. Treating only
    {TARGET_CHILD, "c6"} as expected-to-change (this module's own first draft) was an incomplete,
    hard-coded assumption, not a fact about the architecture -- fixed to derive the set
    structurally instead."""
    expected = {TARGET_CHILD}
    for child_id, contract in contract_by_child.items():
        for req in contract["requirements"]:
            if TARGET_ROLE in (req.get("parent_context_roles") or []) and parent_of.get(child_id) == TARGET_CHILD:
                expected.add(child_id)
    return expected


def target_candidate_pool(sealed: dict, contract_by_child: dict) -> list[dict]:
    """The exact candidate units `nominate_with_model` would offer for TARGET_CHILD/TARGET_ROLE
    over the CURRENT (post-recovery) ledger -- proposition_id, passage text, admissibility, and
    total count. Pure read; does not call anything."""
    by_child = sd.units_by_child(sealed)
    units = by_child.get(TARGET_CHILD, [])
    role_spec = contract_by_child[TARGET_CHILD]["requirements"][0]["role_specs"][TARGET_ROLE]
    out = []
    for unit in units:
        admissible = sm.is_admissible(role_spec, unit.get("flags", {}))
        for pid in unit.get("proposition_ids") or []:
            out.append(
                {
                    "proposition_id": pid,
                    "unit_id": unit["unit_id"],
                    "paper_id": unit["paper_id"],
                    "passage": unit["passage"],
                    "admissible": admissible,
                }
            )
    return out


# ---------------------------------------------------------------------------------------------
# Section H/I: authorization artifact + pin-drift disclosure (self-checked, mirrors Phase 13)
# ---------------------------------------------------------------------------------------------


def write_authorization_artifact(
    *, out_dir: Path, question_hash: str, library_fingerprint_sha256: str, authorized_by: str, authorized_at: str
) -> Path:
    artifact = {
        "experiment_id": "phase15_c4_semantic_consumption_20261001",
        "authorized_by": authorized_by,
        "authorized_at": authorized_at,
        "brief_confirmed": True,
        "question_sha256s": [question_hash],
        "question": "aib",
        "v9_combined_hash": EXPECTED_V9_HASH,
        "target_child": TARGET_CHILD,
        "target_requirement_id": TARGET_REQUIREMENT_ID,
        "target_role": TARGET_ROLE,
        "target_category_description": TARGET_CATEGORY_DESCRIPTION,
        "phase13_sealed_ledger_source": {
            "original_ledger": str(_ORIGINAL_LEDGER.relative_to(Path(__file__).resolve().parents[2])),
            "phase13_result": str(_PHASE13_RESULT.relative_to(Path(__file__).resolve().parents[2])),
            "phase13_qwen_calls": str(_PHASE13_QWEN_CALLS.relative_to(Path(__file__).resolve().parents[2])),
            "reconstruction_method": "deterministic offline replay of recorded W2/C2 raw outputs; verified to "
            "reproduce phase13_result.json's own saved mapped_after_c4/mapped_after_c6 exactly",
        },
        "library_copy_path": str(_LIBRARY_COPY.relative_to(Path(__file__).resolve().parents[2])),
        "library_fingerprint_sha256": library_fingerprint_sha256,
        "qwen_model": {"endpoint": "isolated", "model": _W_MODEL, "think": _T5.W.think},
        "exactly_one_live_nomination_call": True,
        "no_retrieval": True,
        "no_recovery_search": True,
        "no_query_generation": True,
        "all_non_target_roles_served_from_recorded_phase5_output": True,
        "disclosed_deviation": "hierarchy loaded via pins=None (pin-drift bypass, same condition Phase 13 "
        "disclosed); see module docstring",
        "control_map_preflight_drift_disclosure": "confirmed unrelated drift in direction/effectiveness for "
        "c5/c6/c12 caused by the mandatory C2 re-sealing call's side effect on unrelated propositions' "
        "responsive_obligation_ids -- structurally identical between CONTROL and EXPERIMENTAL maps (both "
        "model-client-independent for this pass), so it does not contaminate the CONTROL-vs-EXPERIMENTAL "
        "comparison; see module docstring for the full accounting",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "phase15_authorization.json"
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------------------------
# build_state: everything offline, Sections A-D-F preflight. Raises on any mechanical-gate
# failure. Does NOT raise on the Section-C drift finding -- that is reported, not mechanically
# fatal (see the module docstring) -- but `main()` refuses `--live` without an explicit
# acknowledgement flag regardless.
# ---------------------------------------------------------------------------------------------


def build_state() -> dict:
    gates: list[dict] = []

    def gate(name: str, ok: bool, detail=None) -> None:
        gates.append({"gate": name, "ok": bool(ok), "detail": detail})
        if not ok:
            raise AssertionError(f"MECHANICAL GATE FAILED: {name} -- {detail}")

    gate("v9_combined_hash", True, "checked by caller against EXPECTED_V9_HASH before calling build_state")

    fingerprint = library_copy.verify(_LIBRARY_COPY, _LIBRARY_FINGERPRINT)
    gate("library_copy_unaltered", True, fingerprint["sha256"])

    question_text = e2e_contracts.E2E_QUESTIONS["aib"]
    contract = hc.load_contract(question_text, pins=None)
    hc.assert_executable(contract)
    gate("hierarchy_structurally_executable_pins_none", True, "disclosed deviation, same as Phase 13")

    sealed = reconstruct_post_recovery_sealed(gates=gates)

    _frozen, contract_by_child = load_frozen_contract()
    gate("frozen_v9_hash_matches", _frozen["combined_hash"] == EXPECTED_V9_HASH, _frozen["combined_hash"])
    children_by_id = _load_children_by_id(_PRESERVED_RUN_DIR / "run")
    parent_of = _parent_of(children_by_id)

    # Section D: candidate visibility gate.
    target_pool = target_candidate_pool(sealed, contract_by_child)
    target_pool_ids = sorted(p["proposition_id"] for p in target_pool)
    gate("target_pool_contains_p27_recovered_evidence", "p27" in target_pool_ids, target_pool_ids)
    gate("target_pool_contains_p11_preexisting_evidence", "p11" in target_pool_ids, target_pool_ids)
    gate("target_pool_count_is_3", len(target_pool) == 3, target_pool_ids)

    # Section E (dry run): exactly one would-be live call for the target, zero for everyone else.
    _dry_map, dry_calls_log = build_map(
        sealed, contract_by_child, parent_of, target_client_factory=lambda log: _DryRunTargetClient(log)
    )
    would_be_live = [c for c in dry_calls_log if c["mode"] == "dry_run_would_be_live"]
    held_fixed_calls = [c for c in dry_calls_log if c["mode"] == "held_fixed"]
    gate("dry_run_exactly_one_target_call", len(would_be_live) == 1, len(would_be_live))
    gate("dry_run_zero_other_live_calls", all(not c["live_call_made"] for c in held_fixed_calls), None)
    gate(
        "dry_run_target_call_sees_full_grown_pool",
        would_be_live[0]["offered_proposition_ids"] == target_pool_ids,
        would_be_live[0]["offered_proposition_ids"],
    )

    # Section C preflight: build the CONTROL map, confirm it reproduces c4's historical binding
    # and diff against the Phase-5 with-model baseline.
    control_map, control_calls = build_control_map(sealed, contract_by_child, parent_of)
    control_c4_binding = control_map["c4"]["requirements"][0]["instances"][0]["role_bindings"][TARGET_ROLE]
    gate(
        "control_map_c4_reproduces_historical_amygdala_binding",
        control_c4_binding["exact_text"] == "the specific amygdala response"
        and control_c4_binding["proposition_id"] == "p11",
        control_c4_binding,
    )

    phase5_with_model = replay_mod.replay()["with_model"]
    drift_children = []
    for child_id in sorted(set(control_map) | set(phase5_with_model)):
        if control_map.get(child_id) != phase5_with_model.get(child_id):
            drift_children.append(child_id)
    gate(
        "control_vs_phase5_drift_is_exactly_c5_c6_c12_direction_effectiveness_only",
        drift_children == ["c12", "c5", "c6"],
        drift_children,
    )
    for child_id in drift_children:
        control_req = control_map[child_id]["requirements"][0]
        phase5_req = phase5_with_model[child_id]["requirements"][0]
        non_direction_effectiveness_diff = {
            k: (control_req.get(k), phase5_req.get(k))
            for k in control_req
            if k not in ("direction", "effectiveness") and control_req.get(k) != phase5_req.get(k)
        }
        gate(
            f"drift_in_{child_id}_confined_to_direction_effectiveness",
            not non_direction_effectiveness_diff,
            non_direction_effectiveness_diff,
        )

    return {
        "gates": gates,
        "contract": contract,
        "contract_by_child": contract_by_child,
        "parent_of": parent_of,
        "sealed": sealed,
        "question_text": question_text,
        "question_hash": contract["question_hash"],
        "library_fingerprint": fingerprint,
        "target_pool": target_pool,
        "dry_calls_log": dry_calls_log,
        "control_map": control_map,
        "control_calls": control_calls,
        "phase5_with_model": phase5_with_model,
        "drift_children": drift_children,
    }


# ---------------------------------------------------------------------------------------------
# Section J: the one live call. NOT invoked by this module's own import or by build_state().
# Requires explicit --live AND --acknowledge-drift-finding on the CLI (see main()).
# ---------------------------------------------------------------------------------------------


def run_live(state: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    client = OllamaClient(topo.ENDPOINTS["isolated"])
    guard = backends.ResidencyGuard({"isolated": client})
    trace = cli.TraceWriter(out_dir)
    log: dict = {}
    try:
        worker_config = backends.NativeWorker(
            client=client, model=_W_MODEL, base_options=topo.SUPERVISOR_BASE_OPTIONS, think=_T5.W.think
        )
        qwen = QwenTasks(config=worker_config, trace=trace)

        enter = guard.enter("isolated", _W_MODEL, phase="phase15_target_nomination")
        started = time.monotonic()
        experimental_map, exp_calls = build_map(
            state["sealed"],
            state["contract_by_child"],
            state["parent_of"],
            target_client_factory=lambda log_: LiveTargetClient(qwen, _W_MODEL, log_),
        )
        wall_seconds = time.monotonic() - started
        observe = guard.observe("phase15_target_nomination")
        log["enter"] = enter
        log["observe"] = observe
        log["wall_seconds"] = wall_seconds

        live_rows = [c for c in exp_calls if c["mode"] == "live"]
        if len(live_rows) != 1:
            raise AssertionError(f"expected exactly one live call, got {len(live_rows)}: {live_rows}")
        log["live_call"] = live_rows[0]
        log["all_calls"] = exp_calls
        log["experimental_map_c4"] = experimental_map["c4"]
        log["experimental_map_c5"] = experimental_map["c5"]
        log["experimental_map_c6"] = experimental_map["c6"]
        log["control_map_c5"] = state["control_map"]["c5"]

        expected_to_change = _target_and_descendants(state["contract_by_child"], state["parent_of"])
        log["expected_to_change"] = sorted(expected_to_change)
        drift = []
        for child_id in sorted(set(experimental_map) | set(state["control_map"])):
            if child_id in expected_to_change:
                continue
            if experimental_map.get(child_id) != state["control_map"].get(child_id):
                drift.append(child_id)
        log["unrelated_isolation_failures"] = drift
    finally:
        guard.release_all()
        client.close()
    return log


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--acknowledge-drift-finding",
        action="store_true",
        help="required alongside --live: confirms Cliff has reviewed the Section-C drift finding in this "
        "module's own docstring and is proceeding despite the stop condition it names",
    )
    parser.add_argument("--out", default=None)
    parser.add_argument("--authorized-by", default="Cliff")
    parser.add_argument("--authorized-at", default=None)
    args = parser.parse_args()
    out_dir = (
        Path(args.out)
        if args.out
        else Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "phase15-c4-semantic-consumption"
    )

    state = build_state()
    print(json.dumps({"gates": state["gates"], "drift_children": state["drift_children"]}, indent=2, default=str))

    if not args.live:
        print("\nDRY RUN ONLY -- no live call made. Re-run with --live --acknowledge-drift-finding to execute.")
        return 0
    if not args.acknowledge_drift_finding:
        raise SystemExit(
            "refusing: --live requires --acknowledge-drift-finding (Section C's own stop condition fired "
            "during the offline preflight; see this module's docstring before overriding it)"
        )

    from datetime import datetime, timezone

    authorized_at = args.authorized_at or datetime.now(timezone.utc).isoformat()
    auth_path = write_authorization_artifact(
        out_dir=out_dir,
        question_hash=state["question_hash"],
        library_fingerprint_sha256=state["library_fingerprint"]["sha256"],
        authorized_by=args.authorized_by,
        authorized_at=authorized_at,
    )
    print(f"\nauthorization artifact: {auth_path}")

    log = run_live(state, out_dir)
    out_path = out_dir / "phase15_result.json"
    out_path.write_text(json.dumps(log, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"\nresult written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
