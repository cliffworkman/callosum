"""Offline replay of Phase 5's OWN recorded v9 model outputs, scripted to Cliff's OWN
already-frozen manual adjudication (`PHASE5_V9_LIVE_RERUN_RESULTS.md`) -- NO live model call
anywhere in this module, and NO new adjudication. This answers one narrow question: does
withholding EXACTLY the one nomination Phase 5's adjudication judged circular/self-referential
("described a behavioral manifestation of the 'anomalous-is-bad' stereotype affecting
prosociality") remove c2's false `filled` state without damaging any of the 8 correctly-accepted
claims?

HISTORICAL NOTE (Phase 9): this module originally reproduced Phase 6's live second-pass
specificity-confirmation gate (`confirm_specific_instances`/`verify_specific_instances`), which
Phase 7's live diagnostic found net-harmful and Phase 9 retired from the active mapping path (see
`sufficiency_mapping.py`'s own module comment). The scripted validator below is now
SELF-CONTAINED: it filters Phase 5's recorded raw nominations inline, inside its own
`nominate_sufficiency_role`, so it reproduces the exact same documented net filtering effect
through today's single-model-operation mapping path (`nominate_with_model` ->
`_bind_role_candidates`, no second call) -- it does not call, and does not depend on, any
Phase-6-era code. Never evidence of what a live model would do under any prompt; a scripted
reproduction of an already-completed human judgment call, same as before.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.ask_cli_revised import sufficiency_model_nomination_diagnostic as diag
from experiments.ask_cli_revised.sufficiency_phase2_replay import (
    RecordedNominationClient,
    RecordedNominationReplayError,
    run_recorded_v9,
)

_DEFAULT_TRACE = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "sufficiency-nomination-diagnostic-v9-20260930"
    / "qwen_calls.jsonl"
)
_DEFAULT_RUN_DIR = (
    Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930" / "run"
)

# The exact nominated text PHASE5_V9_LIVE_RERUN_RESULTS.md's manual adjudication judged
# "Incorrect -- Vague/circular" (c2's `behavior_or_behavioral_measure`, propositions p1/p4/p8/
# p12/p24). Extracted byte-for-byte from the recorded trace itself (verified via
# `.encode("unicode_escape")`, not retyped by hand) -- U+201C/U+201D curly quotes, ordinary ASCII
# space before "bad". This is the ONLY string this replay's scripted validator vetoes.
_VETOED_EXACT_TEXT = "described a behavioral manifestation of the “anomalous-is- bad” stereotype affecting prosociality"


class _RecordedV9NominationClient(RecordedNominationClient):
    """Phase 5's trace was recorded directly against the v9 contract (the rerun's own category
    descriptions ARE v9 wording for every role) -- unlike Phase 2's trace, no v8->v9 category-
    description translation applies here. Overrides the lookup to use `category_description`
    verbatim; the (category, proposition_ids) keying and the loud `RecordedNominationReplayError`
    on any unmatched candidate set are otherwise identical to the parent."""

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        proposition_ids = frozenset(c["proposition_id"] for c in candidates)
        row = self._by_key.get((category_description, proposition_ids))
        if row is None:
            raise RecordedNominationReplayError(
                f"no Phase 5 recorded call matches (category={category_description!r}, "
                f"candidates={sorted(proposition_ids)}) -- the replay must never fabricate or "
                "silently skip a structural comparison point"
            )
        parsed = json.loads(row["raw_output"])
        return parsed.get("nominations", [])


class _Phase5AdjudicationValidator:
    """Replays Phase 5's OWN frozen manual adjudication as a scripted, SELF-CONTAINED filter over
    the inner recorded client's raw nominations -- withholds EXACTLY `_VETOED_EXACT_TEXT`, returns
    every other nomination Phase 5 actually produced (the amygdala findings, the two "visual
    attention" phrasings, the EBQ findings, and the four c8 named constructs) unchanged. From
    `nominate_with_model`'s perspective this is indistinguishable from any other
    `nominate_sufficiency_role` implementation returning a shorter list -- there is no second
    call, no separate verdict stage; the filtering decision happens before this method returns."""

    model_name = "scripted-phase5-adjudication (REPLAYED -- not live)"

    def __init__(self, inner_client: _RecordedV9NominationClient):
        self._inner = inner_client
        self.decisions_made: list[dict] = []

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        raw = self._inner.nominate_sufficiency_role(category_description=category_description, candidates=candidates)
        kept = []
        for item in raw:
            exact_text = item.get("exact_text", "")
            specific = exact_text.strip() != _VETOED_EXACT_TEXT
            self.decisions_made.append(
                {"category_description": category_description, "exact_text": exact_text, "specific": specific}
            )
            if specific:
                kept.append(item)
        return kept


def replay(*, run_dir: Path = _DEFAULT_RUN_DIR, trace_path: Path | None = None) -> dict:
    """Runs deterministic-only AND the (self-contained, scripted-filter) mapper over Phase 5's
    RECORDED outputs, mirroring `sufficiency_phase2_replay.replay`'s own shape. `contract_by_child`
    is loaded from the CURRENT committed frozen artifact (v9, byte-identical, hash unchanged by
    this or any later phase) -- this replay never re-authors the contract and makes no live call."""
    _frozen, contract_by_child = diag.load_frozen_contract()
    inner = _RecordedV9NominationClient(trace_path or _DEFAULT_TRACE)
    validator = _Phase5AdjudicationValidator(inner)
    result = run_recorded_v9(
        run_dir=run_dir, contract_by_child=contract_by_child, model_client=validator, model_name=validator.model_name
    )
    return {
        **result,
        "replay_note": "Phase 5's own frozen manual adjudication replayed as a self-contained scripted filter",
    }


def state_report(mapped: dict) -> dict[str, dict]:
    """{child_id: {requirement_id: {'state', 'instance_count', 'instance_keys'}}} -- the same
    descriptive shape `sufficiency_phase2_replay.instance_count_report` uses, so the two replays'
    output is directly comparable by eye."""
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
        "with_model_and_specificity_gate": state_report(result["with_model"]),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
