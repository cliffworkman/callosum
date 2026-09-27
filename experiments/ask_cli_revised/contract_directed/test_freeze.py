import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import freeze

DATA_PRESENT = (freeze.AB_ROOT / "runB" / "out" / "01_request_contract.json").is_file()


@unittest.skipUnless(DATA_PRESENT, "frozen private run data not present on this machine")
class FrozenSubstrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sub = freeze.load_frozen()

    def test_every_recorded_identity_reproduces(self):
        self.assertTrue(self.sub.all_checks_pass, {k: v for k, v in self.sub.checks.items() if not v})

    def test_eleven_children_in_recorded_order(self):
        self.assertEqual(tuple(c.child_id for c in self.sub.children), freeze.CHILD_IDS)

    def test_units_follow_the_frozen_ownership(self):
        c5 = self.sub.child("c5")
        self.assertEqual([u.unit_id for u in c5.units], ["M5", "M6", "C4", "C5"])
        self.assertEqual([u.unit_id for u in c5.content_units], ["M5", "M6"])
        self.assertEqual([u.unit_id for u in c5.condition_units], ["C4", "C5"])
        self.assertEqual(c5.primary_unit_id, "M5")
        self.assertEqual(self.sub.child("c8").primary_unit_id, "M9")
        self.assertEqual(self.sub.child("c12").primary_unit_id, "M14")
        self.assertEqual(self.sub.child("c9").pair_requirement_ids, ("RC-5#pair",))
        self.assertEqual(self.sub.child("c11").pair_requirement_ids, ("RC-6#pair",))
        self.assertEqual(self.sub.child("c5").pair_requirement_ids, ())

    def test_contract_text_is_the_exact_recorded_display(self):
        c11 = self.sub.child("c11")
        self.assertTrue(c11.contract_text.startswith(c11.wording))
        self.assertIn("Scope carried into this question", c11.contract_text)
        self.assertEqual(self.sub.child("c1").contract_text, "how does the anomalous is bad bias manifest in brain")

    def test_retrieval_query_is_child_only(self):
        question = self.sub.contract["original_question"]
        for child in self.sub.children:
            self.assertNotIn(question, child.retrieval_query())
        c11 = self.sub.child("c11")
        self.assertIn(c11.scope_carrier_wording, c11.retrieval_query())
        self.assertEqual(self.sub.child("c5").retrieval_query(), self.sub.child("c5").wording)

    def test_machine_side_constraints_stay_out_of_the_contract_text(self):
        c9 = self.sub.child("c9")
        self.assertTrue(c9.machine_side_constraints)
        for constraint in c9.machine_side_constraints:
            self.assertNotIn(constraint["text"], c9.contract_text)

    def test_baseline_manifest_verifies_and_detects_a_change(self):
        manifest = freeze.baseline_manifest()
        self.assertGreater(len(manifest["files"]), 50)
        self.assertEqual(manifest["library_fingerprint"]["sha256"], freeze.LIBRARY_SHA256)
        self.assertEqual(freeze.verify_baseline_unchanged(manifest), [])
        tampered = {**manifest, "files": {**manifest["files"], "question.txt": "0" * 64}}
        self.assertEqual(
            freeze.verify_baseline_unchanged({**tampered, "files": {"question.txt": "0" * 64}}), ["question.txt"]
        )


class DisposableLibraryTests(unittest.TestCase):
    def test_refuses_a_source_without_the_frozen_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "wrong.sqlite"
            src.write_bytes(b"not the frozen library")
            with self.assertRaises(ValueError):
                freeze.make_disposable_library(Path(tmp) / "slice", src)
            self.assertFalse((Path(tmp) / "slice" / "library.sqlite").exists())

    def test_refuses_to_overwrite_an_existing_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "slice"
            dest.mkdir()
            (dest / "library.sqlite").write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                freeze.make_disposable_library(dest, Path(tmp) / "any")


if __name__ == "__main__":
    unittest.main()
