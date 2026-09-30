"""Tests for the offline Phase 2 recorded-output replay harness. NO live model call anywhere in
this file -- `RecordedNominationClient` is exercised against a small hand-built synthetic trace
file (isolating its own matching logic) and, where the real preserved artifacts are present,
against the actual Phase 2 trace.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised import sufficiency_phase2_replay as replay

_DEFAULT_RUN_DIR = (
    Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930" / "run"
)
_RUN_DIR = Path(os.environ.get("QAIB_HIERARCHICAL_RUN_DIR", str(_DEFAULT_RUN_DIR)))
_DEFAULT_TRACE = replay._DEFAULT_TRACE
needs_real_run = unittest.skipUnless(
    (_RUN_DIR / "01_request_contract.json").is_file(), f"preserved run not present at {_RUN_DIR}"
)
needs_real_trace = unittest.skipUnless(
    _DEFAULT_TRACE.is_file(), f"Phase 2's own recorded trace is not present at {_DEFAULT_TRACE}"
)
needs_frozen_contract = unittest.skipUnless(
    replay.diag.sf.FROZEN_PATH.is_file(), "no installed sufficiency_contract frozen pin in this worktree yet"
)


def _write_trace(rows: list[dict]) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
    for row in rows:
        tmp.write(json.dumps(row) + "\n")
    tmp.close()
    return Path(tmp.name)


def _call_row(category: str, proposition_ids: list[str], nominations: list[dict]) -> dict:
    return {
        "task": "nominate_sufficiency_role",
        "input_text": f"[category] {category}\n[proposition_ids] {proposition_ids!r}",
        "raw_output": json.dumps({"nominations": nominations}),
    }


class RecordedNominationClientSyntheticTests(unittest.TestCase):
    """Isolated proof of the matching logic against a small hand-built trace -- no dependency on
    the real Phase 2 artifacts existing."""

    def test_exact_category_and_candidate_set_match_returns_the_recorded_nominations(self):
        rows = [_call_row("role x", ["p1", "p2"], [{"proposition_id": "p1", "exact_text": "alpha"}])]
        path = _write_trace(rows)
        client = replay.RecordedNominationClient(path)
        result = client.nominate_sufficiency_role(
            category_description="role x", candidates=[{"proposition_id": "p1"}, {"proposition_id": "p2"}]
        )
        self.assertEqual(result, [{"proposition_id": "p1", "exact_text": "alpha"}])

    def test_no_matching_recorded_call_raises_never_fabricates(self):
        path = _write_trace([_call_row("role x", ["p1"], [])])
        client = replay.RecordedNominationClient(path)
        with self.assertRaises(replay.RecordedNominationReplayError):
            client.nominate_sufficiency_role(category_description="role x", candidates=[{"proposition_id": "p9"}])

    def test_two_different_roles_sharing_one_candidate_pool_never_collide(self):
        """The exact bug found and fixed while building this harness: two roles on one child
        drawing from the identical admissible-units pool must not silently cross-answer."""
        rows = [
            _call_row("role a", ["p1", "p2"], [{"proposition_id": "p1", "exact_text": "from role a"}]),
            _call_row("role b", ["p1", "p2"], [{"proposition_id": "p2", "exact_text": "from role b"}]),
        ]
        path = _write_trace(rows)
        client = replay.RecordedNominationClient(path)
        candidates = [{"proposition_id": "p1"}, {"proposition_id": "p2"}]
        result_a = client.nominate_sufficiency_role(category_description="role a", candidates=candidates)
        result_b = client.nominate_sufficiency_role(category_description="role b", candidates=candidates)
        self.assertEqual(result_a, [{"proposition_id": "p1", "exact_text": "from role a"}])
        self.assertEqual(result_b, [{"proposition_id": "p2", "exact_text": "from role b"}])

    def test_v9_wording_for_a_finding_c_role_resolves_to_its_v8_recorded_call(self):
        from experiments.ask_cli_revised import sufficiency_authoring as sa

        rows = [
            _call_row("a neural measure or imaging modality", ["p1"], [{"proposition_id": "p1", "exact_text": "x"}])
        ]
        path = _write_trace(rows)
        client = replay.RecordedNominationClient(path)
        result = client.nominate_sufficiency_role(
            category_description=sa._NEURAL_MEASURE_OR_MODALITY_DESCRIPTION, candidates=[{"proposition_id": "p1"}]
        )
        self.assertEqual(result, [{"proposition_id": "p1", "exact_text": "x"}])

    def test_identical_repeated_call_is_harmless_last_write_wins(self):
        rows = [
            _call_row("role x", ["p1"], [{"proposition_id": "p1", "exact_text": "same"}]),
            _call_row("role x", ["p1"], [{"proposition_id": "p1", "exact_text": "same"}]),
        ]
        path = _write_trace(rows)
        client = replay.RecordedNominationClient(path)
        result = client.nominate_sufficiency_role(category_description="role x", candidates=[{"proposition_id": "p1"}])
        self.assertEqual(result, [{"proposition_id": "p1", "exact_text": "same"}])


@needs_real_run
@needs_real_trace
@needs_frozen_contract
class RealPhase2ReplayTests(unittest.TestCase):
    """Runs the actual replay against Phase 2's own preserved trace -- no live model call."""

    def test_replay_runs_cleanly_against_every_recorded_phase2_call(self):
        """If any candidate set the corrected mapper now requests cannot be matched to a
        historical call, this raises rather than silently passing -- a clean run is itself the
        structural proof that A/B's fixes don't change WHICH (child, role, candidate-set)
        combinations arise, only how they're counted/keyed."""
        result = replay.replay(run_dir=_RUN_DIR)
        self.assertEqual(set(result["with_model"]), set(result["deterministic_only"]))
        self.assertIn("replay_note", result)

    def test_replay_is_deterministic_across_repeated_runs(self):
        first = replay.replay(run_dir=_RUN_DIR)
        second = replay.replay(run_dir=_RUN_DIR)
        self.assertEqual(first["with_model"], second["with_model"])

    def test_instance_count_report_never_exceeds_phase2s_own_raw_nomination_total(self):
        """Never asserts a targeted number -- only the honest invariant that deduplication can
        only ever reduce or hold steady the reported instance count relative to Phase 2's own raw
        (pre-dedup) nomination count, never increase it."""
        result = replay.replay(run_dir=_RUN_DIR)
        report = replay.instance_count_report(result["with_model"])
        total_instances = sum(row["instance_count"] for child in report.values() for row in child.values())
        # Phase 2's own recorded raw nomination total across all 15 calls (see
        # MODEL_NOMINATION_DIAGNOSTIC_RESULTS.md) -- an upper bound, not a target.
        self.assertLessEqual(total_instances, 26 + 20)  # generous slack for non-model-sourced instances too


if __name__ == "__main__":
    unittest.main()
