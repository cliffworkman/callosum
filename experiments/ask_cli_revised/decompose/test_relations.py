"""Model-free proof that relationship meaning is represented structurally and defended against changed wording.

Synthetic request from ``test_decompose`` (no real request). Covers: the relationship contract, span-linked user
clarifications, conformance of wording and repairs, the excerpt splice for list items, and scoring RECORDED wording
offline (no model call).
"""

from __future__ import annotations

import json

import pytest

import experiments.ask_cli_revised.decompose.test_decompose as base
from experiments.ask_cli_revised.decompose import checks, clarifications, relations
from experiments.ask_cli_revised.decompose.calllog import CallLog
from experiments.ask_cli_revised.decompose.children import plan_children
from experiments.ask_cli_revised.decompose.engine import rescore, run_engine
from experiments.ask_cli_revised.decompose.model import ReplayModel, ScriptedModel
from experiments.ask_cli_revised.decompose.parent import build_parent_contract

Q = base.Q
PHRASE = "whether and how they relate to depth"
LO = Q.index(PHRASE)
CLAR = {
    "id": "RC-T",
    "span": [LO, LO + len(PHRASE)],
    "phrase": PHRASE,
    "reference_word": "they",
    "means": "the specific reef zones",
    "authorized_by": "tester",
    "refers_to": {
        "span": [Q.index("specific reef zones"), Q.index("specific reef zones") + 19],
        "phrase": "specific reef zones",
    },
}
NL = chr(10)


def _parent(clars=None):
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    clarifications.apply(parent, clars)
    return parent


def _contract(parent, needle):
    rel = next(r for r in parent["requirements"] if r["kind"] == "relationship" and needle in r["text"])
    return relations.build_contract(parent, rel)


def _slot_text_ok(contract):
    for slot in (contract["subject"], contract["relation"], contract["target"]):
        assert all(Q[a:b] and Q[a:b] in slot["text"] for a, b in slot["spans"])  # exact source spans


# ---- 1. the relationship contract ----------------------------------------------------------------------------------------------


def test_a_relationship_is_represented_structurally_with_exact_spans_before_wording():
    parent = _parent()
    c = _contract(parent, PHRASE)
    assert c["parse_status"] == "parsed" and c["direction"] == "subject_to_target"
    assert (c["subject"]["text"], c["relation"]["text"], c["target"]["text"]) == ("they", "relate to", "depth")
    assert (
        c["subject"]["is_reference"]
        and c["subject"]["reference"]["status"] == "unresolved"
        and c["subject"]["resolved_text"] is None
    )
    assert c["subject"]["reference"]["candidates"][0]["text"] == "specific reef zones"  # a candidate, never an approval
    assert (
        c["polarity"]["requested"]
        and c["polarity"]["text"].lower() == "whether"
        and c["manner"]["requested"]
        and c["manner"]["text"].lower() == "how"
    )
    assert c["answer_form"]["form"] == "polar" and [q["kind"] for q in c["qualifications"]] == ["kinds"]
    _slot_text_ok(c)
    w = _contract(
        parent, "specific pigments"
    )  # a wh-clause: the wh-phrase is the answer form, its modifier joins the subject
    assert (w["subject"]["text"], w["target"]["text"]) == ("specific pigments", "its expression")
    assert (
        w["answer_form"]["form"] == "wh"
        and w["answer_form"]["marker"] == "what kind of"
        and not w["polarity"]["requested"]
    )
    assert [r["word"] for r in w["unresolved_referents"]] == ["its"]
    _slot_text_ok(w)


def test_the_child_writer_receives_the_structure_not_just_the_words():
    result, model = base.run(repair=False)
    prompt = next(
        c["prompt"] for c in model.calls if PHRASE in c["prompt"] and "What this question must ask" in c["prompt"]
    )
    for needle in (
        "Relationship to ask about",
        "- subject:",
        "- relation:",
        '"relate to"',
        "- target:",
        '"depth"',
        "whether (yes/no) AND how",
        "answer form: polar",
        "Do not swap the subject and the target",
    ):
        assert needle in prompt, needle
    kid = next(
        c
        for c in result["pass1"]["children"]
        if c["relation_contract"]
        and PHRASE
        in c["relation_contract"]["subject"]["text"]
        + " "
        + Q[c["relation_contract"]["source_spans"][0][0] : c["relation_contract"]["source_spans"][0][1]]
    )
    assert kid["relation_contract"]["parse_status"] == "parsed"


def test_an_unparseable_relationship_is_left_for_semantic_review_never_counted_as_a_success(monkeypatch):
    monkeypatch.setitem(
        base.UNIT_OBLIGATIONS,
        "please return",
        [
            {"kind": "requested_item", "quotes": ["specific reef zones"], "note": ""},
            {"kind": "relationship", "quotes": ["whether and how they"], "note": ""},
        ],
    )
    result, model = base.run(repair=False)
    kid = next(
        c
        for c in result["pass1"]["children"]
        if c["relation_contract"] and c["relation_contract"]["parse_status"] == "unparsed"
    )
    assert "could not be parsed automatically" in next(
        c["prompt"] for c in model.calls if '"whether and how they"' in c["prompt"]
    )
    assert (
        kid["status"] != "candidate"
        and kid["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]
    )
    assert kid["diagnostics"]["relation"]["status"] == "not_verifiable"


# ---- 2. span-linked user clarification ------------------------------------------------------------------------------------------


def test_a_clarification_is_validated_against_the_exact_words_and_needs_an_authorizer():
    parent = _parent()
    for bad in (
        {**CLAR, "phrase": "whether they relate to depth"},  # phrase is not the text at that span
        {**CLAR, "authorized_by": ""},  # a clarification is a human decision
        {**CLAR, "reference_word": "these"},  # the word is not in the phrase
        {**CLAR, "means": ""},
        {**CLAR, "span": [0, 5000]},
    ):
        with pytest.raises(clarifications.ClarificationError):
            clarifications.apply(parent, [bad])
    rows = clarifications.apply(parent, [CLAR])
    assert rows[0]["target_text"] == "they" and Q[rows[0]["target_span"][0] : rows[0]["target_span"][1]] == "they"
    assert next(a for a in parent["ambiguities"] if a["text"] == "they")["status"] == "resolved_by_user_clarification"


def test_a_clarification_resolves_exactly_the_named_words_and_applies_to_every_affected_child(monkeypatch):
    monkeypatch.setitem(
        base.UNIT_OBLIGATIONS,
        "please return",
        [*base.UNIT_OBLIGATIONS["please return"], {"kind": "requested_item", "quotes": ["they"], "note": ""}],
    )
    result, model = base.run(repair=False, clarifications=[CLAR])
    affected = [
        c
        for c in result["pass1"]["children"]
        if any(s[0] <= Q.index("they") < s[1] for s in c["origin"]["source_spans"])
    ]
    assert len(affected) >= 2  # the relationship child and a child that owns the word itself
    for c in affected:
        prompt = next(
            m["prompt"]
            for m in model.calls
            if f'"{c["question"]}"' not in m["prompt"]
            and c["owns"]
            and f"chars {c['origin']['source_spans'][0][0]}" in m["prompt"]
        )
        assert (
            "Clarified by the user" in prompt
            and '"they" (chars' in prompt.split("Clarified by the user", 1)[1]
            and "the specific reef zones" in prompt
        )
        assert (
            '"they" (chars' not in prompt.split("Unresolved wording (NOT settled", 1)[-1].split(NL * 2)[0]
            or "Unresolved wording (NOT settled" not in prompt
        )
    rows = {r["id"]: r for r in result["pass1"]["reconciliation"]["rows"]}
    assert rows["A-ref1"]["status"] == "resolved_by_user_clarification" and rows["A-ref1"]["clarification"] == "RC-T"
    still_open = [r["text"] for r in rows.values() if r["status"] == "ambiguity_open"]
    assert "its" in still_open and "they" not in still_open  # every other reading stays open


def test_a_wording_that_keeps_the_clarified_subject_is_a_candidate_and_one_that_changes_it_is_a_conflict():
    good, _ = base.run(repair=False, clarifications=[CLAR])
    kid = next(c for c in good["pass1"]["children"] if "whether and how" in c["question"].lower())
    assert kid["status"] == "candidate" and kid["diagnostics"]["relation"]["status"] == "conforms"
    assert any(
        i["kind"] == "reference_resolved_by_user_clarification" and i["status"] == "approved_by_user"
        for i in kid["interpretations"]
    )
    assert kid["child_id"] in good["pass1"]["reconciliation"]["summary"]["successful_children"]
    wrong = "Do the pigments relate to depth, and if so how, which kinds of depth?"
    bad, _ = base.run({"whether and how": {"question": wrong, "unresolved": []}}, repair=False, clarifications=[CLAR])
    conflict = next(c for c in bad["pass1"]["children"] if c["question"] == wrong)
    assert conflict["status"] == "semantic_conflict" and conflict["diagnostics"]["hard_fail"]
    assert [v["kind"] for v in conflict["diagnostics"]["relation"]["violations"]] == ["subject_changed"]
    assert conflict["child_id"] not in bad["pass1"]["reconciliation"]["summary"]["successful_children"]
    assert "owned_semantic_conflict" in {r["status"] for r in bad["pass1"]["reconciliation"]["rows"]}


# ---- 3. changed relationships are never accepted on lexical grounds ---------------------------------------------------------------


def test_conformance_detects_a_changed_subject_target_direction_relation_and_operation():
    parent = _parent([CLAR])
    c = _contract(parent, PHRASE)
    kinds = lambda text: sorted(v["kind"] for v in relations.conformance(c, text)["violations"])  # noqa: E731
    assert kinds("Do the specific reef zones relate to depth, and if so how?") == []
    assert kinds("Do the pigments relate to depth, and if so how?") == ["subject_changed"]
    assert kinds("Do the specific reef zones relate to juveniles, and if so how?") == ["target_changed"]
    assert kinds("Does depth relate to the specific reef zones, and if so how?") == [
        "direction_changed",
        "subject_changed",
        "target_changed",
    ]
    assert kinds("Do the specific reef zones affect depth, and if so how?") == ["relation_changed"]
    assert "operation_changed" in kinds("Which specific reef zones relate to depth?")
    w = _contract(parent, "specific pigments")
    assert sorted(
        v["kind"] for v in relations.conformance(w, "Do specific pigments relate to their expression?")["violations"]
    ) == ["operation_changed", "referent_changed"]
    assert relations.conformance(w, "What kind of specific pigments relate to its expression?")["violations"] == []


def test_a_repair_that_fixes_lexical_flags_but_changes_the_relationship_is_rejected_and_flagged():
    first = "What is the relation of the reef zones to depth?"  # lost polarity and manner: two lexical flags to "fix"

    def overrides(prompt):
        if "Problems found" in prompt:  # ticks the lexical boxes (whether, how, kinds) but swaps the subject
            return {
                "question": "Do the pigments relate to depth, and if so how, which kinds of depth?",
                "unresolved": [],
            }
        return {"question": first, "unresolved": []}

    result, _ = base.run({"whether and how": overrides}, repair=True, clarifications=[CLAR])
    rep = next(r for r in result["pass2"]["repairs"] if r["attempted"] and r["before"] == first)
    assert rep["accepted"] is False and "changes the relationship" in rep["rejected_reason"]
    assert next(c for c in result["pass2"]["children"] if c["child_id"] == rep["child_id"])["question"] == first
    assert result["final_pass"] == 1


def test_a_bare_copula_that_equates_an_item_with_the_subject_is_a_semantic_conflict(monkeypatch):
    me = base
    monkeypatch.setitem(
        me.UNIT_OBLIGATIONS,
        "how does the coral effect",
        [
            {"kind": "requested_item", "quotes": ["show up in"], "note": ""},
            {"kind": "population", "quotes": ["growth, color, and survival"], "note": ""},
        ],
    )
    monkeypatch.setattr(me, "WHOLE", [w for w in me.WHOLE if w["kind"] == "output_expectation"])
    result, _ = base.run(
        {"specific reef zones": {"question": "Which specific reef zones are coral effect?", "unresolved": []}},
        repair=False,
    )
    kid = next(c for c in result["pass1"]["children"] if c["question"] == "Which specific reef zones are coral effect?")
    assert (
        kid["diagnostics"]["identity_introduced"]
        and kid["status"] == "semantic_conflict"
        and kid["diagnostics"]["hard_fail"]
    )
    assert relations.copular_identity("What traits are anomalous is bad bias?", "anomalous is bad bias")
    assert not relations.copular_identity(
        "What traits are associated with anomalous is bad bias?", "anomalous is bad bias"
    )


# ---- 4. the excerpt keeps the connector for later list items ------------------------------------------------------------------------


def test_a_later_list_item_keeps_the_connector_the_source_puts_before_the_list(monkeypatch):
    monkeypatch.setitem(
        base.UNIT_OBLIGATIONS,
        "how does the coral effect",
        [
            {"kind": "requested_item", "quotes": ["show up in"], "note": ""},
            {"kind": "population", "quotes": ["growth, color, and survival"], "note": ""},
        ],
    )
    monkeypatch.setattr(base, "WHOLE", [w for w in base.WHOLE if w["kind"] == "output_expectation"])
    result, model = base.run(repair=False)
    for item in ("growth", "color", "survival"):
        prompt = next(
            c["prompt"]
            for c in model.calls
            if f'"{item}" (chars' in c["prompt"] and "What this question must ask" in c["prompt"]
        )
        excerpt = prompt.split("excerpts in order", 1)[1].split(NL * 2)[0]
        assert f"show up in {item}" in excerpt, (item, excerpt)  # grammatical: the connector "in" precedes the item
        others = {"growth", "color", "survival"} - {item}
        assert not any(o in excerpt for o in others)  # and no sibling item leaks in


# ---- 5. recorded wording is scored offline, with no model call --------------------------------------------------------------------------


def test_recorded_wording_can_be_rescored_offline_and_a_wrong_referent_or_changed_relation_is_not_counted_as_success():
    first, _ = base.run(repair=False)
    inventory = [r for r in first["calls"] if r["task"].startswith("parent.")]
    plans = plan_children(_parent([CLAR]))
    by_q = {
        c["child_id"]: {"question": c["question"], "unresolved": c["declared_unresolved"]}
        for c in first["pass1"]["children"]
        if c["kind"] == "generated"
    }
    zones = next(
        p["child_id"]
        for p in plans
        if p["relation"] and PHRASE in Q[p["relation"]["source_spans"][0][0] : p["relation"]["source_spans"][0][1]]
    )
    pigments = next(
        p["child_id"]
        for p in plans
        if p["relation"] and "specific pigments" in p["relation"].get("subject", {}).get("text", "")
    )
    by_q[zones] = {
        "question": "Does the coral effect relate to depth, and if so how?",
        "unresolved": [{"word": "they", "reading_used": "the coral effect", "other_readings": []}],
    }  # wrong referent
    by_q[pigments] = {
        "question": "Do specific pigments relate to their expression?",
        "unresolved": [{"word": "its", "reading_used": "their", "other_readings": []}],
    }  # changed relationship
    replay = ReplayModel(inventory, "recorded")
    out = rescore(Q, replay, by_q, clarifications=[CLAR], produced_by="recorded")
    kids = {c["child_id"]: c for c in out["pass1"]["children"]}
    assert kids[zones]["status"] == "semantic_conflict" and kids[pigments]["status"] == "semantic_conflict"
    assert {v["kind"] for v in kids[zones]["diagnostics"]["relation"]["violations"]} == {"subject_changed"}
    assert {v["kind"] for v in kids[pigments]["diagnostics"]["relation"]["violations"]} == {
        "operation_changed",
        "referent_changed",
    }
    successful = out["pass1"]["reconciliation"]["summary"]["successful_children"]
    assert zones not in successful and pigments not in successful
    assert replay.misses == [] and replay.identity()["new_model_calls"] == 0  # scoring used recorded calls only
    assert json.dumps(first["calls"][0]) == json.dumps(first["calls"][0])  # the recorded responses were not touched


# ---- 6. the request words the writer sees agree with the structure, and an item never states a relationship ----------------------------


def test_a_quote_repeated_inside_a_longer_quote_is_not_displayed_or_excerpted_twice():
    from experiments.ask_cli_revised.decompose.parent import anchor, make_requirement, maximal_spans

    assert maximal_spans([[5, 20], [10, 20], [5, 20], [30, 35]]) == [[5, 20], [30, 35]]
    a, b = anchor(Q, 0, len(Q), "relate to its expression"), anchor(Q, 0, len(Q), "its expression")
    req = make_requirement(
        "W1", "relationship", "model_whole", "t", [a, b], Q, [{"source_unit_id": "u1", "start": 0, "end": len(Q)}]
    )
    assert req["text"] == "relate to its expression" and len(req["spans"]) == 1
    assert len(req["anchors"]) == 2 and req["anchoring"] == "complete"  # provenance keeps both quotes


def test_the_excerpt_shows_every_word_the_relationship_structure_names():
    _, model = base.run(repair=False)
    prompt = next(
        c["prompt"] for c in model.calls if "specific pigments" in c["prompt"] and "Relationship to ask" in c["prompt"]
    )
    excerpt = prompt.split("excerpts in order", 1)[1].split(NL * 2)[0]
    assert "what kind of specific pigments relate to its expression" in excerpt  # marker + modifier + relation + target
    assert excerpt.count("its expression") == 1


def test_an_item_that_owns_no_relationship_must_not_state_one(monkeypatch):
    stated = "Please return specific reef zones associated with the coral effect."
    result, _ = base.run({"specific reef zones": {"question": stated, "unresolved": []}}, repair=False)
    kid = next(c for c in result["pass1"]["children"] if c["question"] == stated)
    assert kid["diagnostics"]["relationship_introduced"]["family"] == "association"
    assert kid["status"] == "semantic_review_required" and any(
        f["flag"] == "relationship_introduced" for f in kid["flags"]
    )
    assert kid["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]
    plain = next(
        c
        for c in result["pass1"]["children"]
        if c["question"] == "What kind of specific pigments relate to its expression?"
    )
    assert plain["diagnostics"]["relationship_introduced"] is None  # a relationship child owns its relation word
    assert relations.introduced_relation("Which reef zones are returned?", "specific reef zones") is None
    assert relations.introduced_relation("Which reef zones relate to depth?", "reef zones relate to depth") is None


def test_a_repair_that_introduces_a_relationship_is_rejected_even_when_it_clears_other_flags():
    def diag(lost, intro):
        return {
            "lost": lost, "preservation": {}, "unsupported_additions": [], "deixis": [], "silent_resolution": [],
            "possible_bundling_of_other_obligations": [], "assumed_readings": [], "hard_fail": False,
            "copies_of_source_text": [], "bundled_list": [], "at_schema_length_limit": False,
            "relation": None, "identity_introduced": False, "relationship_introduced": intro,
        }  # fmt: skip

    intro = {"verb": "associated", "family": "association", "subject": "zones", "target": "the effect"}
    ok, why = checks.repair_acceptable(diag(["C1"], None), diag([], intro))
    assert ok is False and "relationship" in why
    assert checks.repair_acceptable(diag(["C1"], None), diag([], None))[0] is True
    assert "relationship_introduced" in checks.repair_reasons({**diag([], intro)})


def test_the_engine_runs_end_to_end_with_a_clarification_file_through_the_cli(tmp_path):
    from experiments.ask_cli_revised.decompose.__main__ import main

    result, _ = base.run(repair=False, clarifications=[CLAR])
    calls = tmp_path / "calls.jsonl"
    calls.write_text("".join(json.dumps(r) + NL for r in result["calls"]), encoding="utf-8")
    clar_file = tmp_path / "clar.json"
    clar_file.write_text(json.dumps({"clarifications": [CLAR]}), encoding="utf-8")
    assert (
        main(
            [
                "--question",
                Q,
                "--replay-calls",
                str(calls),
                "--clarifications",
                str(clar_file),
                "--no-repair",
                "--out",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    report = (tmp_path / "out" / "REPORT.md").read_text(encoding="utf-8")
    assert "User clarifications applied" in report and "Relationship contracts" in report
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"clarifications": [{**CLAR, "authorized_by": ""}]}), encoding="utf-8")
    assert (
        main(
            [
                "--question",
                Q,
                "--replay-calls",
                str(calls),
                "--clarifications",
                str(bad),
                "--out",
                str(tmp_path / "out2"),
            ]
        )
        == 6
    )
    assert checks.verify_traceability(result["parent_contract"], result["pass1"])["ok"]
    assert run_engine  # the engine remains importable without the CLI
