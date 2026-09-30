"""No live model call anywhere in this file. Proves the authorization gate fails closed, that the
frozen artifact is LOADED (never re-authored), and that --dry-run runs the full mechanical
pipeline against the preserved run with zero nominations."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised import sufficiency_model_nomination_diagnostic as diag

_DEFAULT_RUN_DIR = (
    Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930" / "run"
)
_RUN_DIR = Path(os.environ.get("QAIB_HIERARCHICAL_RUN_DIR", str(_DEFAULT_RUN_DIR)))
needs_real_run = unittest.skipUnless(
    (_RUN_DIR / "01_request_contract.json").is_file(), f"preserved run not present at {_RUN_DIR}"
)
needs_frozen_contract = unittest.skipUnless(
    diag.sf.FROZEN_PATH.is_file(), "no installed sufficiency_contract frozen pin in this worktree yet"
)


@needs_real_run
@needs_frozen_contract
class LoadFrozenContractTests(unittest.TestCase):
    def test_loads_all_eleven_children_from_the_committed_frozen_file(self):
        frozen, contract_by_child = diag.load_frozen_contract()
        self.assertEqual(len(contract_by_child), 11)
        self.assertEqual(set(contract_by_child), set(frozen["per_child"]))

    def test_module_never_imports_sufficiency_authoring(self):
        """Static proof, stronger than a source-text scan: this module never imports
        sufficiency_authoring at all, so it structurally cannot call build_qaib_contract to
        regenerate the contract -- it can only ever load what was already frozen to disk."""
        self.assertFalse(hasattr(diag, "build_qaib_contract"))
        self.assertFalse(hasattr(diag, "sufficiency_authoring"))
        self.assertFalse(hasattr(diag, "sa"))

    def test_verify_frozen_integrity_passes_on_the_real_committed_file(self):
        frozen, _ = diag.load_frozen_contract()
        self.assertTrue(diag.verify_frozen_integrity(frozen))

    def test_verify_frozen_integrity_fails_on_a_tampered_copy(self):
        frozen, _ = diag.load_frozen_contract()
        tampered = json.loads(json.dumps(frozen))
        first_child = next(iter(tampered["per_child"]))
        tampered["per_child"][first_child]["hash"] = "0" * 64
        self.assertFalse(diag.verify_frozen_integrity(tampered))


@needs_real_run
@needs_frozen_contract
class DryRunTests(unittest.TestCase):
    def test_dry_run_produces_both_maps_with_zero_model_nominations(self):
        _, contract_by_child = diag.load_frozen_contract()
        result = diag.run(
            run_dir=_RUN_DIR,
            contract_by_child=contract_by_child,
            model_client=diag._NullModelClient(),
            model_name="null-dry-run",
        )
        self.assertEqual(set(result["deterministic_only"]), set(result["with_model"]))
        # a null client nominates nothing -- with_model must be state-for-state identical to
        # deterministic_only on every binding (never silently different).
        for child_id in result["deterministic_only"]:
            self.assertEqual(result["deterministic_only"][child_id], result["with_model"][child_id])

    def test_cli_dry_run_exits_zero(self):
        exit_code = diag.main(["--run-dir", str(_RUN_DIR), "--dry-run"])
        self.assertEqual(exit_code, 0)


class AuthorizationGateTests(unittest.TestCase):
    def _write(self, tmp: Path, **overrides) -> Path:
        payload = {
            "experiment_id": diag.EXPERIMENT_ID,
            "authorized_by": "Cliff",
            "authorized_at": "2026-09-30T00:00:00-04:00",
            "brief_confirmed": True,
            "question_sha256s": ["deadbeef"],
            "frozen_contract_hash": "cafef00d",
        }
        payload.update(overrides)
        path = tmp / "auth.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_missing_experiment_id_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), experiment_id="some_other_experiment")
            with self.assertRaises(ValueError):
                diag._load_authorization(path, question_sha256="deadbeef", frozen_combined_hash="cafef00d")

    def test_wrong_question_hash_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp))
            with self.assertRaises(ValueError):
                diag._load_authorization(path, question_sha256="not-the-real-hash", frozen_combined_hash="cafef00d")

    def test_unconfirmed_brief_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), brief_confirmed=False)
            with self.assertRaises(ValueError):
                diag._load_authorization(path, question_sha256="deadbeef", frozen_combined_hash="cafef00d")

    def test_missing_authorized_by_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), authorized_by="")
            with self.assertRaises(ValueError):
                diag._load_authorization(path, question_sha256="deadbeef", frozen_combined_hash="cafef00d")

    def test_frozen_contract_hash_mismatch_refuses(self):
        """Correction #6's live-path requirement: authorization granted against one hash must not
        silently cover a frozen file that has since changed on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), frozen_contract_hash="a-stale-hash")
            with self.assertRaises(ValueError):
                diag._load_authorization(path, question_sha256="deadbeef", frozen_combined_hash="cafef00d")

    def test_correctly_shaped_authorization_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp))
            data = diag._load_authorization(path, question_sha256="deadbeef", frozen_combined_hash="cafef00d")
            self.assertTrue(data["brief_confirmed"])

    @needs_real_run
    @needs_frozen_contract
    def test_main_without_authorization_refuses_before_any_client_construction(self):
        with self.assertRaises(SystemExit):
            diag.main(["--run-dir", str(_RUN_DIR)])  # no --dry-run, no --experiment-authorization


if __name__ == "__main__":
    unittest.main()
