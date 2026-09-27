"""The `live` command end to end with a fake client standing in for Ollama: refusals, ordering, isolation, report."""

import json
import re
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments.ask_cli_revised.contract_directed import (
    budget,
    endpoint_guard,
    freeze,
    realenv,
    run,
)
from experiments.ask_cli_revised.contract_directed import (
    model_stages as ms,
)
from experiments.ask_cli_revised.contract_directed.fakes import FakeClient

RAW = "Raw answer citing [P1]."
CLEAN = {"sha": "abc123", "branch": "experiment/ask-contract-directed", "dirty_paths": []}


def responder(kind, prompt, schema):
    if kind == "free":
        return RAW
    props = schema["properties"]
    if "abstract_quote" in props:
        return {
            "contribution_type": "original_empirical",
            "relation_to_child": "possibly_addresses",
            "abstract_quote": "",
            "reason": "fake",
        }
    if "propositions" in props:
        enum = props["propositions"]["items"]["properties"]["establishing"]["items"]["enum"]
        for line in prompt.splitlines():
            m = re.match(r"\[(s\d+)\] .*?(?:scale|Hadza|found)", line, re.IGNORECASE)
            if m and m.group(1) in enum:
                return {
                    "propositions": [
                        {
                            "establishing": [m.group(1)],
                            "qualifying": [],
                            "referents": [],
                            "provenance_class": "this_study_reports",
                            "attribution_basis_phrase": "",
                            "relation_polarity": "association",
                            "unresolved": [],
                        }
                    ],
                    "none_established": False,
                }
        return {"propositions": [], "none_established": True}
    out = {}
    for uid, spec in props["units"]["properties"].items():
        slots = {
            n: {"span_ids": ["p1"], **({"value": "association"} if n == "polarity" else {})}
            for n in spec["properties"]["slots"]["properties"]
        }
        out[uid] = {"slots": slots, "reason": "fake"}
    return {"units": out}


class FakeOllama(FakeClient):
    """Stands in for `FreeChatClient`: records order and probes the socket guard from inside the first model call."""

    instances: list = []
    digest = freeze.MODEL_DIGEST
    run_dir_probe: dict = {}

    def __init__(self, url):
        super().__init__(responder)
        self.url, self.unloaded, self.closed, self.first_call_probe = url, False, False, None
        FakeOllama.instances.append(self)

    def version(self):
        return freeze.OLLAMA_VERSION

    def tags(self):
        return [{"name": freeze.MODEL, "digest": type(self).digest}]

    def ps(self):
        return []

    def unload(self, model):
        self.unloaded = True

    def close(self):
        self.closed = True

    def _probe(self):
        if self.first_call_probe is None:
            run_dir = Path(FakeOllama.run_dir_probe["dir"])
            shared = "not_refused"
            try:
                socket.socket().connect(("127.0.0.1", 11434))
            except endpoint_guard.EndpointRefused:
                shared = "refused"
            except OSError:
                shared = "reached_socket_layer"
            self.first_call_probe = {
                "expectations_written_first": (run_dir / "expectations.json").exists(),
                "authorization_copied_first": (run_dir / "authorization_used.json").exists(),
                "manifest_written_first": (run_dir / "00_run_manifest.json").exists(),
                "shared_endpoint": shared,
            }

    def chat(self, *a, **k):
        self._probe()
        return super().chat(*a, **k)

    def chat_free(self, *a, **k):
        self._probe()
        return super().chat_free(*a, **k)


def signed_authorization(path: Path, children: list[str], **over) -> dict:
    caps, ceilings = budget.FULL_CAPS, budget.FULL_CEILINGS
    b = budget.run_budget(children, caps, ceilings)
    auth = (
        budget.authorization_template("custom-live", b)
        | {
            "brief_confirmed": True,
            "authorized_by": "Cliff Workman",
            "authorized_at": "2026-09-26T00:00:00-04:00",
            "note": "test",
        }
        | over
    )
    path.write_text(json.dumps(auth), encoding="utf-8")
    return auth


@unittest.skipUnless(realenv.available(), "real disposable library / frozen data not present")
class LiveCommandTests(unittest.TestCase):
    CHILDREN = ["c9", "c11"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.slice = Path(self.tmp.name)
        self.auth = self.slice / "auth.json"
        FakeOllama.instances.clear()
        FakeOllama.digest = freeze.MODEL_DIGEST
        patches = [
            mock.patch.object(freeze, "SLICE_ROOT", self.slice),
            mock.patch.object(ms, "FreeChatClient", FakeOllama),
            mock.patch.object(run, "code_identity", lambda: dict(CLEAN)),
            mock.patch.object(
                run,
                "verify_integrity",
                lambda substrate: {"library_copy_unchanged": True, "baseline_artifacts_unchanged": True},
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def args(self, run_id="live-test"):
        FakeOllama.run_dir_probe["dir"] = str(self.slice / "runs" / run_id)
        return mock.Mock(run_id=run_id, children=",".join(self.CHILDREN), authorization=str(self.auth))

    def test_an_unsigned_authorization_is_refused_before_anything_is_created(self):
        budget_ = budget.run_budget(self.CHILDREN, budget.FULL_CAPS, budget.FULL_CEILINGS)
        self.auth.write_text(json.dumps(budget.authorization_template("custom-live", budget_)), encoding="utf-8")
        with self.assertRaises(budget.AuthorizationRefused):
            run.live(self.args())
        self.assertFalse((self.slice / "runs").exists())
        self.assertEqual(FakeOllama.instances, [])

    def test_a_dirty_tree_is_refused(self):
        signed_authorization(self.auth, self.CHILDREN)
        with mock.patch.object(run, "code_identity", lambda: {**CLEAN, "dirty_paths": [" M x.py"]}):
            with self.assertRaises(SystemExit) as ctx:
                run.live(self.args())
        self.assertIn("dirty tree", str(ctx.exception))
        self.assertEqual(FakeOllama.instances, [])

    def test_a_digest_mismatch_stops_before_any_model_call(self):
        signed_authorization(self.auth, self.CHILDREN)
        FakeOllama.digest = "0" * 64
        with self.assertRaises(SystemExit) as ctx:
            run.live(self.args())
        self.assertIn("digest", str(ctx.exception))
        self.assertEqual(FakeOllama.instances[0].calls, [])

    def test_the_success_path_records_everything_before_inference_and_confines_the_process(self):
        signed_authorization(self.auth, self.CHILDREN)
        code = run.live(self.args("live-ok"))
        run_dir = self.slice / "runs" / "live-ok"
        client = FakeOllama.instances[0]
        self.assertEqual(code, 0)
        self.assertEqual(client.url, "http://127.0.0.1:11435")  # the isolated endpoint, never :11434
        self.assertEqual(
            client.first_call_probe,
            {
                "expectations_written_first": True,
                "authorization_copied_first": True,
                "manifest_written_first": True,
                "shared_endpoint": "refused",
            },
        )
        manifest = json.loads((run_dir / "00_run_manifest.json").read_text(encoding="utf-8"))
        record = json.loads((run_dir / "expectations.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["expectations"]["sha256"], record["sha256"])
        self.assertEqual(manifest["model"]["digest"], freeze.MODEL_DIGEST)
        self.assertEqual(manifest["stop_conditions"]["retries"], 0)
        for name in (
            "09_coverage.json",
            "14_ledger.json",
            "15_expectation_results.json",
            "17_review_sheet.md",
            "authorization_used.json",
        ):
            self.assertTrue((run_dir / name).is_file(), name)
        for child in self.CHILDREN:
            self.assertEqual((run_dir / "12_answers" / f"{child}_raw_answer.txt").read_text(encoding="utf-8"), RAW)
        self.assertTrue(
            client.unloaded and client.closed
        )  # nothing was resident before, so the model is unloaded afterwards
        self.assertFalse(
            any(c["kind"] == "json" and c["options"] != ms.topo.SUPERVISOR_BASE_OPTIONS for c in client.calls)
        )


if __name__ == "__main__":
    unittest.main()
