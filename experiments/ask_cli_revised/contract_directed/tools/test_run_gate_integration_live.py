"""Offline test of the actual `run_gate_integration_live.py` entry point (`main()`) and its run-directory
initialization -- not just the underlying integration functions, which
`test_gate_integration.py::RunLiveOverviewCallTests` already covers with a scripted client.

No real network call is possible here: `FreeChatClient` and `runtime.build_runtime` are both replaced with
fast, scripted/offline stand-ins (so the test is fast and needs no real models), and the whole test additionally
runs under `endpoint_guard.refuse_all()` as a second, independent guarantee that nothing could reach a socket
even if the patching were somehow bypassed.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from experiments.ask_cli_revised.contract_directed import endpoint_guard, freeze
from experiments.ask_cli_revised.contract_directed import gate1_evidence_fixture as fixture
from experiments.ask_cli_revised.contract_directed.tools import run_gate_integration_live as live
from experiments.ask_cli_revised.overview_test_support import Entail, OverviewClient


def _fake_offline_preflight():
    """Stands in for the real `offline_preflight()` in these tests, which target `main()`'s POST-preflight
    orchestration (run-directory creation ordering, trace wiring, the digest check, output writing) -- exactly
    the code that had the bug. The real `offline_preflight()`'s own correctness (git/dirty-tree, question-hash,
    verbatim-prompt, persistence rehearsal, the subprocess pytest re-run, the memory floor) is proven
    separately and would only couple these tests to ambient git/memory state and a slow subprocess re-run for
    no benefit here. Only `manifest_rows` is functionally used by `main()`; the rest is print-only."""
    return {"manifest_rows": fixture.build_c9_c11_manifest()}


class _FakeRuntime:
    """Matches `ExperimentRuntime`'s shape (`.verifier.support_scorer.support_and_contradiction_many`,
    `.close()`) without loading any real model. `runtime.build_runtime`'s own correctness is proven
    elsewhere and is not what this test is for -- it already succeeded for real, reaching the very next
    line, in the failed 2026-09-28 live attempt this driver's fix responds to."""

    def __init__(self, entail):
        self.verifier = SimpleNamespace(support_scorer=SimpleNamespace(support_and_contradiction_many=entail))
        self.closed = False

    def close(self):
        self.closed = True


def _fake_client_factory(client):
    def factory(_endpoint):
        return client

    return factory


class MainEntryPointOfflineTests(unittest.TestCase):
    """Exercises `main()`'s real control flow -- run-directory creation ordering (the corrected path, see
    `d0e730c4`), `DiagnosticTrace` wiring, the digest/version pre-check, and output-file writing."""

    def setUp(self):
        self.tmp_runs = Path(tempfile.mkdtemp(prefix="gate_integration_live_main_test_"))
        self.addCleanup(shutil.rmtree, self.tmp_runs, ignore_errors=True)

    def _client(self, unit_id: str = "U1") -> OverviewClient:
        client = OverviewClient(
            s={"overview": [{"text": "a grounded statement", "unit_ids": [unit_id], "bears_on": []}]}
        )
        # ScriptedClient.tags()'s default digests ("digest-of-<name>") don't match freeze.MODEL_DIGEST;
        # override just this instance's tags() so the real pre-call digest check passes. version() already
        # matches freeze.OLLAMA_VERSION ("0.34.3") without overriding.
        client.tags = lambda: [{"name": freeze.MODEL, "digest": freeze.MODEL_DIGEST}]
        return client

    def _run(self, run_id: str, *, client=None, entail=None):
        client = client or self._client()
        rt = _FakeRuntime(entail or Entail())
        with (
            patch.object(live, "offline_preflight", _fake_offline_preflight),
            patch.object(live, "RUNS_ROOT", self.tmp_runs),
            patch.object(live.ms, "FreeChatClient", _fake_client_factory(client)),
            patch.object(live.ask_runtime, "build_runtime", lambda *a, **k: rt),
            endpoint_guard.refuse_all(),
        ):
            code = live.main(["--run-id", run_id])
        return code, rt, client

    def test_a_fresh_run_id_writes_every_expected_artifact_via_the_real_entry_point(self):
        code, rt, client = self._run("main-test-001")
        self.assertEqual(code, 0)
        run_dir = self.tmp_runs / "main-test-001"
        for name in (
            "00_trace_started.json",
            "01_contract_directed_manifest.json",
            "02_prompt_and_manifest.json",
            "03_raw_response.json",
            "04_final_record.json",
            "pre_call_ollama_state.json",
            "00_integration_receipt.json",
            "01_derived_manifest.json",
            "02_partial_answer.md",
            "03_detailed_audit_view.json",
        ):
            self.assertTrue((run_dir / name).is_file(), name)
        self.assertTrue(rt.closed)
        self.assertTrue(getattr(client, "closed", False))
        receipt = json.loads((run_dir / "00_integration_receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["mode"], "live_partial_pipeline_integration")
        self.assertEqual(client.calls[0]["kind"], "S")  # exactly one call was made, and it was the S-role one

    def test_an_already_existing_run_id_refuses_before_any_preflight_or_call(self):
        (self.tmp_runs / "already-there").mkdir()
        with patch.object(live, "RUNS_ROOT", self.tmp_runs), endpoint_guard.refuse_all():
            with self.assertRaises(SystemExit) as ctx:
                live.main(["--run-id", "already-there"])
        self.assertIn("already-there", str(ctx.exception))
        self.assertIn("never reused", str(ctx.exception))
        # no trace or output was ever created for the pre-existing path
        self.assertEqual(list((self.tmp_runs / "already-there").iterdir()), [])

    def test_a_wrong_ollama_digest_refuses_before_any_call_and_preserves_the_pre_call_state(self):
        client = self._client()
        client.tags = lambda: [{"name": freeze.MODEL, "digest": "not-the-pinned-digest"}]
        code_or_none = None
        rt = _FakeRuntime(Entail())
        with (
            patch.object(live, "offline_preflight", _fake_offline_preflight),
            patch.object(live, "RUNS_ROOT", self.tmp_runs),
            patch.object(live.ms, "FreeChatClient", _fake_client_factory(client)),
            patch.object(live.ask_runtime, "build_runtime", lambda *a, **k: rt),
            endpoint_guard.refuse_all(),
        ):
            with self.assertRaises(SystemExit) as ctx:
                code_or_none = live.main(["--run-id", "main-test-002"])
        self.assertIsNone(code_or_none)  # main() never reached a return; it raised
        self.assertIn("differ from the frozen recorded run", str(ctx.exception))
        run_dir = self.tmp_runs / "main-test-002"
        self.assertTrue((run_dir / "pre_call_ollama_state.json").is_file())
        self.assertFalse((run_dir / "00_integration_receipt.json").exists())
        self.assertEqual(client.calls, [])  # no chat() call was ever made
        self.assertTrue(rt.closed)  # cleanup still ran despite the raise


if __name__ == "__main__":
    unittest.main()
