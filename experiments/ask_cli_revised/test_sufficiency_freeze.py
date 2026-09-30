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


if __name__ == "__main__":
    unittest.main()
