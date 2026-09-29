"""Model-free proof of the source-edit ledger and the source-preserving writer rules. Synthetic requests only.

The ledger is an AUDIT of detected source-edit problems, never proof of provenance or fidelity; these tests pin what it
detects (and that it says so), not that a clean ledger means a faithful question."""

from __future__ import annotations

import pytest

import experiments.ask_cli_revised.decompose.test_decompose as base
from experiments.ask_cli_revised.decompose import checks, ledger, relations
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ScriptedModel
from experiments.ask_cli_revised.decompose.test_relations import CLAR, Q

CLAR_ZONES = CLAR  # "they" = the specific reef zones, so the reference is settled

CHILD = {"growth": "How does the coral effect show up in growth?"}


def _child(result, needle):
    return next(c for c in result["pass1"]["children"] if needle in c["question"])


def _flags(child):
    return {f["kind"] for f in child["edit_ledger"]["flags"] if f["class"] != "info"}


def _ops(child, op):
    return [o for o in child["edit_ledger"]["ops"] if o["op"] == op]


# ---- a clean coordinate split is copy + remove siblings + punctuation ----------------------------------------------------------------


def test_a_coordinate_split_copies_the_shared_wording_and_records_the_sibling_words_it_left_out():
    result, _ = base.run(repair=False)
    kid = _child(result, "growth")
    led = kid["edit_ledger"]
    assert led["status"] == "no_detected_problem" and kid["status"] == "candidate"
    assert "not proof" in led["audit_note"] and "does not certify" in led["audit_note"]
    copied = _ops(kid, "copied")
    assert copied[0]["text"].lower().startswith("how does the coral effect show up in growth")
    assert copied[0]["source_spans"] and copied[0]["attribution"] == "recorded_span"
    removed = {o["text"]: o["nodes"] for o in _ops(kid, "sibling_removed")}
    assert {"color", "survival"} <= set(removed) and removed["color"] != removed[
        "survival"
    ]  # each names its own question
    assert {o["kind"] for o in _ops(kid, "grammatical")} == {"capitalization", "terminal_punctuation"}
    # every recorded span of the audit is a real slice of the request
    assert all(Q[lo:hi] for lo, hi in led["source_spans_carried"])


def test_changing_or_breaking_the_shared_wording_of_a_split_is_reported_not_accepted():
    for wording in ("How does the coral effect relate to growth?", "How does the coral effect show growth?"):
        result, _ = base.run({"growth": {"question": wording}}, repair=False)
        kid = _child(result, "growth")
        assert "shared_wording_changed" in _flags(kid), wording
        assert (
            kid["status"] != "candidate"
            and kid["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]
        )
    swapped, _ = base.run({"growth": {"question": "How does the coral effect relate to growth?"}}, repair=False)
    # "relate" is another question's word here (borrowed from a sibling); a word in no span at all is an unsupported substitution
    assert _flags(_child(swapped, "relate to growth")) & {"borrowed_from_other_thread", "unsupported_substitution"}
    invented, _ = base.run({"growth": {"question": "How does the coral effect amplify growth?"}}, repair=False)
    assert "unsupported_substitution" in _flags(_child(invented, "amplify growth"))


# ---- protected small words -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "wording", "kind", "word"),
    [
        ("is there any", "Is there evidence for the effect in juveniles?", "operator_dropped", "any"),
        ("is there any", "Is there not any evidence for the effect in juveniles?", "operator_added", "not"),
        ("is there any", "Is there any effective evidence for the effect in juveniles?", "operator_added", "effective"),
        ("is there any", "Which evidence is there for the effect in juveniles?", "operator_added", "which"),
        ("specific reef zones", "Please return specific reef zones.", None, None),
    ],
)
def test_words_that_are_the_requested_operation_can_be_neither_dropped_nor_added(key, wording, kind, word):
    result, _ = base.run({key: {"question": wording}}, repair=False)
    kid = _child(result, wording[:25])
    ops = [o for o in _ops(kid, "operation_change")]
    if kind is None:
        assert not ops and "operator_dropped" not in _flags(kid)
        return
    assert any(o["kind"] == kind and o["text"].lower() == word for o in ops), (wording, ops)
    assert kid["status"] == "semantic_conflict" and kid["diagnostics"]["hard_fail"]
    assert kid["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]
    if word == "not":
        assert next(o for o in ops if o["text"] == "not")["negation"] is True  # negation is told apart


def test_a_whether_kept_as_written_is_clean_recast_as_a_yes_no_question_is_a_form_change_and_whether_to_what_is_a_conflict():
    result, _ = base.run(repair=False)
    kid = _child(result, "Whether and how")
    assert not _ops(kid, "request_form_change") and not _ops(kid, "operation_change")
    assert "request_form_changed" not in _flags(kid)  # (its unresolved "they" is a separate, declared matter)
    recast = "Do the specific reef zones relate to depth, and if so how, which kinds of depth"
    form, _ = base.run({"whether and how": {"question": recast}}, repair=False, clarifications=[CLAR_ZONES])
    kid1 = _child(form, "Do the specific")
    assert "request_form_changed" in _flags(kid1) and "whether_recast" in kid1["edit_ledger"]["flags"][0]["words"]
    assert (
        kid1["status"] == "semantic_review_required" and not kid1["diagnostics"]["hard_fail"]
    )  # reported, not a conflict
    assert not [
        o for o in _ops(kid1, "operation_change")
    ]  # the operation (whether AND how) is intact; only the FORM moved
    swapped = "What do the specific reef zones relate to depth, and how, which kinds of depth?"
    bad, _ = base.run({"whether and how": {"question": swapped}}, repair=False)
    kid2 = _child(bad, "What do the specific")
    kinds = {(o["kind"], o["text"].lower()) for o in _ops(kid2, "operation_change")}
    assert ("operator_added", "what") in kinds and ("operator_dropped", "whether") in kinds
    assert kid2["status"] == "semantic_conflict"


def test_the_extract_keeps_the_researchers_own_operation_words_but_never_a_conjunction_or_anothers_words():
    _, model = base.run(repair=False)
    item = next(
        c["prompt"]
        for c in model.calls
        if '"specific reef zones" (chars' in c["prompt"] and "Relationship to ask" not in c["prompt"]
    )
    extract = item.split("Source extract", 1)[1].split("\n\n", 1)[0]
    assert '"please return specific reef zones"' in extract
    rel = next(
        c["prompt"]
        for c in model.calls
        if "Relationship to ask about" in c["prompt"] and "whether and how they relate" in c["prompt"]
    )
    rel_extract = rel.split("Source extract", 1)[1].split("\n\n", 1)[0]
    assert (
        "please return" not in rel_extract and "specific reef zones" not in rel_extract
    )  # another question's words, and a conjunction
    assert "minimal EXTRACTION, not a rewrite" in rel and "Do not add a connecting word" in rel
    assert "for/of/about" not in rel and "neutral joiner" not in rel.lower()  # nothing is a universally safe connective


# ---- context: restored by copying, connected only by supported wording -----------------------------------------------------------------

Q4 = "how does coral bleaching spread across reefs? please return specific reef zones."


def _respond4(wording: str):
    def respond(prompt: str, schema: dict):
        props = schema["properties"]
        if "requirements" in props:
            part = prompt.split("Part to read:\n", 1)[1] if "Part to read:\n" in prompt else ""
            if part.startswith("how does"):
                return {"requirements": [{"kind": "manner", "quotes": ["how"], "note": ""}]}
            if part.startswith("please return"):
                return {"requirements": [{"kind": "requested_item", "quotes": ["specific reef zones"], "note": ""}]}
            return {"requirements": []}
        if "ambiguities" in props:
            return {"ambiguities": []}
        return {"question": wording.replace("{S}", _respond4.subject), "unresolved": []}

    return respond


def _run4(wording: str):
    from experiments.ask_cli_revised.decompose.calllog import CallLog
    from experiments.ask_cli_revised.decompose.parent import build_parent_contract

    parent = build_parent_contract(CallLog(ScriptedModel(_respond4("x"))), Q4)
    _respond4.subject = parent["referents"][0]["text"]
    result = run_engine(Q4, ScriptedModel(_respond4(wording)), repair=False)
    return next(c for c in result["pass1"]["children"] if c["kind"] == "generated"), _respond4.subject


def test_restored_context_is_copied_and_a_connection_is_never_invented():
    kid, subject = _run4("Please return specific reef zones, {S}?")
    assert subject and _ops(kid, "context_carried") and _ops(kid, "context_carried")[0]["source_spans"]
    assert "context_link_unstated" in _flags(
        kid
    )  # placed next to the item with no connecting word: reported, not chosen
    assert any(
        u["kind"] == "item_subject_link_unstated" and u["status"] == "unresolved"
        for u in kid["interpretations"] + [{**u, "status": "unresolved"} for u in kid["unresolved_links"]]
    )
    invented, _ = _run4("Please return specific reef zones involved in {S}?")
    assert {"link_introduced", "unsupported_substitution", "relation_word_added"} <= _flags(invented)
    for connective in ("for", "of", "about", "in", "with"):  # no connecting word is universally neutral
        kid2, _ = _run4(f"Please return specific reef zones {connective} {{S}}?")
        assert "link_introduced" in _flags(kid2) or "relation_word_added" in _flags(kid2), connective
    bare, _ = _run4("Please return specific reef zones.")
    # nothing approved says how the item relates to its subject: a finding about the REQUEST (source_gap), not a writer failure
    assert "context_missing" in _flags(bare) and bare["status"] == "source_gap" and not bare["diagnostics"]["hard_fail"]


# ---- clarified wording is labelled and kept apart from the source ------------------------------------------------------------------------


def test_a_clarification_can_add_how_to_a_contract_without_pretending_it_was_in_the_source():
    plain, _ = base.run(repair=False)
    pig = _child(plain, "pigments")
    assert pig["relation_contract"]["manner"] == {
        "requested": False,
        "text": None,
        "spans": [],
        "basis": None,
        "clarification": None,
    }
    lo = Q.index("relate to its expression")
    rc = {
        "id": "RC-A",
        "span": [lo, lo + len("relate to its expression")],
        "phrase": "relate to its expression",
        "means": "how they relate, including whether the association is positive or negative",
        "adds": ["manner"],
        "authorized_by": "tester",
    }
    result, _ = base.run(
        {"pigments": {"question": "What kind of specific pigments relate to its expression, how?"}},
        repair=False,
        clarifications=[rc],
    )
    kid = _child(result, "pigments")
    contract = kid["relation_contract"]
    assert (
        contract["manner"]["requested"]
        and contract["manner"]["basis"] == "clarification"
        and contract["manner"]["clarification"] == "RC-A"
    )
    assert (
        contract["manner"]["text"] is None and contract["manner"]["spans"] == []
    )  # no source words: none are invented
    assert [(m["id"], m["basis"], m["adds"]) for m in contract["clarified_meanings"]] == [
        ("RC-A", "clarification", ["manner"])
    ]
    assert pig["relation_contract"]["clarified_meanings"] == []  # an original-only run claims none of it as explicit
    assert "added by the user's clarification RC-A; not in the source words" in relations.render(contract)
    supplied = [o for o in _ops(kid, "clarification_supplied") if o["text"].lower() == "how"]
    assert supplied and supplied[0]["clarification"] == ["RC-A"]
    assert not [o for o in _ops(kid, "operation_change") if o["text"].lower() == "how"]
    lacking = relations.conformance(contract, "What kind of specific pigments relate to its expression?")
    assert [v["kind"] for v in lacking["violations"]] == ["operation_changed"] and "RC-A" in lacking["violations"][0][
        "note"
    ]
    # an incidental operator word in the clarification's prose does not license adding it
    negated, _ = base.run(
        {"pigments": {"question": "What kind of specific pigments relate to its expression, and not how?"}},
        repair=False,
        clarifications=[{**rc, "means": rc["means"] + " It does not presuppose an association."}],
    )
    assert {"operator_added"} <= {f["kind"] for f in _child(negated, "pigments")["edit_ledger"]["flags"]}
    with pytest.raises(Exception, match="adds"):
        base.run(repair=False, clarifications=[{**rc, "adds": ["scope"]}])


# ---- audit, not proof --------------------------------------------------------------------------------------------------------------


def test_a_match_that_could_come_from_several_places_is_marked_uncertain_and_lists_its_alternatives():
    a = {
        "kind": "extract",
        "priority": 0,
        "label": "extract",
        "tokens": [("go", 0, 2), ("in", 3, 5)],
        "roles": ["owned", "owned"],
    }
    b = {
        "kind": "inherited",
        "priority": 1,
        "label": "inherited x",
        "tokens": [("in", 10, 12), ("it", 13, 15)],
        "roles": ["inherited"] * 2,
    }
    segments, used_c, _ = ledger._tile([("go", 0, 2), ("in", 3, 5)], [a, b])
    assert used_c == [0, 0] and not segments[0]["alternatives"]  # a two-word run found in ONE piece is not ambiguous
    segments, used_c, _ = ledger._tile([("in", 0, 2)], [a, b])
    assert segments[0]["uncertain"] and segments[0]["alternatives"][0]["piece"] in ("inherited x", "extract")
    result, _ = base.run(repair=False)
    for c in result["pass1"]["children"]:
        if c.get("edit_ledger"):
            assert c["edit_ledger"]["status"] in ("no_detected_problem", "problems_detected")  # never "verified"


def test_a_repair_may_not_trade_one_departure_from_the_researchers_wording_for_another():
    blank = {
        "lost": [],
        "unsupported_additions": [],
        "deixis": [],
        "possible_bundling_of_other_obligations": [],
        "assumed_readings": [],
        "silent_resolution": [],
        "hard_fail": False,
        "preservation": {},
        "relation": None,
        "identity_introduced": False,
    }

    def edits(*findings):
        kinds = sorted({f.split(":")[0] for f in findings})
        return {"conflict": [], "review": kinds, "notes": [], "findings": list(findings)}

    before = {
        **blank,
        "source_edit": edits("unsupported_substitution:involved", "relation_word_added:in"),
    }
    worse = {
        **blank,
        "source_edit": edits("unsupported_substitution:involved", "relation_word_added:in", "link_introduced:are"),
    }
    partial = {
        **blank,
        "source_edit": edits("relation_word_added:in"),
    }  # "involved" dropped, but the added "in" remains
    better = {**blank, "source_edit": edits()}
    ok, why = checks.repair_acceptable(before, worse)
    assert ok is False and "link_introduced:are" in why
    ok, why = checks.repair_acceptable(
        before, partial
    )  # removing SOME departures while another remains is not an improvement
    assert ok is False and "relation_word_added:in" in why  # the remaining departure is named
    lexical = {**partial, "unsupported_additions": []}
    lexical_before = {**before, "unsupported_additions": ["involved"]}
    ok, why = checks.repair_acceptable(
        lexical_before, lexical
    )  # fixes a lexical flag, but a departure remains: not certified
    assert ok is False and "still departs" in why
    gap = {**blank, "source_edit": edits("context_missing:subject")}
    assert (
        checks.repair_acceptable({**gap, "lost": ["X"]}, gap)[0] is True
    )  # a GAP that was already there is not a departure
    swapped = {**blank, "source_edit": edits("unsupported_substitution:are", "relation_word_added:in")}
    assert checks.repair_acceptable(before, swapped)[0] is False  # one unsupported word traded for another
    assert checks.repair_acceptable(before, better)[0] is True
    assert "source_edit:link_introduced" in checks.repair_reasons(
        {**worse, "copies_of_source_text": [], "bundled_list": [], "at_schema_length_limit": False}
    )


def test_an_imperative_recast_as_a_question_is_a_review_never_a_conflict_and_a_wh_to_polar_change_stays_a_conflict():
    result, _ = base.run({"specific reef zones": {"question": "Which specific reef zones?"}}, repair=False)
    kid = _child(result, "Which specific")
    assert "request_form_changed" in _flags(kid) and "operator_added" not in _flags(kid)
    assert "imperative_to_question" in kid["edit_ledger"]["flags"][0]["words"]
    assert kid["status"] == "semantic_review_required" and not kid["diagnostics"]["hard_fail"]
    kinds = {o["kind"] for o in _ops(kid, "request_form_change")}
    assert "imperative_recast_as_question" in kinds  # neither harmless nor a conflict: named, so the researcher decides
    bad, _ = base.run(
        {"specific pigments": {"question": "Do specific pigments relate to its expression?"}}, repair=False
    )
    kid2 = _child(bad, "Do specific pigments")
    assert {"operator_dropped"} <= _flags(kid2) and kid2["status"] == "semantic_conflict"  # wh dropped: not a recast


def test_a_harmless_word_is_never_credited_to_a_clarification_whose_prose_happens_to_contain_it():
    lo = Q.index("relate to its expression")
    rc = {
        "id": "RC-D",
        "span": [lo, lo + len("relate to its expression")],
        "phrase": "relate to its expression",
        "means": "does the association hold, including the article the writer might add",
        "authorized_by": "tester",
    }
    result, _ = base.run(
        {"pigments": {"question": "Do the specific pigments relate to its expression?"}},
        repair=False,
        clarifications=[rc],
    )
    kid = _child(result, "the specific pigments")
    assert not [o for o in _ops(kid, "clarification_supplied") if o["text"].lower() in ("do", "the")]
    assert {"article", "auxiliary"} <= {o["kind"] for o in _ops(kid, "grammatical")}


def test_a_leading_context_clause_does_not_hide_the_question_form_or_the_subject_of_a_relationship():
    parsed = relations.parse_question(
        "In the context of the coral effect, whether and how specific reef zones relate to depth, which kinds of depth?"
    )
    assert parsed["form"] == "polar" and parsed["subject_text"].endswith("specific reef zones")
    assert parsed["target_text"] == "depth" and parsed["family"] == "association"
    assert relations.parse_question("What kind of specific pigments relate to its expression?")["form"] == "wh"
    assert relations.parse_question("Do the pigments relate to depth, and if so how?")["form"] == "polar"
    # a wording that keeps the researcher's words, context restored, and the contract's whether is a candidate, not a conflict
    contract = relations.build_contract(
        _rebuilt_parent(), next(r for r in _rebuilt_parent()["requirements"] if r["kind"] == "relationship")
    )
    ok = relations.conformance(
        contract, "In the context of the coral effect, whether and how they relate to depth, which kinds of depth?"
    )
    assert "operation_changed" not in {v["kind"] for v in ok["violations"]}


def _rebuilt_parent():
    from experiments.ask_cli_revised.decompose.calllog import CallLog
    from experiments.ask_cli_revised.decompose.parent import build_parent_contract

    return build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
