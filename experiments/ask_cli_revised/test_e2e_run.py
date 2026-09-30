"""The two-round orchestrator: sequencing, topology-skipped stages, fail-closed NO ANSWER, residency, artifacts."""

import contextlib
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from experiments.ask_cli_revised import backends, e2e, library_copy, provenance, stages
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.calibration.run06.dataset06 import DEPRESSION_QUESTION
from experiments.ask_cli_revised.e2e_contracts import ContractDriftError
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions
from experiments.ask_cli_revised.trace import TraceWriter

QUESTION = DEPRESSION_QUESTION
CONTRACT = build_request_contract(QUESTION)
SUBQUESTIONS = request_subquestions(CONTRACT)
IDS = [sq["obligations"][0]["field_id"] for sq in SUBQUESTIONS]


def rec(sid, claim, *, chunk, origin="initial", status="verified"):
    return {
        "subquestion_id": sid,
        "proposition_text": claim,
        "quote": f"QUOTE {chunk}",
        "paper_id": 7,
        "evidence_anchor_chunk_id": chunk,
        "evidence_span_id": "e1",
        "obligation_ids": [],
        "mapping_state": "pending",
        "verification": {"status": status},
        "provenance": {"origin": origin},
    }


def add(sink, record):
    sink.all_records.append(record)
    if record["verification"]["status"] == "verified":
        sink.evidence_packets.append(
            {
                "paper_id": record["paper_id"],
                "candidate_spans": [
                    {"chunk_id": record["evidence_anchor_chunk_id"], "span_id": "e1", "text": record["quote"]}
                ],
            }
        )


class ScriptedClient:
    """An Ollama-shaped client that answers R / C / P from small handlers keyed off the schema, and records calls."""

    def __init__(self, *, r=None, c=None, p=None):
        self.handlers = {"R": r, "C": c, "P": p}
        self.calls = []
        self.unloaded = []

    def chat(self, model, prompt, *, schema, options, think=None, keep_alive=None, wall_timeout=None):
        props = schema["properties"]
        kind = "R" if "responsive_obligation_ids" in props else "C" if "coverage" in props else "P"
        self.calls.append({"kind": kind, "model": model, "prompt": prompt, "think": think, "options": dict(options)})
        handler = self.handlers[kind]
        answer = handler(prompt, schema) if handler else None
        base = {"status": "ok", "error": None, "thinking": "", "timings": {}, "wall_seconds": 0.0}
        if answer is None:
            return {**base, "content": "", "done_reason": "length"}
        return {**base, "content": json.dumps(answer), "done_reason": "stop"}

    def ps(self):
        return []

    def unload(self, model):
        self.unloaded.append(model)

    def tags(self):
        # Ollama lists an untagged alias with its implicit ":latest" tag.
        return [
            {"name": name, "digest": f"digest-of-{name}"} for name in ("callosum-managed-local:latest", "qwen3.5:9b")
        ]

    def version(self):
        return "0.34.3"

    def close(self):
        self.closed = True

    def kinds(self):
        return [call["kind"] for call in self.calls]


def r_maps(field):
    return lambda prompt, schema: {"rationale": "ok", "responsive_obligation_ids": [field]}


def r_none(prompt, schema):
    return {"rationale": "nothing", "responsive_obligation_ids": []}


def p_all(action):
    return lambda prompt, schema: {
        "rationale": "plan",
        "plan": {ob: schema["properties"]["plan"]["properties"][ob]["enum"][0].replace("DEEPEN", action) for ob in IDS},
    }


def c_supports(field_to_pid):
    def answer(prompt, schema):
        coverage = {}
        for ob in IDS:
            pid = field_to_pid.get(ob)
            coverage[ob] = {
                "status": "responsive_support" if pid else "unresolved",
                "supporting_proposition_ids": [pid] if pid else [],
            }
        return {"rationale": "c", "coverage": coverage}

    return answer


class Harness:
    """Builds a profile-bound run with faked retrieval, so only the orchestration is under test."""

    def __init__(self, profile, *, initial=(), recovery=(), clients=None, worker_clients=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile = profile
        self.initial = list(initial)
        self.recovery = list(recovery)
        self.clients = clients or {}
        self.recover_calls = []
        self.trace = TraceWriter(Path(self.tmp.name) / "run")
        self.rt = SimpleNamespace(
            engine=SimpleNamespace(connect=lambda: contextlib.nullcontext(MagicMock())),
            qwen_config="QWEN-CONFIG",
        )
        self.guard = backends.ResidencyGuard(self.clients)

    def close(self):
        self.tmp.cleanup()

    def _initial_pass(self, conn, *, rt, qwen, subquestions, sink, trace):
        self.initial_subquestions = len(subquestions)
        for record in self.initial:
            add(sink, dict(record, provenance=dict(record["provenance"])))

    def _recover_round(self, conn, *, rt, qwen, subquestions, gaps, plan, sink, trace):
        self.recover_calls.append({"gaps": [g["field_id"] for g in gaps], "plan": dict(plan)})
        for record in self.recovery:
            add(sink, dict(record, provenance=dict(record["provenance"])))
        return [{"gap": g, "action": plan.get(g["field_id"])} for g in gaps]

    def run(self, managed_chat=None, smoke_limits=None, seed_pass=None):
        bound = e2e.bind(
            self.profile,
            rt=self.rt,
            clients=self.clients,
            trace=self.trace,
            managed_chat=managed_chat or (lambda config: self.clients["shared"]),
        )
        with (
            patch.object(e2e, "_initial_pass", self._initial_pass),
            patch.object(e2e, "_recover_round", self._recover_round),
        ):
            return e2e.execute(
                rt=self.rt,
                profile=self.profile,
                contract=CONTRACT,
                trace=self.trace,
                guard=self.guard,
                bound=bound,
                smoke_limits=smoke_limits,
                seed_pass=seed_pass,
            )


def stage_names(result):
    return [entry["stage"] for entry in result["stage_log"]]


INITIAL = [
    rec("s3", "Amyloid burden was higher in late-life depression.", chunk=11),
    rec("s4", "Glucose metabolism was lower in temporal cortex.", chunk=12),
]
NEW = [rec("s5", "Tau was elevated in a small cohort.", chunk=21, origin="recovery")]


class CausalDetTopologyTests(unittest.TestCase):
    """T0-shaped: Q2.5 worker and R, deterministic coverage, legacy recovery."""

    def setUp(self):
        self.shared = ScriptedClient(r=r_maps("s3-o1"))
        self.h = Harness(topo.WAVE1["T0"], initial=INITIAL, recovery=NEW, clients={"shared": self.shared})
        self.addCleanup(self.h.close)

    def test_the_sequence_is_W_R_C_P_then_W_R_C_with_only_topology_absent_stages_skipped(self):
        result = self.h.run()
        self.assertEqual(stage_names(result), ["W1", "R1", "C1", "P1", "W2", "R2", "C2"])

    def test_round_two_asks_r_only_about_the_newly_source_verified_claims(self):
        self.h.run()
        # 2 initial claims in round 1, exactly the 1 new claim in round 2; nothing is ever re-asked.
        self.assertEqual(self.shared.kinds(), ["R", "R", "R"])
        self.assertIn("Tau was elevated", self.shared.calls[2]["prompt"])

    def test_legacy_planning_sends_every_unresolved_item_to_the_shipped_recovery(self):
        self.h.run()
        call = self.h.recover_calls[0]
        self.assertEqual(set(call["plan"].values()), {"LEGACY"})
        # s3-o1 was judged responsive by R in round 1, so it is not a gap; the other items are.
        self.assertNotIn("s3-o1", call["gaps"])
        self.assertIn("s1-o1", call["gaps"])

    def test_the_final_state_moves_only_through_r_and_the_deterministic_authority(self):
        result = self.h.run()
        final = {row["field_id"]: row for row in result["coverage_final"]["obligations"]}
        self.assertEqual(final["s3-o1"]["state"], stages.JUDGED_RESPONSIVE)
        self.assertEqual(result["coverage_final"]["authority"], {"kind": "det", "role": "R"})
        self.assertEqual(result["coverage_initial"]["authority"], {"kind": "det", "role": "R"})

    def test_the_sealed_ledger_holds_only_source_verified_claims_and_renders_conformantly(self):
        result = self.h.run()
        self.assertEqual(len(result["sealed"]["verified_propositions"]), 3)
        self.assertTrue(result["final_audit"]["constrained_render_match"])
        self.assertEqual(result["final_audit"]["nonexistent_ids"], [])

    def test_the_worker_and_r_share_one_resident_model_so_no_swap_occurs(self):
        result = self.h.run()
        events = self.h.guard.events
        self.assertEqual({e["model"] for e in events}, {"callosum-managed-local"})
        self.assertTrue(all(e["unloaded"] == [] for e in events))
        self.assertEqual(result["skipped"], [])

    def test_each_model_stage_is_observed_again_after_it_runs(self):
        self.h.run()
        self.assertEqual([o["phase"] for o in self.h.guard.observations], ["W1", "R1", "W2", "R2"])


class NoNewEvidenceTests(unittest.TestCase):
    def test_a_recovery_that_finds_nothing_new_skips_round_two_r_and_c_and_reuses_round_one_coverage(self):
        shared = ScriptedClient(r=r_maps("s3-o1"))
        h = Harness(topo.WAVE1["T0"], initial=INITIAL, recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        result = h.run()
        self.assertEqual(stage_names(result), ["W1", "R1", "C1", "P1", "W2"])
        self.assertEqual(
            [(s["stage"], s["reason"]) for s in result["skipped"]],
            [("R2", "no_new_source_verified_evidence"), ("C2", "no_new_source_verified_evidence")],
        )
        self.assertEqual(result["coverage_final"], result["coverage_initial"])
        self.assertEqual(shared.kinds(), ["R", "R"])


class ModelCoverageTopologyTests(unittest.TestCase):
    """T5-shaped: no R at all (it would be noncausal), a model C over the ledger in both rounds, a model P."""

    def setUp(self):
        self.shared = ScriptedClient()
        self.isolated = ScriptedClient(
            c=c_supports({"s3-o1": "p1"}),
            p=p_all("DEEPEN"),
        )
        self.h = Harness(
            topo.WAVE1["T5"],
            initial=INITIAL,
            recovery=NEW,
            clients={"shared": self.shared, "isolated": self.isolated},
        )
        self.addCleanup(self.h.close)

    def test_r_is_skipped_by_topology_and_c_audits_the_ledger_in_both_rounds(self):
        result = self.h.run()
        self.assertEqual(stage_names(result), ["W1", "C1", "P1", "W2", "C2"])
        self.assertEqual(self.isolated.kinds(), ["C", "P", "C"])
        self.assertNotIn("R", self.shared.kinds() + self.isolated.kinds())

    def test_the_model_c_is_the_authority_and_the_manifest_names_it(self):
        result = self.h.run()
        self.assertEqual(result["coverage_final"]["authority"], {"kind": "model", "role": "C", "model": "phi4:14b"})
        final = {row["field_id"]: row for row in result["coverage_final"]["obligations"]}
        self.assertEqual(final["s3-o1"]["proposition_ids"], ["p1"])

    def test_c_and_p_use_their_own_bound_models_and_the_p_call_is_the_recovery_planning_stage(self):
        self.h.run()
        models = [call["model"] for call in self.isolated.calls]
        self.assertEqual(models, ["phi4:14b", "gemma3:12b", "phi4:14b"])


class FailClosedTests(unittest.TestCase):
    def test_p_no_answer_performs_no_recovery_and_never_falls_back_to_legacy_recovery(self):
        isolated = ScriptedClient(c=c_supports({"s3-o1": "p1"}), p=None)  # P is capped: NO ANSWER
        h = Harness(
            topo.WAVE1["T5"], initial=INITIAL, recovery=NEW, clients={"shared": ScriptedClient(), "isolated": isolated}
        )
        self.addCleanup(h.close)
        result = h.run()
        self.assertEqual(h.recover_calls, [])
        self.assertEqual(stage_names(result), ["W1", "C1", "P1"])
        self.assertEqual(result["recovery_plan"]["state"], "no_answer")
        self.assertEqual(result["recovery_plan"]["reason_code"], "recovery_plan_no_answer")
        self.assertEqual(result["skipped"], [{"stage": "W2", "reason": "recovery_plan_no_answer"}])
        self.assertEqual(result["recovery_log"], [])
        self.assertEqual(len(result["sealed"]["verified_propositions"]), 2)  # no round-two evidence exists

    def test_a_coverage_no_answer_does_not_plan_or_recover_and_leaves_every_item_not_assessed(self):
        isolated = ScriptedClient(c=None, p=p_all("DEEPEN"))
        h = Harness(
            topo.WAVE1["T5"], initial=INITIAL, recovery=NEW, clients={"shared": ScriptedClient(), "isolated": isolated}
        )
        self.addCleanup(h.close)
        result = h.run()
        self.assertEqual(isolated.kinds(), ["C"])
        self.assertEqual(h.recover_calls, [])
        self.assertEqual(result["recovery_plan"]["reason_code"], "coverage_not_assessed")
        self.assertFalse(result["coverage_final"]["assessed"])
        self.assertTrue(all(row["state"] == stages.NOT_ASSESSED for row in result["coverage_final"]["obligations"]))
        self.assertTrue(result["final_audit"]["constrained_render_match"])

    def test_a_plan_with_no_search_action_skips_the_second_round_entirely(self):
        isolated = ScriptedClient(c=c_supports({}), p=p_all("PRESERVE_UNRESOLVED"))
        h = Harness(
            topo.WAVE1["T5"], initial=INITIAL, recovery=NEW, clients={"shared": ScriptedClient(), "isolated": isolated}
        )
        self.addCleanup(h.close)
        result = h.run()
        self.assertEqual(h.recover_calls, [])
        self.assertEqual(stage_names(result), ["W1", "C1", "P1"])
        self.assertEqual(result["recovery_plan"]["state"], "planned")


class ResidencyTests(unittest.TestCase):
    def test_the_q25_worker_is_unloaded_before_qwen35_runs_and_reloaded_only_for_round_two(self):
        shared = ScriptedClient()
        isolated = ScriptedClient(r=r_maps("s3-o1"), p=p_all("DEEPEN"))
        h = Harness(topo.WAVE1["T1"], initial=INITIAL, recovery=NEW, clients={"shared": shared, "isolated": isolated})
        self.addCleanup(h.close)
        result = h.run()
        self.assertEqual(stage_names(result), ["W1", "R1", "C1", "P1", "W2", "R2", "C2"])
        phases = [(e["phase"], e["endpoint"], e["model"]) for e in h.guard.events]
        self.assertEqual(
            phases,
            [
                ("W1", "shared", "callosum-managed-local"),
                ("R1", "isolated", "qwen3.5:9b"),
                ("P1", "isolated", "qwen3.5:9b"),
                ("W2", "shared", "callosum-managed-local"),
                ("R2", "isolated", "qwen3.5:9b"),
            ],
        )
        # Every phase change between the two Ollamas unloads the other's model: two swaps out of Q2.5, one out of Qwen3.5.
        self.assertEqual(shared.unloaded, ["callosum-managed-local"] * 2)
        self.assertEqual(isolated.unloaded, ["qwen3.5:9b"])

    def test_qwen35_r_and_p_carry_their_bound_reasoning_setting_and_the_p_allowance_is_8k(self):
        isolated = ScriptedClient(r=r_maps("s3-o1"), p=p_all("PRESERVE_UNRESOLVED"))
        h = Harness(
            topo.WAVE1["T1"], initial=INITIAL, recovery=NEW, clients={"shared": ScriptedClient(), "isolated": isolated}
        )
        self.addCleanup(h.close)
        h.run()
        r_call = next(c for c in isolated.calls if c["kind"] == "R")
        p_call = next(c for c in isolated.calls if c["kind"] == "P")
        self.assertIs(r_call["think"], True)
        self.assertEqual(r_call["options"]["num_predict"], 4096)
        self.assertEqual(p_call["options"]["num_predict"], 8192)


class ArtifactTests(unittest.TestCase):
    def test_the_run_writes_the_sealed_ledger_the_coverage_and_plan_records_and_the_final_answer(self):
        shared = ScriptedClient(r=r_maps("s3-o1"))
        h = Harness(topo.WAVE1["T0"], initial=INITIAL, recovery=NEW, clients={"shared": shared})
        self.addCleanup(h.close)
        result = h.run()
        out = h.trace.dir
        for name in (
            "01_request_contract.json",
            "11_verified_ledger.json",
            "12_coverage_audit.initial.json",
            "12_coverage_audit.json",
            "13_recovery_plan.json",
            "13_gap_recovery.json",
            "14_final_answer.md",
            "14_render_manifest.json",
            "14_final_audit.json",
            "stage_log.json",
        ):
            self.assertTrue((out / name).is_file(), name)
        ledger = json.loads((out / "11_verified_ledger.json").read_text(encoding="utf-8"))
        sealed = {k: v for k, v in ledger.items() if k != "sealed_hash"}
        digest = hashlib.sha256(json.dumps(sealed, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(ledger["sealed_hash"], digest)
        self.assertEqual(result["sealed_hash"], digest)
        self.assertIn("Judged responsive to this item", (out / "14_final_answer.md").read_text(encoding="utf-8"))


class RunTopologyGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []

    def run_it(self, *, dirty=(), scored=True, verify=None, contract_ok=True):
        def git_state(root):
            return {"sha": "abc123", "branch": "experiment/ask-e2e", "dirty_paths": list(dirty)}

        def build(*args, **kwargs):
            self.calls.append("runtime")
            raise RuntimeError("stop after guards")

        def frozen():
            if not contract_ok:
                raise ContractDriftError("drift")

        return e2e.run_topology(
            "T0",
            "lld",
            db_path=Path(self.tmp.name) / "library.sqlite",
            library_frozen=Path(self.tmp.name) / "library.frozen.json",
            out_dir=Path(self.tmp.name) / "out",
            git_root=Path(self.tmp.name),
            scored=scored,
            git_state_fn=git_state,
            verify_library=verify or (lambda db, frozen: {"ok": True}),
            verify_contracts=frozen,
            runtime_factory=build,
        )

    def test_a_scored_run_refuses_a_dirty_tree_before_building_anything(self):
        with self.assertRaises(provenance.DirtyTreeError):
            self.run_it(dirty=["experiments/ask_cli_revised/qwen.py"])
        self.assertEqual(self.calls, [])

    def test_a_contract_drift_refuses_before_building_anything(self):
        with self.assertRaises(ContractDriftError):
            self.run_it(contract_ok=False)
        self.assertEqual(self.calls, [])

    def test_a_library_that_drifted_before_the_run_refuses_before_building_anything(self):
        def drifted(db, frozen):
            raise library_copy.LibraryCopyDrift("sha256")

        with self.assertRaises(library_copy.LibraryCopyDrift):
            self.run_it(verify=drifted)
        self.assertEqual(self.calls, [])

    def test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored(self):
        with self.assertRaises(RuntimeError):  # reaches the runtime build: the guards passed
            self.run_it(dirty=["x.py"], scored=False)
        self.assertEqual(self.calls, ["runtime"])


class ModelPresenceTests(unittest.TestCase):
    """A bound model that is not on its Ollama fails the run at the start, not halfway through it."""

    def test_every_bound_model_present_returns_its_digest(self):
        clients = {"shared": ScriptedClient(), "isolated": ScriptedClient()}
        digests = e2e.require_models(clients, topo.WAVE1["T1"])
        self.assertEqual(set(digests), {"callosum-managed-local", "qwen3.5:9b"})

    def test_a_missing_model_is_named_with_its_endpoint_before_any_work(self):
        clients = {"shared": ScriptedClient(), "isolated": ScriptedClient()}  # neither lists gemma3:12b or phi4:14b
        with self.assertRaises(e2e.ModelMissingError) as caught:
            e2e.require_models(clients, topo.WAVE1["T5"])
        self.assertIn("phi4:14b", str(caught.exception))
        self.assertIn("isolated", str(caught.exception))

    def test_run_topology_checks_models_before_running(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        client = ScriptedClient()
        with self.assertRaises(e2e.ModelMissingError):
            e2e.run_topology(
                "T5", "lld",
                db_path=Path(tmp.name) / "l.sqlite", library_frozen=Path(tmp.name) / "l.json",
                out_dir=Path(tmp.name) / "out", git_root=Path(tmp.name), scored=False,
                git_state_fn=lambda root: {"sha": "x", "branch": "b", "dirty_paths": []},
                verify_library=lambda db, frozen: {"sha256": "same"},
                verify_contracts=lambda: None,
                runtime_factory=lambda db, **kw: SimpleNamespace(
                    engine=SimpleNamespace(connect=lambda: contextlib.nullcontext(MagicMock())),
                    qwen_config="Q", close=lambda: None),
                client_factory=lambda url: client,
                managed_chat=lambda config: client,
            )  # fmt: skip
        self.assertEqual(client.calls, [])  # nothing was sent to any model


class BindTests(unittest.TestCase):
    """Release-gate production-binding fix (2026-09-30): e2e.bind() constructs the REAL per-role
    Supervisor a live run would use. profile_names()/resolve_profile() only prove a profile is
    reachable BY NAME -- this proves the S-role Supervisor it actually builds carries the RIGHT
    options, closing the exact gap that left bind() hardcoding topo.OVERVIEW_S_OPTIONS for every
    Ollama S regardless of which profile was resolved."""

    def bound(self, profile):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        clients = {"shared": ScriptedClient(), "isolated": ScriptedClient()}
        rt = SimpleNamespace(qwen_config="QWEN-CONFIG")
        trace = TraceWriter(Path(tmp.name) / "run")
        return e2e.bind(profile, rt=rt, clients=clients, trace=trace)

    def test_t5o_s_gets_its_own_existing_options_unchanged(self):
        bound = self.bound(topo.OVERVIEW_PROFILES["T5O"])
        s = bound.supervisors["S"]
        self.assertEqual(s.binding.model, "qwen3.5:9b")
        self.assertIs(s.binding.think, True)
        self.assertEqual(s.base_options, topo.OVERVIEW_S_OPTIONS)

    def test_t5c_s_gets_child_overview_options_not_t5os(self):
        bound = self.bound(topo.CHILD_OVERVIEW_PROFILES["T5C"])
        s = bound.supervisors["S"]
        self.assertEqual(s.binding.model, "qwen3.5:9b")
        self.assertIs(s.binding.think, False)
        self.assertEqual(s.base_options, topo.CHILD_OVERVIEW_S_OPTIONS)
        self.assertNotEqual(s.base_options, topo.OVERVIEW_S_OPTIONS)

    def test_the_two_option_sets_remain_distinct_where_intentionally_so(self):
        self.assertNotEqual(topo.CHILD_OVERVIEW_S_OPTIONS["num_predict"], topo.OVERVIEW_S_OPTIONS["num_predict"])
        self.assertNotEqual(topo.CHILD_OVERVIEW_S_OPTIONS["temperature"], topo.OVERVIEW_S_OPTIONS["temperature"])

    def test_wave1_profiles_have_no_s_supervisor_at_all(self):
        for name in topo.WAVE1:
            with self.subTest(name=name):
                bound = self.bound(topo.WAVE1[name])
                self.assertNotIn("S", bound.supervisors)

    def test_non_s_roles_never_receive_s_role_options(self):
        # T5C derives its R/C/P unchanged from WAVE1["T5"] (R=off, C=phi4, P=gemma3) -- confirm bind()'s
        # unrelated R/C/P construction (untouched by this fix) still uses SUPERVISOR_BASE_OPTIONS, never
        # either S-only options dict, so the fix's new per-profile S routing cannot leak into another role.
        bound = self.bound(topo.CHILD_OVERVIEW_PROFILES["T5C"])
        for role in ("R", "C", "P"):
            sup = bound.supervisors.get(role)
            if sup is None:  # off in this profile (T5 derives R=off)
                continue
            with self.subTest(role=role):
                self.assertEqual(sup.base_options, topo.SUPERVISOR_BASE_OPTIONS)

    def test_t0_through_t5_bindings_are_unaffected(self):
        for name in topo.WAVE1:
            with self.subTest(name=name):
                bound = self.bound(topo.WAVE1[name])
                for role, sup in bound.supervisors.items():
                    self.assertEqual(sup.base_options, topo.SUPERVISOR_BASE_OPTIONS)


class SmokeLimitTests(unittest.TestCase):
    def test_smoke_limits_bound_the_work_without_touching_the_contract_or_the_stage_sequence(self):
        shared = ScriptedClient(r=r_maps("s3-o1"))
        h = Harness(topo.WAVE1["T0"], initial=INITIAL, recovery=NEW, clients={"shared": shared})
        self.addCleanup(h.close)
        result = h.run(smoke_limits={"max_initial_subquestions": 2, "max_recovery_gaps": 1})
        self.assertEqual(h.initial_subquestions, 2)
        self.assertEqual(len(h.recover_calls[0]["gaps"]), 1)
        self.assertEqual(stage_names(result), ["W1", "R1", "C1", "P1", "W2", "R2", "C2"])
        self.assertEqual(len(result["sealed"]["request_contract"]["source_units"]), len(SUBQUESTIONS))

    def test_the_retrieval_caps_are_lowered_only_inside_the_context_and_restored_after(self):
        from experiments.ask_cli_revised import discovery, retrieval

        before = (discovery.PER_SUBQ_PAPER_CAP, retrieval.WITHIN_PAPER_TOP_K)
        with e2e.smoke_caps({"per_subq_paper_cap": 1, "within_paper_top_k": 2}):
            self.assertEqual((discovery.PER_SUBQ_PAPER_CAP, retrieval.WITHIN_PAPER_TOP_K), (1, 2))
        self.assertEqual((discovery.PER_SUBQ_PAPER_CAP, retrieval.WITHIN_PAPER_TOP_K), before)

    def test_a_scored_run_may_not_carry_smoke_limits(self):
        with self.assertRaises(ValueError):
            e2e.run_topology(
                "T0",
                "lld",
                db_path="x",
                library_frozen="y",
                out_dir="z",
                git_root=".",
                scored=True,
                smoke_limits={"max_initial_subquestions": 1},
            )


class SeededSmokeTests(unittest.TestCase):
    """A smoke-only way to hand the supervisory stages real source-verified claims when the worker yields none."""

    def seed_ledger(self):
        first = Harness(topo.WAVE1["T0"], initial=INITIAL, recovery=[], clients={"shared": ScriptedClient(r=r_none)})
        self.addCleanup(first.close)
        first.run()
        return first.trace.dir / "11_verified_ledger.json"

    def test_seeded_claims_enter_round_one_as_pending_source_verified_and_r_then_judges_them(self):
        path = self.seed_ledger()
        shared = ScriptedClient(r=r_maps("s3-o1"))
        h = Harness(topo.WAVE1["T0"], initial=[], recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        result = h.run(seed_pass=e2e.seed_pass_from(path))
        self.assertEqual(len(result["sealed"]["verified_propositions"]), 2)
        self.assertEqual(shared.kinds(), ["R", "R"])  # both seeded claims were pending until R judged them
        self.assertTrue(all(r["provenance"].get("seeded") for r in result["sealed"]["verified_propositions"]))
        self.assertTrue(result["final_audit"]["constrained_render_match"])  # spans travelled with the claims
        w1 = next(s for s in result["stage_log"] if s["stage"] == "W1")
        self.assertEqual(w1["detail"]["seeded_claims"], 2)
        self.assertEqual(len(w1["detail"]["ledger_sha256"]), 64)

    def test_a_ledger_for_a_different_request_is_refused(self):
        path = self.seed_ledger()
        ledger = json.loads(path.read_text(encoding="utf-8"))
        ledger["request_contract"]["question_hash"] = "0" * 64
        path.write_text(json.dumps(ledger), encoding="utf-8")
        h = Harness(topo.WAVE1["T0"], initial=[], recovery=[], clients={"shared": ScriptedClient()})
        self.addCleanup(h.close)
        with self.assertRaises(ValueError):
            h.run(seed_pass=e2e.seed_pass_from(path))

    def test_a_scored_run_may_not_be_seeded(self):
        with self.assertRaises(ValueError):
            e2e.run_topology(
                "T0",
                "lld",
                db_path="x",
                library_frozen="y",
                out_dir="z",
                git_root=".",
                scored=True,
                smoke_seed="s.json",
            )


class GuardedRunEndToEndTests(unittest.TestCase):
    """run_topology around a fully faked runtime: the manifest, the checks, cleanup, and the after-run library check."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.shared = ScriptedClient(r=r_maps("s3-o1"))
        self.runtime_closed = False

        def build(db, **kwargs):
            self.build_kwargs = kwargs
            rt = SimpleNamespace(
                engine=SimpleNamespace(connect=lambda: contextlib.nullcontext(MagicMock())),
                qwen_config="QWEN-CONFIG",
                close=lambda: setattr(self, "runtime_closed", True),
            )
            return rt

        self.build = build

    def go(self, *, verify=None, scored=True):
        def initial_pass(conn, *, rt, qwen, subquestions, sink, trace):
            for record in INITIAL:
                add(sink, dict(record, provenance=dict(record["provenance"])))

        def recover_round(conn, *, rt, qwen, subquestions, gaps, plan, sink, trace):
            for record in NEW:
                add(sink, dict(record, provenance=dict(record["provenance"])))
            return []

        with patch.object(e2e, "_initial_pass", initial_pass), patch.object(e2e, "_recover_round", recover_round):
            return e2e.run_topology(
                "T0",
                "lld",
                db_path=Path(self.tmp.name) / "library.sqlite",
                library_frozen=Path(self.tmp.name) / "library.frozen.json",
                out_dir=Path(self.tmp.name) / "out",
                git_root=Path(self.tmp.name),
                scored=scored,
                git_state_fn=lambda root: {"sha": "abc123", "branch": "experiment/ask-e2e", "dirty_paths": []},
                verify_library=verify or (lambda db, frozen: {"sha256": "same"}),
                verify_contracts=lambda: None,
                runtime_factory=self.build,
                client_factory=lambda url: self.shared,
                managed_chat=lambda config: self.shared,
            )

    def test_a_clean_run_writes_a_manifest_with_provenance_stages_checks_and_valid_technical_state(self):
        manifest = self.go()
        out = Path(self.tmp.name) / "out"
        self.assertEqual(manifest["git"]["sha"], "abc123")
        self.assertEqual(manifest["profile"]["name"], "T0")
        self.assertTrue(manifest["scored"])
        self.assertEqual([s["stage"] for s in manifest["stage_log"]], ["W1", "R1", "C1", "P1", "W2", "R2", "C2"])
        self.assertTrue(all(manifest["mechanical_checks"].values()))
        self.assertEqual(manifest["technical_validity"], {"valid": True, "issues": []})
        self.assertTrue(manifest["library_unchanged_after_run"])
        self.assertEqual(manifest["model_digests"]["callosum-managed-local"], "digest-of-callosum-managed-local:latest")
        self.assertEqual(manifest["ollama_versions"], {"shared": "0.34.3"})
        self.assertIn("gate_no_answer", manifest)
        self.assertEqual(manifest["verified_claims"], 3)  # 2 in round one + 1 from recovery
        for name in ("15_run_manifest.json", "16_mechanical_checks.json", "00_question.json"):
            self.assertTrue((out / name).is_file(), name)
        self.assertEqual(self.build_kwargs["want_qwen"], True)

    def test_cleanup_unloads_only_what_the_run_loaded_and_closes_the_runtime(self):
        self.go()
        self.assertEqual(self.shared.unloaded, ["callosum-managed-local"])
        self.assertTrue(self.runtime_closed)

    def test_a_library_that_changed_during_the_run_is_recorded_as_a_technical_validity_issue(self):
        calls = []

        def verify(db, frozen):
            calls.append(1)
            if len(calls) > 1:
                raise library_copy.LibraryCopyDrift("sha256")
            return {"sha256": "same"}

        manifest = self.go(verify=verify)
        self.assertFalse(manifest["technical_validity"]["valid"])
        self.assertIn("library_copy_drift_after_run", manifest["technical_validity"]["issues"][0])
        self.assertFalse(manifest["library_unchanged_after_run"])

    def test_an_unscored_smoke_run_is_marked_and_records_its_limits(self):
        manifest = self.go(scored=False)
        self.assertFalse(manifest["scored"])


if __name__ == "__main__":
    unittest.main()
