"""Model-free tests for the obligation-driven decomposition engine. No real model, no library, no protected request text.

The synthetic request mirrors the STRUCTURE the engine must handle (an enumerated list with a shared frame, a compound
unit with several separate asks, "whether and how", a cross-unit referent, an ambiguous pronoun) without using any
real request.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys

import pytest

from experiments.ask_cli_revised.decompose import checks, gate
from experiments.ask_cli_revised.decompose.calllog import CallLog
from experiments.ask_cli_revised.decompose.children import plan_children
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ReplayModel, ScriptedModel
from experiments.ask_cli_revised.decompose.parent import anchor, build_parent_contract, find_cues

Q = (
    "how does the coral effect show up in growth, color, and survival? please return specific reef zones and whether "
    "and how they relate to depth, which kinds of depth. what kind of specific pigments relate to its expression? "
    "is there any evidence for the effect in juveniles?"
)
U1 = "how does the coral effect show up in growth, color, and survival?"
U2_TEXT_START = "please return specific reef zones"

UNIT_OBLIGATIONS = {
    "how does the coral effect": [
        {"kind": "requested_item", "quotes": ["how does the coral effect show up in"], "note": ""},
        {"kind": "population", "quotes": ["growth, color, and survival"], "note": ""},
    ],
    "please return": [
        {"kind": "requested_item", "quotes": ["specific reef zones"], "note": ""},
        {"kind": "relationship", "quotes": ["whether and how they relate to depth"], "note": ""},
        {"kind": "kinds", "quotes": ["which kinds of depth"], "note": ""},
        {"kind": "relationship", "quotes": ["specific pigments", "relate to its expression"], "note": ""},
    ],
    "is there any": [
        {"kind": "existence", "quotes": ["is there any evidence for the effect in juveniles"], "note": ""}
    ],
    "and using": [{"kind": "requested_item", "quotes": ["scales"], "note": ""}],
}
WHOLE = [
    {
        "kind": "relationship",
        "quotes": ["coral effect", "its expression"],
        "note": "cross-unit: pigments and the effect",
    },
    {"kind": "output_expectation", "quotes": ["please return specific reef zones"], "note": ""},
]
AMBIGUITIES = [{"quote": "they", "alternatives": ["the reef zones", "the depths"], "note": ""}]
CHILDREN = {
    "growth": "How does the coral effect show up in growth?",
    "color": "How does the coral effect show up in color?",
    "survival": "How does the coral effect show up in survival?",
    "specific reef zones": "Please return specific reef zones.",
    "whether and how": "Whether and how the specific reef zones relate to depth, which kinds of depth",
    "specific pigments": "What kind of specific pigments relate to its expression?",
    "is there any": "Is there any evidence for the effect in juveniles?",
}


def _owned_first_line(prompt: str) -> str:
    """The words this child was asked to write, from any of the three prompt layouts (v3, corrected-full, lean)."""
    for marker in ("What this question must ask", "What this request must ask"):
        if marker in prompt:
            block = prompt.split(marker, 1)[1].split(chr(10), 2)[1]
            return block.split('"', 2)[1].lower()
    block = prompt.split("Source extract (exact words from the request):" + chr(10), 1)[1].split(chr(10) * 2, 1)[0]
    return block.replace(chr(10), " ").lower()


def _declared(prompt: str, question: str) -> list[dict]:
    """What a careful writer reports: every listed unresolved word that its question no longer contains."""
    if "Unresolved wording (NOT settled" in prompt:  # the frozen v3 layout
        block = prompt.split("Unresolved wording (NOT settled", 1)[1].split(chr(10) * 2)[0]
        words = re.findall(r'- "([^"]+)" \(chars', block)
    elif "Not clarified (" in prompt:  # corrected-full and lean layouts
        block = prompt.split("Not clarified (", 1)[1].split(chr(10) * 2)[0].split(chr(10), 1)
        words = [
            w
            for w in re.findall(r'"([^"]+)"', block[0] + chr(10) + (block[1] if len(block) > 1 else ""))
            if w != "unresolved"
        ]
    else:
        return []
    return [
        {"word": w, "reading_used": "the nearest earlier item", "other_readings": ["something else"]}
        for w in words
        if w.lower() not in question.lower().split()
    ]


def responder(overrides: dict | None = None, fail: set | None = None):
    overrides = overrides or {}
    fail = fail or set()

    def respond(prompt: str, schema: dict):
        props = schema["properties"]
        if "requirements" in props:
            if "Part to read:\n" in prompt:
                part = prompt.split("Part to read:\n", 1)[1]
                key = next(k for k in UNIT_OBLIGATIONS if part.startswith(k) or part.strip().startswith(k))
                return {"requirements": UNIT_OBLIGATIONS[key]} if "unit" not in fail else None
            return {"requirements": WHOLE} if "whole" not in fail else None
        if "ambiguities" in props:
            return {"ambiguities": AMBIGUITIES}
        first = _owned_first_line(prompt)
        for key, question in overrides.items():
            if key in first:
                out = question(prompt) if callable(question) else question
                return (
                    out
                    if out is None or "unresolved" in out
                    else {**out, "unresolved": _declared(prompt, out["question"])}
                )
        for key, question in CHILDREN.items():
            if key in first:
                return None if "child" in fail else {"question": question, "unresolved": _declared(prompt, question)}
        return {"question": "What is asked?", "unresolved": []}

    return respond


def run(overrides=None, fail=None, **kw):
    model = ScriptedModel(responder(overrides, fail))
    return run_engine(Q, model, **kw), model


# ---- inventory over the whole request ------------------------------------------------------------------------------


def test_anchor_states_and_multi_span_requirements():
    q = "Which  kinds of Behaviors matter?"
    assert anchor(q, 0, len(q), "kinds of Behaviors")["state"] == "exact"
    assert anchor(q, 0, len(q), "KINDS OF behaviors")["state"] == "case_insensitive"
    ws = anchor(q, 0, len(q), "Which kinds")
    assert ws["state"] == "whitespace_normalized" and q[ws["span"][0] : ws["span"][1]] == "Which  kinds"
    assert anchor(q, 0, len(q), "not present")["span"] is None
    parent = build_parent_contract(CallLog(ScriptedModel(responder())), Q)
    cross = [r for r in parent["requirements"] if r["kind"] == "relationship" and len(r["unit_ids"]) >= 2]
    assert cross and len(cross[0]["spans"]) >= 2 and cross[0]["anchoring"] == "complete"


def test_cues_are_anchored_facts_and_whether_and_how_are_separate_obligations():
    units = build_parent_contract(CallLog(ScriptedModel(responder())), Q)["source_units"]
    reqs, ambs = find_cues(Q, units)
    kinds = {r["kind"] for r in reqs}
    assert {"polarity", "manner", "qualifier", "operation"} <= kinds
    for r in [*reqs, *ambs]:
        s = r["spans"][0]
        assert Q[s[0] : s[1]] == r["text"]
    parent = build_parent_contract(CallLog(ScriptedModel(responder())), Q)
    rel = next(r for r in parent["requirements"] if r["kind"] == "relationship" and "whether and how" in r["text"])
    deps = {r["kind"]: r for r in parent["requirements"] if r.get("part_of") == rel["id"]}
    assert {"polarity", "manner", "kinds"} <= set(deps)  # separate obligations, all attached to the one relationship
    assert deps["polarity"]["text"].lower() == "whether" and deps["manner"]["text"].lower() == "how"


def test_enumerated_list_is_split_and_its_introducing_words_become_a_shared_frame():
    parent = build_parent_contract(CallLog(ScriptedModel(responder())), Q)
    items = [r for r in parent["requirements"] if r["origin"] == "deterministic_list_split"]
    assert [r["text"] for r in items] == ["growth", "color", "survival"]
    frame = next(r for r in parent["requirements"] if r["kind"] == "shared_frame")
    assert frame["reclassified_from"] == "requested_item" and "coral effect" in frame["text"]
    original = next(r for r in parent["requirements"] if r["id"] == items[0]["split_from"])
    assert original["superseded"] and original["status"] == "split_into_items"


def test_overlapping_same_kind_obligations_from_unit_and_whole_passes_merge_into_one_cross_unit_obligation():
    parent = build_parent_contract(CallLog(ScriptedModel(responder())), Q)
    merged = [r for r in parent["requirements"] if r.get("merged_from")]
    assert merged and merged[0]["unit_ids"] == ["u1", "u2"]
    assert parent["post_processing"]["merged"]


# ---- children come from obligations, not units ------------------------------------------------------------------------


def test_several_children_per_unit_and_a_child_can_own_an_obligation_that_crosses_units():
    result, _ = run(repair=False)
    kids = result["pass1"]["children"]
    per_unit = {}
    for c in kids:
        per_unit.setdefault(c["origin"]["source_unit_ids"][0], []).append(c["child_id"])
    assert len(per_unit["u1"]) >= 3 and len(per_unit["u2"]) >= 2  # several children from one unit
    cross = [c for c in kids if len(c["origin"]["source_unit_ids"]) >= 2 and "pigments" in c["question"]]
    assert len(cross) == 1 and cross[0]["origin"]["source_unit_ids"] == [
        "u1",
        "u2",
    ]  # one child carries a cross-unit obligation
    by = {r["id"]: r for r in result["parent_contract"]["requirements"]}
    rel = next(c for c in kids if "whether and how" in c["question"].lower())
    kinds = sorted(by[i]["kind"] for i in rel["owns"])
    assert kinds == ["kinds", "manner", "polarity", "relationship"]  # ownership is preserved and explicit
    facets = [c for c in kids if any(by[i]["text"] in ("growth", "color", "survival") for i in c["owns"])]
    assert len(facets) == 3 and all(c["carries_shared"] for c in facets)
    assert not any(c["carries_shared"] for c in kids if c not in facets)  # the frame belongs to its own unit only


def test_plan_is_deterministic_and_every_child_traces_to_exact_spans():
    parent = build_parent_contract(CallLog(ScriptedModel(responder())), Q)
    assert json.dumps(plan_children(parent)) == json.dumps(plan_children(parent))
    result, _ = run(repair=False)
    assert result["pass1"]["verified_traceability"]["ok"], result["pass1"]["verified_traceability"]
    tampered = copy.deepcopy(result["parent_contract"])
    req = next(r for r in tampered["requirements"] if r["origin"] == "model_unit" and r["spans"])
    req["anchors"][0]["span"] = [req["anchors"][0]["span"][0] + 1, req["anchors"][0]["span"][1] + 1]
    assert not checks.verify_traceability(tampered, result["pass1"])["ok"]
    broken = copy.deepcopy(result["pass1"])
    broken["children"][0]["owns"].append("ZZ")
    assert not checks.verify_traceability(result["parent_contract"], broken)["ok"]


# ---- reconciliation against the parent ----------------------------------------------------------------------------------


def test_reconciliation_accounts_for_every_obligation_and_exposes_open_ambiguity():
    result, _ = run(repair=False)
    rec = result["pass1"]["reconciliation"]
    statuses = {r["id"]: r["status"] for r in rec["rows"]}
    by = {r["id"]: r for r in result["parent_contract"]["requirements"]}
    assert not any(s == "unowned_unresolved" for s in statuses.values())
    assert any(s == "split_into_items" for s in statuses.values()) and any(
        s == "shared_carried_candidate" for s in statuses.values()
    )
    assert any(s == "parent_level_recorded_open" for s in statuses.values())
    amb = [r for r in rec["rows"] if r["status"] == "ambiguity_open" and r["alternatives"]]
    assert amb and amb[0]["alternatives"] == ["the reef zones", "the depths"]
    dependent = next(
        r
        for r in rec["rows"]
        if r["id"] in by and by[r["id"]]["kind"] == "relationship" and "whether and how" in r["text"]
    )
    assert dependent["depends_on_open_ambiguity"]  # a consequential reading is exposed on the obligation, not hidden
    kid = next(c for c in result["pass1"]["children"] if "whether and how" in c["question"].lower())
    assert any(
        i["kind"] == "depends_on_open_ambiguity" and i["status"] == "reading_not_established"
        for i in kid["interpretations"]
    )
    assert (
        rec["semantic_fidelity"]["status"] == "not_certified"
        and result["manifest"]["semantic_fidelity"] == "not_certified"
    )
    assert all(c["semantic_fidelity"]["status"] == "not_certified" for c in result["pass1"]["children"])


def test_a_child_that_repeats_the_compound_question_is_not_a_successful_decomposition():
    compound = "Please return specific reef zones and whether and how they relate to depth, which kinds of depth."
    result, _ = run({"whether and how": {"question": compound}}, repair=False)
    kid = next(
        c
        for c in result["pass1"]["children"]
        if "whether and how" in c["question"].lower() and c["question"].startswith("Please")
    )
    assert kid["diagnostics"]["copies_of_source_text"] and kid["diagnostics"]["hard_fail"]
    rec = result["pass1"]["reconciliation"]
    assert (
        kid["child_id"] in rec["summary"]["bundled_children"]
        and kid["child_id"] not in rec["summary"]["successful_children"]
    )
    assert all(
        r["status"] == "bundled_unresolved"
        for r in rec["rows"]
        if r["id"] in kid["owns"] and r["kind"] != "source_unit"
    )


def test_fallback_is_marked_unresolved_and_never_counted_as_success():
    result, _ = run(fail={"child"}, repair=False)
    grown = [c for c in result["pass1"]["children"] if "whether and how" not in c["question"].lower()]
    assert grown and all(
        c["kind"] == "fallback" and c["status"] == "fallback_unresolved" and c["is_decomposition"] is False
        for c in result["pass1"]["children"]
        if c["kind"] == "fallback"
    )
    rec = result["pass1"]["reconciliation"]
    assert rec["summary"]["successful_children"] == [] or all(
        c["kind"] == "generated"
        for c in result["pass1"]["children"]
        if c["child_id"] in rec["summary"]["successful_children"]
    )
    assert any(r["status"] == "fallback_unresolved" for r in rec["rows"])


# ---- "whether" and "how" stay visible, and repairs may not trade an obligation for a passing check --------------------------


def test_polarity_and_manner_loss_is_flagged_separately():
    result, _ = run(
        {
            "whether and how": {
                "question": "What is the relation between the specific reef zones and depth, and which kinds?"
            }
        },
        repair=False,
    )
    kid = next(c for c in result["pass1"]["children"] if "relation between" in c["question"])
    lost_kinds = sorted(f["kind"] for f in kid["flags"] if f["flag"] == "obligation_not_lexically_preserved")
    assert "polarity" in lost_kinds and "manner" in lost_kinds
    good, _ = run(repair=False)
    ok = next(c for c in good["pass1"]["children"] if "whether and how" in c["question"].lower())
    assert not [f for f in ok["flags"] if f["flag"] == "obligation_not_lexically_preserved"]


def test_a_repair_that_passes_more_checks_but_loses_an_obligation_is_rejected():
    first = {
        "question": "What is the relation of the reef zones to depth, and why does mortality matter?"
    }  # lost whether/how + addition

    def overrides(prompt):
        if "Problems found" in prompt:  # removes the addition but drops "depth" and the polar/manner asks
            return {"question": "What do the reef zones show?"}
        return first

    result, _ = run({"whether and how": overrides}, repair=True)
    rep = next(r for r in result["pass2"]["repairs"] if r["attempted"] and "relation of the reef zones" in r["before"])
    assert rep["accepted"] is False
    assert any(w in rep["rejected_reason"] for w in ("loses", "hard failure", "changes the relationship"))
    kept = next(c for c in result["pass2"]["children"] if c["child_id"] == rep["child_id"])
    assert kept["question"] == first["question"]  # the first-pass wording stands; the repair is stored, not applied


def test_a_genuine_repair_is_accepted_stored_separately_and_the_first_pass_is_unchanged():
    def overrides(prompt):
        if "Problems found" in prompt:
            return {"question": CHILDREN["whether and how"]}
        return {"question": "What is the relation of the specific reef zones to depth?"}

    result, model = run({"whether and how": overrides}, repair=True)
    snapshot = json.dumps(result["pass1"]["children"], sort_keys=True)
    rep = next(r for r in result["pass2"]["repairs"] if r["attempted"] and r["accepted"])
    assert "does not properly ask" in " ".join(rep["problems"]).lower() and "yes/no" in " ".join(rep["problems"])
    assert json.dumps(result["pass1"]["children"], sort_keys=True) == snapshot and result["final_pass"] == 1
    assert result["pass1"]["children"] != result["pass2"]["children"]
    assert sum(1 for c in model.calls if "Problems found" in c["prompt"]) == len(
        [r for r in result["pass2"]["repairs"] if r["attempted"]]
    )  # one attempt per flagged child


# ---- hard call cap, replay, gate ----------------------------------------------------------------------------------------


def test_the_call_cap_is_hard_and_degrades_to_fallback_instead_of_calling_again():
    model = ScriptedModel(responder())
    result = run_engine(Q, model, repair=True, max_calls=9)
    assert (
        len(model.calls) == 9
        and result["manifest"]["call_summary"]["calls"] == 9
        and result["manifest"]["call_cap_reached"] is True
    )
    assert any(
        c["kind"] == "fallback" and any(f["flag"] == "call_cap_reached" for f in c["flags"])
        for c in result["pass1"]["children"]
    )
    assert result["pass1"]["verified_traceability"]["ok"]


def test_replay_reuses_recorded_outputs_and_never_calls_a_model():
    first, _ = run(repair=False)
    replay = ReplayModel(first["calls"], first["manifest"]["model_label"])
    again = run_engine(Q, replay, repair=False)
    assert [c["question"] for c in again["pass1"]["children"]] == [c["question"] for c in first["pass1"]["children"]]
    assert replay.misses == [] and again["manifest"]["model_identity"]["new_model_calls"] == 0


def test_polar_and_manner_cues_are_not_faked_by_auxiliary_verbs():
    assert not checks.cue_preserved("whether", "What are the regions involved?")
    assert checks.cue_preserved("whether", "Do the regions differ by depth?") and checks.cue_preserved(
        "whether", "Ask if regions differ."
    )
    assert not checks.cue_preserved("how", "What is the effect of depth?") and checks.cue_preserved(
        "how", "How does depth matter?"
    )


def test_gate_refuses_protected_requests_without_a_matching_authorization(tmp_path):
    from experiments.ask_cli_revised.e2e_contracts import E2E_QUESTIONS

    protected = E2E_QUESTIONS["builtenv"]
    gate.check(E2E_QUESTIONS["aib"])  # the development target is not protected
    gate.check(Q)
    with pytest.raises(gate.GateRefused):
        gate.check(protected)
    digest = hashlib.sha256(protected.encode("utf-8")).hexdigest()
    for name, body in (
        (
            "wrong",
            {"brief_confirmed": True, "experiment_id": "x", "authorized_by": "Cliff", "question_sha256s": ["0" * 64]},
        ),
        (
            "nobrief",
            {"brief_confirmed": False, "experiment_id": "x", "authorized_by": "Cliff", "question_sha256s": [digest]},
        ),
    ):
        f = tmp_path / f"{name}.json"
        f.write_text(json.dumps(body), encoding="utf-8")
        with pytest.raises(gate.GateRefused):
            gate.check(protected, str(f))
    ok = tmp_path / "ok.json"
    ok.write_text(
        json.dumps(
            {"brief_confirmed": True, "experiment_id": "x", "authorized_by": "Cliff", "question_sha256s": [digest]}
        ),
        encoding="utf-8",
    )
    gate.check(protected, str(ok))


# ---- bundling, unit-level anchors, and robustness on a real-length request ------------------------------------------------


def test_a_child_that_asks_two_separate_relationships_is_flagged_as_bundling():
    both = {
        "question": "Do the specific reef zones relate to depth, and which specific pigments relate to the expression of the coral effect?"
    }
    result, _ = run({"whether and how": both}, repair=False)
    kid = next(c for c in result["pass1"]["children"] if c["question"] == both["question"])
    assert kid["diagnostics"]["possible_bundling_of_other_obligations"]
    assert kid["child_id"] in result["pass1"]["reconciliation"]["summary"]["bundled_children"]
    assert kid["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]


def test_a_unit_with_no_obligations_gets_a_unit_level_child_that_is_unresolved_not_a_success():
    result, _ = run(fail={"unit", "whole"}, repair=False)
    kids = result["pass1"]["children"]
    assert kids and all(
        c["kind"] == "unit_level" and c["status"] == "unit_level_unresolved" and c["is_decomposition"] is False
        for c in kids
    )
    assert result["pass1"]["reconciliation"]["summary"]["successful_children"] == []


def test_the_engine_survives_a_real_length_request_when_the_model_fails_everywhere():
    from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

    result = run_engine(BENCHMARK_QUESTION, ScriptedModel(lambda prompt, schema: None), repair=True, max_calls=40)
    assert result["pass1"]["verified_traceability"]["ok"]
    assert all(c["kind"] in ("fallback", "unit_level") for c in result["pass1"]["children"])
    assert result["pass1"]["reconciliation"]["summary"]["successful_children"] == []


def test_every_model_call_is_persisted_as_it_is_made_even_if_the_run_crashes(tmp_path):
    inner = responder()
    state = {"n": 0}

    def crashing(prompt, schema):
        state["n"] += 1
        if state["n"] == 6:
            raise RuntimeError("boom")
        return inner(prompt, schema)

    sink = tmp_path / "calls.jsonl"
    with pytest.raises(RuntimeError):
        run_engine(Q, ScriptedModel(crashing), call_sink=sink)
    lines = [json.loads(line) for line in sink.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 5 and all(r["prompt"] and "raw_output" in r for r in lines)


# ---- defects found on the first obligation-driven q_aib run (deterministic fixes, model-free proof) -------------------------


def test_a_whole_pass_compound_inside_one_unit_is_absorbed_by_finer_obligations_not_merged_into_them(monkeypatch):
    me = sys.modules[__name__]

    compound = {
        "kind": "relationship",
        "quotes": ["whether and how they relate to depth", "which kinds of depth", "specific reef zones"],
        "note": "bundles three asks",
    }
    monkeypatch.setattr(me, "WHOLE", [compound])
    parent = build_parent_contract(CallLog(ScriptedModel(responder())), Q)
    whole = next(r for r in parent["requirements"] if r["origin"] == "model_whole" and r["kind"] == "relationship")
    assert whole["superseded"] and whole["status"] == "covered_by_finer_obligations" and whole["superseded_by"]
    unit_rel = next(
        r
        for r in parent["requirements"]
        if r["origin"] == "model_unit" and r["kind"] == "relationship" and "whether and how" in r["text"]
    )
    assert len(unit_rel["spans"]) == 1 and not unit_rel.get("merged_from")  # not unioned into a compound
    assert parent["post_processing"]["absorbed_whole_pass"][0]["id"] == whole["id"]
    assert whole["id"] not in {p["anchor_id"] for p in plan_children(parent)}  # and it produces no child


def test_a_dependent_is_never_attached_across_units_and_its_unit_becomes_unit_level_unresolved(monkeypatch):
    me = sys.modules[__name__]

    monkeypatch.setitem(
        me.UNIT_OBLIGATIONS, "is there any", [{"kind": "population", "quotes": ["in juveniles"], "note": ""}]
    )
    result, _ = run(repair=False)
    by = {r["id"]: r for r in result["parent_contract"]["requirements"]}
    pop = next(r for r in by.values() if r["kind"] == "population" and r["text"] == "in juveniles")
    assert pop["part_of"] == "P-u3" and pop["attach_basis"] == "unit_floor"
    u3 = next(c for c in result["pass1"]["children"] if c["origin"]["anchor_id"] == "P-u3")
    assert u3["kind"] == "unit_level" and u3["status"] == "unit_level_unresolved" and pop["id"] in u3["owns"]
    assert u3["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]
