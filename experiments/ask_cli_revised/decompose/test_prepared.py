"""Model-free proof of deterministic preparation (``prepare.py``), the ``prepared`` writer variant and the bounded wording check.

Synthetic requests only (the coral/pigment/reef fixtures of the other test modules), except the tests marked as reading the preserved local
v6 artifacts, which skip themselves when those are absent. No model is called and nothing is sent anywhere. What is proved:

* approved references are resolved at their anchored source spans, with the smallest edit, and each edit cites its source or clarification;
* a clarification-added cue is inserted from the relationship contract, recorded with NO invented source span;
* a fragment's indispensable context is carried whether or not the parent's relationship parsed, and is never a question;
* preparation does not forbid a second question word: a compound operation is legal, an added NEW ask is still caught by the existing checks;
* the deterministic edits are recorded apart from the model's wording, and the natural-language view shows exactly what the model returned;
* nothing-to-prepare children and every historical variant are byte-identical to the corrected-full baseline;
* the bounded runner refuses without freeze + gate + authorization, and writes at most the listed children.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

import experiments.ask_cli_revised.decompose.test_correction_pass as tcp
import experiments.ask_cli_revised.decompose.test_decompose as base
from experiments.ask_cli_revised.decompose import children as ch
from experiments.ask_cli_revised.decompose import (
    clarifications,
    integrated,
    prepare,
    prompts,
    prompts_prepared,
    views,
    wording_check,
)
from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose.calllog import CallLog
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ScriptedModel
from experiments.ask_cli_revised.decompose.parent import build_parent_contract
from experiments.ask_cli_revised.decompose.test_relations import CLAR, Q
from experiments.ask_cli_revised.decompose.test_tree import CLAR_FRAGMENT, CLAR_UNIT, Q2, _respond_q2

ROOT = Path(__file__).resolve().parents[3]
AIB = ROOT / ".local" / "decompose-runs" / "aib-dev"
V7 = AIB / "followup_v7"
DECOMPOSE = Path(__file__).resolve().parent

ZONES = Q.index("specific reef zones")
CLAR_THEY = {
    **CLAR,
    "refers_to": {"span": [ZONES, ZONES + len("specific reef zones")], "phrase": "specific reef zones"},
}
_ITS = Q.index("relate to its expression")
_EFFECT = Q.index("coral effect")
CLAR_ITS = {
    "id": "RC-I",
    "span": [_ITS, _ITS + len("relate to its expression")],
    "phrase": "relate to its expression",
    "reference_word": "its",
    "means": "the coral effect",
    "authorized_by": "tester",
    "refers_to": {"span": [_EFFECT, _EFFECT + len("coral effect")], "phrase": "coral effect"},
}


def _link(question: str, text: str) -> dict:
    lo = question.index(text)
    return {"span": [lo, lo + len(text)], "phrase": text}


def _state(question, respond, clars, annotations=None):
    parent = build_parent_contract(CallLog(ScriptedModel(respond)), question)
    clarifications.apply(parent, clars)
    if annotations:
        clarifications.annotate(parent, annotations)
    plans = ch.plan_children(parent)
    return parent, plans, ch.by_id_map(parent)


def _preps(question, respond, clars, annotations=None):
    parent, plans, by_id = _state(question, respond, clars, annotations)
    out = {}
    for plan in plans:
        if plan["kind"] == "anchor":
            ctx = ch.child_context(parent, plan, by_id, plans=plans, governing_operation=True)
            out[plan["child_id"]] = (plan, prepare.prepare_child(parent, plan, plans, by_id, ctx))
    return parent, plans, by_id, out


def _find(preps, needle):
    return next(p for _, p in preps.values() if needle in p["original_extract_text"])


def _text(prep):
    return " ".join(e["text"] for e in prep["extract_entries"])


def _write_prompt(result, needle):
    """The child-writing prompt whose first owned item contains ``needle`` (inventory calls are skipped)."""
    return next(
        c["prompt"]
        for c in result["calls"]
        if c["task"] == "children.write" and needle in base._owned_first_line(c["prompt"])
    )


def _kinds(kid) -> set:
    return {f["kind"] for f in kid["edit_ledger"]["flags"] if f["class"] != "info"}


# ---- 1. references are resolved at their anchored source spans ---------------------------------------------------------------------------
def test_an_approved_pronoun_is_replaced_at_its_own_source_span_by_the_antecedent_words_and_the_edit_cites_both():
    parent, _, _, preps = _preps(Q, base.responder(), [CLAR_THEY, CLAR_ITS])
    prep = _find(preps, "whether and how they relate")
    assert "specific reef zones relate to depth" in _text(prep) and " they " not in f" {_text(prep)} "
    (edit,) = [e for e in prep["edits"] if e["op"] == "reference_resolved"]
    lo, hi = edit["replaces"]["source_span"]
    assert Q[lo:hi] == "they" and edit["clarification"] == "RC-T" and edit["supplied"] == []
    assert (
        [Q[x["span"][0] : x["span"][1]] for x in edit["from_source"]]
        == [x["text"] for x in edit["from_source"]]
        == ["specific reef zones"]
    )


def test_a_possessive_is_resolved_to_the_antecedent_plus_a_recorded_suffix_and_no_source_span_is_invented_for_the_suffix():
    _, _, _, preps = _preps(Q, base.responder(), [CLAR_THEY, CLAR_ITS])
    prep = _find(preps, "relate to its expression")
    assert "relate to the coral effect's expression" in _text(prep)
    (edit,) = [e for e in prep["edits"] if e["op"] == "reference_resolved"]
    assert edit["rule"] == "possessive_singular_noun_phrase"
    assert [x["text"] for x in edit["from_source"]] == [
        "the",
        "coral effect",
    ]  # the source article travels with its noun
    (suffix,) = edit["supplied"]
    assert suffix["text"] == "'s" and suffix["by"].startswith("rule:") and "span" not in suffix


@pytest.mark.parametrize(
    "antecedent, why",
    [
        ("the reef zones", "plural"),
        ("growth, color and survival", "coordinated"),
        ("depth or color", "coordinated"),
    ],
)
def test_a_possessive_whose_safe_transformation_is_unclear_is_left_to_the_writer_with_the_referent_supplied(
    antecedent, why
):
    q = f"{antecedent} matter. what relates to their depth?"
    lo = q.index("their")
    clar = {"id": "RC-X", "refers_to": {"text": antecedent, "span": [0, len(antecedent)]}}
    edit, not_applied = prepare._reference_edit(q, clar, lo, lo + 5)
    assert edit is None and why in not_applied["reason"]
    assert not_applied["clarification"] == "RC-X" and not_applied["source_span"] == [lo, lo + 5]


def test_a_reference_word_outside_the_handled_shapes_is_not_edited_and_a_plain_singular_possessive_is():
    q = "the coral effect matters. what relates to whose depth?"
    clar = {"id": "RC-X", "refers_to": {"text": "coral effect", "span": [4, 16]}}
    lo = q.index("whose")
    edit, not_applied = prepare._reference_edit(q, clar, lo, lo + 5)
    assert edit is None and "not a reference shape" in not_applied["reason"]
    q2 = "the coral effect matters. what relates to its depth?"
    lo2 = q2.index("its")
    edit2, none = prepare._reference_edit(q2, clar, lo2, lo2 + 3)
    assert none is None and edit2["result"] == "the coral effect's"


def test_a_reference_that_cannot_be_prepared_stays_a_writer_instruction_and_says_why():
    growth = Q.index("growth, color, and survival")
    clar = {
        **CLAR_ITS,
        "id": "RC-J",
        "refers_to": {
            "span": [growth, growth + len("growth, color, and survival")],
            "phrase": "growth, color, and survival",
        },
    }
    result, _ = base.run(prompt_variant="prepared", clarifications=[CLAR_THEY, clar])
    prompt = _write_prompt(result, "specific pigments")
    assert "Not prepared by code" in prompt and "coordinated or punctuated" in prompt
    assert 'replace it with the exact source words "growth, color, and survival"' in prompt  # still asked of the writer
    kid = next(c for c in result["pass1"]["children"] if "specific pigments" in c["question"].lower())
    assert kid["preparation"]["not_applied"] and "its expression" in kid["preparation"]["original_extract_text"]


# ---- 2. a clarification-added cue -----------------------------------------------------------------------------------------------------------
QB = "which specific pigments relate to shell color? please return whether they relate to depth, and which kinds of depth."
QP = "which specific pigments relate to shell color? please return how they relate to depth."


def _respond_b(question):
    def respond(prompt, schema):
        if "requirements" in schema["properties"]:
            part = prompt.split("Part to read:\n", 1)[1] if "Part to read:\n" in prompt else ""
            if part.startswith("which specific"):
                return {
                    "requirements": [
                        tcp._item("specific pigments"),
                        tcp._item("specific pigments relate to shell color", kind="relationship"),
                    ]
                }
            if part.startswith("please return"):
                phrase = "whether they relate to depth" if "whether" in question else "how they relate to depth"
                extra = [tcp._item("which kinds of depth", kind="kinds")] if "kinds" in question else []
                return {"requirements": [tcp._item(phrase, kind="relationship"), *extra]}
            return {"requirements": []}
        if "ambiguities" in schema["properties"]:
            return {"ambiguities": []}
        return {"question": "What is asked?", "unresolved": []}

    return respond


def _adds(question, phrase, cue, cid="RC-A"):
    lo = question.index(phrase)
    return {
        "id": cid,
        "span": [lo, lo + len(phrase)],
        "phrase": phrase,
        "means": "both are asked, with direction where documented",
        "adds": [cue],
        "authorized_by": "tester",
    }


def _they(question, phrase="they relate to depth"):
    lo = question.index(phrase)
    return {
        "id": "RC-R",
        "span": [lo, lo + len(phrase)],
        "phrase": phrase,
        "reference_word": "they",
        "means": "the specific pigments",
        "authorized_by": "tester",
        "refers_to": _link(question, "specific pigments"),
    }


def test_a_clarification_added_how_is_inserted_after_the_source_whether_and_carries_no_source_span():
    parent, _, _, preps = _preps(QB, _respond_b(QB), [_they(QB), _adds(QB, "whether they relate to depth", "manner")])
    prep = _find(preps, "whether they relate")
    assert "whether and how specific pigments relate to depth" in _text(prep) and _text(prep).endswith(
        "kinds of depth."
    )
    (cue,) = [e for e in prep["edits"] if e["op"] == "cue_added"]
    assert cue["clarification"] == "RC-A" and cue["from_source"] == [] and cue["result"] == " and how"
    assert (
        QB[cue["inserted_after_source_span"][0] : cue["inserted_after_source_span"][1]]
        == "whether"
        == cue["anchor_text"]
    )
    assert cue["supplied"][0]["by"].startswith("RC-A adds manner") and "span" not in cue["supplied"][0]
    assert any("still asks 'how'" in r["text"] for r in prep["requirements"])


def test_a_clarification_added_whether_is_placed_before_the_sources_how():
    _, _, _, preps = _preps(QP, _respond_b(QP), [_they(QP), _adds(QP, "how they relate to depth", "polarity")])
    prep = _find(preps, "how they relate")
    assert "whether and how specific pigments relate to depth" in _text(prep)
    (cue,) = [e for e in prep["edits"] if e["op"] == "cue_added"]
    assert (
        cue["result"] == "whether and "
        and cue["from_source"] == []
        and cue["anchor_text"] == "how"
        and "inserted_before_source_span" in cue
    )


def test_a_cue_the_source_already_states_is_not_added_again():
    _, _, _, preps = _preps(
        Q, base.responder(), [CLAR_THEY, _adds(Q, "whether and how they relate to depth", "manner")]
    )
    prep = _find(preps, "whether and how they relate")
    assert not [e for e in prep["edits"] if e["op"] == "cue_added"]
    assert " and how and how" not in _text(prep)


def test_a_cue_whose_relationship_did_not_parse_is_not_placed_and_the_reason_is_recorded():
    q = tcp.Q6
    row = _adds(q, "frobnicate shell color", "manner")
    _, plans, _, preps = _preps(q, tcp._respond_q6, [row])
    prep = _find(preps, "frobnicate")
    assert not [e for e in prep["edits"] if e["op"] == "cue_added"]
    assert [n["cue"] for n in prep["not_applied"]] == ["how"] and "not parsed" in prep["not_applied"][0]["reason"]


QC = "in the coral effect, which specific pigments relate to shell color? please return whether they relate to depth, and which kinds of depth."


def _respond_c(prompt, schema):
    if "requirements" in schema["properties"]:
        part = prompt.split("Part to read:" + chr(10), 1)[1] if "Part to read:" + chr(10) in prompt else ""
        if part.startswith("in the coral"):
            return {
                "requirements": [
                    tcp._item("specific pigments"),
                    tcp._item("specific pigments relate to shell color", kind="relationship"),
                ]
            }
        if part.startswith("please return"):
            return {
                "requirements": [
                    tcp._item("whether they relate to depth", kind="relationship"),
                    tcp._item("which kinds of depth", kind="kinds"),
                ]
            }
        return {"requirements": []}
    if "ambiguities" in schema["properties"]:
        return {"ambiguities": []}
    return {"question": "What is asked?", "unresolved": []}


def test_an_approved_context_link_becomes_a_lead_in_and_an_unapproved_one_is_never_used():
    row = {
        **_adds(QC, "whether they relate to depth", "manner"),
        "means": "in the context of the coral effect: whether they relate to depth",
    }
    pending = {"clarification": "RC-A", "context_link": "in the context of"}
    _, _, _, off = _preps(QC, _respond_c, [row], [pending])
    prep = _find(off, "whether they relate")
    assert prep["prefix"] is None and "not researcher-approved" in prep["not_applied"][0]["reason"]
    _, _, _, on = _preps(
        QC, _respond_c, [row], [{**pending, "context_link_approved_by": "tester", "context_link_decision": "D-T"}]
    )
    prep = _find(on, "whether they relate")
    assert prep["prefix"] == "in the context of the coral effect,"
    (lead,) = [e for e in prep["edits"] if e["op"] == "context_prefix"]
    assert lead["decision"] == "D-T" and [x["text"] for x in lead["from_source"]] == ["the", "coral effect"]
    assert all(
        "span" not in x and x["by"].startswith(("RC-A context_link", "punctuation")) for x in lead["supplied"]
    )  # words the source never had


# ---- 3. a fragment's indispensable context, with or without a parsed parent relationship -----------------------------------------------------
def _frag_clar(question, frag, cid="RC-F"):
    return {
        "id": cid,
        "span": [question.index(frag), question.index(frag) + len(frag)],
        "phrase": frag,
        "means": "the scales used to measure the pigments asked about just before",
        "authorized_by": "tester",
        "refers_to": _link(question, "specific pigments"),
        "pairs": [_link(question, "specific pigments"), _link(question, "which scales")],
    }


def test_a_fragment_carries_its_parents_words_when_the_parents_relationship_parsed_and_the_carry_is_never_a_question():
    q = tcp.Q4
    _, _, _, preps = _preps(q, tcp._respond_q4, [_frag_clar(q, tcp.FRAG4)])
    prep = _find(preps, "using which scales")
    carry = prep["carry"]
    assert carry["text"] == "specific pigments relate to shell color" and carry["relationship_parsed"] is True
    assert q[carry["source_spans"][0][0] : carry["source_spans"][0][1]] == carry["text"]  # exact source words
    assert not (set(lx.tokens(carry["text"])) & prepare.QUESTION_WORDS) and "NOT a question" in carry["note"]


def test_a_fragment_carries_the_same_context_when_the_parents_relationship_did_not_parse():
    q = tcp.Q6
    _, plans, _, preps = _preps(q, tcp._respond_q6, [_frag_clar(q, tcp.FRAG4, "RC-F6")])
    parent_relations = [p["relation"] for p in plans if p.get("relation")]
    assert parent_relations and all(
        r["parse_status"] == "unparsed" for r in parent_relations
    )  # the fixture really is unparsed
    prep = _find(preps, "using which scales")
    assert (
        prep["carry"]["text"] == "specific pigments frobnicate shell color"
        and prep["carry"]["relationship_parsed"] is False
    )
    assert "parser is not needed" in prep["carry"]["relationship_note"]


def test_a_fragment_whose_pair_members_are_both_in_its_own_words_gets_no_carry_and_keeps_its_context_as_context_only():
    _, _, _, preps = _preps(Q2, _respond_q2, [CLAR_FRAGMENT, CLAR_UNIT])
    prep = _find(preps, "which reefs and how was this measured")
    assert prep["carry"] is None and not prep["not_prepared"]
    result = run_engine(
        Q2,
        ScriptedModel(_respond_q2),
        repair=False,
        prompt_variant="prepared",
        clarifications=[CLAR_FRAGMENT, CLAR_UNIT],
    )
    prompt = _write_prompt(result, "which reefs")
    assert "CONTINUES the question" in prompt and "Carried context" not in prompt


def test_a_carry_that_cannot_be_prepared_safely_says_precisely_what_is_missing(monkeypatch):
    monkeypatch.setattr(prepare, "CARRY_MAX_CHARS", 5)
    q = tcp.Q4
    result = run_engine(
        q,
        ScriptedModel(tcp._respond_q4),
        repair=False,
        prompt_variant="prepared",
        clarifications=[_frag_clar(q, tcp.FRAG4)],
    )
    kid = next(c for c in result["pass1"]["children"] if c.get("clarified_fragment"))
    (missing,) = kid["preparation"]["not_prepared"]
    assert kid["preparation"]["carry"] is None and "too long" in missing["reason"]
    prompt = _write_prompt(result, "scales")
    assert "Not prepared by code" in prompt and missing["reason"] in prompt and "Carried context" not in prompt


def test_an_approved_joining_word_is_offered_with_the_carry_and_an_unapproved_one_is_not():
    q = tcp.Q4
    row = {"clarification": "RC-F", "context_link": "measure"}
    _, _, _, pending = _preps(q, tcp._respond_q4, [_frag_clar(q, tcp.FRAG4)], [row])
    assert _find(pending, "using which scales")["join"] is None  # engine-recorded, not researcher-approved
    _, _, _, approved = _preps(
        q,
        tcp._respond_q4,
        [_frag_clar(q, tcp.FRAG4)],
        [{**row, "context_link_approved_by": "tester", "context_link_decision": "D-T"}],
    )
    join = _find(approved, "using which scales")["join"]
    assert join["text"] == "measure" and join["decision"] == "D-T" and join["approved_by"] == "tester"


# ---- 4. a compound operation is legal; a NEW ask is still caught by the existing checks --------------------------------------------------------------
def _run_prepared(overrides, clars, question=Q, respond=None):
    model = ScriptedModel(respond or base.responder(overrides))
    return run_engine(question, model, repair=False, prompt_variant="prepared", clarifications=clars), model


def _kid(result, needle):
    return next(c for c in result["pass1"]["children"] if needle in c["question"].lower())


@pytest.mark.parametrize(
    "wording",
    [
        "Please return whether and how specific reef zones relate to depth, which kinds of depth.",  # the prepared request, unchanged
        "Whether and how the specific reef zones relate to depth, which kinds of depth",  # a compound operation, kept whole
    ],
)
def test_a_compound_question_operation_is_kept_whole_and_raises_no_operator_finding(wording):
    result, _ = _run_prepared({"whether and how": {"question": wording}}, [CLAR_THEY])
    kid = (
        _kid(result, "specific reef zones relate to depth")
        if "Please" in wording
        else _kid(result, "whether and how the specific")
    )
    assert not {"operator_dropped", "operator_added"} & _kinds(kid), _kinds(kid)


def test_a_compound_which_and_how_pair_stays_whole_in_a_fragment_with_no_operator_finding():
    wording = "Which reefs and how was this measured?"
    result = run_engine(
        Q2,
        ScriptedModel(_wrap(_respond_q2, "which reefs", wording)),
        repair=False,
        prompt_variant="prepared",
        clarifications=[CLAR_FRAGMENT, CLAR_UNIT],
    )
    assert not {"operator_dropped", "operator_added"} & _kinds(_kid(result, "which reefs"))


def _wrap(respond, owned, wording):
    def r(prompt, schema):
        if "requirements" in schema["properties"] or "ambiguities" in schema["properties"]:
            return respond(prompt, schema)
        if owned in base._owned_first_line(prompt):
            return {"question": wording, "unresolved": []}
        return respond(prompt, schema)

    return r


@pytest.mark.parametrize(
    "wording, kind",
    [
        ("Using which scales are the specific pigments that relate to shell color, and which kinds?", "operator_added"),
        ("Which specific pigments relate to shell color, and using which scales?", "operator_added"),
    ],
)
def test_an_added_unrelated_ask_or_a_restated_ancestor_question_is_still_caught(wording, kind):
    q = tcp.Q4
    result = run_engine(
        q,
        ScriptedModel(_wrap(tcp._respond_q4, "using which scales", wording)),
        repair=False,
        prompt_variant="prepared",
        clarifications=[_frag_clar(q, tcp.FRAG4)],
    )
    kid = next(c for c in result["pass1"]["children"] if c.get("clarified_fragment"))
    assert kind in _kinds(kid) and kid["status"] != "candidate"


def test_dropping_half_of_a_compound_operation_is_still_a_finding():
    result, _ = _run_prepared(
        {"whether and how": {"question": "Whether the specific reef zones relate to depth, which kinds of depth"}},
        [CLAR_THEY],
    )
    assert (
        "operator_dropped" in _kinds(_kid(result, "whether the specific"))
        or _kid(result, "whether the specific")["status"] != "candidate"
    )


# ---- 5. edits are recorded apart from the model's wording, and every edit is traceable ----------------------------------------------------------
def test_the_model_wording_is_stored_and_shown_exactly_apart_from_the_deterministic_preparation():
    sentinel = "wHATever  the model said, VERBATIM?"
    result, _ = _run_prepared({"whether and how": {"question": sentinel}}, [CLAR_THEY, CLAR_ITS])
    kid = next(c for c in result["pass1"]["children"] if c["question"] == sentinel)
    assert kid["preparation"]["prepared_request"] != sentinel and sentinel not in json.dumps(kid["preparation"])
    nl = views.render_natural_language(views.natural_language_view(result))
    assert sentinel in nl  # exactly what the model returned
    assert kid["preparation"]["prepared_request"] not in nl  # the prepared request is not presented as the child
    contract = views.contract_view(result)
    entry = next(c for c in contract["children"] if c["child_id"] == kid["child_id"])
    assert entry["preparation"]["extract_after"] == " ".join(e["text"] for e in kid["preparation"]["extract_entries"])
    assert (
        entry["preparation"]["lead_in"] == kid["preparation"]["prefix"]
        and entry["preparation"]["edits"] == kid["preparation"]["edits"]
    )
    assert "preparation (by code, before the writer)" in views.render_contract(contract)


def test_every_edit_names_exactly_where_its_words_came_from_and_supplies_no_source_span_for_words_that_were_not_in_the_source():
    result, _ = _run_prepared(None, [CLAR_THEY, CLAR_ITS])
    q = result["parent_contract"]["original_question"]
    ids = {c["id"] for c in result["parent_contract"]["clarifications"]}
    seen = set()
    for kid in result["pass1"]["children"]:
        prep = kid.get("preparation")
        for e in (prep or {}).get("edits", []) + [x for x in ((prep or {}).get("carry") or {}).get("edits", [])]:
            seen.add(e["op"])
            for src in e["from_source"]:
                assert q[src["span"][0] : src["span"][1]] == src["text"]
            for sup in e["supplied"]:
                assert "span" not in sup and (
                    "rule:" in sup["by"] or any(cid in sup["by"] for cid in ids) or sup["by"] == "punctuation"
                )
            if e["op"] in ("cue_added", "context_prefix"):
                assert e["clarification"] in ids
            if e["op"] == "cue_added":
                assert e["from_source"] == []
    assert {"reference_resolved", "terminal_punctuation"} <= seen


def test_the_prompt_and_the_contract_trace_to_the_same_requirements():
    result, _ = _run_prepared(None, [CLAR_THEY, CLAR_ITS])
    kid = next(
        c for c in result["pass1"]["children"] if c.get("preparation", {}).get("active") and c["preparation"]["edits"]
    )
    prompt = next(
        c["prompt"]
        for c in result["calls"]
        if c["task"] == "children.write" and all(line in c["prompt"] for line in kid["preparation"]["prepared_lines"])
    )
    for r in kid["preparation"]["requirements"]:
        assert r["text"] in prompt
    for e in kid["preparation"]["edits"]:
        assert e["clarification"] is None or e["clarification"] in prompt


def test_a_reference_replaced_by_code_is_no_longer_a_writer_instruction_but_an_unresolved_one_still_is():
    result, _ = _run_prepared(None, [CLAR_THEY])  # its is deliberately NOT clarified
    zones = _write_prompt(result, "whether and how")
    assert "replace it with the exact source words" not in zones and "already replaced by code" in zones
    pigments = _write_prompt(result, "specific pigments")
    assert 'Not clarified (keep as written, report under "unresolved")' in pigments and '"its"' in pigments


# ---- 6. nothing to prepare -> byte-identical to the historical baseline; historical variants untouched -------------------------------------------
def test_a_child_with_nothing_to_prepare_gets_exactly_the_corrected_full_prompt():
    parent, plans, by_id = _state(Q, base.responder(), [])
    inactive = active = 0
    for plan in plans:
        if plan["kind"] != "anchor":
            continue
        sub, prep = prompts_prepared.prepared_for(parent, plan, plans, by_id)
        same = prompts_prepared.render_prepared(parent, sub, prep) == prompts.render_full(sub)
        if prep["active"]:
            active += 1
            assert not same
        else:
            inactive += 1
            assert same
    assert inactive and active  # both paths are exercised


def test_the_historical_renderers_and_frozen_v3_are_unchanged_since_the_frozen_snapshot():
    snap = V7 / "baseline_snapshot" / "decompose"
    if not snap.exists():
        pytest.skip("the local v7 baseline snapshot is not present")

    def funcs(path, names):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        return {
            n.name: ast.dump(n)
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.Assign)) and getattr(n, "name", None) in names
        }

    kept = (
        "render_full",
        "render_lean",
        "substance",
        "_join_extract",
        "_annotated",
        "_relationship_facts",
        "_means_label",
        "_line",
        "applicable_safeguards",
    )
    assert funcs(DECOMPOSE / "prompts.py", kept) == funcs(snap / "prompts.py", kept) and len(
        funcs(snap / "prompts.py", kept)
    ) == len(kept)
    v3 = ("child_prompt", "context_block", "_exact_words", "child_context", "_inherited_extracts", "excerpts")
    assert funcs(DECOMPOSE / "children.py", v3) == funcs(snap / "children.py", v3) and len(
        funcs(snap / "children.py", v3)
    ) == len(v3)
    for name in ("SAFEGUARDS", "HEADER", "LEAN_HEADER", "MATCHED_LIMITS"):
        a = next(
            n
            for n in ast.parse((DECOMPOSE / "prompts.py").read_text(encoding="utf-8")).body
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == name
        )
        b = next(
            n
            for n in ast.parse((snap / "prompts.py").read_text(encoding="utf-8")).body
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == name
        )
        assert ast.dump(a) == ast.dump(b), name


def test_the_prepared_variant_shares_the_corrected_full_schema_cap_limits_and_safeguards():
    a, b = prompts.settings_for("corrected-full"), prompts.settings_for("prepared")
    for key in ("schema", "cap", "limits", "extract_mode", "preflight"):
        assert a[key] == b[key], key
    assert b["variant"] == "prepared" and "prepared" in prompts.VARIANTS
    assert set(prompts.SAFEGUARDS) == {
        "FORM",
        "EDITS",
        "NO_LINK",
        "PROTECTED",
        "RELATION",
        "UNRESOLVED",
        "NO_PASTE",
        "SCOPE",
    }


# ---- 7. terminal punctuation (offline regression: a request's closing mark is kept only when the extract ends where its sentence ends) -------------
@pytest.mark.parametrize(
    "question, quote, expected",
    [
        ("What is a coral effect?", "What is a coral effect", "What is a coral effect?"),
        (
            "Please list the risk factors for stroke.",
            "the risk factors for stroke",
            "Please list the risk factors for stroke.",
        ),
    ],
)
def test_a_closing_mark_is_kept_when_the_extract_ends_at_its_sentence_and_added_from_the_source_span(
    question, quote, expected
):
    model = tcp._single(question, quote)
    parent = build_parent_contract(CallLog(model), question)
    plans = ch.plan_children(parent)
    by_id = ch.by_id_map(parent)
    ctx = ch.child_context(parent, plans[0], by_id, plans=plans, governing_operation=True)
    prep = prepare.prepare_child(parent, plans[0], plans, by_id, ctx)
    assert _text(prep) == expected
    (edit,) = [e for e in prep["edits"] if e["op"] == "terminal_punctuation"]
    span = edit["from_source"][0]["span"]
    assert question[span[0] : span[1]] == expected[-1] and edit["supplied"] == []


def test_an_extract_that_already_ends_with_its_mark_gets_no_second_one():
    question = "What is a coral effect?"
    parent = build_parent_contract(CallLog(tcp._single(question, "a coral effect?")), question)
    plans = ch.plan_children(parent)
    by_id = ch.by_id_map(parent)
    ctx = ch.child_context(parent, plans[0], by_id, plans=plans, governing_operation=True)
    prep = prepare.prepare_child(parent, plans[0], plans, by_id, ctx)
    assert _text(prep) == question and not prep["edits"] and not prep["active"]


def test_no_closing_mark_is_added_mid_sentence_or_twice():
    _, _, _, preps = _preps(Q, base.responder(), [])
    mid = _find(preps, "please return specific reef zones")
    assert not [e for e in mid["edits"] if e["op"] == "terminal_punctuation"] and not _text(mid).endswith(("?", "."))
    for _, prep in preps.values():
        assert not _text(prep).endswith(("??", "..", "?.", ".?"))


# ---- 8. isolation --------------------------------------------------------------------------------------------------------------------------------
def test_the_new_modules_never_read_a_file_or_name_the_held_out_reference():
    forbidden = (
        "intent_reference",
        "expected_evidence",
        "reference_correspondence",
        "hier-decomp",
        "children_v2",
        "BLIND_EVALUATION",
    )
    for name in ("prepare.py", "prompts_prepared.py"):
        text = (DECOMPOSE / name).read_text(encoding="utf-8")
        assert "open(" not in text and "Path(" not in text and "read_text" not in text, name  # pure: no I/O of any kind
        assert not [n for n in forbidden if n in text], name
    text = (DECOMPOSE / "wording_check.py").read_text(encoding="utf-8")
    assert (
        not [n for n in forbidden if n in text] and "q_aib" not in text
    )  # the runner names neither the reference nor a real request
    assert "reference_diagnostic" not in text and "reference_compare" not in text


# ---- 9. the bounded runner -----------------------------------------------------------------------------------------------------------------------
def _inputs():
    needed = [V7 / "inputs" / "primary_request.txt", V7 / "inputs" / "frozen_v6" / "model_calls.jsonl"]
    if not all(p.exists() for p in needed) or not (AIB / "clarifications" / "q_aib.v3.approved.json").exists():
        pytest.skip("the local v6/v7 development artifacts are not present")
    return wording_check.load_inputs(
        V7 / "inputs",
        {
            "approved": AIB / "clarifications" / "q_aib.v3.approved.json",
            "decisions": AIB / "clarifications" / "q_aib.v6.researcher_decisions.json",
        },
    )


def test_replaying_the_recorded_inventory_reproduces_the_frozen_plans_and_all_frozen_prompts_byte_for_byte():
    inp = _inputs()
    ident = wording_check.replay_identity(inp)
    assert ident["identical"] and ident["new_model_calls"] == 0 and ident["plans_compared"] == 11, ident
    base_ident = wording_check.baseline_prompt_identity(inp)
    assert base_ident["all_identical"] and base_ident["count"] == 11
    assert all(r["sha256_rebuilt"] == r["sha256_frozen"] for r in base_ident["children"])


def test_the_bounded_run_writes_only_the_listed_children_with_at_most_four_calls_and_saves_every_prompt(tmp_path):
    inp = _inputs()
    prep = wording_check.prepared_prompts(inp)
    assert set(prep) == set(wording_check.CONFIG["children"]) and all(
        r["prepared"] != r["baseline"] for r in prep.values()
    )
    calls = []

    def writer(prompt, schema):
        calls.append(prompt)
        row = next(r for r in prep.values() if r["prepared"] == prompt)
        return {"question": row["preparation"]["prepared_request"], "unresolved": []}

    summary = wording_check.run_check(tmp_path / "run", lambda: ScriptedModel(writer), live=False, inp=inp)
    assert summary["outcome"] == "COMPLETE" and summary["replay_identity_identical"]
    assert len(calls) == 4 and [w[0] for w in summary["written"]] == ["c6", "c8", "c9", "c11"]
    records = wording_check.read_jsonl(tmp_path / "run" / "model_calls.jsonl")
    assert len(records) == 4 and {r["task"] for r in records} == {
        "children.write"
    }  # the inventory was replayed, not called
    assert {r["prompt"] for r in records} == {r["prepared"] for r in prep.values()}
    nl = json.loads((tmp_path / "run" / "artifacts" / "VIEW_natural_language.json").read_text(encoding="utf-8"))
    assert nl and (tmp_path / "run" / "artifacts" / "VIEW_contract.md").exists()
    children = json.loads((tmp_path / "run" / "artifacts" / "02_pass1_children.json").read_text(encoding="utf-8"))[
        "children"
    ]
    assert [c["kind"] for c in children if c["child_id"] not in wording_check.CONFIG["children"]] == [
        "not_selected"
    ] * 7
    rows = wording_check.comparison(inp["frozen_children"], children, prep)
    assert [r["child"] for r in rows] == ["c6", "c8", "c9", "c11"] and rows[0]["frozen"][
        "status"
    ] == "semantic_conflict"


def test_a_call_that_does_not_parse_halts_the_whole_check_and_nothing_is_retried(tmp_path):
    inp = _inputs()
    calls = []

    def bad(prompt, schema):
        calls.append(prompt)
        return "not json at all"

    summary = wording_check.run_check(tmp_path / "run", lambda: ScriptedModel(bad), live=False, inp=inp)
    assert summary["outcome"] == "INCOMPLETE" and "halted" in summary["reason"] and len(calls) == 1
    assert (tmp_path / "run" / "HALTED.json").exists()


def test_the_run_refuses_without_the_freeze_the_gate_and_the_researchers_authorization_of_that_exact_gate(tmp_path):
    frozen = {"a": 1, "freeze_sha256": "f" * 64}
    gate = tmp_path / "GATE.md"
    gate.write_text("gate citing " + frozen["freeze_sha256"], encoding="utf-8")
    auth = tmp_path / "AUTHORIZATION.json"
    with pytest.raises(RuntimeError, match="changed since the freeze"):
        wording_check.preconditions(frozen, {"a": 2, "freeze_sha256": "e" * 64}, gate, auth, tmp_path / "run")
    with pytest.raises(PermissionError, match="no authorization record"):
        wording_check.preconditions(frozen, frozen, gate, auth, tmp_path / "run")
    auth.write_text(
        json.dumps({"gate_sha256": "0" * 64, "authorized_by": "Cliff", "authorization_quote": "yes"}), encoding="utf-8"
    )
    with pytest.raises(PermissionError, match="different gate"):
        wording_check.preconditions(frozen, frozen, gate, auth, tmp_path / "run")
    gate_hash = hashlib.sha256(gate.read_bytes()).hexdigest()
    auth.write_text(
        json.dumps({"gate_sha256": gate_hash, "authorized_by": "Cliff", "authorization_quote": "I authorize it"}),
        encoding="utf-8",
    )
    (tmp_path / "run").mkdir()
    with pytest.raises(RuntimeError, match="already exists"):
        wording_check.preconditions(frozen, frozen, gate, auth, tmp_path / "run")
    (tmp_path / "run").rmdir()
    assert wording_check.preconditions(frozen, frozen, gate, auth, tmp_path / "run")["authorized_by"] == "Cliff"
    other = tmp_path / "GATE2.md"
    other.write_text("a gate that does not cite the freeze", encoding="utf-8")
    with pytest.raises(RuntimeError, match="does not cite the freeze"):
        wording_check.preconditions(frozen, frozen, other, auth, tmp_path / "run2")


def test_the_check_config_pins_the_bounds_the_gate_will_state():
    c = wording_check.CONFIG
    assert c["children"] == ["c6", "c8", "c9", "c11"] and c["max_writer_calls"] == 4 and c["max_calls"] == 4
    assert c["repair"] is False and c["automatic_retries"] is False and c["think"] is False
    assert c["options"]["temperature"] == 0 and c["options"]["seed"] == 42
    assert c["model"] == integrated.CONFIG["model"] and c["endpoint"] == integrated.CONFIG["endpoint"]
    assert c["variant"] == "prepared" and c["baseline_variant"] == "corrected-full"
