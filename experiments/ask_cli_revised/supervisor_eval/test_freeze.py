"""The freeze must hash-pin every frozen input, including private ones we never publish."""

import json
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.supervisor_eval import freeze


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.code = self.dir / "scoring.py"
        self.code.write_bytes(b"def score():\n    return 1\n")
        self.private = self.dir / "battery.private.json"
        self.private.write_bytes(b'{"quotes": "verbatim source text"}')
        self.spec = {
            "code_files": {"scoring.py": self.code},
            "json": {"manifest": {"cases": ["A1", "A2"]}},
            "private_files": {"battery.private.json": self.private},
        }
        self.freeze_path = self.dir / "FREEZE.txt"

    def _write(self):
        freeze.write(self.freeze_path, freeze.compute(self.spec))

    def test_an_unchanged_freeze_verifies_clean(self):
        self._write()
        self.assertEqual(freeze.verify(self.freeze_path, self.spec), [])

    def test_the_freeze_file_is_public_safe_hashes_only(self):
        self._write()
        text = self.freeze_path.read_text(encoding="utf-8")
        self.assertNotIn("verbatim source text", text)
        data = json.loads(text)
        self.assertEqual(set(data["private_files"]), {"battery.private.json"})
        self.assertRegex(data["private_files"]["battery.private.json"], r"^[0-9a-f]{64}$")

    def test_editing_frozen_code_is_detected(self):
        self._write()
        self.code.write_bytes(b"def score():\n    return 2\n")
        problems = freeze.verify(self.freeze_path, self.spec)
        self.assertTrue(any("scoring.py" in p for p in problems), problems)

    def test_editing_the_private_battery_is_detected(self):
        self._write()
        self.private.write_bytes(b'{"quotes": "changed"}')
        self.assertTrue(any("battery.private.json" in p for p in freeze.verify(self.freeze_path, self.spec)))

    def test_editing_the_public_manifest_is_detected(self):
        self._write()
        self.spec["json"]["manifest"]["cases"].append("A9")
        self.assertTrue(any("manifest" in p for p in freeze.verify(self.freeze_path, self.spec)))

    def test_a_missing_private_file_is_reported(self):
        self._write()
        self.private.unlink()
        self.assertTrue(any("missing" in p.lower() for p in freeze.verify(self.freeze_path, self.spec)))

    def test_line_endings_do_not_change_a_code_hash(self):
        # the demo/showcase gates were bitten by CRLF vs LF checkouts; the freeze must not be
        self._write()
        self.code.write_bytes(b"def score():\r\n    return 1\r\n")
        self.assertEqual(freeze.verify(self.freeze_path, self.spec), [])

    def test_a_tampered_overall_digest_is_detected(self):
        self._write()
        data = json.loads(self.freeze_path.read_text(encoding="utf-8"))
        data["freeze_sha256"] = "0" * 64
        self.freeze_path.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(any("freeze_sha256" in p for p in freeze.verify(self.freeze_path, self.spec)))

    def test_normalized_sha256_matches_lf_and_crlf(self):
        self.assertEqual(freeze.normalized_sha256(b"a\nb\n"), freeze.normalized_sha256(b"a\r\nb\r\n"))
        self.assertNotEqual(freeze.normalized_sha256(b"a\nb\n"), freeze.normalized_sha256(b"a\nc\n"))


if __name__ == "__main__":
    unittest.main()
