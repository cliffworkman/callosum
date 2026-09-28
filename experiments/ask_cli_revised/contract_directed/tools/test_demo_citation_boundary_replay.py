"""Offline safety tests for `demo_citation_boundary_replay.py`. No model/NLI/network call: `StubEntail` is a
fixed-score fake, and every assertion here is about the script's own guard logic and pure output shape."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import demo_citation_boundary_replay as demo


class StubEntailTests(unittest.TestCase):
    def test_stub_returns_the_fixed_score_for_every_pair_and_records_calls(self):
        stub = demo.StubEntail(score=(0.5, 0.1))
        pairs = [("premise a", "hyp a"), ("premise b", "hyp b")]
        scores = stub(pairs)
        self.assertEqual(scores, [(0.5, 0.1), (0.5, 0.1)])
        self.assertEqual(stub.calls, [pairs])


class ProtectedRunDirsTests(unittest.TestCase):
    def test_protected_dirs_covers_every_currently_existing_run_directory(self):
        existing = {p.name for p in demo.RUNS_DIR.iterdir() if p.is_dir() and p.name != demo.DEMO_DIR.name}
        missing = existing - demo.PROTECTED_RUN_DIRS
        self.assertEqual(missing, set(), f"these existing run dirs are not in PROTECTED_RUN_DIRS: {missing}")


class MainGuardTests(unittest.TestCase):
    def test_main_refuses_to_overwrite_an_already_populated_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            populated = Path(tmp) / "already-has-stuff"
            populated.mkdir()
            (populated / "x.txt").write_text("x", encoding="utf-8")
            original = demo.DEMO_DIR
            try:
                demo.DEMO_DIR = populated
                with self.assertRaises(RuntimeError):
                    with endpoint_guard.refuse_all():
                        demo.main()
            finally:
                demo.DEMO_DIR = original


if __name__ == "__main__":
    unittest.main()
