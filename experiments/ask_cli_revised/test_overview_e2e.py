"""The overview through the real ``e2e.execute``: placement in the run, the separate artifacts, the final audit, and the flat path.

Retrieval and every model are faked (scripted clients, a fake NLI scorer); no network, no database, no library.
"""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from experiments.ask_cli_revised import e2e, e2e_checks
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.ledger_renderer import render_answer
from experiments.ask_cli_revised.overview_test_support import (
    CONTRACT,
    S1,
    S2,
    Entail,
    OverviewClient,
    OverviewHarness,
    ScriptedClient,
    c_maps,
    harness_records,
    p_preserve,
    stmt,
)

T5O = topo.OVERVIEW_PROFILES["T5O"]
FAITHFUL_GIVING = "In one study the insular response to pictured scarring correlated with lower generosity toward the people pictured."
FAITHFUL_HEDGE = (
    "One paper suggests that training in perspective taking might reduce avoidance of people with visible scarring."
)
ANSWER = {"overview": [stmt(FAITHFUL_GIVING, ["U1"], [S1]), stmt(FAITHFUL_HEDGE, ["U3"], [S2])]}


def run(profile=T5O, s=ANSWER, entail=None, thinking="", **kwargs):
    isolated = OverviewClient(c=c_maps({S1: "p1", S2: "p3"}), p=p_preserve, s=s, thinking=thinking)
    h = OverviewHarness(
        profile, initial=harness_records(), recovery=[], clients={"shared": ScriptedClient(), "isolated": isolated}
    )
    return h, isolated, h.run(entail=entail or Entail(), **kwargs)


class TopologyTests(unittest.TestCase):
    def test_wave1_and_t5star_are_unchanged(self):
        self.assertEqual(list(topo.WAVE1), ["T0", "T1", "T2", "T3", "T4", "T5"])
        for profile in topo.WAVE1.values():
            self.assertEqual(profile.S.kind, "off")  # no Wave-1 profile has an overview
        t5 = topo.WAVE1["T5"]
        self.assertEqual(
            (t5.name, t5.W.model, t5.W.think, t5.R.kind, t5.C.model, t5.P.model),
            ("T5*", "qwen3.5:9b", False, "off", "phi4:14b", "gemma3:12b"),
        )

    def test_the_overview_profile_is_derived_from_t5star_and_adds_only_s(self):
        t5 = topo.WAVE1["T5"]
        for role in "WRCP":
            self.assertEqual(getattr(T5O, role), getattr(t5, role))
        self.assertEqual(
            (T5O.name, T5O.S.kind, T5O.S.model, T5O.S.think, T5O.S.endpoint),
            ("T5*+O", "ollama", "qwen3.5:9b", True, "isolated"),
        )
        # profile_names()'s full membership (WAVE1 + T5O + Stage B's own T5C) is ProfileResolutionTests'
        # job in test_topology.py; this assertion only needs T5O's own presence, not the exact full list --
        # hardcoding the whole list here is exactly what went stale when Stage B added CHILD_OVERVIEW_PROFILES.
        self.assertIn("T5O", topo.profile_names())
        self.assertIs(topo.resolve_profile("T5O"), T5O)

    def test_the_envelope_is_explicit_and_fixed(self):
        o = topo.OVERVIEW_S_OPTIONS
        self.assertEqual((o["num_ctx"], o["num_predict"]), (20480, 16384))
        self.assertEqual(
            (o["temperature"], o["top_p"], o["top_k"], o["min_p"], o["presence_penalty"], o["seed"]),
            (1.0, 0.95, 20, 0.0, 1.5, 42),
        )
        self.assertNotEqual(o, topo.SUPERVISOR_BASE_OPTIONS)  # a deliberate, recorded deviation for S only
        self.assertEqual(topo.SUPERVISOR_BASE_OPTIONS["temperature"], 0)  # every other role's envelope is untouched

    def test_s_must_be_off_or_an_ollama_model(self):
        from dataclasses import replace

        with self.assertRaises(ValueError):
            topo.validate(
                replace(topo.WAVE1["T5"], S=topo.Binding("managed_local", "callosum-managed-local", endpoint="shared"))
            )
        with self.assertRaises(ValueError):
            topo.validate(replace(topo.WAVE1["T5"], S=topo.Binding("ollama", None, endpoint="isolated")))

    def test_endpoints_and_models_include_s_only_when_bound(self):
        self.assertEqual(e2e.endpoints_used(T5O), ["isolated"])
        self.assertEqual(e2e._roles(topo.WAVE1["T5"]), ("W", "R", "C", "P"))
        self.assertEqual(e2e._roles(T5O), ("W", "R", "C", "P", "S"))


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.h, self.client, self.result = run(thinking="some reasoning text")
        self.dir = self.h.trace.dir

    def test_the_overview_follows_the_last_coverage_stage_and_uses_the_bound_model(self):
        names = [s["stage"] for s in self.result["stage_log"]]
        self.assertEqual(names[-1], "S1")
        entry = self.result["stage_log"][-1]
        self.assertEqual(
            (entry["role"], entry["binding"]["model"], entry["binding"]["think"]), ("S", "qwen3.5:9b", True)
        )
        self.assertEqual(self.client.kinds(), ["C", "P", "S"])  # exactly one S call, after C and P
        self.assertEqual(entry["detail"]["state"], "ok")

    def test_the_sealed_evidence_ledger_is_unchanged_and_referenced_by_hash(self):
        ledger = json.loads((self.dir / "11_verified_ledger.json").read_text(encoding="utf-8"))
        self.assertNotIn("overview", ledger)  # model-written prose is never inside the sealed evidence ledger
        record = json.loads((self.dir / "14a_overview.json").read_text(encoding="utf-8"))
        self.assertEqual(record["sealed_ledger_hash"], ledger["sealed_hash"])
        self.assertEqual(record["sealed_ledger_hash"], self.result["sealed_hash"])
        self.assertNotIn("overview", self.result["sealed"])

    def test_the_researcher_answer_is_the_primary_file_and_the_inspection_is_separate(self):
        answer = (self.dir / "14_final_answer.md").read_text(encoding="utf-8")
        detail = (self.dir / "14b_detailed_inspection.md").read_text(encoding="utf-8")
        self.assertTrue(answer.startswith("# Overview of the retrieved evidence"))
        self.assertLess(len(answer), len(detail))
        self.assertNotIn("Overview construction record", answer)
        base, _ = render_answer(self.result["sealed"])
        self.assertTrue(
            detail.startswith(base.rstrip("\n"))
        )  # the existing ledger rendering, unchanged, opens the inspection
        self.assertTrue(
            (self.dir / "14c_overview_reasoning.txt").read_text(encoding="utf-8").startswith("some reasoning text")
        )

    def test_the_final_audit_covers_the_overview_and_does_not_claim_zero_unsupported_prose(self):
        final = json.loads((self.dir / "14_final_audit.json").read_text(encoding="utf-8"))
        self.assertTrue(final["overview_audit"]["ok"], final["overview_audit"])
        self.assertTrue(final["overview_audit"]["screening_not_proof"])
        self.assertTrue(final["constrained_render_match"])  # the ledger rendering is still exact

    def test_the_mechanical_report_checks_the_overview_and_everything_else_still_passes(self):
        report = e2e_checks.mechanical_report(self.dir, profile=T5O)
        self.assertTrue(report["checks"]["overview_screening"]["ok"], report["checks"]["overview_screening"])
        failed = [name for name, check in report["checks"].items() if not check["ok"]]
        self.assertEqual(failed, [])
        self.assertEqual(report["no_answer"]["by_task"]["overview_synthesis"]["qwen3.5:9b"]["usable"], 1)

    def test_a_record_edited_after_the_run_fails_the_mechanical_check(self):
        path = self.dir / "14a_overview.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["items"][0]["text"] += " (edited)"
        path.write_text(json.dumps(record), encoding="utf-8")
        report = e2e_checks.mechanical_report(self.dir, profile=T5O)
        self.assertFalse(report["checks"]["overview_screening"]["ok"])

    def test_the_run_records_the_explicit_options_the_model_actually_received(self):
        call = next(c for c in self.client.calls if c["kind"] == "S")
        self.assertIs(call["think"], True)
        self.assertEqual(call["options"], topo.OVERVIEW_S_OPTIONS)
        (s_record,) = self.result["supervisor_records"]["S"]
        self.assertEqual(
            (s_record["allowance"], s_record["stage"], s_record["role"]), (16384, "overview_synthesis", "S")
        )
        self.assertEqual(self.result["overview"]["options"], topo.OVERVIEW_S_OPTIONS)


class HonestFailureInTheRunTests(unittest.TestCase):
    def test_a_capped_call_is_a_visible_mechanical_no_answer_and_the_run_still_audits_clean(self):
        h, client, result = run(s=None)
        self.assertEqual(client.kinds().count("S"), 1)  # no retry, no fallback
        self.assertEqual(result["overview"]["state"], "model_no_answer")
        answer = (h.trace.dir / "14_final_answer.md").read_text(encoding="utf-8")
        self.assertIn("(mechanical: capped_at_allowance). This is not a scientific result.", answer)
        report = e2e_checks.mechanical_report(h.trace.dir, profile=T5O)
        self.assertTrue(report["checks"]["overview_screening"]["ok"])
        self.assertEqual(report["no_answer"]["by_task"]["overview_synthesis"]["qwen3.5:9b"]["model"], 1)
        self.assertEqual(
            report["technical_validity"]["issues"], []
        )  # a model NO ANSWER is not an infrastructure failure

    def test_a_missing_scorer_fails_closed_before_any_stage_or_file(self):
        isolated = OverviewClient(c=c_maps({}), p=p_preserve, s=ANSWER)
        h = OverviewHarness(
            T5O, initial=harness_records(), recovery=[], clients={"shared": ScriptedClient(), "isolated": isolated}
        )
        with self.assertRaises(ValueError):
            h.run(entail=None)
        self.assertEqual(isolated.calls, [])
        self.assertFalse((h.trace.dir / "01_request_contract.json").exists())

    def test_every_statement_withheld_still_produces_a_clean_audited_run(self):
        bad = {"overview": [stmt("Avoidance is reduced in people with visible scarring.", ["U3"], [S2])]}
        h, _, result = run(s=bad)
        self.assertEqual(result["overview"]["state"], "no_grounded_sentences")
        self.assertTrue(
            json.loads((h.trace.dir / "14_final_audit.json").read_text(encoding="utf-8"))["overview_audit"]["ok"]
        )


class FlatPathUnchangedTests(unittest.TestCase):
    def test_a_profile_without_s_makes_no_overview_call_and_writes_the_original_files_only(self):
        h, client, result = run(profile=topo.WAVE1["T5"])
        self.assertEqual(client.kinds(), ["C", "P"])
        self.assertIsNone(result["overview"])
        self.assertNotIn("S1", [s["stage"] for s in result["stage_log"]])
        for name in ("14a_overview.json", "14b_detailed_inspection.md", "14c_overview_reasoning.txt"):
            self.assertFalse((h.trace.dir / name).exists(), name)
        expected, _ = render_answer(result["sealed"])
        self.assertEqual(
            (h.trace.dir / "14_final_answer.md").read_text(encoding="utf-8"), expected
        )  # byte-identical to before
        final = json.loads((h.trace.dir / "14_final_audit.json").read_text(encoding="utf-8"))
        self.assertNotIn("overview_audit", final)

    def test_the_mechanical_report_of_a_flat_run_has_no_overview_check(self):
        h, _, _ = run(profile=topo.WAVE1["T5"])
        self.assertNotIn(
            "overview_screening", e2e_checks.mechanical_report(h.trace.dir, profile=topo.WAVE1["T5"])["checks"]
        )


class RuntimeWiringTests(unittest.TestCase):
    def test_run_topology_hands_the_runtimes_local_nli_scorer_to_the_overview_stage(self):
        import tempfile

        scorer = object()
        rt = SimpleNamespace(
            engine=None, model=None, vector_store=None,
            verifier=SimpleNamespace(support_scorer=SimpleNamespace(support_and_contradiction_many=scorer)),
            qwen_config=None, close=lambda: None,
        )  # fmt: skip

        class Every(ScriptedClient):
            def tags(self):
                return [{"name": n, "digest": "d"} for n in ("qwen3.5:9b", "phi4:14b", "gemma3:12b")]

        captured = {}

        def stop(**kwargs):
            captured.update(kwargs)
            raise RuntimeError("captured")

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with patch.object(e2e, "execute", stop):
            with self.assertRaises(RuntimeError):
                e2e.run_topology(
                    "T5O", "lld", db_path=Path(tmp.name) / "l.sqlite", library_frozen=Path(tmp.name) / "l.json",
                    out_dir=Path(tmp.name) / "out", git_root=Path(tmp.name), scored=False,
                    git_state_fn=lambda root: {"sha": "x", "branch": "b", "dirty_paths": []},
                    verify_library=lambda db, frozen: {"sha256": "same"}, verify_contracts=lambda: None,
                    runtime_factory=lambda db, **kw: rt, client_factory=lambda url: Every(),
                )  # fmt: skip
        self.assertIs(captured["entail"], scorer)
        self.assertIn("S", captured["bound"].supervisors)
        self.assertIsNone(CONTRACT and None)  # fixture import sanity


if __name__ == "__main__":
    unittest.main()
