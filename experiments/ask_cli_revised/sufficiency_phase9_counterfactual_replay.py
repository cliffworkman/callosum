"""COUNTERFACTUAL plumbing fixture (Phase 9 Part H) -- NOT a replay of any real model trace, and
NOT evidence of what `qwen3.5:9b` (or any model) would actually produce under the reformulated
minimal-referent-extraction prompt (`qwen.nomination_prompt`, Phase 9 Part B). It hand-scripts the
MANUALLY ADJUDICATED outcome Phase 8's forensic pass derived -- what a well-behaved nominator,
under the new extraction framing, SHOULD have returned for each of the real role-calls Phase 5/7
actually exercised against q_aib's preserved hierarchical evidence -- and runs it through today's
real, single-stage mapping path end-to-end: `nominate_with_model` -> deterministic grounding/
admissibility -> `RoleBinding` -> `map_requirement`/`map_paired_requirement` ->
`compute_diagnostic_sufficiency_map`. The point is to prove the PLUMBING (grounding, forking,
anchor-dedup, same_proposition joint grounding, parent propagation, instance-key derivation) still
behaves correctly end-to-end when FED these specific counterfactual nominations -- never a claim
about live model behavior.

Keyed by `(category_description, frozenset(all proposition_ids offered in that exact call))` --
the SAME collision-safe keying `sufficiency_phase2_replay.RecordedNominationClient` already uses
and for the SAME documented reason: several role-calls here share an IDENTICAL
`category_description` (c1's/c5's own region attempts both read "a specific named brain area";
c2's/c5's own behavior attempts both read the identical long behavior description) while offering
DIFFERENT candidate pools -- a per-proposition-only key would silently leak a nomination scripted
for one child's call into another child's call that happens to share some, but not all, of the
same underlying propositions. Caught empirically while building this fixture (c5 spuriously
became `filled` before this keying fix) -- left documented here as a reminder, not silently fixed
away.

Every scripted `exact_text` below is independently grounded against the REAL verified passage in
`.local/e2e-runs/q-aib-hierarchical-t5c-live-20260930/run/11_verified_ledger.json` by the
engine's own (unmodified) `canonical_text_contains` check -- a typo or invented span here would be
silently dropped by the real grounding gate, exactly as it would for a real model.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.ask_cli_revised import sufficiency_model_nomination_diagnostic as diag

_DEFAULT_RUN_DIR = Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930" / "run"

_CATEGORY_REGION_C1_C5 = "a specific named brain area"
_CATEGORY_REGION_C4 = "a specific NAMED brain area"
_CATEGORY_BEHAVIOR = (
    "an observed behavior, behavioral choice or action, or a task or measure of behavior "
    "(not a self-report attitude, belief, or prejudice questionnaire)"
)
_CATEGORY_TRAIT = "a named individual-difference trait or construct"
_CATEGORY_ATTITUDE = "a named attitude type or measure"

# The exact per-call candidate pools Phase 5/7's own live trace offered, reproduced here as plain
# proposition-id frozensets -- NOT loaded from the trace file (this is a hand-authored
# counterfactual, not a replay), but transcribed from it for authenticity of SCOPE (which
# propositions a well-behaved nominator would actually have been shown for each real call).
_C1_REGION_POOL = frozenset({"p2", "p11"})
_C4_REGION_POOL = frozenset({"p11", "p2"})
_C2_BEHAVIOR_POOL = frozenset({"p1", "p4", "p8", "p12", "p24", "p5", "p15", "p6", "p18", "p25"})
_C5_REGION_AND_BEHAVIOR_POOL = frozenset(
    {"p12", "p1", "p4", "p8", "p24", "p14", "p3", "p7", "p17", "p26", "p15", "p5", "p16", "p10", "p19", "p13"}
)
_C6_SECOND_REGION_AND_ATTITUDE_POOL = frozenset({"p17", "p3", "p7", "p14", "p26", "p18", "p6", "p25", "p19", "p10", "p16"})
_C8_TRAIT_POOL = frozenset({"p20", "p9"})

# {(category_description, full_candidate_pool): [(proposition_id, exact_text_or_list), ...]}.
# A (category_description, pool) pair NOT listed here declines entirely (empty list) -- matching
# every true-negative decline Phase 2/5/7 already manually confirmed (c1's own modality attempt,
# c10's culture attempt, c12's intervention attempts x2 units, c5's region AND behavior attempts
# over its own 16-proposition pool, c6's second region search over its own 11-proposition pool).
# None of those candidate pools contain an extractable referent under ANY framing, so a
# well-behaved nominator declines them identically regardless of this reformulation.
_SCRIPTED: dict[tuple[str, frozenset], list[tuple[str, object]]] = {
    (_CATEGORY_REGION_C1_C5, _C1_REGION_POOL): [("p2", "amygdala"), ("p11", "amygdala")],
    (_CATEGORY_REGION_C4, _C4_REGION_POOL): [("p11", "amygdala"), ("p2", "amygdala")],
    (_CATEGORY_BEHAVIOR, _C2_BEHAVIOR_POOL): [
        (
            "p5",
            [
                "visual attention toward people with facial anomalies",
                "influence visual attention when looking at faces with anomalous anatomy",
            ],
        ),
        ("p15", "visual attention toward people with facial anomalies"),
    ],
    (_CATEGORY_TRAIT, _C8_TRAIT_POOL): [
        ("p20", ["IAT and EBQ", "just-world beliefs", "affective empathy", "less generosity in the DG"]),
        ("p9", ["IAT and EBQ", "just-world beliefs", "affective empathy", "less generosity in the DG"]),
    ],
    (_CATEGORY_ATTITUDE, _C6_SECOND_REGION_AND_ATTITUDE_POOL): [
        ("p17", "Explicit Bias Questionnaire"),
        ("p3", "Explicit Bias Questionnaire"),
        ("p7", "Explicit Bias Questionnaire"),
        ("p14", "Explicit Bias Questionnaire"),
        ("p26", "Explicit Bias Questionnaire"),
    ],
    # c5's region AND behavior calls, and c6's second region search, are DELIBERATELY absent --
    # true-negative declines, confirmed unchanged from every prior phase.
}


class _CounterfactualMinimalReferentClient:
    """Hand-scripted, NOT a replay of any trace file -- see module docstring. Declines (returns no
    nomination) for any `(category_description, full_candidate_pool)` pair not explicitly listed
    in `_SCRIPTED`."""

    model_name = "counterfactual-minimal-referent (SCRIPTED -- not live, not a replay)"

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        pool = frozenset(c["proposition_id"] for c in candidates)
        entries = _SCRIPTED.get((category_description, pool))
        if entries is None:
            return []
        out = []
        for proposition_id, texts in entries:
            for text in texts if isinstance(texts, list) else [texts]:
                out.append({"proposition_id": proposition_id, "exact_text": text})
        return out


def replay(*, run_dir: Path = _DEFAULT_RUN_DIR) -> dict:
    """Runs deterministic-only AND the counterfactual-scripted mapper over the REAL preserved
    q_aib evidence. `contract_by_child` is loaded from the CURRENT committed frozen artifact (v9,
    byte-identical, hash unchanged by this or any prior/later phase) -- never re-authored here,
    and no live call is made anywhere in this module."""
    _frozen, contract_by_child = diag.load_frozen_contract()
    client = _CounterfactualMinimalReferentClient()
    result = diag.run(run_dir=run_dir, contract_by_child=contract_by_child, model_client=client, model_name=client.model_name)
    return {
        **result,
        "replay_note": (
            "COUNTERFACTUAL -- a hand-scripted fixture representing the manually adjudicated outcome "
            "under the Phase 9 minimal-referent extraction framing, never a real model trace or a "
            "claim about live Qwen behavior"
        ),
    }


def state_report(mapped: dict) -> dict[str, dict]:
    report: dict[str, dict] = {}
    for child_id, contract in mapped.items():
        report[child_id] = {}
        for req in contract["requirements"]:
            report[child_id][req["id"]] = {
                "state": req["state"],
                "instance_count": len(req["instances"]),
                "instance_keys": [inst["instance_key"] for inst in req["instances"]],
            }
    return report


def main() -> int:
    result = replay()
    report = {
        "deterministic_only": state_report(result["deterministic_only"]),
        "counterfactual_minimal_referent": state_report(result["with_model"]),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
