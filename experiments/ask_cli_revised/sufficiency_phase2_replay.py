"""Offline replay of the Phase 2 diagnostic's OWN recorded model outputs through the CORRECTED
mapper (Finding 1 instance-key fix, Finding 2 anchor-dedup fix) -- NO live model call anywhere in
this module. This tests A/B structural accounting only: Phase 2's raw calls used v8 RoleSpec
wording (pre-Finding-C), so a clean replay is NOT evidence that v9's tightened semantics solve
anything -- that claim needs a separately-authorized live rerun. Never reinterprets, edits, or
silently skips a historical Qwen output; a candidate set this replay cannot match to a recorded
call raises loudly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from experiments.ask_cli_revised import sufficiency_authoring as sa
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_model_nomination_diagnostic as diag

# Finding C changed exactly these 3 roles' category_description wording (v8 -> v9, verified by
# the exact-diff in INCREMENT-level handback). Phase 2's trace recorded calls under the OLD (v8)
# text; this table is the explicit, disclosed way to recognize "this v9 call corresponds to that
# recorded v8 call" -- never a fuzzy heuristic, never a guess, just the KNOWN wording change.
_V9_TO_V8_CATEGORY_DESCRIPTION = {
    sa._NEURAL_MEASURE_OR_MODALITY_DESCRIPTION: "a neural measure or imaging modality",
    sa._BEHAVIOR_OR_BEHAVIORAL_MEASURE_DESCRIPTION: "a named behavior or behavioral measure",
}

_DEFAULT_TRACE = (
    Path(__file__).resolve().parents[2] / ".local" / "sufficiency-nomination-diagnostic-20260930" / "qwen_calls.jsonl"
)
_PROPOSITION_ID_RE = re.compile(r"'(p\d+)'")


class RecordedNominationReplayError(RuntimeError):
    """Raised when the replay cannot find a historically-recorded call matching a candidate set
    the CORRECTED mapper now requests -- never silently fabricated or skipped."""


class RecordedNominationClient:
    """Replays Phase 2's own recorded raw model outputs, keyed by (category_description, the
    exact set of proposition_ids offered). The candidate-set component alone is NOT sufficient --
    two different roles on the same child can share an identical admissible-units pool (e.g. c5's
    `named_brain_region_or_network` and `behavior_or_behavioral_measure` both draw from c5's full
    16-proposition pool), so a set-only key silently collides across roles and was empirically
    proven to do so while building this harness (see the module's own commit history) --
    `category_description` disambiguates exactly the way the real prompt already does.

    For the 3 roles Finding C's v9 wording changed, `_V9_TO_V8_CATEGORY_DESCRIPTION` is the
    explicit, disclosed translation back to what Phase 2 actually recorded -- never a fuzzy guess,
    just the known wording change. Every other role's category text is unchanged, so this is a
    no-op for them. Never calls a model."""

    model_name = "qwen3.5:9b (REPLAYED from Phase 2 -- not live)"

    def __init__(self, trace_path: Path | None = None):
        path = trace_path or _DEFAULT_TRACE
        self._by_key: dict[tuple[str, frozenset], dict] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("task") != "nominate_sufficiency_role":
                continue
            category = row["input_text"].split("\n", 1)[0].replace("[category] ", "")
            proposition_ids = frozenset(_PROPOSITION_ID_RE.findall(row["input_text"]))
            # A later identical-key call (Finding 1's own duplicate-call artifact, e.g. c1's
            # brain_region_or_network queried twice) returns the same recorded content either
            # way -- last-write-wins is harmless here, never a silent divergence.
            self._by_key[(category, proposition_ids)] = row

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        proposition_ids = frozenset(c["proposition_id"] for c in candidates)
        lookup_category = _V9_TO_V8_CATEGORY_DESCRIPTION.get(category_description, category_description)
        row = self._by_key.get((lookup_category, proposition_ids))
        if row is None:
            raise RecordedNominationReplayError(
                f"no Phase 2 recorded call matches (category={category_description!r}, "
                f"candidates={sorted(proposition_ids)}) -- the replay must never fabricate or "
                "silently skip a structural comparison point"
            )
        parsed = json.loads(row["raw_output"])
        return parsed.get("nominations", [])


def run_recorded_v9(*, run_dir: Path, contract_by_child: dict, model_client, model_name: str) -> dict:
    """The nomination diagnostic over a PRESERVED v9 run, under that run's recorded historical semantics (v3).

    Mirrors `sufficiency_model_nomination_diagnostic.run` exactly, except that the version is pinned to v3, the version the
    recorded run was produced under. The production driver keeps the current constant and is never reused here (I2-2).
    """
    children = diag._load_children_by_id(run_dir)
    sealed = diag._load_sealed(run_dir)
    parent_of = diag._parent_of(children)
    deterministic_only = sd.compute_diagnostic_sufficiency_map(
        sealed, contract_by_child, parent_of, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
    )
    with_model = sd.compute_diagnostic_sufficiency_map(
        sealed,
        contract_by_child,
        parent_of,
        model_client=model_client,
        semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
    )
    return {"deterministic_only": deterministic_only, "with_model": with_model, "model_name": model_name}


def replay(*, run_dir: Path, trace_path: Path | None = None) -> dict:
    """Runs deterministic-only AND corrected-mapper-over-RECORDED-outputs, mirroring
    `sufficiency_model_nomination_diagnostic.run`'s own shape exactly, but with
    `RecordedNominationClient` in place of a live `QwenTasks`. `contract_by_child` is loaded from
    the CURRENT committed frozen artifact (v9, post-Findings 1/2/C) -- this replay tests the
    CORRECTED mapper's structural accounting; it never re-authors the contract."""
    _frozen, contract_by_child = diag.load_frozen_contract()
    client = RecordedNominationClient(trace_path)
    result = run_recorded_v9(
        run_dir=run_dir, contract_by_child=contract_by_child, model_client=client, model_name=client.model_name
    )
    return {**result, "replay_note": "structural accounting only -- not evidence v9 semantics solve Finding C"}


def instance_count_report(with_model: dict) -> dict[str, dict]:
    """{child_id: {requirement_id: {'state', 'instance_count', 'supporting_proposition_ids_by_instance'}}}
    -- never a targeted expected number, purely descriptive."""
    report: dict[str, dict] = {}
    for child_id, contract in with_model.items():
        report[child_id] = {}
        for req in contract["requirements"]:
            report[child_id][req["id"]] = {
                "state": req["state"],
                "instance_count": len(req["instances"]),
                "instance_keys": [inst["instance_key"] for inst in req["instances"]],
            }
    return report


def main() -> int:
    run_dir = (
        Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930" / "run"
    )
    result = replay(run_dir=run_dir)
    report = instance_count_report(result["with_model"])
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
