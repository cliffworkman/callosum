"""Model-free proof of the researcher decisions (v6), the two views and their crosswalk, and the bounded integrated-test runner:
hard caps, halting, the writer budget checked before any child is written, the freeze, the authorization record, and the rule that the
held-out reference stays unreachable until the outputs and the blind evaluation are frozen. Synthetic requests plus, where the local
development artifacts exist, the audited q_aib cases. No model is called."""

from __future__ import annotations

import dataclasses
import json
import os
import re
import stat
from pathlib import Path

import pytest

import experiments.ask_cli_revised.decompose.test_correction_pass as cp
import experiments.ask_cli_revised.decompose.test_tree as tt
from experiments.ask_cli_revised.decompose import clarifications, integrated, requirements, views
from experiments.ask_cli_revised.decompose.calllog import CallLog, RunHalted, strict_live_halt
from experiments.ask_cli_revised.decompose.engine import WriterBudgetExceeded, run_engine
from experiments.ask_cli_revised.decompose.model import ReplayModel, ScriptedModel, StopAwareCall

_AIB = Path(__file__).resolve().parents[3] / ".local" / "decompose-runs" / "aib-dev"
_V6 = _AIB / "clarifications" / "q_aib.v6.researcher_decisions.json"
_HAVE_V6 = _V6.exists() and (_AIB / "reference" / "q_aib.original.v1.txt").exists()
needs_aib = pytest.mark.skipif(not _HAVE_V6, reason="local q_aib development artifacts are not present")


def _aib_parts():
    q = (_AIB / "reference" / "q_aib.original.v1.txt").read_text(encoding="utf-8")
    rows = clarifications.load(_AIB / "clarifications" / "q_aib.v3.approved.json")
    calls = [
        json.loads(x)
        for x in (_AIB / "dev-run-2-obligation-qwen35-9b" / "model_calls_LIVE_ORIGINAL.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x.strip()
    ]
    return q, rows, [r for r in calls if r["task"].startswith("parent.")]


def _v6(cid: str, wording: str):
    from experiments.ask_cli_revised.decompose.engine import rescore

    q, rows, inv = _aib_parts()
    r = rescore(
        q,
        ReplayModel(inv, "x"),
        {cid: {"question": wording, "unresolved": []}},
        clarifications=rows,
        clarification_annotations=clarifications.load_annotations(_V6),
        extract_mode="governing",
    )
    return next(c for c in r["pass1"]["children"] if c["child_id"] == cid), r


CTX = "In the context of the anomalous is bad bias, "


def _kinds(kid) -> set:
    return {f["kind"] for f in kid["edit_ledger"]["flags"] if f["class"] != "info"}


# ---- the researcher's decisions, encoded with provenance ---------------------------------------------------------------------------
@needs_aib
def test_every_recorded_decision_names_who_authorized_it_and_leaves_nothing_pending():
    decisions = clarifications.load_decisions(_V6)
    assert [d["id"] for d in decisions] == [f"D{i}" for i in range(1, 10)]
    assert all(d["authorized_by"] == "Cliff" and d["authorization"] for d in decisions)
    _, r = _v6(
        "c5", CTX + "please return whether and how specific brain areas relate to behaviors, which kinds of behaviors"
    )
    assert requirements.pending_decisions(r["parent_contract"]) == []  # nothing about RC-5/8/9 is left undecided
    ids = {c["id"]: c for c in r["parent_contract"]["clarifications"]}
    for rid in ("RC-8", "RC-9"):
        assert (
            ids[rid]["context_link"]["authority"] == requirements.APPROVED
            and ids[rid]["context_link"]["decision"] == "D2"
        )
    assert ids["RC-5"]["context_link"]["text"] == "measure" and ids["RC-5"]["context_link"]["decision"] == "D3"
    assert ids["RC-5"]["human_review"]["decision"] == "D9" and ids["RC-6"]["human_review"]["decision"] == "D9"


@needs_aib
def test_the_proposed_briefs_stay_unapproved_and_unused():
    q, rows, inv = _aib_parts()
    decisions = clarifications.load_decisions(_V6)
    with pytest.raises(clarifications.ClarificationError, match="UNUSED"):
        run_engine(
            q,
            ScriptedModel(lambda p, s: None),
            clarifications=rows,
            researcher_decisions=decisions,
            use_proposed_briefs=True,
            inventory_model=ReplayModel(inv, "x"),
        )
    _, r = _v6(
        "c5", CTX + "please return whether and how specific brain areas relate to behaviors, which kinds of behaviors"
    )
    assert all(
        "brief" not in c for c in r["parent_contract"]["clarifications"]
    )  # the v4 brief rows are not even loaded


@needs_aib
def test_the_approved_joining_words_apply_only_within_their_relationships_and_never_to_c4():
    ok, _ = _v6(
        "c5", CTX + "please return whether and how specific brain areas relate to behaviors, which kinds of behaviors"
    )
    assert ok["status"] == "candidate" and "pending_authority_used" not in _kinds(ok)  # approved: no longer pending
    for wording in (
        CTX + "please return specific brain areas",
        "In the context of the anomalous is bad bias please return specific brain areas",
    ):
        c4, _ = _v6("c4", wording)
        assert c4["status"] != "candidate" and _kinds(c4) & {
            "relation_word_added",
            "link_introduced",
        }  # not authorized for c4
    gap, _ = _v6("c4", "please return specific brain areas")
    assert (
        gap["status"] == "source_gap" and gap["edit_ledger"]["unresolved"]
    )  # the unstated link stays unresolved and is reported
    scales, _ = _v6(
        "c9",
        "using which scales are the specific personality traits that relate to the anomalous is bad bias's manifestation measured?",
    )
    assert scales["status"] == "candidate" and not _kinds(scales)  # "measure" approved for the scales request


@needs_aib
def test_where_supported_is_permitted_but_not_required_and_the_other_question_words_stay_protected():
    for cid, target, tail in (
        ("c5", "behaviors", ", which kinds of behaviors"),
        ("c6", "attitudes", ", and which kinds of attitudes"),
    ):
        base = CTX + f"please return whether and how specific brain areas relate to {target}"
        without, _ = _v6(cid, base + tail)
        with_it, _ = _v6(cid, base + " where supported" + tail)
        assert without["status"] == "candidate" and with_it["status"] == "candidate"  # permitted, not required
        state = {r["id"].split("#")[1]: r["state"] for r in with_it["edit_ledger"]["requirements"]}
        assert state["expression:where-supported"] == "used"
        assert {r["id"].split("#")[1]: r["state"] for r in without["edit_ledger"]["requirements"]}[
            "expression:where-supported"
        ] == "not_present"
        bad, _ = _v6(cid, base + ", where are the areas" + tail)
        assert bad["status"] == "semantic_conflict" and "operator_added" in _kinds(bad)


@needs_aib
def test_the_approved_scope_is_preserved_in_meaning_with_flexible_words_and_pasting_the_prose_is_still_flagged():
    plain, _ = _v6(
        "c6",
        CTX + "please return whether and how specific brain areas relate to attitudes, and which kinds of attitudes",
    )
    states = {r["id"].split("#")[1]: r["state"] for r in plain["edit_ledger"]["requirements"]}
    assert plain["status"] == "candidate"  # the researcher's own words are enough: the full prose is not required
    assert states["scope:areas-and-networks"] == "meaning_not_lexically_verified"  # reported, never certified
    assert any("human review" in x for x in plain["edit_ledger"]["verification_limits"])
    scoped, _ = _v6(
        "c6",
        CTX
        + "please return whether and how specific brain areas and networks relate to measures of implicit and explicit attitudes, and which kinds of attitudes",
    )
    assert scoped["status"] == "candidate" and not _kinds(
        scoped
    )  # the approved words are authorized, no pending or review flags
    assert {r["id"].split("#")[1]: r["state"] for r in scoped["edit_ledger"]["requirements"]}[
        "scope:areas-and-networks"
    ] == "approved_words_present"
    pasted, _ = _v6(
        "c6",
        CTX
        + "please return whether they relate to attitudes, and which kinds of attitudes, including the documented nature or direction of an association where supported",
    )
    assert pasted["status"] != "candidate"
    dropped_how, _ = _v6(
        "c6", CTX + "please return whether specific brain areas relate to attitudes, and which kinds of attitudes"
    )
    assert dropped_how["status"] == "semantic_conflict"  # RC-8's approved "how" is still enforced
    constraint = next(r for r in dropped_how["edit_ledger"]["requirements"] if r["kind"] == "constraint")
    assert (
        constraint["state"] == "relationship_check_flagged"
    )  # a changed relationship is what "do not presuppose" can rely on


@needs_aib
def test_an_approved_referent_left_unresolved_is_a_review_and_human_review_is_kept_without_changing_the_status():
    left, _ = _v6("c11", "which cultures and how was this measured?")
    assert left["status"] == "semantic_review_required" and "clarified_reference_unresolved" in _kinds(left)
    for cid, wording in (
        ("c11", "which cultures and how was the anomalous is bad bias measured?"),
        (
            "c9",
            "using which scales are the specific personality traits that relate to the anomalous is bad bias's manifestation measured?",
        ),
    ):
        kid, r = _v6(cid, wording)
        assert (
            kid["status"] == "candidate"
            and kid["human_review_required"]
            and any(f["flag"] == "human_review_required" for f in kid["flags"])
        )
        assert cid in r["pass1"]["reconciliation"]["summary"]["human_review_required"]
    other, _ = _v6(
        "c5", CTX + "please return whether and how specific brain areas relate to behaviors, which kinds of behaviors"
    )
    assert not other["human_review_required"]


def test_only_the_researcher_can_record_a_scope_item_a_constraint_or_a_human_review():
    parent = cp.build_parent_contract(CallLog(ScriptedModel(cp.base.responder())), cp.Q)
    clarifications.apply(parent, [cp.CLAR, cp.MEAN])
    scope = {
        "clarification": "RC-Q",
        "requirements": [{"kind": "scope_item", "text": "the reef zones", "phrases": ["reef zones"]}],
    }
    with pytest.raises(clarifications.ClarificationError, match="approved_by is mandatory"):
        clarifications.annotate(parent, [scope])
    with pytest.raises(clarifications.ClarificationError, match="not verbatim"):
        clarifications.annotate(
            parent,
            [
                {
                    "clarification": "RC-Q",
                    "requirements": [{**scope["requirements"][0], "approved_by": "tester", "text": "the coral"}],
                }
            ],
        )
    with pytest.raises(clarifications.ClarificationError, match="approved_by is mandatory"):
        clarifications.annotate(parent, [{"clarification": "RC-Q", "human_review": {"of": ["pairing"]}}])
    ok = {"clarification": "RC-Q", "requirements": [{**scope["requirements"][0], "approved_by": "tester"}]}
    clarifications.annotate(parent, [ok])
    rec = next(r for c in parent["clarifications"] for r in c["requirements"] if r["kind"] == "scope_item")
    assert (rec["expression"], rec["required_in_child"], rec["literal_wording"], rec["authority"]) == (
        "permitted",
        "required_in_meaning",
        "not_required",
        "researcher_approved",
    )


# ---- bounds: time, stop conditions, and the writer budget checked before any child is written -----------------------------------
def test_the_time_cap_refuses_a_call_that_would_start_after_it():
    now = [0.0]
    log = CallLog(ScriptedModel(lambda p, s: {"question": "x", "unresolved": []}), max_seconds=10, clock=lambda: now[0])
    log.call("t", "p", {"type": "object"}, 10)
    now[0] = 11.0
    with pytest.raises(RunHalted, match="time_cap"):
        log.call("t", "p", {"type": "object"}, 10)
    assert len(log.records) == 1 and log.halted.startswith("time_cap")


class _LiveFake:
    label = "live-fake"

    def __init__(self, inner: ScriptedModel, done_reason, fail_when: str | None = None):
        self.inner, self.done_reason, self.fail_when = inner, done_reason, fail_when

    def call(self, prompt, *, schema, output_cap):
        c = self.inner.call(prompt, schema=schema, output_cap=output_cap)
        if self.fail_when and self.fail_when in prompt:
            c = dataclasses.replace(c, provider_ok=False, schema_ok=False, failure_reason="provider_error: simulated")
        return StopAwareCall(
            **{
                **dataclasses.asdict(c),
                "mode": "ollama_native_format",
                "done_reason": self.done_reason,
                "truncated": self.done_reason == "length",
            }
        )

    def identity(self):
        return {"kind": "fake-live"}


@pytest.mark.parametrize(("reason", "halts"), [("stop", False), (None, True), ("load", True), ("length", True)])
def test_a_live_call_that_is_not_a_confirmed_clean_stop_ends_the_run_and_nothing_is_retried(reason, halts):
    q = cp.CONTROLS[1]
    model = _LiveFake(cp._single(q, cp._quote(q, "noun_phrase")), reason)
    if halts:
        with pytest.raises(RunHalted):
            run_engine(q, model, halt_on=strict_live_halt, repair=False)
        assert len(model.inner.calls) == 1  # the offending call was the last call: no retry, no continuation
    else:
        assert run_engine(q, model, halt_on=strict_live_halt, repair=False)["decomposition_decision"]["applied"]


def test_the_writer_budget_is_checked_before_any_child_is_written_so_nothing_is_dropped_and_no_partial_run_exists():
    question = "What is a placebo effect? How is it measured?"
    units = {"What is": [cp._item("a placebo effect")], "How is": [cp._item("How is it measured")]}
    model = cp._scripted(units)
    with pytest.raises(WriterBudgetExceeded) as caught:
        run_engine(question, model, repair=False, max_writer_calls=1)
    exc = caught.value
    assert (exc.needed, exc.budget) == (2, 1) and len(exc.plans) == 2 and exc.decision["outcome"] == "decompose"
    assert all(c["task"].startswith("parent.") for c in exc.calls)  # only the inventory ran; no writer call was made
    ok = run_engine(question, cp._scripted(units), repair=False, max_writer_calls=2)
    assert (
        ok["manifest"]["run_completeness"]["complete"]
        and len([c for c in ok["pass1"]["children"] if c["kind"] == "generated"]) == 2
    )


def test_a_call_cap_hit_makes_the_run_visibly_incomplete_never_a_quiet_partial():
    question = "What is a placebo effect? How is it measured?"
    units = {"What is": [cp._item("a placebo effect")], "How is": [cp._item("How is it measured")]}
    result = run_engine(
        question, cp._scripted(units), repair=False, max_calls=4
    )  # 3 inventory calls + 1 of the 2 writer calls
    completeness = result["manifest"]["run_completeness"]
    assert not completeness["complete"] and "call_cap_reached" in completeness["reasons"]
    assert any(c["kind"] == "fallback" for c in result["pass1"]["children"])


# ---- the two views and the crosswalk -------------------------------------------------------------------------------------------------------
def _views_run():
    def respond(prompt: str, schema: dict):
        if "requirements" in schema["properties"] or "ambiguities" in schema["properties"]:
            return tt._respond_q2(prompt, schema)
        return {"question": "  Using WHICH scales, exactly as the model wrote it.  ", "unresolved": []}

    return run_engine(
        tt.Q2,
        ScriptedModel(respond),
        repair=False,
        clarifications=[tt.CLAR_FRAGMENT, tt.CLAR_UNIT],
        prompt_variant="corrected-full",
    )


def test_the_natural_language_view_shows_each_generated_request_exactly_in_its_hierarchy_and_marks_what_is_not_runnable():
    result = _views_run()
    nl = views.natural_language_view(result)
    nodes = {n["child_id"]: n for n in nl["nodes"]}
    written = [c for c in result["pass1"]["children"] if c["kind"] == "generated"]
    assert written
    for c in written:
        assert nodes[c["child_id"]]["request"] == c["question"]  # not cleaned up, repaired or replaced
    assert (
        nodes["c3"]["parent"] == "c2"
        and nodes["c3"]["depth"] == 2
        and nodes["c3"]["nesting_basis"]["clarification"] == "RC-F"
    )
    unwritten = [c for c in result["pass1"]["children"] if c["kind"] not in ("generated", "passthrough")]
    for c in unwritten:
        n = nodes[c["child_id"]]
        assert (
            n["request"] is None
            and n["retained_source_words_not_a_request"] == c["question"]
            and "UNWRITTEN" in n["markers"]
        )
    assert any(
        "NOT INDEPENDENTLY RUNNABLE (detected)" in n["markers"] or "SOURCE GAP" in n["markers"] for n in nl["nodes"]
    )
    md = views.render_natural_language(nl)
    assert (
        "Using WHICH scales, exactly as the model wrote it." in md and "UNWRITTEN" in md and "not a certificate" in md
    )
    assert "success" not in md.lower().replace("no independence", "")  # the view reports; it never scores


def test_the_contract_view_and_the_crosswalk_trace_every_child_id_to_the_natural_language_request():
    result = _views_run()
    nl, ct, cw = views.natural_language_view(result), views.contract_view(result), views.crosswalk(result)
    ids = [c["child_id"] for c in result["pass1"]["children"]]
    assert [n["child_id"] for n in nl["nodes"]] == [
        n["node_id"] for n in result["pass1"]["question_tree"]["nodes"]
    ] or set(n["child_id"] for n in nl["nodes"]) == set(ids)
    assert {c["child_id"] for c in ct["children"]} == set(ids) == {r["child_id"] for r in cw["children"]}
    frag = next(c for c in ct["children"] if c["child_id"] == "c3")
    for key in (
        "owned_obligations",
        "source",
        "inherited_context",
        "dependencies",
        "clarifications_that_apply",
        "relationship_requirement",
        "unresolved_meanings",
        "acceptance_status",
        "requirement_results",
        "edit_ledger",
        "nesting",
    ):
        assert key in frag
    assert frag["dependencies"]["approved"][0]["node"] == "c2" and frag["nesting"]["parent"] == "c2"
    assert (
        frag["clarifications_that_apply"][0]["id"] == "RC-F"
        and frag["clarifications_that_apply"][0]["authorized_by"] == "tester"
    )
    assert frag["inherited_source_words_of_the_question_continued"][0]["from_node"] == "c2"
    assert all(o["owners"] or o["reconciliation_status"] for o in cw["obligation_to_child"])
    json.dumps([nl, ct, cw], default=str)
    md = views.render_crosswalk(cw)
    assert all(f"| {i} |" in md for i in ids)


def test_a_passed_through_control_shows_the_unchanged_request_its_decision_and_its_call_count():
    q = cp.CONTROLS[1]
    result = run_engine(q, cp._single(q, cp._quote(q, "noun_phrase")))
    nl = views.natural_language_view(result)
    (node,) = nl["nodes"]
    assert node["request"] == q and node["markers"] == ["PASSED THROUGH UNCHANGED"]
    assert nl["decision"]["outcome"] == "no_decomposition_needed" and nl["decision"]["applied"]
    assert nl["calls"]["total_calls"] == 3 and nl["calls"]["writer_calls"] == 0 and nl["answer_state"] == "not_executed"
    md = views.render_natural_language(nl)
    assert "PASSED THROUGH UNCHANGED" in md and "Model calls:** 3" in md and "writer was not called" in md


# ---- the bounded runner: freeze, authorization, outcomes, output freeze and the reference gate ---------------------------------------------
@pytest.fixture
def small_config(monkeypatch):
    monkeypatch.setitem(integrated.CONFIG, "order", ["control_placebo", "primary_request"])
    monkeypatch.setitem(
        integrated.CONFIG,
        "requests",
        {
            "control_placebo": {"max_writer_calls": 1, "max_seconds": 60},
            "primary_request": {"max_writer_calls": 1, "max_seconds": 60},
        },
    )


def test_the_inventory_call_count_is_known_before_any_call():
    assert integrated.inventory_call_count(cp.CONTROLS[1]) == 3
    assert integrated.inventory_call_count("What is X? How is it measured? Why?") == 5
    assert integrated.inventory_call_count(cp.CONTROLS[1], whole_pass=False) == 2


def test_a_run_refuses_to_start_without_an_authorization_naming_the_gate_it_was_given(tmp_path):
    gate = tmp_path / "GATE.md"
    gate.write_text("the gate", encoding="utf-8")
    with pytest.raises(PermissionError, match="no authorization"):
        integrated.check_authorization(None, gate)
    auth = tmp_path / "AUTH.json"
    auth.write_text(
        json.dumps({"gate_sha256": "0" * 64, "authorized_by": "Cliff", "authorization_quote": "yes"}), encoding="utf-8"
    )
    with pytest.raises(PermissionError, match="different gate"):
        integrated.check_authorization(auth, gate)
    auth.write_text(
        json.dumps(
            {
                "gate_sha256": integrated.sha256_file(gate),
                "authorized_by": "Cliff",
                "authorization_quote": "I authorize this gate",
            }
        ),
        encoding="utf-8",
    )
    assert integrated.check_authorization(auth, gate)["authorized_by"] == "Cliff"
    gate.write_text("the gate, edited after authorization", encoding="utf-8")
    with pytest.raises(PermissionError, match="different gate"):
        integrated.check_authorization(auth, gate)


def test_the_freeze_detects_any_change_to_the_request_the_clarification_set_or_the_tools(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    q, c, t = tmp_path / "q.txt", tmp_path / "c.json", tmp_path / "tool.py"
    q.write_text(cp.CONTROLS[1], encoding="utf-8")
    c.write_text("{}", encoding="utf-8")
    t.write_text("print(1)", encoding="utf-8")
    kw = {
        "question_files": {"control_placebo": q, "primary_request": q},
        "clarification_files": {"c": c},
        "tool_files": [t],
    }
    frozen = integrated.build_freeze(repo, tmp_path, **kw)
    assert integrated.verify_freeze(frozen, integrated.build_freeze(repo, tmp_path, **kw)) == []
    assert frozen["writer"]["variant"] == "corrected-full" and frozen["writer"]["proposed_briefs_used"] is False
    assert (
        frozen["hard_caps"]["control_placebo"]["inventory_calls"] == 3 and frozen["engine_code_sha256"]["integrated.py"]
    )
    for path, text in ((q, "What is a different request?"), (c, '{"x": 1}'), (t, "print(2)")):
        old = path.read_text(encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        assert integrated.verify_freeze(frozen, integrated.build_freeze(repo, tmp_path, **kw)), path.name
        path.write_text(old, encoding="utf-8")


def test_the_control_completes_as_a_pass_through_and_writes_both_views_and_the_crosswalk(
    tmp_path, small_config, monkeypatch
):
    monkeypatch.setitem(integrated.CONFIG, "order", ["control_placebo"])
    q = cp.CONTROLS[1]
    summary = integrated.run_test(
        tmp_path,
        lambda: cp._single(q, cp._quote(q, "noun_phrase")),
        live=False,
        questions={"control_placebo": q},
        clarifications=[],
        annotations=[],
        decisions=[],
    )
    assert (
        summary["outcome"] == "COMPLETE" and summary["runs"]["control_placebo"]["decision"] == "no_decomposition_needed"
    )
    assert summary["runs"]["control_placebo"]["calls_by_task"] == {
        "parent.ambiguities": 1,
        "parent.obligations_unit": 1,
        "parent.obligations_whole": 1,
    }
    out = tmp_path / "control_placebo"
    for name in (
        "VIEW_natural_language.md",
        "VIEW_natural_language.json",
        "VIEW_contract.md",
        "VIEW_contract.json",
        "VIEW_crosswalk.md",
        "VIEW_crosswalk.json",
        "model_calls.jsonl",
        "RUN_RECORD.json",
        "08_decomposition_decision.json",
    ):
        assert (out / name).exists(), name
    assert json.loads((out / "VIEW_natural_language.json").read_text(encoding="utf-8"))["nodes"][0]["request"] == q


def test_the_first_halt_ends_the_whole_test_as_incomplete_and_the_second_request_is_not_run(tmp_path, small_config):
    q_control, q_second = cp.CONTROLS[1], "What is FAILME?"
    inner = cp._scripted(
        {"What": [cp._item("a placebo effect")]},
        whole=[cp._item("a placebo effect")],
        writer=lambda p: {"question": q_control, "unresolved": []},
    )
    summary = integrated.run_test(
        tmp_path,
        lambda: _LiveFake(inner, "stop", fail_when="FAILME"),
        live=True,
        questions={"control_placebo": q_control, "primary_request": q_second},
        clarifications=[],
        annotations=[],
        decisions=[],
    )
    assert summary["outcome"] == "INCOMPLETE" and summary["runs"]["control_placebo"]["outcome"] == "completed"
    assert (
        summary["runs"]["primary_request"]["outcome"] == "halted"
        and "provider_failure" in summary["runs"]["primary_request"]["reason"]
    )
    halted = json.loads((tmp_path / "primary_request" / "HALTED.json").read_text(encoding="utf-8"))
    assert (
        "INCOMPLETE" in halted["note"] and not (tmp_path / "primary_request" / "VIEW_natural_language.md").exists()
    )  # no decomposition is claimed


def test_a_plan_that_needs_more_writer_calls_than_the_budget_stops_before_writing_and_says_so(
    tmp_path, small_config, monkeypatch
):
    monkeypatch.setitem(integrated.CONFIG, "order", ["primary_request"])
    question = "What is a placebo effect? How is it measured?"
    units = {"What is": [cp._item("a placebo effect")], "How is": [cp._item("How is it measured")]}
    summary = integrated.run_test(
        tmp_path,
        lambda: cp._scripted(units),
        live=False,
        questions={"primary_request": question},
        clarifications=[],
        annotations=[],
        decisions=[],
    )
    assert (
        summary["outcome"] == "INCOMPLETE"
        and summary["runs"]["primary_request"]["outcome"] == "incomplete_writer_budget"
    )
    rec = json.loads((tmp_path / "primary_request" / "INCOMPLETE_writer_budget.json").read_text(encoding="utf-8"))
    assert (
        (rec["needed_writer_calls"], rec["writer_budget"]) == (2, 1)
        and len(rec["plans"]) == 2
        and "none written, none dropped" in rec["note"]
    )
    calls = [
        json.loads(x)
        for x in (tmp_path / "primary_request" / "model_calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all(c["task"].startswith("parent.") for c in calls)


def test_the_model_identity_is_checked_before_any_generation_call(tmp_path, small_config, monkeypatch):
    monkeypatch.setitem(integrated.CONFIG, "order", ["control_placebo"])
    q = cp.CONTROLS[1]
    model = cp._single(q, cp._quote(q, "noun_phrase"))
    summary = integrated.run_test(
        tmp_path,
        lambda: model,
        live=False,
        questions={"control_placebo": q},
        clarifications=[],
        annotations=[],
        decisions=[],
        identity_check=integrated.check_identity,
    )
    assert (
        summary["outcome"] == "not_started" and model.calls == []
    )  # scripted identity is not the frozen model: no call was made
    good = {
        "model": "qwen3.5:9b",
        "endpoint": "http://127.0.0.1:11435",
        "think": False,
        "show": integrated.CONFIG["expected_model_family"],
        "digest": integrated.CONFIG["expected_model_digest"],
    }
    assert integrated.check_identity(good) == []
    assert integrated.check_identity({**good, "think": None}) and integrated.check_identity(
        {**good, "show_error": "down"}
    )


def test_outputs_freeze_read_only_and_the_reference_stays_unreachable_until_the_blind_evaluation_is_frozen_too(
    tmp_path,
):
    run = tmp_path / "run"
    (run / "primary_request").mkdir(parents=True)
    (run / "primary_request" / "model_calls.jsonl").write_text("raw\n", encoding="utf-8")
    evaluation = tmp_path / "BLIND_EVALUATION.md"
    evaluation.write_text("written from the frozen outputs alone", encoding="utf-8")
    assert integrated.reference_diagnostic_allowed(run, evaluation) == (False, "the outputs are not frozen")
    with pytest.raises(PermissionError, match="not frozen"):
        integrated.freeze_blind_evaluation(run, evaluation)
    frozen = integrated.freeze_outputs(run)
    assert "primary_request/model_calls.jsonl" in frozen["files"]
    with pytest.raises(PermissionError):
        (run / "primary_request" / "model_calls.jsonl").write_text("tampered", encoding="utf-8")
    assert integrated.reference_diagnostic_allowed(run, evaluation) == (False, "the blind evaluation is not frozen")
    integrated.freeze_blind_evaluation(run, evaluation)
    assert integrated.reference_diagnostic_allowed(run, evaluation)[0] is True
    evaluation.write_text("edited after the reference was consulted", encoding="utf-8")
    assert integrated.reference_diagnostic_allowed(run, evaluation) == (False, "the frozen blind evaluation changed")
    evaluation.write_text("written from the frozen outputs alone", encoding="utf-8")
    os.chmod(run / "primary_request" / "model_calls.jsonl", stat.S_IWRITE | stat.S_IREAD)
    (run / "primary_request" / "model_calls.jsonl").write_text("tampered", encoding="utf-8")
    assert integrated.outputs_unchanged(run) == ["primary_request/model_calls.jsonl"]
    assert integrated.reference_diagnostic_allowed(run, evaluation)[0] is False


def test_no_frozen_module_reads_the_held_out_reference():
    root = Path(__file__).parent
    forbidden = re.compile(r"intent_reference|reference_correspondence|hier-decomp-aib|reference_compare|children_v2")
    for name in (
        "integrated.py",
        "views.py",
        "engine.py",
        "children.py",
        "ledger.py",
        "requirements.py",
        "passthrough.py",
        "prompts.py",
        "clarifications.py",
    ):
        assert not forbidden.search((root / name).read_text(encoding="utf-8")), name


def test_the_identity_capture_reads_the_digest_from_the_clients_list_of_models_as_the_real_client_returns_it():
    class FakeClient:  # mirrors OllamaClient: tags() returns the LIST of model records, not a dict
        def version(self):
            return "9.9.9"

        def tags(self):
            return [
                {"name": "other:1b", "digest": "x"},
                {"name": "qwen3.5:9b", "digest": integrated.CONFIG["expected_model_digest"]},
            ]

    class FakeModel:
        client = FakeClient()

        def identity(self):
            return {
                "model": "qwen3.5:9b",
                "endpoint": "http://127.0.0.1:11435",
                "think": False,
                "show": integrated.CONFIG["expected_model_family"],
            }

    got = integrated.capture_identity(FakeModel())
    assert got["digest"] == integrated.CONFIG["expected_model_digest"] and got["ollama_version"] == "9.9.9"
    assert integrated.check_identity(got) == []
    FakeClient.tags = lambda self: {"models": [{"name": "qwen3.5:9b", "digest": "dict-shaped also works"}]}
    assert integrated.capture_identity(FakeModel())["digest"] == "dict-shaped also works"

    def broken(self):
        raise RuntimeError("down")

    FakeClient.tags = broken
    lost = integrated.capture_identity(FakeModel())
    assert (
        lost["digest"] is None and "down" in lost["digest_error"] and integrated.check_identity(lost)
    )  # never guessed: it fails safe
