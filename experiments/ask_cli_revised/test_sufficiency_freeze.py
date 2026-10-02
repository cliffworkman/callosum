"""Tests for the frozen-contract materialization CLI. No model, no network, no E2E."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised import sufficiency_freeze as sf

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "q-aib-hierarchical-t5c-live-20260930"
    / "run"
    / "01_request_contract.json"
)
_PATH = Path(os.environ.get("QAIB_REQUEST_CONTRACT", str(_DEFAULT_PATH)))
needs_real_contract = unittest.skipUnless(
    _PATH.is_file(), f"the preserved q_aib request contract is not present at {_PATH}"
)

# v8's own reviewed, live-run-authorized hash -- Cliff reviewed this exact value on 2026-09-30
# (sufficiency_contract.aib_hier_v8.review.json) and it was the frozen basis for the Phase 2 live
# replay (sufficiency_model_nomination_authorization.json). MUST remain byte-identical forever;
# this constant is never updated to track whatever `sa.QUESTION_KEY` currently points at.
_V8_REVIEWED_HASH = "9de276b19d2e5afee5f532d64c6a678de6e59a9f41f37198fa00409c5f3094ac"
_V8_FROZEN_PATH = Path(__file__).with_name("sufficiency_contract.aib_hier_v8.frozen.json")


@needs_real_contract
class WriteFrozenTests(unittest.TestCase):
    def test_write_frozen_writes_valid_json_with_combined_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            frozen = sf.write_frozen(output_path=out)
            self.assertTrue(out.is_file())
            on_disk = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(on_disk, frozen)
            self.assertEqual(len(frozen["combined_hash"]), 64)

    def test_the_committed_v8_frozen_file_is_permanently_immutable(self):
        """Reads the COMMITTED v8 artifact by its own fixed filename directly -- independent of
        whatever `sa.QUESTION_KEY`/`sf.FROZEN_PATH` currently point at (v9 and beyond). This is a
        permanent regression guard, not a 'does a fresh build match' check: v8 must never change
        again, no matter how many later contract versions are authored."""
        self.assertTrue(_V8_FROZEN_PATH.is_file(), "sufficiency_contract.aib_hier_v8.frozen.json must stay committed")
        on_disk = json.loads(_V8_FROZEN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["combined_hash"], _V8_REVIEWED_HASH)

    def test_write_frozen_matches_the_committed_frozen_pin_if_one_exists(self):
        """Never reopens FROZEN_PATH for writing -- regenerates into a temp file and compares."""
        if not sf.FROZEN_PATH.is_file():
            self.skipTest("no installed sufficiency_contract frozen pin in this worktree yet")
        on_disk = json.loads(sf.FROZEN_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            regenerated = sf.write_frozen(output_path=Path(tmp) / "regenerated.json")
        self.assertEqual(on_disk["combined_hash"], regenerated["combined_hash"])
        self.assertEqual(on_disk, regenerated)


class LoadVerifiedTests(unittest.TestCase):
    """Phase 20a: the reader half of this module -- `load_verified` is the one place a real
    hierarchy run sources its `{child_id: SufficiencyContract}` input. Uses the COMMITTED
    `sufficiency_contract.aib_hier_v9.frozen.json` + `.review.json` pair as its base fixture (both
    are tracked files, unlike the `.local/` closure artifacts `needs_real_contract` gates on) --
    copied to a temp dir and mutated per-test, never opening either committed file for writing.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.frozen_path = Path(self.tmp.name) / "frozen.json"
        self.review_path = Path(self.tmp.name) / "review.json"
        self.frozen = json.loads(sf.FROZEN_PATH.read_text(encoding="utf-8"))
        self.review = json.loads(sf.REVIEW_PATH.read_text(encoding="utf-8"))
        self._write()

    def _write(self, frozen=None, review=None):
        self.frozen_path.write_text(json.dumps(frozen if frozen is not None else self.frozen), encoding="utf-8")
        self.review_path.write_text(json.dumps(review if review is not None else self.review), encoding="utf-8")

    def load(self):
        return sf.load_verified(frozen_path=self.frozen_path, review_path=self.review_path)

    def test_the_real_committed_v9_pair_verifies_and_returns_every_child(self):
        contract_by_child = self.load()
        self.assertEqual(set(contract_by_child), set(self.frozen["per_child"]))
        for child_id, contract in contract_by_child.items():
            self.assertEqual(contract, self.frozen["per_child"][child_id]["frozen_view"])
            self.assertEqual(contract["child_id"], child_id)
            # exactly the shape compute_diagnostic_sufficiency_map's contract_by_child expects --
            # frozen_view strips every runtime-only key; none of them should be present.
            for req in contract["requirements"]:
                self.assertNotIn("instances", req)
                self.assertNotIn("state", req)
                self.assertNotIn("reason", req)

    def test_a_missing_frozen_file_is_a_benign_none_not_an_error(self):
        self.assertIsNone(sf.load_verified(frozen_path=Path(self.tmp.name) / "does-not-exist.json"))

    def test_a_tampered_per_child_frozen_view_is_rejected_naming_the_child(self):
        tampered = json.loads(json.dumps(self.frozen))
        any_child = next(iter(tampered["per_child"]))
        tampered["per_child"][any_child]["frozen_view"]["requirements"][0]["id"] = "TAMPERED"
        self._write(frozen=tampered)
        with self.assertRaises(sf.SufficiencyContractRejected) as ctx:
            self.load()
        self.assertIn(any_child, " ".join(ctx.exception.problems))

    def test_a_tampered_combined_hash_is_rejected(self):
        tampered = json.loads(json.dumps(self.frozen))
        tampered["combined_hash"] = "0" * 64
        self._write(frozen=tampered)
        with self.assertRaises(sf.SufficiencyContractRejected) as ctx:
            self.load()
        self.assertIn("combined_hash", " ".join(ctx.exception.problems))

    def test_a_missing_review_file_is_rejected_mentioning_review(self):
        self.review_path.unlink()
        with self.assertRaises(sf.SufficiencyContractRejected) as ctx:
            self.load()
        self.assertIn("review", " ".join(ctx.exception.problems).lower())

    def test_a_review_naming_a_different_combined_hash_is_rejected(self):
        stale_review = {**self.review, "combined_hash": "0" * 64}
        self._write(review=stale_review)
        with self.assertRaises(sf.SufficiencyContractRejected) as ctx:
            self.load()
        self.assertIn("combined_hash", " ".join(ctx.exception.problems))

    def test_a_review_naming_a_different_question_key_is_rejected(self):
        stale_review = {**self.review, "question_key": "some_other_question"}
        self._write(review=stale_review)
        with self.assertRaises(sf.SufficiencyContractRejected) as ctx:
            self.load()
        self.assertIn("question_key", " ".join(ctx.exception.problems))

    def test_every_missing_review_field_is_rejected(self):
        for field in ("reviewed_by", "reviewed_at"):
            with self.subTest(field=field):
                self._write(review={**self.review, field: ""})
                with self.assertRaises(sf.SufficiencyContractRejected) as ctx:
                    self.load()
                self.assertIn(field, " ".join(ctx.exception.problems))


if __name__ == "__main__":
    unittest.main()
