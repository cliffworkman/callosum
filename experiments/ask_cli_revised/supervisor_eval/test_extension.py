"""The Gemma3:27B tier-up extension seam.

The first tranche is frozen and immutable. The extension adds ONE candidate identity for a post-hoc, predeclared
same-family scale test without touching the frozen registry, envelope, battery or scorer, and without letting the
new model masquerade as a member of the original four.
"""

import json
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.supervisor_eval import build_battery as bb
from experiments.ask_cli_revised.supervisor_eval import cases, extension, freeze, models, run_eval
from experiments.ask_cli_revised.supervisor_eval.test_run_eval import rec
from experiments.ask_cli_revised.supervisor_eval.test_scoring import perfect_output

FIRST_TRANCHE_KEYS = ["qwen3.5-9b", "gemma3-12b", "phi4-14b", "gpt-oss-20b"]


class RegistrySeparationTests(unittest.TestCase):
    def test_the_first_tranche_candidate_set_is_unchanged(self):
        self.assertEqual([c["key"] for c in models.CANDIDATES], FIRST_TRANCHE_KEYS)

    def test_the_extension_adds_exactly_gemma3_27b_outside_the_frozen_registry(self):
        self.assertEqual([c["key"] for c in extension.CANDIDATES], ["gemma3-27b"])
        self.assertEqual(extension.CANDIDATES[0]["tag"], "gemma3:27b")
        self.assertFalse({c["key"] for c in extension.CANDIDATES} & {c["key"] for c in models.CANDIDATES})

    def test_the_extension_module_is_not_part_of_the_frozen_code(self):
        self.assertNotIn("extension.py", bb.FROZEN_CODE)

    def test_the_candidate_carries_no_execution_override_it_runs_the_frozen_envelope(self):
        cand = extension.CANDIDATES[0]
        self.assertIsNone(cand["think_level"])  # Gemma3 has no thinking channel; none is injected
        overrides = {
            "options",
            "envelope",
            "num_ctx",
            "num_predict",
            "temperature",
            "seed",
            "prompt",
            "schema",
            "think",
        }
        self.assertEqual(set(cand) & overrides, set())

    def test_the_registry_size_is_labelled_a_pre_run_estimate_for_the_headroom_check_only(self):
        note = extension.CANDIDATES[0]["size_gb_note"]
        self.assertIn("estimate", note)
        self.assertIn("headroom", note)

    def test_candidate_lookup_resolves_both_registries_and_rejects_an_unknown_key(self):
        self.assertEqual(run_eval._candidate("gemma3-12b"), models.by_key("gemma3-12b"))
        self.assertEqual(run_eval._candidate("gemma3-27b")["tag"], "gemma3:27b")
        with self.assertRaises(KeyError):
            run_eval._candidate("no-such-model")

    def test_the_real_freeze_is_still_intact(self):
        manifest_path, private_path, freeze_path = run_eval._paths()
        if not private_path.exists():
            self.skipTest("private battery not present on this machine")
        self.assertEqual(freeze.verify(freeze_path, bb.freeze_spec(manifest_path, private_path)), [])


class ArtifactIdentityTests(unittest.TestCase):
    """Durable identity comes from what the runtime observed, never from the pre-run estimate."""

    ENTRY = {"name": "gemma3:27b", "digest": "abc123", "size": 17_400_000_000, "modified_at": "2026-09-23", "x": 1}

    def test_identity_is_the_observed_digest_and_size_only(self):
        self.assertEqual(extension.artifact_identity(self.ENTRY), {"digest": "abc123", "size_bytes": 17_400_000_000})

    def test_a_missing_or_incomplete_entry_is_absent_not_guessed(self):
        self.assertIsNone(extension.artifact_identity(None))
        self.assertIsNone(extension.artifact_identity({"name": "gemma3:27b"}))

    def test_capture_finds_the_entry_by_tag_or_latest_alias(self):
        class Client:
            def tags(self_inner):
                return [{"name": "other:1b", "digest": "z", "size": 1}, self.ENTRY]

        self.assertEqual(extension.capture_artifact(Client(), "gemma3:27b")["digest"], "abc123")
        self.assertIsNone(extension.capture_artifact(Client(), "gemma3:12b"))


class ExtensionBlockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "FREEZE.txt"
        self.path.write_text(
            json.dumps(
                {
                    "freeze_sha256": "f" * 64,
                    "json": {"battery_manifest": "a" * 64},
                    "private_files": {"battery.private.json": "b" * 64},
                }
            ),
            encoding="utf-8",
        )

    def test_the_block_names_itself_a_post_hoc_extension_of_the_frozen_first_tranche(self):
        block = extension.extension_block(self.path, {"digest": "d", "size_bytes": 5})
        self.assertEqual(block["extension_of"], "first-tranche")
        self.assertIn("post-hoc", block["kind"])
        self.assertIn("predeclared", block["kind"])
        self.assertEqual(block["first_tranche_freeze_commit"], "3d12610d")
        self.assertEqual(block["first_tranche_results_commit"], "87e3d7c3")

    def test_the_block_pins_the_original_freeze_battery_and_envelope(self):
        block = extension.extension_block(self.path, None)
        self.assertEqual(block["freeze_sha256"], "f" * 64)
        self.assertEqual(block["battery_manifest_sha256"], "a" * 64)
        self.assertEqual(block["private_battery_sha256"], "b" * 64)
        self.assertEqual(block["envelope"], models.ENVELOPE)

    def test_the_artifact_is_passed_through_as_observed_and_no_registry_estimate_leaks_in(self):
        block = extension.extension_block(self.path, {"digest": "d", "size_bytes": 5})
        self.assertEqual(block["artifact"], {"digest": "d", "size_bytes": 5})
        self.assertNotIn("size_gb", json.dumps(block))
        self.assertIsNone(extension.extension_block(self.path, None)["artifact"])


class ReceiptRoutingTests(unittest.TestCase):
    """`report` keeps writing only the first tranche; `report-extension` writes only the extension."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.work, self.receipts = root / "work", root / "receipts"
        self.saved = (run_eval.WORK_DIR, run_eval.RECEIPT_DIR)
        run_eval.WORK_DIR, run_eval.RECEIPT_DIR = self.work, self.receipts
        self.addCleanup(lambda: setattr(run_eval, "WORK_DIR", self.saved[0]))
        self.addCleanup(lambda: setattr(run_eval, "RECEIPT_DIR", self.saved[1]))

    def _stage0(self, key, tag):
        (self.work / key).mkdir(parents=True, exist_ok=True)
        (self.work / key / "stage0.json").write_text(
            json.dumps({"model": tag, "verdict": "ok", "envelope": models.ENVELOPE}), encoding="utf-8"
        )

    def _battery(self, key):
        rows = [
            {"case_id": s["case_id"], "attempt": 1, "input_sha256": "x", "call": rec(json.dumps(perfect_output(s)))}
            for s in cases.build_case_specs()
        ]
        (self.work / key / "battery_calls.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
        )

    def _written(self):
        return sorted(p.name for p in self.receipts.glob("*.json")) if self.receipts.exists() else []

    def test_report_writes_only_first_tranche_receipts(self):
        self._stage0("gemma3-12b", "gemma3:12b")
        self._stage0("gemma3-27b", "gemma3:27b")
        run_eval._cmd_report()
        self.assertEqual(self._written(), ["gemma3-12b.json"])

    def test_report_extension_writes_only_the_extension_receipt(self):
        self._stage0("gemma3-12b", "gemma3:12b")
        self._stage0("gemma3-27b", "gemma3:27b")
        run_eval._cmd_report_extension()
        self.assertEqual(self._written(), ["gemma3-27b.json"])

    def test_the_first_tranche_receipt_gains_no_extension_block(self):
        self._stage0("gemma3-12b", "gemma3:12b")
        self._battery("gemma3-12b")
        run_eval._cmd_report()
        receipt = json.loads((self.receipts / "gemma3-12b.json").read_text(encoding="utf-8"))
        self.assertNotIn("extension", receipt)

    def test_a_scored_extension_receipt_carries_the_block_and_the_observed_artifact(self):
        self._stage0("gemma3-27b", "gemma3:27b")
        self._battery("gemma3-27b")
        (self.work / "gemma3-27b" / "artifact.json").write_text(
            json.dumps({"digest": "d", "size_bytes": 5}), encoding="utf-8"
        )
        run_eval._cmd_report_extension()
        receipt = json.loads((self.receipts / "gemma3-27b.json").read_text(encoding="utf-8"))
        frozen = json.loads((bb.PACKAGE_DIR / bb.FREEZE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(receipt["candidate"], "gemma3-27b")
        self.assertEqual(receipt["extension"]["freeze_sha256"], frozen["freeze_sha256"])
        self.assertEqual(receipt["extension"]["artifact"], {"digest": "d", "size_bytes": 5})
        self.assertIn("qualified", receipt)

    def test_main_dispatches_report_extension(self):
        self._stage0("gemma3-27b", "gemma3:27b")
        self.assertEqual(run_eval.main(["report-extension"]), 0)
        self.assertEqual(self._written(), ["gemma3-27b.json"])


class ArtifactRecordingTests(unittest.TestCase):
    def test_recording_writes_the_observed_identity_next_to_the_candidate_run(self):
        class Client:
            def tags(self):
                return [{"name": "gemma3:27b", "digest": "abc", "size": 9}]

        with tempfile.TemporaryDirectory() as tmp:
            saved, run_eval.WORK_DIR = run_eval.WORK_DIR, Path(tmp)
            try:
                run_eval._record_artifact(Client(), {"key": "gemma3-27b", "tag": "gemma3:27b"})
                written = json.loads((Path(tmp) / "gemma3-27b" / "artifact.json").read_text(encoding="utf-8"))
            finally:
                run_eval.WORK_DIR = saved
        self.assertEqual(written, {"digest": "abc", "size_bytes": 9})


if __name__ == "__main__":
    unittest.main()
