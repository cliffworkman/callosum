"""Model-free proof of the closure pass: deterministic scaffolds for fragments, the recorded inflection edit, the structural checks and the execution
readiness that stop a `candidate` label from authorizing malformed wording, the raw-output record, and the no-split route.

Synthetic, unrelated requests only (pigments/scales, reefs/coral), except the tests marked as reading the preserved local v6/v7 artifacts, which skip
themselves when those are absent. No model is called and nothing is sent anywhere. A scripted test shows a decision PATH; it never shows what a real
inventory model will return.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

import experiments.ask_cli_revised.decompose.test_correction_pass as tcp
import experiments.ask_cli_revised.decompose.test_decompose as base
import experiments.ask_cli_revised.decompose.test_prepared as tp
from experiments.ask_cli_revised.decompose import execution, prepare, scaffold, structure, views
from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose import parent as pm
from experiments.ask_cli_revised.decompose.calllog import CallLog
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ReplayModel, ScriptedModel
from experiments.ask_cli_revised.decompose.parent import build_parent_contract

ROOT = Path(__file__).resolve().parents[3]
AIB = ROOT / ".local" / "decompose-runs" / "aib-dev"
DECOMPOSE = Path(__file__).resolve().parent


def _link(question: str, text: str) -> dict:
    lo = question.index(text)
    return {"span": [lo, lo + len(text)], "phrase": text}


def _approve(cid: str, word: str = "measure") -> list[dict]:
    return [
        {
            "clarification": cid,
            "context_link": word,
            "context_link_approved_by": "tester",
            "context_link_decision": "D-T",
        }
    ]


def _pairs_clar(question, frag, cid, wh, means="the scales used to measure the pigments asked about just before"):
    return {
        "id": cid,
        "span": [question.index(frag), question.index(frag) + len(frag)],
        "phrase": frag,
        "means": means,
        "authorized_by": "tester",
        "refers_to": _link(question, "specific pigments"),
        "pairs": [_link(question, "specific pigments"), _link(question, wh)],
    }


def _scaffold_of(preps):
    (prep,) = [p for _, p in preps.values() if p.get("scaffold") is not None]
    return prep["scaffold"]


# ---- 1. template 1: "which <noun> <approved verb> the <carried subject> that <relation> <target>?" ------------------------------------------------
def test_a_fragment_with_a_parsed_parent_and_an_approved_verb_gets_a_grammatical_scaffold_with_every_part_traced():
    q = tcp.Q4
    clar = _pairs_clar(q, tcp.FRAG4, "RC-F", "which scales")
    _, _, _, preps = tp._preps(q, tcp._respond_q4, [clar], _approve("RC-F"))
    sc = _scaffold_of(preps)
    assert sc["built"] and sc["template"] == scaffold.T1
    assert sc["text"] == "which scales measure the specific pigments that relate to shell color?"
    origins = [(p["text"], p["origin"]) for p in sc["pieces"]]
    assert origins == [
        ("which scales", "source"),
        ("measure", "approved_joining_word"),
        ("the", "rule"),
        ("specific pigments", "source"),
        ("that", "rule"),
        ("relate to", "source"),
        ("shell color", "source"),
        ("?", "source"),
    ]
    for p in sc["pieces"]:
        if p["origin"] == "source":
            assert q[p["span"][0] : p["span"][1]] == p["text"]  # exact source words
        else:
            assert p["span"] is None  # words that were not in the source never get a source span
    join = next(p for p in sc["pieces"] if p["origin"] == "approved_joining_word")
    assert join["clarification"] == "RC-F" and join["decision"] == "D-T" and join["approved_by"] == "tester"
    assert [(d["text"]) for d in sc["dropped_source_words"]] == ["using"]  # recorded, never silent
    assert [x["kind"] for x in sc["pending"]] == ["fragment_rewritten_as_question"]


Q_REF = "how does the coral effect show up? what kind of specific pigments relate to its color? and using which scales?"


def _respond_ref(prompt, schema):
    if "requirements" in schema["properties"]:
        part = prompt.split("Part to read:" + chr(10), 1)[1] if "Part to read:" + chr(10) in prompt else ""
        if part.startswith("what kind"):
            return {
                "requirements": [
                    tcp._item("specific pigments"),
                    tcp._item("specific pigments relate to its color", kind="relationship"),
                ]
            }
        if part.startswith("and using"):
            return {"requirements": [tcp._item("scales")]}
        return {"requirements": []}
    return {"ambiguities": []} if "ambiguities" in schema["properties"] else {"question": "x", "unresolved": []}


def _its(antecedent):
    phrase = "relate to its color"
    return {
        "id": "RC-I",
        "span": [Q_REF.index(phrase), Q_REF.index(phrase) + len(phrase)],
        "phrase": phrase,
        "reference_word": "its",
        "means": "the thing named",
        "authorized_by": "tester",
        "refers_to": _link(Q_REF, antecedent),
    }


def test_a_reference_inside_the_carried_target_is_resolved_from_its_clarification_and_no_second_question_is_introduced():
    clar = _pairs_clar(Q_REF, "and using which scales?", "RC-F", "which scales")
    _, _, _, preps = tp._preps(Q_REF, _respond_ref, [clar, _its("coral effect")], _approve("RC-F"))
    sc = _scaffold_of(preps)
    assert (
        sc["built"]
        and sc["text"] == "which scales measure the specific pigments that relate to the coral effect's color?"
    )
    assert not (set(lx.tokens(sc["text"])) & {"what", "whether", "how"})
    resolved = next(p for p in sc["pieces"] if p["origin"] == "reference_resolution")
    assert resolved["clarification"] == "RC-I" and resolved["supplied"][0]["text"] == "'s" and resolved["span"] is None


def test_a_carried_reference_that_cannot_be_resolved_safely_stops_the_scaffold_instead_of_guessing():
    clar = _pairs_clar(Q_REF, "and using which scales?", "RC-F", "which scales")
    plural = _its("specific pigments")  # a plural antecedent: where the 's belongs is not clearly safe
    _, _, _, preps = tp._preps(Q_REF, _respond_ref, [clar, plural], _approve("RC-F"))
    sc = _scaffold_of(preps)
    assert not sc["built"] and "could not be resolved safely" in sc["not_built"][0]["reason"]


@pytest.mark.parametrize("approved", [False, True])
def test_a_fragment_that_needs_an_approved_verb_gets_no_scaffold_without_one_and_the_reason_is_recorded(approved):
    q = tcp.Q4
    _, _, _, preps = tp._preps(
        q, tcp._respond_q4, [_pairs_clar(q, tcp.FRAG4, "RC-F", "which scales")], _approve("RC-F") if approved else None
    )
    sc = _scaffold_of(preps)
    assert sc["built"] is approved
    if not approved:
        assert "no researcher-approved joining word" in sc["not_built"][0]["reason"]
        prep = next(p for _, p in preps.values() if p.get("scaffold") is not None)
        assert prep["carry"] is not None  # the v7 behaviour: carried context for the writer, wording held for approval


def test_a_fragment_whose_parent_relationship_did_not_parse_gets_no_scaffold_but_still_gets_its_carried_context():
    q = tcp.Q6
    clar = _pairs_clar(q, tcp.FRAG4, "RC-F6", "which scales")
    _, plans, _, preps = tp._preps(q, tcp._respond_q6, [clar], _approve("RC-F6"))
    sc = _scaffold_of(preps)
    assert not sc["built"] and "not parsed" in sc["not_built"][0]["reason"]
    prep = next(p for _, p in preps.values() if p.get("scaffold") is not None)
    assert (
        prep["carry"]["text"] == "specific pigments frobnicate shell color"
        and prep["carry"]["relationship_parsed"] is False
    )


def test_a_parent_relationship_that_asks_whether_or_how_cannot_be_carried_as_a_relative_clause():
    q = "whether and how specific pigments relate to shell color? and using which scales?"

    def respond(prompt, schema):
        if "requirements" in schema["properties"]:
            part = prompt.split("Part to read:" + chr(10), 1)[1] if "Part to read:" + chr(10) in prompt else ""
            if part.startswith("whether"):
                return {
                    "requirements": [
                        tcp._item("specific pigments"),
                        tcp._item("whether and how specific pigments relate to shell color", kind="relationship"),
                    ]
                }
            if part.startswith("and using"):
                return {"requirements": [tcp._item("scales")]}
            return {"requirements": []}
        return {"ambiguities": []} if "ambiguities" in schema["properties"] else {"question": "x", "unresolved": []}

    clar = _pairs_clar(q, "and using which scales?", "RC-W", "which scales")
    _, _, _, preps = tp._preps(q, respond, [clar], _approve("RC-W"))
    sc = _scaffold_of(preps)
    assert not sc["built"] and "whether/how" in sc["not_built"][0]["reason"]


def test_a_singular_asked_noun_is_not_forced_into_agreement_with_the_approved_word():
    q = "what kind of specific pigments relate to shell color? and using which scale?"
    clar = _pairs_clar(q, "and using which scale?", "RC-S", "which scale")
    _, _, _, preps = tp._preps(q, tcp._respond_q4, [clar], _approve("RC-S"))
    sc = _scaffold_of(preps)
    assert not sc["built"] and "plural" in sc["not_built"][0]["reason"]


# ---- 2. template 2: "in which <noun> is there evidence for <Y>, and how was <Y> <participle> in each?" -------------------------------------------
Q_T2 = "is there any cross-reef evidence for the coral effect? which reefs and how was this measures?"
Q_T2_BRIDGE = "how does the coral effect show up in growth? is there any cross-reef evidence for the effect? which reefs and how was this measures?"


def _t2_setup(question, owner_quote, evidence_ref):
    def respond(prompt, schema):
        if "requirements" in schema["properties"]:
            part = prompt.split("Part to read:" + chr(10), 1)[1] if "Part to read:" + chr(10) in prompt else ""
            if part.startswith("is there any"):
                return {"requirements": [tcp._item(owner_quote, kind="existence")]}
            return {"requirements": []}
        return {"ambiguities": []} if "ambiguities" in schema["properties"] else {"question": "x", "unresolved": []}

    frag, phrase = "which reefs and how was this measures?", "how was this measures"
    lo, rlo = question.index(frag), question.index(phrase)
    clars = [
        {
            "id": "RC-R",
            "span": [rlo, rlo + len(phrase)],
            "phrase": phrase,
            "reference_word": "this",
            "means": "the coral effect",
            "authorized_by": "tester",
            "refers_to": _link(question, "coral effect"),
        },
        {
            "id": "RC-Q",
            "span": [lo, lo + len(frag)],
            "phrase": frag,
            "means": "the requested reefs stay paired with how the effect was measured in those reefs",
            "authorized_by": "tester",
            "refers_to": _link(question, evidence_ref),
            "pairs": [_link(question, "which reefs"), _link(question, "how was this measures")],
        },
    ]
    return respond, clars


def _t2(question, owner_quote, evidence_ref):
    respond, clars = _t2_setup(question, owner_quote, evidence_ref)
    return tp._preps(question, respond, clars)


def test_a_population_and_manner_fragment_continuing_an_existence_question_becomes_one_compound_request_with_each_part_traced():
    _, _, _, preps = _t2(
        Q_T2, "is there any cross-reef evidence for the coral effect", "cross-reef evidence for the coral effect"
    )
    sc = _scaffold_of(preps)
    assert sc["built"] and sc["template"] == scaffold.T2
    assert (
        sc["text"]
        == "in which reefs is there evidence for the coral effect, and how was the coral effect measured in each?"
    )
    by_origin = {}
    for p in sc["pieces"]:
        by_origin.setdefault(p["origin"], []).append(p["text"])
    assert by_origin["rule"] == ["in", ",", "in each"]
    assert by_origin["inflection"] == ["measured"] and by_origin["reference_resolution"] == ["the coral effect"]
    for p in sc["pieces"]:
        if p["origin"] == "source":
            assert Q_T2[p["span"][0] : p["span"][1]] == p["text"]
    assert [d["text"] for d in sc["dropped_source_words"]] == [
        "any",
        "cross-reef",
    ]  # the source modifier is recorded as left out
    assert [x["kind"] for x in sc["pending"]] == [
        "scope_words_dropped_and_supplied"
    ]  # and waits for the researcher, never silently settled


def test_a_topic_named_differently_in_the_continued_question_is_bridged_only_as_a_recorded_pending_inference():
    _, _, _, preps = _t2(
        Q_T2_BRIDGE, "is there any cross-reef evidence for the effect", "cross-reef evidence for the effect"
    )
    sc = _scaffold_of(preps)
    assert (
        sc["built"]
        and sc["text"]
        == "in which reefs is there evidence for the coral effect, and how was the coral effect measured in each?"
    )
    inferred = next(p for p in sc["pieces"] if p["origin"] == "inferred_reference")
    assert inferred["based_on"] == "RC-R" and inferred["replaces"]["text"] == "the effect"
    assert "inferred_reference" in {
        x["kind"] for x in sc["pending"]
    }  # no approved clarification covers "the effect": an inference, flagged


def test_a_population_fragment_whose_parent_is_not_an_existence_question_gets_no_such_scaffold():
    from experiments.ask_cli_revised.decompose.test_tree import CLAR_FRAGMENT, CLAR_UNIT, Q2, _respond_q2

    _, _, _, preps = tp._preps(Q2, _respond_q2, [CLAR_FRAGMENT, CLAR_UNIT])
    prep = next(p for _, p in preps.values() if "which reefs" in p["original_extract_text"])
    assert prep["scaffold"] is not None and not prep["scaffold"]["built"]
    assert "existence question" in prep["scaffold"]["not_built"][0]["reason"]


def test_the_compound_scaffold_raises_no_operator_finding_when_returned_and_dropping_a_clause_is_held_for_approval():
    inventory, rows = _t2_setup(
        Q_T2, "is there any cross-reef evidence for the coral effect", "cross-reef evidence for the coral effect"
    )

    def run(wording):
        def respond(prompt, schema):
            if "requirements" in schema["properties"] or "ambiguities" in schema["properties"]:
                return inventory(prompt, schema)
            if "built by code" in prompt:
                return {"question": wording, "unresolved": []}
            return {"question": "Is there any cross-reef evidence for the coral effect?", "unresolved": []}

        result = run_engine(Q_T2, ScriptedModel(respond), repair=False, prompt_variant="prepared", clarifications=rows)
        return next(c for c in result["pass1"]["children"] if c.get("clarified_fragment") == "RC-Q")

    verbatim = run(
        "in which reefs is there evidence for the coral effect, and how was the coral effect measured in each?"
    )
    flags = {f["flag"] for f in verbatim["flags"] if not f.get("informational")}
    assert not {"operator_dropped", "operator_added", "relation_word_added"} & flags, flags
    assert "explained_by_scaffold" in {
        f["flag"] for f in verbatim["flags"]
    }  # the ledger's raw findings are kept, and explained
    assert (
        verbatim["status"] == "pending_researcher_confirmation"
        and verbatim["execution"]["state"] == execution.REQUIRES_APPROVAL
    )
    dropped = run("in which reefs is there evidence for the coral effect?")
    assert dropped["status"] != "candidate" and dropped["execution"]["state"] != execution.RUNNABLE_BY_CONSTRUCTION


# ---- 3. the recorded inflection edit is narrow -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, expected",
    [
        ("which cultures and how was this measures?", "measured"),
        ("how were the results lists?", "listed"),
        ("when was the effect compares?", "compared"),
        ("how was that quantifies?", "quantified"),
    ],
)
def test_a_clear_passive_inflection_error_is_corrected_as_a_recorded_edit_of_that_one_word(text, expected):
    (edit,) = prepare._inflection_edits(text, [{"span": [0, len(text)], "text": text}])
    lo, hi = edit["replaces"]["source_span"]
    assert text[lo:hi] == edit["replaces"]["text"] and edit["result"] == expected and edit["from_source"] == []
    assert (
        edit["supplied"][0]["by"].startswith("rule:") and "span" not in edit["supplied"][0]
    )  # a rule-supplied inflection, no invented span


@pytest.mark.parametrize(
    "text",
    [
        "how were these measures?",  # a plural noun, not a verb
        "how was this measured?",  # already correct
        "how was the effect measures of depth?",  # the -s word does not end the span
        "the effect measures depth",  # no wh-passive question
        "what was this?",  # not an operation verb
    ],
)
def test_the_inflection_rule_leaves_everything_it_is_not_sure_about_alone(text):
    assert prepare._inflection_edits(text, [{"span": [0, len(text)], "text": text}]) == []


# ---- 4. structural checks and execution readiness -----------------------------------------------------------------------------------------------
def _child(
    question,
    *,
    status="candidate",
    prepared="which scales measure the traits?",
    carry=None,
    join=None,
    scaffold_=None,
    **kw,
):
    return {
        "child_id": "cX",
        "kind": "generated",
        "status": status,
        "question": question,
        "preparation": {"prepared_request": prepared, "carry": carry, "join": join, "scaffold": scaffold_},
        **kw,
    }


CARRY = {"subject_words": "specific traits", "relation_words": "relate to", "text": "specific traits relate to depth"}


def test_the_preparation_is_the_only_wording_that_runs_on_a_candidate_label_alone():
    same = _child("Which scales measure the traits?")  # case and closing punctuation never make a wording different
    assert structure.departs_from_prepared_request(same) is None
    assert execution.readiness(same)["state"] == execution.RUNNABLE_BY_CONSTRUCTION
    other = _child("Which scales were used to measure the traits?")
    found = structure.departs_from_prepared_request(other)
    assert found["words_added"] == ["were", "used", "to"] and found["words_removed"] == []
    ex = execution.readiness(other)
    assert (
        ex["state"] == execution.REQUIRES_APPROVAL and not ex["executable"]
    )  # a clean-looking candidate is still not authorized


def test_the_run_on_pattern_after_a_verb_is_flagged_and_a_joined_or_unrelated_sentence_is_not():
    join = {"text": "measure"}
    bad = _child("measure specific traits relate to depth using which scales?", carry=CARRY, join=join)
    assert structure.unjoined_carried_clause(bad)["flag"] == "unjoined_carried_clause"
    joined = _child("which scales measure the specific traits that relate to depth?", carry=CARRY, join=join)
    assert structure.unjoined_carried_clause(joined) is None
    question_form = _child(
        "what kind of specific traits relate to depth?", carry=CARRY, join=join
    )  # the subject after "of": a normal question
    assert structure.unjoined_carried_clause(question_form) is None
    assert (
        structure.unjoined_carried_clause(_child("measure specific traits relate to depth", carry=None)) is None
    )  # no carried relation: nothing to check


def test_the_structural_checks_do_not_claim_to_verify_grammar():
    ungrammatical_but_prepared = _child("Which scales measure the traits?", prepared="which scales measure the traits?")
    assert (
        structure.findings(ungrammatical_but_prepared) == []
    )  # passing means "matches the defended construction", nothing more
    assert "not a certificate" in structure.__doc__.lower()


@pytest.mark.parametrize(
    "kw, state",
    [
        ({"kind": "passthrough"}, execution.RUNNABLE_ORIGINAL),
        ({"status": "semantic_conflict"}, execution.NOT_EXECUTABLE),
        ({"kind": "fallback", "status": "fallback_unresolved"}, execution.NOT_EXECUTABLE),
        ({"kind": "not_selected", "status": "not_selected"}, execution.NOT_EXECUTABLE),
        ({"status": "semantic_review_required"}, execution.REQUIRES_APPROVAL),
        ({"status": "source_gap"}, execution.REQUIRES_APPROVAL),
        ({"status": "pending_researcher_confirmation"}, execution.REQUIRES_APPROVAL),
        ({"human_review_required": True}, execution.REQUIRES_APPROVAL),
        ({}, execution.RUNNABLE_BY_CONSTRUCTION),
    ],
)
def test_execution_readiness_follows_the_status_and_never_lets_a_label_authorize_by_itself(kw, state):
    child = (
        _child("which scales measure the traits?", **kw) if kw.get("kind") != "passthrough" else {**_child("x"), **kw}
    )
    assert execution.readiness(child)["state"] == state


def test_an_approval_names_the_exact_wording_and_a_different_string_is_not_approved(tmp_path):
    child = _child("Which scales were used to measure the traits?")
    approval = {
        "child_id": "cX",
        "wording_sha256": execution.wording_sha256(child["question"]),
        "approved_by": "tester",
        "authorization_quote": "yes, that wording",
    }
    assert execution.readiness(child, approvals=[approval])["state"] == execution.RESEARCHER_APPROVED
    assert (
        execution.readiness({**child, "question": child["question"] + " "}, approvals=[approval])["state"]
        == execution.REQUIRES_APPROVAL
    )
    assert (
        execution.readiness({**child, "child_id": "cY"}, approvals=[approval])["state"] == execution.REQUIRES_APPROVAL
    )
    hard = {**child, "status": "semantic_conflict"}
    assert (
        execution.readiness(hard, approvals=[approval])["state"] == execution.NOT_EXECUTABLE
    )  # an approval never overrides a hard failure
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps({"approvals": [approval]}), encoding="utf-8")
    assert execution.load_approvals(path) == [approval]
    path.write_text(json.dumps({"approvals": [{**approval, "wording_sha256": "abc"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        execution.load_approvals(path)
    path.write_text(
        json.dumps({"approvals": [{k: v for k, v in approval.items() if k != "approved_by"}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="approved_by"):
        execution.load_approvals(path)


def test_a_departing_wording_is_held_and_the_deterministic_proposal_is_offered_separately_never_substituted():
    scaffold_ = {"built": True, "text": "which scales measure the traits?", "pending": []}
    child = _child("Which scales were used to measure the traits?", scaffold_=scaffold_)
    ex = execution.readiness(child)
    assert ex["state"] == execution.REQUIRES_APPROVAL
    assert (
        ex["fallback_proposal"]["text"] == "which scales measure the traits?"
        and ex["fallback_proposal"]["requires_researcher_approval"]
    )
    assert child["question"] == "Which scales were used to measure the traits?"  # the writer's wording is untouched
    no_defensible = _child(
        "measure x using which scales?",
        carry=CARRY,
        scaffold_={"built": False, "not_built": [{"template": None, "reason": "x"}]},
    )
    assert (
        execution.readiness(no_defensible)["fallback_proposal"] is None
    )  # nothing defensible to offer: the researcher decides


def test_the_writers_exact_response_is_kept_and_a_stripped_wording_is_disclosed():
    result, _ = base.run({"whether and how": {"question": "  Padded wording?  "}}, repair=False)
    kid = next(c for c in result["pass1"]["children"] if c["question"] == "Padded wording?")
    raw = kid["model_raw"]
    assert raw["question_as_returned"] == "  Padded wording?  " and raw["whitespace_stripped"] is True
    assert json.loads(raw["response_text"])["question"] == "  Padded wording?  "
    assert "surrounding whitespace only stripped" in views.natural_language_view(result)["exactness"]


def test_a_broken_writer_wording_for_a_scaffolded_child_is_never_presented_as_runnable_or_replaced():
    q = tcp.Q4
    clar = _pairs_clar(q, tcp.FRAG4, "RC-F", "which scales")
    broken = "measure specific pigments relate to shell color using which scales?"

    def respond(prompt, schema):
        if "requirements" in schema["properties"] or "ambiguities" in schema["properties"]:
            return tcp._respond_q4(prompt, schema)
        if "built by code" in prompt:
            return {"question": broken, "unresolved": []}
        return {"question": "What kind of specific pigments relate to shell color?", "unresolved": []}

    result = run_engine(
        q,
        ScriptedModel(respond),
        repair=False,
        prompt_variant="prepared",
        clarifications=[clar],
        clarification_annotations=_approve("RC-F"),
    )
    kid = next(c for c in result["pass1"]["children"] if c.get("clarified_fragment"))
    assert kid["question"] == broken  # exactly what the model returned
    assert kid["status"] == "semantic_review_required" and {
        "unjoined_carried_clause",
        "departs_from_prepared_request",
    } <= {f["flag"] for f in kid["flags"]}
    ex = kid["execution"]
    assert ex["state"] == execution.REQUIRES_APPROVAL and not ex["executable"]
    assert ex["fallback_proposal"]["text"] == "which scales measure the specific pigments that relate to shell color?"
    nl = views.render_natural_language(views.natural_language_view(result))
    assert broken in nl and "SEPARATE PROPOSAL" in nl and "REQUIRES RESEARCHER APPROVAL" in nl


def test_a_scaffold_returned_verbatim_is_pending_and_awaits_approval_not_a_conflict():
    q = tcp.Q4
    clar = _pairs_clar(q, tcp.FRAG4, "RC-F", "which scales")
    text = "which scales measure the specific pigments that relate to shell color?"

    def respond(prompt, schema):
        if "requirements" in schema["properties"] or "ambiguities" in schema["properties"]:
            return tcp._respond_q4(prompt, schema)
        return {
            "question": text if "built by code" in prompt else "What kind of specific pigments relate to shell color?",
            "unresolved": [],
        }

    result = run_engine(
        q,
        ScriptedModel(respond),
        repair=False,
        prompt_variant="prepared",
        clarifications=[clar],
        clarification_annotations=_approve("RC-F"),
    )
    kid = next(c for c in result["pass1"]["children"] if c.get("clarified_fragment"))
    assert (
        kid["status"] == "pending_researcher_confirmation" and kid["execution"]["state"] == execution.REQUIRES_APPROVAL
    )
    assert "explained_by_scaffold" in {f["flag"] for f in kid["flags"]} and "scaffold_pending_confirmation" in {
        f["flag"] for f in kid["flags"]
    }


# ---- 5. the no-split route --------------------------------------------------------------------------------------------------------------------------
def test_the_prompt_examples_are_derived_from_the_prompt_itself_so_they_cannot_drift():
    assert "is there any..." in pm.PROMPT_EXAMPLES and "whether" in pm.PROMPT_EXAMPLES and "how" in pm.PROMPT_EXAMPLES
    assert all(f"'{x}'" in pm._KIND_HELP for x in pm.PROMPT_EXAMPLES)
    assert pm.is_prompt_echo("Is There Any ...") and not pm.is_prompt_echo("a placebo effect")


def _inventory(units, whole):
    return tcp._scripted(
        units, whole=whole, writer=lambda prompt: {"question": "SHOULD NOT BE WRITTEN", "unresolved": []}
    )


@pytest.mark.parametrize(
    "question, entities",
    [
        ("What is the coral effect?", ("the coral effect", "What is the coral effect?")),
        ("Which pigments absorb blue light?", ("pigments absorb blue light", "Which pigments absorb blue light?")),
        (
            "Please list the risk factors for stroke.",
            ("the risk factors for stroke", "Please list the risk factors for stroke."),
        ),
    ],
)
def test_a_simple_question_whose_inventory_echoes_a_prompt_example_still_takes_the_no_split_route_with_its_exact_punctuation(
    question, entities
):
    key = question.split()[0]
    units = {key: [{"kind": "existence", "quotes": ["is there any..."], "note": "an echo of the prompt"}]}
    whole = [tcp._item(entities[0]), {"kind": "output_expectation", "quotes": [entities[1]], "note": ""}]
    model = _inventory(units, whole)
    result = run_engine(question, model, repair=False, prompt_variant="prepared")
    (kid,) = result["pass1"]["children"]
    assert (
        result["decomposition_decision"]["outcome"] == "no_decomposition_needed"
        and result["decomposition_decision"]["applied"]
    )
    assert kid["kind"] == "passthrough" and kid["question"] == question  # the original, character for character
    assert kid["execution"]["state"] == execution.RUNNABLE_ORIGINAL
    assert sum(1 for c in result["calls"] if c["task"] == "children.write") == 0
    (aside,) = result["parent_contract"]["post_processing"]["set_aside_prompt_echoes"]
    assert aside["quotes"] == ["is there any..."] and aside["reason"].startswith("prompt_example_echo")


def test_an_example_phrase_that_really_is_in_the_request_is_an_obligation_and_never_set_aside():
    question = "Is there any evidence for reef bleaching in juveniles?"
    units = {"Is there any": [{"kind": "existence", "quotes": ["Is there any"], "note": ""}]}
    parent = build_parent_contract(CallLog(_inventory(units, [])), question)
    assert "set_aside_prompt_echoes" not in parent["post_processing"]
    assert any(r["kind"] == "existence" and r["anchoring"] != "none" for r in parent["requirements"])


def test_an_unanchored_item_that_is_not_a_prompt_echo_still_blocks_the_no_split_route_and_is_reported_not_hidden():
    question = "What is the coral effect?"
    units = {"What": [{"kind": "requested_item", "quotes": ["reef bleaching depth"], "note": "not in the request"}]}
    whole = [tcp._item("the coral effect")]
    result = run_engine(question, _inventory(units, whole), repair=False, prompt_variant="prepared")
    d = result["decomposition_decision"]
    assert d["outcome"] == "uncertain" and "no_unanchored_inventory_obligation" in d["blocking"] and not d["applied"]
    assert "set_aside_prompt_echoes" not in result["parent_contract"]["post_processing"]


def test_a_row_that_mixes_an_echo_with_a_real_quote_keeps_only_the_real_one():
    question = "What is the coral effect?"
    units = {"What": [{"kind": "existence", "quotes": ["is there any...", "the coral effect"], "note": ""}]}
    parent = build_parent_contract(CallLog(_inventory(units, [])), question)
    kept = [r for r in parent["requirements"] if r["origin"] == "model_unit"]
    assert [a["quote"] for r in kept for a in r["anchors"]] == ["the coral effect"]
    assert parent["post_processing"]["set_aside_prompt_echoes"][0]["quotes"] == ["is there any..."]


def test_a_contract_without_an_echo_is_unchanged_byte_for_byte():
    question = "What is the coral effect?"
    units = {"What": [tcp._item("the coral effect")]}
    parent = build_parent_contract(CallLog(_inventory(units, [tcp._item("the coral effect")])), question)
    assert "set_aside_prompt_echoes" not in json.dumps(parent)


def test_the_recorded_placebo_control_inventory_now_takes_the_no_split_route_offline():
    control = AIB / "integrated_test_v6" / "run" / "control_placebo" / "model_calls.jsonl"
    if not control.exists():
        pytest.skip("the local v6 control run is not present")
    recs = [json.loads(x) for x in control.read_text(encoding="utf-8").splitlines() if x.strip()]
    inv = [r for r in recs if r["task"].startswith("parent.")]
    assert any("is there any..." in r["raw_output"] for r in inv)  # the recorded echo is really in the record

    class Refuse:
        label = "refusing"

        def call(self, prompt, *, schema, output_cap):
            raise AssertionError("a writer call was attempted")

        def identity(self):
            return {"kind": "refusing"}

    result = run_engine(
        "What is a placebo effect?",
        Refuse(),
        repair=False,
        inventory_model=ReplayModel(inv, "frozen-v6-control"),
        prompt_variant="prepared",
        max_calls=0,
    )
    (kid,) = result["pass1"]["children"]
    assert (
        result["decomposition_decision"]["outcome"] == "no_decomposition_needed"
        and kid["question"] == "What is a placebo effect?"
    )


# ---- 6. genericity and isolation ------------------------------------------------------------------------------------------------------------------
def test_the_closure_modules_name_no_child_and_no_real_request_and_read_no_file():
    for name in ("scaffold.py", "structure.py", "execution.py"):
        text = (DECOMPOSE / name).read_text(encoding="utf-8")
        assert not re.search(r"\bc\d{1,2}\b", text), name  # no child-id branch
        assert not [w for w in ("q_aib", "anomalous", "intent_reference", "expected_evidence") if w in text], name
    for name in ("scaffold.py", "structure.py"):
        text = (DECOMPOSE / name).read_text(encoding="utf-8")
        assert "open(" not in text and "read_text" not in text and "Path(" not in text, name  # pure
    assert "open(" not in (DECOMPOSE / "execution.py").read_text(encoding="utf-8").replace(
        "load_approvals", ""
    )  # only the approvals loader reads a file


# ---- 7. the preserved v6/v7 evidence (skips when absent) -----------------------------------------------------------------------------------------------
def _v7_inputs():
    v7 = AIB / "followup_v7"
    if (
        not (v7 / "inputs" / "primary_request.txt").exists()
        or not (AIB / "clarifications" / "q_aib.v3.approved.json").exists()
    ):
        pytest.skip("the local v6/v7 development artifacts are not present")
    from experiments.ask_cli_revised.decompose import wording_check

    return wording_check, wording_check.load_inputs(
        v7 / "inputs",
        {
            "approved": AIB / "clarifications" / "q_aib.v3.approved.json",
            "decisions": AIB / "clarifications" / "q_aib.v6.researcher_decisions.json",
        },
    )


def test_the_prompts_of_the_children_that_needed_no_new_preparation_are_identical_to_the_v7_run_and_only_the_two_fragments_changed():
    wording_check, inp = _v7_inputs()
    v7 = wording_check.read_jsonl(AIB / "followup_v7" / "run" / "model_calls.jsonl")
    recorded = {r["unit_id"]: r["prompt"] for r in v7}
    now = wording_check.prepared_prompts(inp)
    assert now["c6"]["prepared"] == recorded["c6"] and now["c8"]["prepared"] == recorded["c8"]
    assert now["c9"]["prepared"] != recorded["c9"] and now["c11"]["prepared"] != recorded["c11"]
    assert (
        wording_check.replay_identity(inp)["identical"] and wording_check.baseline_prompt_identity(inp)["all_identical"]
    )


def test_the_two_fragment_scaffolds_are_derived_from_the_frozen_contracts_and_are_grammatical_questions():
    wording_check, inp = _v7_inputs()
    now = wording_check.prepared_prompts(inp)
    c9, c11 = (now[c]["preparation"] for c in ("c9", "c11"))
    assert (
        c9["prepared_request"]
        == "which scales measure the specific personality traits that relate to the anomalous is bad bias's manifestation?"
    )
    assert (
        c11["prepared_request"]
        == "in which cultures is there evidence for the anomalous is bad bias, and how was the anomalous is bad bias measured in each?"
    )
    for prep in (c9, c11):
        sc = prep["scaffold"]
        assert sc["built"] and hashlib.sha256(sc["text"].encode()).hexdigest()
        assert all(p["span"] is None for p in sc["pieces"] if p["origin"] != "source")
    assert [d["text"] for d in c11["scaffold"]["dropped_source_words"]] == ["any", "cross-cultural"]
    assert any(
        p["kind"] == "inferred_reference" for p in c11["scaffold"]["pending"]
    )  # "the bias" has no approved clarification: flagged


def test_the_v7_broken_c9_wording_is_now_held_for_review_and_the_v7_c6_and_c8_outputs_stay_runnable_by_construction():
    wording_check, inp = _v7_inputs()
    prep = wording_check.prepared_prompts(inp)
    frozen = {
        "c9": "measure specific personality traits relate to the anomalous is bad bias's manifestation using which scales?",
        "c6": prep["c6"]["preparation"]["prepared_request"],
        "c8": prep["c8"]["preparation"]["prepared_request"],
    }

    def respond(prompt, schema):
        for cid, text in frozen.items():
            if prep[cid]["prepared"] == prompt:
                return {"question": text, "unresolved": []}
        return {"question": prep["c11"]["preparation"]["prepared_request"], "unresolved": []}

    from experiments.ask_cli_revised.decompose.model import ReplayModel as RM

    result = run_engine(
        inp["question"],
        ScriptedModel(respond),
        repair=False,
        inventory_model=RM(inp["inventory"], "frozen-v6"),
        clarifications=inp["rows"],
        clarification_annotations=inp["annotations"],
        researcher_decisions=inp["decisions"],
        prompt_variant="prepared",
        only=["c6", "c8", "c9", "c11"],
        max_calls=4,
    )
    kids = {c["child_id"]: c for c in result["pass1"]["children"]}
    assert (
        kids["c9"]["status"] == "semantic_review_required"
        and kids["c9"]["execution"]["state"] == execution.REQUIRES_APPROVAL
    )
    assert {"unjoined_carried_clause", "departs_from_prepared_request"} <= {f["flag"] for f in kids["c9"]["flags"]}
    assert kids["c6"]["execution"]["state"] == kids["c8"]["execution"]["state"] == execution.RUNNABLE_BY_CONSTRUCTION


# ---- 8. the two proposed gates: bounded runners, rehearsed offline (no model) ---------------------------------------------------------------------
def test_gate_a_covers_only_the_two_fragments_with_two_calls_and_the_v7_settings_otherwise():
    from experiments.ask_cli_revised.decompose import wording_check

    a, v7 = wording_check.CONFIG_A, wording_check.CONFIG
    assert a["children"] == ["c9", "c11"] and a["max_writer_calls"] == a["max_calls"] == 2
    for key in (
        "model",
        "endpoint",
        "think",
        "options",
        "repair",
        "automatic_retries",
        "variant",
        "per_call_wall_timeout_seconds",
        "expected_model_digest",
    ):
        assert a[key] == v7[key], key
    assert v7["children"] == ["c6", "c8", "c9", "c11"]  # the historical v7 configuration is untouched


def test_gate_a_rehearsal_writes_only_the_two_fragments_and_saves_both_prompts(tmp_path):
    from experiments.ask_cli_revised.decompose import wording_check

    _, inp = _v7_inputs()
    prep = wording_check.prepared_prompts(inp, wording_check.CONFIG_A)
    assert set(prep) == {"c9", "c11"}
    seen = []

    def respond(prompt, schema):
        seen.append(prompt)
        row = next(r for r in prep.values() if r["prepared"] == prompt)
        return {"question": row["preparation"]["prepared_request"], "unresolved": []}

    summary = wording_check.run_check(
        tmp_path / "run", lambda: ScriptedModel(respond), live=False, inp=inp, config=wording_check.CONFIG_A
    )
    assert summary["outcome"] == "COMPLETE" and [w[0] for w in summary["written"]] == ["c9", "c11"] and len(seen) == 2
    assert {w[2] for w in summary["written"]} == {
        "pending_researcher_confirmation"
    }  # the scaffolds returned verbatim await the researcher
    records = wording_check.read_jsonl(tmp_path / "run" / "model_calls.jsonl")
    assert len(records) == 2 and {r["prompt"] for r in records} == {r["prepared"] for r in prep.values()}
    manifest = wording_check.freeze_manifest(
        ROOT, tmp_path, input_files={}, tool_files=[], clarification_files={}, config=wording_check.CONFIG_A
    )
    assert manifest["hard_caps"]["max_calls"] == 2 and manifest["config"]["children"] == ["c9", "c11"]


def test_gate_a_halts_after_one_call_when_the_output_does_not_parse(tmp_path):
    from experiments.ask_cli_revised.decompose import wording_check

    _, inp = _v7_inputs()
    calls = []

    def bad(prompt, schema):
        calls.append(prompt)
        return "not json"

    summary = wording_check.run_check(
        tmp_path / "run", lambda: ScriptedModel(bad), live=False, inp=inp, config=wording_check.CONFIG_A
    )
    assert summary["outcome"] == "INCOMPLETE" and len(calls) == 1 and (tmp_path / "run" / "HALTED.json").exists()


def test_gate_b_config_pins_one_request_and_a_hard_cap_of_three_inventory_calls_plus_at_most_one_writer_call():
    from experiments.ask_cli_revised.decompose import nosplit_check

    c = nosplit_check.CONFIG_B
    assert (
        c["request"] == "What is a placebo effect?"
        and c["max_calls"] == 4
        and c["inventory_calls_known_in_advance"] == 3
    )
    assert (
        c["repair"] is False
        and c["automatic_retries"] is False
        and c["think"] is False
        and c["options"]["seed"] == 42
        and c["options"]["temperature"] == 0
    )


def _echo_model(question=None, unanchored=None):
    """A scripted inventory: the unit call returns an echo (or another unanchored quote), the whole-request call two anchored obligations."""
    quote = unanchored or "is there any..."

    def respond(prompt, schema):
        props = schema["properties"]
        if "requirements" in props:
            if "Part to read:" + chr(10) in prompt:
                return {"requirements": [{"kind": "existence", "quotes": [quote], "note": "scripted"}]}
            return {
                "requirements": [
                    tcp._item("a placebo effect", kind="existence"),
                    {"kind": "output_expectation", "quotes": ["What is a placebo effect?"], "note": ""},
                ]
            }
        if "ambiguities" in props:
            return {"ambiguities": []}
        return {"question": "What is a placebo effect", "unresolved": []}

    return ScriptedModel(respond)


def test_gate_b_rehearsal_takes_the_no_split_route_in_three_calls_and_keeps_the_original_punctuation(tmp_path):
    from experiments.ask_cli_revised.decompose import nosplit_check

    summary = nosplit_check.run_check(tmp_path / "run", _echo_model, live=False)
    assert summary["outcome"] == "COMPLETE" and summary["route"] == "no_split_pass_through"
    assert summary["calls_total"] == 3 and summary["writer_calls"] == 0
    assert (
        summary["child"]["wording"] == "What is a placebo effect?" and summary["child"]["exactly_the_original_request"]
    )
    assert summary["child"]["execution"] == "runnable_original" and summary["set_aside_prompt_echoes"][0]["quotes"] == [
        "is there any..."
    ]
    assert (tmp_path / "run" / "artifacts" / "VIEW_natural_language.md").exists()


def test_gate_b_rehearsal_reports_the_writer_path_when_a_non_echo_unanchored_item_blocks_pass_through(tmp_path):
    from experiments.ask_cli_revised.decompose import nosplit_check

    summary = nosplit_check.run_check(
        tmp_path / "run", lambda: _echo_model(unanchored="reef bleaching depth"), live=False
    )
    assert (
        summary["route"] == "writer_path" and summary["writer_calls"] == 1 and summary["calls_total"] == 4
    )  # the hard cap, never exceeded
    assert summary["decision"]["outcome"] == "uncertain" and not summary["child"]["exactly_the_original_request"]


def test_gate_b_compares_each_raw_response_with_the_recorded_v6_control(tmp_path):
    from experiments.ask_cli_revised.decompose import nosplit_check

    control = AIB / "integrated_test_v6" / "run" / "control_placebo" / "model_calls.jsonl"
    if not control.exists():
        pytest.skip("the local v6 control run is not present")
    recorded = [json.loads(x) for x in control.read_text(encoding="utf-8").splitlines() if x.strip()]
    summary = nosplit_check.run_check(tmp_path / "run", _echo_model, live=False, recorded=recorded)
    rows = {r["task"]: r for r in summary["same_as_recorded_v6_control"]}
    assert set(rows) == {"parent.obligations_unit", "parent.obligations_whole", "parent.ambiguities"}
    assert all(
        r["prompt_identical_to_recorded"] for r in rows.values()
    )  # the inventory prompts are the very ones the v6 control used
    assert not any(
        r["raw_response_identical_to_recorded"] for r in rows.values()
    )  # a scripted answer is, correctly, not the recorded one


def test_the_summary_separates_what_ask_may_run_from_what_waits_and_what_cannot_run():
    kids = [
        {**_child("Which scales measure the traits?"), "child_id": "a"},
        {**_child("Which scales were used to measure the traits?"), "child_id": "b"},
        {**_child("x", status="semantic_conflict"), "child_id": "c"},
        {"child_id": "d", "kind": "passthrough", "status": "no_decomposition_needed", "question": "Original?"},
    ]
    summary = execution.summarize(kids)
    assert (
        summary["executable"] == ["a", "d"]
        and summary["requires_researcher_approval"] == ["b"]
        and summary["not_executable"] == ["c"]
    )
    assert not summary["all_executable"]
    assert execution.summarize([kids[0], kids[3]])["all_executable"]


def test_a_gate_run_refuses_cleanly_when_there_is_no_gate_document(tmp_path):
    from experiments.ask_cli_revised.decompose import wording_check

    frozen = {"freeze_sha256": "f" * 64}
    with pytest.raises(RuntimeError, match="no gate document"):
        wording_check.preconditions(
            frozen, frozen, tmp_path / "GATE.md", tmp_path / "AUTHORIZATION.json", tmp_path / "run"
        )
