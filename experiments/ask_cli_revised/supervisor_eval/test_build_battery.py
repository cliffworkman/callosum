"""The builder turns real run artifacts into a frozen battery, verifying every constant against the source.

Synthetic fixture runs carry fake quotes, so the public-safe split can be asserted directly: no source quote
may appear in the public manifest or the freeze file.
"""

import json
import tempfile
import unittest
from pathlib import Path

from experiments.ask_070.hashing import digest
from experiments.ask_cli_revised.supervisor_eval import build_battery as bb
from experiments.ask_cli_revised.supervisor_eval import cases, freeze

QH = "q" * 64
_STATUS_AT = {
    21: ("There is cross-cultural evidence for the bias in personality or behavior.", "unverified", 269, "s4"),
    72: ("how many years participants attended school", "weak", 68, "s5"),
    16: ("The EBQ measures explicit bias.", "weak", 248, "s3"),
}


def make_run(run_dir, *, claim_override=None, status_override=None, question_hash=QH, original_question=None):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "01_request_contract.json").write_text(
        json.dumps({"question_hash": question_hash, "original_question": original_question or cases.ORIGINAL_QUESTION}),
        encoding="utf-8",
    )
    verified = []
    for p in cases.PROPOSITIONS:
        text = (claim_override or {}).get(p["proposition_id"], p["claim"])
        verified.append(
            {
                "proposition_id": p["proposition_id"],
                "subquestion_id": p["retrieved_for"].split("-")[0],
                "paper_id": p["paper_id"],
                "proposition_text": text,
                "quote": f"SECRET-QUOTE-{p['proposition_id']}",
                "verification": {"status": "verified"},
            }
        )
    ledger = {
        "sealed_hash": "s" * 64,
        "subquestions": [
            {"subquestion_id": o["field_id"].split("-")[0], "obligations": [dict(o)]} for o in cases.OBLIGATIONS
        ],
        "verified_propositions": verified,
    }
    (run_dir / "11_verified_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    props, vers = [], []
    for i in range(73):
        text, status, paper, sq = _STATUS_AT.get(i, (f"filler {i}", "weak", 1, "s1"))
        props.append({"proposition_text": text, "subquestion_id": sq, "paper_id": paper})
        vers.append({"status": (status_override or {}).get(i, status)})
    (run_dir / "09_propositions.jsonl").write_text("\n".join(json.dumps(r) for r in props) + "\n", encoding="utf-8")
    (run_dir / "10_verification.jsonl").write_text("\n".join(json.dumps(r) for r in vers) + "\n", encoding="utf-8")
    return run_dir


class VerifySourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_a_matching_source_yields_the_private_quotes(self):
        out = bb.verify_source(make_run(self.dir / "run"), expected_question_hash=QH)
        self.assertEqual(out["quotes"]["p3"], "SECRET-QUOTE-p3")
        self.assertEqual(sorted(out["quotes"]), cases.PROPOSITION_IDS)

    def test_a_source_with_different_question_text_is_refused(self):
        run = make_run(self.dir / "run", original_question="a subtly different research question?")
        with self.assertRaises(bb.SourceMismatch) as ctx:
            bb.verify_source(run, expected_question_hash=QH)
        self.assertIn("question", str(ctx.exception).lower())

    def test_a_drifted_ledger_claim_is_refused(self):
        run = make_run(self.dir / "run", claim_override={"p5": "The dmPFC does something else entirely."})
        with self.assertRaises(bb.SourceMismatch) as ctx:
            bb.verify_source(run, expected_question_hash=QH)
        self.assertIn("p5", str(ctx.exception))

    def test_the_wrong_question_is_refused(self):
        with self.assertRaises(bb.SourceMismatch):
            bb.verify_source(make_run(self.dir / "run"), expected_question_hash="0" * 64)

    def test_a_candidate_whose_verification_status_differs_is_refused(self):
        # the EBQ / cross-cultural / years-of-school claims must really be non-verified, or Task A's label is a lie
        run = make_run(self.dir / "run", status_override={16: "verified"})
        with self.assertRaises(bb.SourceMismatch) as ctx:
            bb.verify_source(run, expected_question_hash=QH)
        self.assertIn("A7", str(ctx.exception))

    def test_a_missing_source_file_is_refused_clearly(self):
        run = make_run(self.dir / "run")
        (run / "10_verification.jsonl").unlink()
        with self.assertRaises(bb.SourceMismatch):
            bb.verify_source(run, expected_question_hash=QH)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.run = make_run(self.dir / "run")
        self.public, self.private = self.dir / "public", self.dir / "private"
        self.manifest, self.priv = bb.build(self.run, self.public, self.private, expected_question_hash=QH)

    def test_the_manifest_lists_all_19_calls_with_expected_judgments(self):
        self.assertEqual(len(self.manifest["cases"]), 19)
        a3 = next(c for c in self.manifest["cases"] if c["case_id"] == "A3.original")
        self.assertEqual(a3["expected"]["required"], [])
        self.assertEqual(
            a3["claim"], "The dorsomedial prefrontal cortex affects individuals' responses to social situations."
        )

    def test_no_source_quote_reaches_any_public_file(self):
        for path in self.public.rglob("*"):
            if path.is_file():
                self.assertNotIn("SECRET-QUOTE", path.read_text(encoding="utf-8"), path.name)
        self.assertNotIn("SECRET-QUOTE", json.dumps(self.manifest))

    def test_the_private_battery_holds_the_quotes_and_the_rendered_prompts(self):
        self.assertEqual(self.priv["quotes"]["p5"], "SECRET-QUOTE-p5")
        b = next(c for c in self.priv["cases"] if c["case_id"] == "B1.original")
        self.assertIn("SECRET-QUOTE-p5", b["prompt"])
        a = next(c for c in self.priv["cases"] if c["case_id"] == "A3.original")
        self.assertNotIn("SECRET-QUOTE", a["prompt"])  # Task A is claim-only

    def test_every_case_is_hash_pinned_publicly_without_publishing_its_prompt(self):
        priv_by_id = {c["case_id"]: c for c in self.priv["cases"]}
        for c in self.manifest["cases"]:
            p = priv_by_id[c["case_id"]]
            self.assertEqual(c["input_sha256"], digest({"prompt": p["prompt"], "schema": p["schema"]}))
            self.assertNotIn("prompt", c)

    def test_the_manifest_records_the_source_identity(self):
        self.assertEqual(self.manifest["source"]["question_hash"], QH)
        self.assertEqual(self.manifest["source"]["ledger_sealed_hash"], "s" * 64)
        self.assertEqual(
            sorted(self.manifest["source"]["file_sha256"]),
            ["01_request_contract.json", "09_propositions.jsonl", "10_verification.jsonl", "11_verified_ledger.json"],
        )

    def test_the_manifest_carries_the_envelope_and_disclosed_reconstruction(self):
        self.assertEqual(self.manifest["envelope"]["num_ctx"], 12288)
        c = next(c for c in self.manifest["cases"] if c["case_id"] == "C1.original")
        self.assertIn("reconstruction", c["state"]["s4-o1"]["state_provenance"])

    def test_building_twice_is_byte_identical(self):
        again_public = self.dir / "public2"
        bb.build(self.run, again_public, self.dir / "private2", expected_question_hash=QH)
        self.assertEqual((self.public / bb.MANIFEST_NAME).read_bytes(), (again_public / bb.MANIFEST_NAME).read_bytes())
        self.assertEqual(
            (self.private / bb.PRIVATE_NAME).read_bytes(), (self.dir / "private2" / bb.PRIVATE_NAME).read_bytes()
        )

    def test_freeze_spec_pins_code_manifest_and_the_private_file_and_stays_public_safe(self):
        spec = bb.freeze_spec(self.public / bb.MANIFEST_NAME, self.private / bb.PRIVATE_NAME)
        self.assertEqual(
            set(spec["code_files"]),
            {"cases.py", "prompts.py", "schemas.py", "scoring.py", "models.py", "ollama_client.py", "freeze.py"},
        )
        self.assertEqual(set(spec["private_files"]), {bb.PRIVATE_NAME})
        frozen = freeze.compute(spec)
        self.assertNotIn("SECRET-QUOTE", json.dumps(frozen))
        path = self.dir / "FREEZE.txt"
        freeze.write(path, frozen)
        self.assertEqual(freeze.verify(path, spec), [])

    def test_a_changed_private_prompt_breaks_the_freeze(self):
        spec = bb.freeze_spec(self.public / bb.MANIFEST_NAME, self.private / bb.PRIVATE_NAME)
        path = self.dir / "FREEZE.txt"
        freeze.write(path, freeze.compute(spec))
        priv_path = self.private / bb.PRIVATE_NAME
        priv_path.write_text(
            priv_path.read_text(encoding="utf-8").replace("Candidate claim", "Candidate CLAIM"), encoding="utf-8"
        )
        self.assertTrue(any(bb.PRIVATE_NAME in p for p in freeze.verify(path, spec)))


@unittest.skipUnless(bb.REAL_RUN_DIR.exists(), "real run9 artifacts are not on this machine")
class RealSourceTests(unittest.TestCase):
    def test_the_embedded_constants_match_the_real_run9_artifacts_byte_for_byte(self):
        out = bb.verify_source(bb.REAL_RUN_DIR)
        self.assertEqual(sorted(out["quotes"]), cases.PROPOSITION_IDS)
        self.assertTrue(all(len(q) > 50 for q in out["quotes"].values()))
        self.assertEqual(out["source"]["question_hash"], bb.EXPECTED_QUESTION_HASH)


if __name__ == "__main__":
    unittest.main()
