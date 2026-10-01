"""Phase 12 offline RecoveryTarget inventory. NO live model call, NO retrieval, NO recovery
execution -- replays Phase 5's own FROZEN recorded nomination outputs
(`sufficiency_phase5_replay.replay`, scripted to Cliff's already-frozen manual adjudication, never
re-adjudicated here) through the CURRENT mapper/runtime (today's `compute_diagnostic_sufficiency_
map`, which now also stamps `model_dependency_origins` -- Phase 12's own addition -- and the
current, rolled-back-to-Phase-5 `qwen.nomination_prompt`), then computes what the NEW
`sufficiency_recovery_targets.compute_recovery_targets` generator produces against that real,
historical, empirically-tested mapping result.

This is evidence about "what does the new RecoveryTarget architecture produce when fed the
empirically strongest Phase-5 mapper's own outputs" -- never a claim that Phase 5 itself
historically contained fields that did not yet exist, and never a new live run. No historical
Phase-5 artifact (the recorded `qwen_calls.jsonl` trace, the frozen v9 contract) is altered.

Per round 3's own design: the first live recovery experiment must be selected from targets that
actually appear here, never pre-committed to a shape (e.g. c8->c9 redirection) without first
confirming the real preserved state instantiates it.
"""

from __future__ import annotations

import json

from experiments.ask_cli_revised import sufficiency_phase5_replay as replay_mod
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
from experiments.ask_cli_revised.sufficiency_model_nomination_diagnostic import _load_children_by_id, _parent_of


def build_inventory(*, run_dir=None) -> dict:
    """Returns `{"targets": [...], "replay_note": ...}` -- `targets` is a list (not the raw
    `{target_id: RecoveryTarget}` dict) so it serializes to stable, orderable JSON for a human
    hand-back report."""
    run_dir = run_dir or replay_mod._DEFAULT_RUN_DIR
    result = replay_mod.replay(run_dir=run_dir)
    children = _load_children_by_id(run_dir)
    parent_of = _parent_of(children)
    targets = srt.compute_recovery_targets(result["with_model"], parent_of)
    rows = [
        {
            "target_id": target["target_id"],
            "reason": target["reason"],
            "goal_mode": target["goal_mode"],
            "search_child_id": target["search_child_id"],
            "trigger_child_id": target["trigger_child_id"],
            "requirement_id": target["requirement_id"],
            "scope": target["scope"],
            "target_roles": target["target_roles"],
            "dependency_origins": target["dependency_origins"],
            "affected_descendants": list(target["affected_descendants"]),
            "hint": srt.recovery_query_hint(target, result["with_model"]),
        }
        for target in sorted(targets.values(), key=lambda t: t["target_id"])
    ]
    return {"targets": rows, "replay_note": result["replay_note"], "target_count": len(rows)}


def main() -> int:
    print(json.dumps(build_inventory(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
