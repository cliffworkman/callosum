"""Phase 27 production wiring, offline. Three layers, none touching a model or the network:

1. The CLI flag and the run_topology() precondition (no artifacts).
2. e2e.execute() over the frozen hierarchy with the real v9 contract and scripted clients: default-off zero change,
   the explicit no-map decline, and lifecycle position (the parent block runs after every per-child stage).
3. The production helper ``e2e._parent_synthesis_outputs`` driven by a real claim ledger built from the Phase-26
   fixtures: exactly one S2 call through the bound S supervisor, the S2 stage label, the 15* artifacts, and the audit.

The positive run through execute() is deliberately NOT asserted here: no existing offline fixture drives a
deterministic role fill through the whole hierarchy (the Phase-22/24 integration tests reach fills through model
nomination). The real frozen state is exercised by the Phase-27 offline replay, and the live run is Phase 28.
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from experiments.ask_cli_revised import e2e, sufficiency_freeze
from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import parent_synthesis_test_support as pst
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.hierarchy_test_support import HierHarness, needs_artifacts, r_by_claim
from experiments.ask_cli_revised.overview_test_support import Entail, OverviewClient
from experiments.ask_cli_revised.overview_test_support import record as overview_record
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.test_e2e_run import ScriptedClient
from experiments.ask_cli_revised.trace import TraceWriter

PARENT_FILES = ("15a_parent_synthesis.json", "15_parent_answer.md", "15b_parent_synthesis_inspection.md")

# Evidence that the deterministic sufficiency mapper fills a role for (the real Phase-23 c12 outcome passage, which
# matches achieved_outcome_predicate with no model nomination). Used only for the execute()-level default-off /
# decline / position tests, where the parent layer is expected to produce no claims and make no call.
C12_OUTCOME_CLAIM = "the intervention produced a reduction in implicit bias"
C12_OUTCOME_PASSAGE = (
    90,
    9001,
    "e1",
    "The anomalous faces variant of the NAME intervention produced a clear reduction in implicit bias against "
    "people with anomalous faces, whereas bias toward people of color in that condition remained essentially unchanged.",
)
EVIDENCE = [overview_record(C12_OUTCOME_CLAIM, C12_OUTCOME_PASSAGE, sid="c12")]


class ParentS2Client(OverviewClient):
    """Routes the parent schema (``items``) to ``parent``; every other schema keeps the Overview routing."""

    def __init__(self, *, parent=None, **kwargs):
        super().__init__(**kwargs)
        self.parent = parent
        self.parent_calls: list[dict] = []

    def chat(self, model, prompt, *, schema, options, think=None, keep_alive=None, wall_timeout=None):
        if "items" not in schema["properties"]:
            return super().chat(
                model,
                prompt,
                schema=schema,
                options=options,
                think=think,
                keep_alive=keep_alive,
                wall_timeout=wall_timeout,
            )
        self.parent_calls.append({"prompt": prompt, "schema": schema, "options": dict(options), "think": think})
        answer = self.parent(prompt, schema) if callable(self.parent) else self.parent
        base = {
            "status": "ok",
            "error": None,
            "thinking": "",
            "timings": {"prompt_eval_count": 900, "eval_count": 300},
            "wall_seconds": 1.0,
        }
        if answer is None:
            return {**base, "content": "", "done_reason": "length"}
        return {**base, "content": json.dumps(answer), "done_reason": "stop"}


def _profile_with_s():
    """T0 (managed-local workers, deterministic coverage) plus a thinking-off S binding on the parent envelope, derived
    with dataclasses.replace so no Wave-1 profile is touched."""
    profile = dataclasses.replace(
        topo.WAVE1["T0"],
        name="T0+S2",
        S=topo.Binding("ollama", "qwen3.5:9b", endpoint="isolated", think=False),
        S_options=topo.PARENT_SYNTHESIS_S_OPTIONS,
    )
    topo.validate(profile)
    return profile


class ParentSynthesisCliTests(unittest.TestCase):
    def test_the_flag_is_default_off(self):
        self.assertFalse(e2e.parse_args(["--hierarchy", "--preflight-only"]).parent_synthesis)

    def test_the_flag_parses_with_hierarchy(self):
        self.assertTrue(e2e.parse_args(["--hierarchy", "--parent-synthesis", "--preflight-only"]).parent_synthesis)

    def test_the_flag_without_hierarchy_is_refused_by_the_parser(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            e2e.parse_args(["--parent-synthesis", "--preflight-only"])

    def test_run_topology_refuses_the_flag_without_hierarchy_before_doing_any_work(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError) as caught:
            e2e.run_topology(
                "T0",
                "lld",
                db_path=Path(tmp) / "x.sqlite",
                library_frozen=Path(tmp) / "f.json",
                out_dir=Path(tmp) / "out",
                git_root=Path(tmp),
                hierarchy=False,
                parent_synthesis=True,
            )
        self.assertIn("--parent-synthesis requires --hierarchy", str(caught.exception))


@needs_artifacts
class ParentSynthesisExecuteTests(unittest.TestCase):
    """The real execute() path over the frozen hierarchy and the real v9 sufficiency contract."""

    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.contract_by_child = sufficiency_freeze.load_verified()
        cls.parent_of = hc.parent_of(cls.contract)

    def _harness(self):
        # The managed-local workers: R maps the evidence claim to its requirement.
        shared = ScriptedClient(r=r_by_claim({C12_OUTCOME_CLAIM: ["c12"]}))
        s_client = ParentS2Client()
        harness = HierHarness(
            _profile_with_s(),
            self.contract,
            initial=EVIDENCE,
            recovery=[],
            clients={"shared": shared, "isolated": s_client},
        )
        self.addCleanup(harness.close)
        return harness, s_client

    def test_flag_absent_is_a_zero_change_run(self):
        harness, s_client = self._harness()
        result = harness.run(
            entail=Entail(), sufficiency_contract=self.contract_by_child, sufficiency_parent_of=self.parent_of
        )
        self.assertNotIn("parent_synthesis", result)
        self.assertFalse([p for p in PARENT_FILES if (harness.trace.dir / p).exists()])
        self.assertFalse(any(e["stage"] == "S2" for e in result["stage_log"]))
        self.assertEqual(s_client.parent_calls, [])

    def test_no_sufficiency_contract_is_an_explicit_decline_with_no_call(self):
        harness, s_client = self._harness()
        result = harness.run(entail=Entail(), parent_synthesis_enabled=True)
        record = result["parent_synthesis"]["record"]
        self.assertEqual(record["realization_state"], "declined")
        self.assertEqual(record["skip_reason"], "no_sufficiency_map")
        self.assertEqual(s_client.parent_calls, [])
        self.assertTrue((harness.trace.dir / "15a_parent_synthesis.json").exists())
        self.assertFalse((harness.trace.dir / "15_parent_answer.md").exists())

    def test_the_parent_block_runs_only_after_every_per_child_stage(self):
        """Lifecycle position, proven at runtime: when the parent block is entered, every per-child overview artifact
        already exists on disk. A spy wraps the real helper and calls it through."""
        harness, _s_client = self._harness()
        seen_at_entry = {}
        real = e2e._parent_synthesis_outputs

        def spy(**kwargs):
            seen_at_entry["child_manifest"] = (kwargs["trace"].dir / "14_child_overview_manifest.json").exists()
            seen_at_entry["child_record"] = (kwargs["trace"].dir / "14a_overview.c1.json").exists()
            return real(**kwargs)

        with mock.patch.object(e2e, "_parent_synthesis_outputs", side_effect=spy):
            harness.run(
                entail=Entail(),
                sufficiency_contract=self.contract_by_child,
                sufficiency_parent_of=self.parent_of,
                parent_synthesis_enabled=True,
            )
        self.assertEqual(seen_at_entry, {"child_manifest": True, "child_record": True})

    def test_a_run_with_no_claims_writes_the_deterministic_answer_and_calls_nothing(self):
        harness, s_client = self._harness()
        result = harness.run(
            entail=Entail(),
            sufficiency_contract=self.contract_by_child,
            sufficiency_parent_of=self.parent_of,
            parent_synthesis_enabled=True,
        )
        record = result["parent_synthesis"]["record"]
        self.assertEqual(record["claim_ledger"], [])  # this evidence fills no role: nothing to realize
        self.assertEqual(record["realization_state"], "no_claims")
        self.assertFalse(record["call_attempted"])
        self.assertEqual(s_client.parent_calls, [])
        self.assertTrue((harness.trace.dir / "15_parent_answer.md").exists())
        self.assertFalse(any(e["stage"] == "S2" for e in result["stage_log"]))

    def test_the_parent_answer_never_replaces_the_top_level_final_answer(self):
        harness, _s_client = self._harness()
        harness.run(
            entail=Entail(),
            sufficiency_contract=self.contract_by_child,
            sufficiency_parent_of=self.parent_of,
            parent_synthesis_enabled=True,
        )
        top = (harness.trace.dir / "14_final_answer.md").read_text(encoding="utf-8")
        parent = (harness.trace.dir / "15_parent_answer.md").read_text(encoding="utf-8")
        self.assertTrue(top)
        self.assertNotEqual(top, parent)


class ParentHelperWiringTests(unittest.TestCase):
    """``e2e._parent_synthesis_outputs`` over a real ledger built from the Phase-26 fixtures: the positive path."""

    def _stage_recorder(self):
        entries: list[dict] = []

        @contextlib.contextmanager
        def stage(name, role):
            entry = {"stage": name, "role": role}
            entries.append(entry)
            yield entry

        return stage, entries

    def _run(self, sealed, smf, *, client, trace_dir):
        sup = pst.make_s2_supervisor(client)
        stage, entries = self._stage_recorder()
        out = e2e._parent_synthesis_outputs(
            trace=TraceWriter(trace_dir),
            stage=stage,
            bound=SimpleNamespace(supervisors={"S": sup}),
            sealed=sealed,
            sealed_hash="h-sealed",
            sufficiency_map_final=smf,
            recovery_targets_final={},
            question="Which regions respond to scarring?",
            entail=pst.FakeEntail(),
        )
        return out, entries

    def test_one_s2_call_through_the_bound_s_supervisor_with_the_s2_label_and_the_15_artifacts(self):
        sealed, smf = self._two_claim_map()
        client = pst.FakeParentClient(answer=self._restate)
        with tempfile.TemporaryDirectory() as tmp:
            out, entries = self._run(sealed, smf, client=client, trace_dir=Path(tmp) / "run")
            self.assertEqual(len(client.calls), 1)
            self.assertEqual([e["stage"] for e in entries], ["S2"])
            self.assertEqual(out["record"]["realization_state"], "model_realized")
            for name in PARENT_FILES:
                self.assertTrue((Path(tmp) / "run" / name).exists(), name)
            self.assertTrue(out["audit"]["ok"], out["audit"])

    def test_a_non_grounded_statement_renders_its_literal_fallback_in_the_answer(self):
        sealed, smf = self._two_claim_map()
        client = pst.FakeParentClient(answer=self._unsupported)
        with tempfile.TemporaryDirectory() as tmp:
            out, _entries = self._run(sealed, smf, client=client, trace_dir=Path(tmp) / "run")
            self.assertEqual(out["record"]["grounded_count"], 0)
            answer = (Path(tmp) / "run" / "15_parent_answer.md").read_text(encoding="utf-8")
            self.assertNotIn("causes a loss", answer)
            self.assertTrue(out["audit"]["ok"], out["audit"])

    def test_the_answer_carries_each_claims_own_citation_and_no_other(self):
        sealed, smf = self._two_claim_map()
        client = pst.FakeParentClient(answer=self._restate)
        with tempfile.TemporaryDirectory() as tmp:
            out, _entries = self._run(sealed, smf, client=client, trace_dir=Path(tmp) / "run")
            answer = (Path(tmp) / "run" / "15_parent_answer.md").read_text(encoding="utf-8")
            for claim in out["record"]["claim_ledger"]:
                self.assertIn(f"[{', '.join(claim['admissible_proposition_ids'])}]", answer)

    def test_the_helper_is_independent_of_per_child_overview_prose(self):
        """Wildly different per-child Overview artifacts on disk cannot change the parent record."""
        sealed, smf = self._two_claim_map()
        with tempfile.TemporaryDirectory() as tmp:
            run_a = Path(tmp) / "a"
            run_b = Path(tmp) / "b"
            run_b.mkdir(parents=True)
            (run_b / "14a_overview.c1.json").write_text(
                json.dumps({"items": ["wildly different prose"]}), encoding="utf-8"
            )
            out_a, _ = self._run(sealed, smf, client=pst.FakeParentClient(answer=self._restate), trace_dir=run_a)
            out_b, _ = self._run(sealed, smf, client=pst.FakeParentClient(answer=self._restate), trace_dir=run_b)
            self.assertEqual(out_a["record"]["parent_synthesis_hash"], out_b["record"]["parent_synthesis_hash"])

    def test_the_helper_never_mutates_the_sufficiency_map_it_consumes(self):
        sealed, smf = self._two_claim_map()
        before = json.dumps(smf, sort_keys=True, default=str)
        with tempfile.TemporaryDirectory() as tmp:
            self._run(sealed, smf, client=pst.FakeParentClient(answer=self._restate), trace_dir=Path(tmp) / "run")
        self.assertEqual(json.dumps(smf, sort_keys=True, default=str), before)

    def test_a_declined_run_writes_only_the_decline_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = e2e._parent_synthesis_outputs(
                trace=TraceWriter(Path(tmp) / "run"),
                stage=None,
                bound=SimpleNamespace(supervisors={}),
                sealed=pst.sealed_with(),
                sealed_hash="h",
                sufficiency_map_final=None,
                recovery_targets_final={},
                question="q",
                entail=pst.FakeEntail(),
            )
            self.assertEqual(out["record"]["realization_state"], "declined")
            self.assertTrue((Path(tmp) / "run" / "15a_parent_synthesis.json").exists())
            self.assertFalse((Path(tmp) / "run" / "15_parent_answer.md").exists())

    @staticmethod
    def _restate(prompt, schema):
        # One faithful statement per claim: the amygdala claim restates its own value; the behavior claim does too.
        statements = {}
        for cid in pst.prompt_claim_ids(prompt):
            block = prompt.split(f"[{cid}]", 1)[1].split("\n\n", 1)[0]
            statements[cid] = (
                "The amygdala responded to scarring."
                if "amygdala" in block
                else "Participants avoided the scarred faces."
            )
        return {"items": [{"claim_id": cid, "statement": text} for cid, text in statements.items()]}

    @staticmethod
    def _unsupported(prompt, schema):
        return {
            "items": [
                {"claim_id": cid, "statement": "The insula causes a loss of attention."}
                for cid in pst.prompt_claim_ids(prompt)
            ]
        }

    def _two_claim_map(self):
        sealed = pst.sealed_with(
            ("p1", 1, "the amygdala responded to scarring", ["a"]),
            ("p2", 2, "participants avoided the scarred faces", ["b"]),
        )
        specs_a = {"region": pst.spec("region", "a named brain region")}
        specs_b = {"behavior": pst.spec("behavior", "an observed behavior")}
        req_a = pst.requirement(
            "a#req",
            specs_a,
            se.new_role_completion(required_roles=["region"]),
            "exists",
            [pst.instance({"region": pst.filled("region", "p1", "the amygdala responded to scarring")})],
        )
        req_b = pst.requirement(
            "b#req",
            specs_b,
            se.new_role_completion(required_roles=["behavior"]),
            "exists",
            [pst.instance({"behavior": pst.filled("behavior", "p2", "participants avoided the scarred faces")})],
        )
        return sealed, {**pst.map_with("a", req_a), **pst.map_with("b", req_b)}


if __name__ == "__main__":
    unittest.main()
