"""Model-free proof of the question tree: nesting from approved clarifications, inherited obligations, dependencies kept
apart from nesting, joint answers, the closure roll-up, and folding of slot items. Synthetic requests only."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

import experiments.ask_cli_revised.decompose.test_decompose as base
from experiments.ask_cli_revised.decompose import clarifications, relations, tree
from experiments.ask_cli_revised.decompose.calllog import CallLog
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ScriptedModel
from experiments.ask_cli_revised.decompose.parent import build_parent_contract
from experiments.ask_cli_revised.decompose.test_relations import CLAR, Q


def _link(text: str, question: str = Q, nth: int = 0) -> dict:
    lo = -1
    for _ in range(nth + 1):
        lo = question.index(text, lo + 1)
    return {"span": [lo, lo + len(text)], "phrase": text}


ZONES = _link("specific reef zones")
CLAR_ZONES = {**CLAR, "refers_to": ZONES}

# a second synthetic request: an elliptical fragment and an anchorless unit, each about the first question's item
Q2 = "which specific pigments relate to shell color? and using which scales? which reefs and how was this measured?"
FRAGMENT = "and using which scales?"
UNIT = "which reefs and how was this measured?"


def _respond_q2(prompt: str, schema: dict):
    props = schema["properties"]
    if "requirements" in props:
        part = prompt.split("Part to read:\n", 1)[1] if "Part to read:\n" in prompt else ""
        if part.startswith("which specific pigments"):
            return {
                "requirements": [
                    {"kind": "requested_item", "quotes": ["specific pigments"], "note": ""},
                    {"kind": "relationship", "quotes": ["specific pigments relate to shell color"], "note": ""},
                ]
            }
        if part.startswith("and using"):
            return {"requirements": [{"kind": "requested_item", "quotes": ["scales"], "note": ""}]}
        return {"requirements": []}
    if "ambiguities" in props:
        return {"ambiguities": []}
    return {"question": "What is asked?", "unresolved": []}


CLAR_FRAGMENT = {
    "id": "RC-F",
    "span": [Q2.index(FRAGMENT), Q2.index(FRAGMENT) + len(FRAGMENT)],
    "phrase": FRAGMENT,
    "means": "the scales used to measure the pigments asked about just before",
    "authorized_by": "tester",
    "refers_to": _link("specific pigments", Q2),
    "pairs": [_link("specific pigments", Q2), _link("which scales", Q2)],
}
CLAR_UNIT = {
    "id": "RC-U",
    "span": [Q2.index(UNIT), Q2.index(UNIT) + len(UNIT)],
    "phrase": UNIT,
    "means": "which reefs were studied and, for each, how the color was measured",
    "authorized_by": "tester",
    "refers_to": _link("shell color", Q2),
    "pairs": [_link("which reefs", Q2), _link("how was this measured", Q2)],
}


def _run2(clars=None):
    model = ScriptedModel(_respond_q2)
    return run_engine(Q2, model, repair=False, clarifications=clars), model


# ---- clarification links are verified ---------------------------------------------------------------------------------------------


def test_a_clarification_link_must_quote_the_request_exactly():
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    bad = {**CLAR, "refers_to": {"span": ZONES["span"], "phrase": "specific reef areas"}}
    with pytest.raises(clarifications.ClarificationError, match="refers_to phrase does not equal"):
        clarifications.apply(parent, [bad])
    with pytest.raises(clarifications.ClarificationError, match="between two and six"):
        clarifications.apply(parent, [{**CLAR, "pairs": [ZONES]}])
    ok = clarifications.apply(parent, [CLAR_ZONES])[0]
    assert ok["kind"] == "reference" and ok["refers_to"]["text"] == "specific reef zones"


def test_a_meaning_clarification_resolves_no_ambiguity_by_itself_and_a_reference_one_resolves_only_its_word():
    parent = build_parent_contract(CallLog(ScriptedModel(_respond_q2)), Q2)
    before = [a["status"] for a in parent["ambiguities"]]
    clarifications.apply(parent, [CLAR_FRAGMENT, CLAR_UNIT])
    assert [c["kind"] for c in parent["clarifications"]] == ["meaning", "meaning"]
    assert [a["status"] for a in parent["ambiguities"]] == before
    p2 = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    clarifications.apply(p2, [CLAR_ZONES])
    resolved = [a for a in p2["ambiguities"] if a.get("clarification")]
    assert {a["text"].lower() for a in resolved} == {"they"} and all(a["clarification"] == "RC-T" for a in resolved)


def test_a_proposed_clarification_is_never_applied_as_if_the_user_had_approved_it():
    pending = {**CLAR_ZONES, "id": "RC-P", "authorized_by": "PENDING: derived by the engine author, not yet approved"}
    with pytest.raises(clarifications.ClarificationError, match="awaiting the user's approval"):
        base.run(repair=False, clarifications=[pending])
    result, _ = base.run(
        repair=False, clarifications=[pending], allow_pending_clarifications=True
    )  # a labelled what-if
    assert result["manifest"]["pending_clarifications"] == ["RC-P"]
    assert result["parent_contract"]["clarifications"][0]["status"] == "pending_user_approval"
    approved, _ = base.run(repair=False, clarifications=[CLAR_ZONES])
    assert approved["manifest"]["pending_clarifications"] == []


# ---- nesting and dependencies come only from an approved antecedent -----------------------------------------------------------------


def test_a_relationship_nests_under_the_question_that_owns_its_clarified_antecedent_and_not_before():
    result, _ = base.run(repair=False, clarifications=[CLAR_ZONES])
    nodes = {n["node_id"]: n for n in result["pass1"]["question_tree"]["nodes"]}
    rel = next(
        n
        for n in nodes.values()
        if any(o["kind"] == "relationship" and "whether and how" in o["text"] for o in n["own_obligations"])
    )
    item = nodes[rel["parent"]]
    assert item["parent"] == tree.ROOT and any(o["text"] == "specific reef zones" for o in item["own_obligations"])
    assert rel["depth"] == 2 and rel["nesting_basis"]["kind"] == "clarified_antecedent"
    assert {
        "node": item["node_id"],
        "kind": "antecedent_of_reference",
        "via": "RC-T",
        "basis": "user_clarification",
    }.items() <= {k: v for k, v in rel["depends_on"][0].items()}.items()
    assert any(i["from_node"] == item["node_id"] and i["role"] == "subject_antecedent" for i in rel["inherited"])
    assert item["subordinates"] == [rel["node_id"]]
    # the item keeps its OWN obligation: nothing about the relationship is owned by, or closed by, the item's question
    assert not any(o["kind"] == "relationship" for o in item["own_obligations"])
    # without the clarification the reference stays a candidate: no nesting, no dependency, only a listed candidate
    flat, _ = base.run(repair=False)
    frel = next(n for n in flat["pass1"]["question_tree"]["nodes"] if n["node_id"] == rel["node_id"])
    assert frel["parent"] == tree.ROOT and frel["depends_on"] == [] and frel["depth"] == 1
    assert any(
        c["basis"] == "unapproved_candidate" and c["candidate_node"] == item["node_id"]
        for c in frel["candidate_dependencies"]
    )


def test_the_writer_of_a_nested_question_is_told_what_it_inherits_and_not_to_ask_it_again():
    result, model = base.run(repair=False, clarifications=[CLAR_ZONES])
    prompt = next(
        c["prompt"]
        for c in model.calls
        if "whether and how they relate to depth" in c["prompt"] and "What this question must ask" in c["prompt"]
    )
    assert (
        'It points at the request words "specific reef zones"' in prompt
        or 'points at the request words "specific reef zones"' in prompt
    )
    assert "Inherited from a question that sits above this one" in prompt and "do NOT ask it again" in prompt
    top = next(
        c["prompt"]
        for c in model.calls
        if '"specific reef zones" (chars' in c["prompt"]
        and "Relationship to ask about" not in c["prompt"]
        and "What this question must ask" in c["prompt"]
    )
    assert "Inherited from a question that sits above" not in top  # the parent is told nothing about its subordinate


def test_depth_is_a_property_of_the_parent_pointers_not_a_fixed_two_levels_and_a_loop_is_cut():
    plans = [
        {"child_id": x, "node": {"parent": p}}
        for x, p in [("a", "R"), ("b", "a"), ("c", "b"), ("d", "c"), ("x", "y"), ("y", "x")]
    ]
    tree._depths(plans)
    depth = {p["child_id"]: p["node"]["depth"] for p in plans}
    assert [depth[k] for k in "abcd"] == [1, 2, 3, 4]
    assert {depth["x"], depth["y"]} <= {1, 2}  # the loop was cut at one link; every node has a finite depth
    assert any("note" in p["node"].get("nesting_basis", {}) for p in plans if p["child_id"] in ("x", "y"))


# ---- slot items are folded, fragments become writable only under a clarification, joint answers are recorded ----------------------------


def test_a_requested_item_that_is_the_subject_of_a_relationship_is_folded_into_it_and_keeps_its_id_in_the_record():
    result, _ = _run2(None)
    ids = [c["child_id"] for c in result["pass1"]["children"]]
    rel = next(c for c in result["pass1"]["children"] if c["relation_contract"])
    assert rel["folded"] and rel["folded"][0]["slot"] == "subject"
    folded_id = rel["folded"][0]["child_id"]
    assert folded_id not in ids and folded_id != rel["child_id"]  # the gap is the record: nothing was renumbered
    assert {p["role"] for p in rel["parent_links"] if p["requirement_id"] in rel["folded"][0]["owned"]} == {"slot_item"}
    node = next(n for n in result["pass1"]["question_tree"]["nodes"] if n["node_id"] == rel["child_id"])
    assert node["folded_from"][0]["child_id"] == folded_id


def test_a_fragment_is_written_only_when_the_user_said_what_it_asks_and_then_it_nests_under_its_antecedent():
    plain, plain_model = _run2(None)
    kinds = {c["origin"]["source_text"][:6]: c["kind"] for c in plain["pass1"]["children"]}
    assert "unresolved_elliptical" in kinds.values() and "unit_level" in kinds.values()
    assert not any(
        FRAGMENT in c["prompt"] or "scales" in c["prompt"]
        for c in plain_model.calls
        if "What this question must ask" in c["prompt"]
    )
    result, _ = _run2([CLAR_FRAGMENT, CLAR_UNIT])
    kids = result["pass1"]["children"]
    assert all(c["kind"] == "generated" for c in kids) and len(kids) == len(plain["pass1"]["children"])
    nodes = {n["node_id"]: n for n in result["pass1"]["question_tree"]["nodes"]}
    rel = next(c["child_id"] for c in kids if c["relation_contract"])
    frag = next(c for c in kids if c["clarified_fragment"] == "RC-F")
    unit = next(c for c in kids if c["clarified_fragment"] == "RC-U")
    assert (
        nodes[frag["child_id"]]["parent"] == rel
        and nodes[frag["child_id"]]["depends_on"][0]["kind"] == "fragment_target"
    )
    assert (
        nodes[unit["child_id"]]["parent"] != tree.ROOT
    )  # its antecedent ("shell color") is inside the relationship's words
    prompts = {c["unit_id"]: c["prompt"] for c in result["calls"] if "What this question must ask" in c["prompt"]}
    assert (
        "Clarified by the user" in prompts[frag["child_id"]]
        and "Inherited from a question that sits above" in prompts[frag["child_id"]]
    )
    assert "Paired answers (RC-U)" in prompts[unit["child_id"]]  # both halves of the pairing are in this one question
    assert (
        "Paired answers" not in prompts[frag["child_id"]]
    )  # only one half is: the tree, not this prompt, holds the pairing


def test_joint_answer_groups_name_their_member_nodes_and_stay_open_until_every_member_has_no_open_flag():
    result, _ = _run2([CLAR_FRAGMENT, CLAR_UNIT])
    qt = result["pass1"]["question_tree"]
    assert [g["id"] for g in qt["joint_answer_groups"]] == ["J-RC-F", "J-RC-U"]
    for g in qt["joint_answer_groups"]:
        assert all(m["node"] for m in g["members"]) and all(
            result["question"][m["span"][0] : m["span"][1]] == m["text"] for m in g["members"]
        )
    roll = result["pass1"]["reconciliation"]["question_tree"]
    ok = set(result["pass1"]["reconciliation"]["summary"]["successful_children"])
    for g in roll["joint_answer_groups"]:
        assert (g["status"] == "no_open_flag") == all(m["node"] in ok for m in g["members"])
    assert "independent lists" in roll["joint_answer_groups"][0]["rule"]


# ---- the roll-up: a subordinate never closes its parent, a parent never closes a subordinate --------------------------------------------


def test_reconciliation_rolls_up_without_letting_either_level_close_the_other():
    children = [{"child_id": "a", "status": "candidate"}, {"child_id": "b", "status": "semantic_conflict"}]
    nodes = [
        {"node_id": "a", "parent": "R", "depth": 1, "subordinates": ["b"], "depends_on": []},
        {
            "node_id": "b",
            "parent": "a",
            "depth": 2,
            "subordinates": [],
            "depends_on": [{"node": "a", "kind": "antecedent_of_reference"}],
        },
    ]
    tr = {"root": {"subordinates": ["a"]}, "nodes": nodes, "joint_answer_groups": [], "closure_rule": tree.CLOSURE_RULE}
    roll = tree.reconcile_tree(tr, children, {"successful_children": ["a"], "unresolved_count": 0})
    assert roll["nodes"]["a"]["own_open"] is False and roll["nodes"]["a"]["no_open_flag_in_subtree"] is False
    assert roll["nodes"]["a"]["subtree_open"] == ["b"] and roll["nodes"]["b"]["own_state"] == "semantic_conflict"
    assert roll["root"]["state"] == "open" and roll["root"]["open_nodes"] == ["b"]
    flipped = tree.reconcile_tree(tr, children, {"successful_children": ["b"], "unresolved_count": 0})
    assert (
        flipped["nodes"]["b"]["own_open"] is False and flipped["nodes"]["a"]["own_open"] is True
    )  # neither closes the other
    assert "Identifying an item and establishing its relationship" in roll["closure_rule"]


def test_the_tree_is_part_of_verified_traceability_and_a_tampered_tree_is_caught():
    result, _ = base.run(repair=False, clarifications=[CLAR_ZONES])
    doc = result["pass1"]
    assert doc["verified_traceability"]["ok"], doc["verified_traceability"]
    broken = copy.deepcopy(doc["question_tree"])
    broken["nodes"][0]["parent"] = "c99"
    broken["joint_answer_groups"] = [{"id": "J-x", "members": [{"span": [0, 3], "text": "zzz", "node": None}]}]
    problems = tree.verify(result["parent_contract"], broken)
    assert any("unknown parent" in p for p in problems) and any("do not match the request" in p for p in problems)


# ---- the relationship contract follows the approved antecedent ----------------------------------------------------------------------


def test_a_clarified_subject_and_a_clarified_target_referent_are_judged_against_the_words_they_point_at():
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    effect = _link("coral effect")
    its = {
        "id": "RC-I",
        "span": [
            Q.index("relate to its expression") + len("relate to "),
            Q.index("relate to its expression") + len("relate to its"),
        ],
        "phrase": "its",
        "reference_word": "its",
        "means": "the coral effect",
        "authorized_by": "tester",
        "refers_to": effect,
    }
    clarifications.apply(parent, [CLAR_ZONES, its])
    zones = next(r for r in parent["requirements"] if r["kind"] == "relationship" and "whether and how" in r["text"])
    contract = relations.build_contract(parent, zones)
    assert (
        contract["subject"]["resolved_text"] == "specific reef zones"
    )  # the exact words, not the paraphrase in "means"
    assert relations.conformance(contract, "Do the reef zones relate to depth, and if so how?")["status"] == "conforms"
    assert {
        v["kind"] for v in relations.conformance(contract, "Do pigments relate to depth, and if so how?")["violations"]
    } == {"subject_changed"}
    pig = next(r for r in parent["requirements"] if r["kind"] == "relationship" and "specific pigments" in r["text"])
    pc = relations.build_contract(parent, pig)
    assert pc["target"]["references"][0]["antecedent"]["text"] == "coral effect"
    assert (
        relations.conformance(pc, "What kind of specific pigments relate to the expression of the coral effect?")[
            "violations"
        ]
        == []
    )
    changed = relations.conformance(pc, "What kind of specific pigments relate to their expression?")
    assert [v["kind"] for v in changed["violations"]] == ["referent_changed"]


# ---- the held-out reference can never reach generation ------------------------------------------------------------------------------


def test_generation_code_never_reads_the_held_out_reference_or_hard_codes_a_real_request():
    root = Path(__file__).parent
    forbidden = ("intent_reference", "expected_evidence", "q_aib", "reference_correspondence", "anomalous")
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("test_") or path.name == "reference_compare.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not [w for w in forbidden if w in text], (path.name, [w for w in forbidden if w in text])
