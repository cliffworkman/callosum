"""Model-free proof of the v5 correction pass: the explicit no-decomposition outcome, requirement records with provenance and pending
state, role-sensitive word authorization, relationship/pair/reference checks that report the limit of a lexical check, and the
output-acceptance rules. Synthetic requests only (no q_lld/q_builtenv, no real model, nothing sent anywhere)."""

from __future__ import annotations

import copy
import dataclasses
import re
from collections import Counter
from pathlib import Path

import pytest

import experiments.ask_cli_revised.decompose.test_decompose as base
import experiments.ask_cli_revised.decompose.test_tree as tt
from experiments.ask_cli_revised.decompose import children as ch
from experiments.ask_cli_revised.decompose import clarifications, passthrough, prompts, requirements
from experiments.ask_cli_revised.decompose.calllog import CallLog
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ScriptedModel, StopAwareCall
from experiments.ask_cli_revised.decompose.parent import build_parent_contract
from experiments.ask_cli_revised.decompose.test_relations import CLAR, LO, PHRASE, Q


# ---- scripted models ---------------------------------------------------------------------------------------------------------------
def _scripted(units: dict, *, whole=None, writer=None, ambiguities=None) -> ScriptedModel:
    """Answers the three inventory schemas from a table keyed by the start of each unit, and the writer from ``writer(prompt)``."""

    def respond(prompt: str, schema: dict):
        props = schema["properties"]
        if "requirements" in props:
            if "Part to read:\n" in prompt:
                part = prompt.split("Part to read:\n", 1)[1].strip()
                key = next((k for k in units if part.startswith(k)), None)
                return {"requirements": units.get(key, [])}
            return {"requirements": whole if whole is not None else []}
        if "ambiguities" in props:
            return {"ambiguities": ambiguities or []}
        return writer(prompt) if writer else {"question": "What is asked?", "unresolved": []}

    return ScriptedModel(respond)


def _item(*quotes: str, kind: str = "requested_item") -> dict:
    return {"kind": kind, "quotes": list(quotes), "note": ""}


def _single(question: str, quote: str, **kw):
    """One unit, one obligation, the same obligation from the whole-request call: what a plausible inventory returns."""
    obligations = [_item(quote)]
    key = question.split()[0]
    kw.setdefault(
        "writer", lambda prompt: {"question": question, "unresolved": []}
    )  # the best case: a writer that changes nothing
    return _scripted({key: obligations}, whole=obligations, **kw)


def _tasks(result: dict) -> Counter:
    return Counter(r["task"] for r in result["calls"])


CONTROLS = ["What is the anomalous-is-bad bias?", "What is a placebo effect?"]


def _quote(question: str, shape: str) -> str:
    stripped = question.rstrip("?")
    return re.sub(r"^\s*what is\s+", "", stripped, flags=re.I) if shape == "noun_phrase" else stripped


# ---- 1. the explicit "no decomposition needed" outcome ---------------------------------------------------------------------------
@pytest.mark.parametrize("variant", ["lean", "corrected-full", "v3"])
@pytest.mark.parametrize("shape", ["noun_phrase", "whole_question"])
@pytest.mark.parametrize("question", CONTROLS)
def test_a_complete_one_part_request_is_kept_exactly_and_the_writer_is_not_called(question, shape, variant):
    model = _single(question, _quote(question, shape))
    result = run_engine(question, model, prompt_variant=variant)
    dec = result["decomposition_decision"]
    assert dec["outcome"] == "no_decomposition_needed" and dec["applied"] and not dec["blocking"]
    (child,) = result["pass1"]["children"]
    assert child["kind"] == "passthrough" and child["status"] == "no_decomposition_needed"
    assert child["question"] == question and child["is_decomposition"] is False  # exact wording and form
    assert child["node"]["parent"] == "R"
    tasks = _tasks(result)
    assert tasks["children.write"] == 0 and sum(v for k, v in tasks.items() if k.startswith("parent.")) == 3
    assert result["pass2"] is None and dec["model_calls_avoided"]["writer_calls"] == 1
    # the writer was the ONLY difference: with the pass-through off, the same run makes exactly one more call
    forced = run_engine(
        question, _single(question, _quote(question, shape)), prompt_variant=variant, passthrough_enabled=False
    )
    assert len(forced["calls"]) == len(result["calls"]) + 1 and _tasks(forced)["children.write"] == 1


def test_no_decomposition_never_means_the_request_was_answered():
    question = CONTROLS[1]
    result = run_engine(question, _single(question, _quote(question, "noun_phrase")))
    (child,) = result["pass1"]["children"]
    assert child["downstream"]["ask_execution"] == "run_the_original_request_once_through_the_normal_ask_path"
    assert child["downstream"]["answer_state"] == "not_executed"
    summary = result["pass1"]["reconciliation"]["summary"]
    root = result["pass1"]["reconciliation"]["question_tree"]["root"]
    assert summary["passed_through_children"] == ["c1"] and summary["answer_state"] == "not_executed"
    assert root["answer_state"] == "not_executed" and "never means" in root["note"]  # closure is a WRITING state only
    assert result["manifest"]["answer_state"] == "not_executed"
    assert not result["pass1"]["reconciliation"]["unresolved"]  # decomposition-complete, still not answered


def test_a_one_part_imperative_stays_an_imperative_and_is_kept_exactly():
    question = "Please list the risk factors for stroke."
    result = run_engine(question, _single(question, "the risk factors for stroke"))
    assert result["decomposition_decision"]["outcome"] == "no_decomposition_needed"
    assert result["pass1"]["children"][0]["question"] == question


def test_a_zero_obligation_inventory_is_uncertain_and_is_not_evidence():
    question = CONTROLS[1]
    result = run_engine(question, _scripted({}))
    dec = result["decomposition_decision"]
    assert dec["outcome"] == "uncertain" and not dec["applied"]
    assert "not evidence" in dec["basis"] and "exactly_one_written_anchor" in dec["blocking"]
    assert [c["kind"] for c in result["pass1"]["children"]] == ["unit_level"]  # the existing path, unresolved as before


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What is a placebo effect and how is it measured?", "uncertain"),  # one broad obligation over two requests
        (
            "What is a placebo effect, how is it measured, which drugs cause it?",
            "decompose",
        ),  # the cues split it: not a pass-through either
        ("What is a placebo effect how is it measured", "uncertain"),  # no punctuation, two request heads
        ("Please list the risk factors and describe their treatments.", "uncertain"),
        (
            "What is the relationship between sleep and memory?",
            "uncertain",
        ),  # a coordinator: not established either way
        (
            "What is a placebo effect? How is it measured?",
            "uncertain",
        ),  # two units but ONE broad obligation was returned
    ],
)
def test_one_broad_obligation_is_not_proof_that_the_request_is_one_thread(question, expected):
    whole = question.rstrip("?.")
    model = _scripted({question.split()[0]: [_item(whole)]}, whole=[_item(whole)])
    result = run_engine(question, model)
    dec = result["decomposition_decision"]
    assert dec["outcome"] == expected and not dec["applied"]
    assert result["pass1"]["children"][0]["kind"] != "passthrough" and _tasks(result)["children.write"] >= 1


def test_two_anchor_obligations_are_a_decomposition_by_the_inventory():
    question = "What is a placebo effect? How is it measured?"
    units = {"What is": [_item("a placebo effect")], "How is": [_item("How is it measured")]}
    dec = run_engine(question, _scripted(units))["decomposition_decision"]
    assert dec["outcome"] == "decompose" and not dec["applied"]


def test_an_open_reference_or_an_applicable_clarification_or_a_subset_run_blocks_the_pass_through():
    q = "What does it cause?"
    dec = run_engine(q, _single(q, "What does it cause"))["decomposition_decision"]
    assert dec["outcome"] == "uncertain" and "no_open_reference_or_ambiguity" in dec["blocking"]
    lo = q.index("it")
    clar = {
        "id": "RC-X",
        "span": [lo, lo + 2],
        "phrase": "it",
        "reference_word": "it",
        "means": "the effect",
        "authorized_by": "tester",
    }
    dec = run_engine(q, _single(q, "What does it cause"), clarifications=[clar])["decomposition_decision"]
    assert dec["outcome"] == "uncertain" and "no_clarification_or_restored_context_applies" in dec["blocking"]
    question = CONTROLS[1]
    sub = run_engine(question, _single(question, _quote(question, "noun_phrase")), only=["c1"])
    assert (
        sub["decomposition_decision"]["outcome"] == "no_decomposition_needed"
        and not sub["decomposition_decision"]["applied"]
    )
    assert (
        sub["pass1"]["children"][0]["kind"] == "generated"
        and "subset run" in sub["decomposition_decision"]["not_applied_because"]
    )


def test_two_unrelated_subjects_make_the_single_background_subject_limit_visible():
    question = "In older adults, what is the effect of caffeine on sleep? Which drugs treat tinnitus?"
    units = {
        "In older": [_item("what is the effect of caffeine on sleep")],
        "Which drugs": [_item("Which drugs treat tinnitus")],
    }

    def writer_for(second: str):
        def writer(prompt: str):
            asks_drugs = "which drugs" in prompt.lower() and "effect of caffeine" not in prompt.lower()
            return {"question": second if asks_drugs else "What is the effect of caffeine on sleep?", "unresolved": []}

        return writer

    result = run_engine(question, _scripted(units, writer=writer_for("Which drugs treat tinnitus?")), repair=False)
    assert result["decomposition_decision"]["outcome"] == "decompose"
    summary = result["pass1"]["reconciliation"]["summary"]
    scope = summary["background_subject_scope"]
    assert scope["single"] and scope["subject"] and "first source unit only" in scope["derived_from"]
    assert scope["unverified_for"], "a question that never states the derived subject must be named"
    assert any("English-only" in x for x in summary["known_limitations"])
    for cid in scope["unverified_for"]:  # named, and never a clean success
        kid = next(c for c in result["pass1"]["children"] if c["child_id"] == cid)
        assert cid not in summary["successful_children"] and kid["status"] != "candidate"
        assert any(f["flag"] == "background_subject_scope_unverified" for f in kid["flags"])
    # a writer that copies the first subject into the unrelated question is caught, not accepted
    copied = run_engine(
        question, _scripted(units, writer=writer_for("In older adults, which drugs treat tinnitus?")), repair=False
    )
    kid = next(c for c in copied["pass1"]["children"] if "tinnitus" in c["question"])
    assert kid["status"] == "semantic_review_required" and "relation_word_added" in _kinds(kid)


# ---- 2. clarification requirements: provenance, pending state, expressible without exempting a word class --------------------------
MEAN = {
    "id": "RC-Q",
    "span": [LO, LO + len(PHRASE)],
    "phrase": PHRASE,
    "means": "whether and how the reef zones relate to depth, including the documented direction where supported",
    "authorized_by": "tester",
}


def _expr(**kw) -> list[dict]:
    row = {
        "kind": "qualifier_expression",
        "text": "where supported",
        "function": "conditional_qualification",
        "recorded_by": "engine author",
    }
    return [{"clarification": "RC-Q", "requirements": [{**row, **kw}]}]


def _wording(text: str, ann=None):
    result, _ = base.run(
        {"whether and how": {"question": text}},
        repair=False,
        clarifications=[CLAR, MEAN],
        clarification_annotations=ann,
    )
    kid = next(c for c in result["pass1"]["children"] if c["question"] == text)
    return kid, result


WHERE = "Whether and how the specific reef zones relate to depth where supported, which kinds of depth"


def _kinds(kid) -> set:
    return {f["kind"] for f in kid["edit_ledger"]["flags"] if f["class"] != "info"}


def test_where_supported_is_expressible_only_as_that_exact_expression_and_stays_pending_until_the_researcher_decides():
    kid, result = _wording(WHERE, _expr())
    assert "operator_added" not in _kinds(kid) and not kid["diagnostics"]["hard_fail"]
    assert kid["status"] == "pending_researcher_confirmation"  # a QUALIFIED result, never an unqualified clean one
    assert kid["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]
    op = next(o for o in kid["edit_ledger"]["ops"] if o["op"] == "authorized_expression")
    assert op["authority"] == requirements.PENDING and op["role"] == "expression" and op["clarification"] == "RC-Q"
    rec = next(
        r
        for c in result["parent_contract"]["clarifications"]
        for r in c["requirements"]
        if r["kind"] == "qualifier_expression"
    )
    # three different questions, kept apart
    assert (rec["in_approved_clarification"], rec["expression"], rec["required_in_child"]) == (
        True,
        "permitted_pending_confirmation",
        "undecided",
    )
    assert any(d["id"] == rec["id"] for d in result["manifest"]["pending_researcher_decisions"])
    # no other where/if/when is exempted, and the same words outside qualifier position stay protected
    for text, word in (
        ("Whether and how the specific reef zones relate to depth, where is the depth, which kinds of depth", "where"),
        ("Whether and how the specific reef zones relate to depth if supported, which kinds of depth", "if"),
        ("Whether and how the specific reef zones relate to depth when supported, which kinds of depth", "when"),
    ):
        bad, _ = _wording(text, _expr())
        assert bad["status"] == "semantic_conflict" and any(
            o["text"].lower() == word for o in bad["edit_ledger"]["ops"] if o["op"] == "operation_change"
        ), text
    # without a recorded expression the same words are the conflict they always were
    plain, _ = _wording(WHERE)
    assert plain["status"] == "semantic_conflict" and "operator_added" in _kinds(plain)


def test_only_the_researcher_can_approve_or_require_wording_and_an_approval_removes_the_pending_state():
    kid, _ = _wording(WHERE, _expr(approved_by="tester"))
    assert kid["status"] == "candidate" and "pending_authority_used" not in _kinds(kid)
    dropped, _ = _wording(
        "Whether and how the specific reef zones relate to depth, which kinds of depth",
        _expr(approved_by="tester", required_in_child="required"),
    )
    assert dropped["status"] == "semantic_conflict" and "required_qualification_missing" in _kinds(dropped)
    kept, _ = _wording(WHERE, _expr(approved_by="tester", required_in_child="required"))
    assert kept["status"] == "candidate"
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    clarifications.apply(parent, [CLAR, MEAN])
    with pytest.raises(clarifications.ClarificationError, match="only the researcher can make wording required"):
        clarifications.annotate(parent, _expr(required_in_child="required"))
    with pytest.raises(clarifications.ClarificationError, match="not verbatim in the approved meaning"):
        clarifications.annotate(parent, _expr(text="when documented"))
    with pytest.raises(clarifications.ClarificationError, match="declared function"):
        clarifications.annotate(parent, _expr(function=None))
    detail = {
        "clarification": "RC-Q",
        "requirements": [{"kind": "detail", "text": "documented direction", "approved_by": "tester"}],
    }
    with pytest.raises(clarifications.ClarificationError, match="undecided until the researcher decides"):
        clarifications.annotate(parent, [detail])


def test_an_undecided_detail_is_pending_and_a_child_that_uses_it_is_a_review_never_a_conflict_or_a_clean_result():
    detail = [
        {
            "clarification": "RC-Q",
            "requirements": [
                {"kind": "detail", "text": "documented direction", "evidence_words": ["documented", "direction"]}
            ],
        }
    ]
    used, result = _wording(
        "Whether and how the specific reef zones relate to depth, documented direction, which kinds of depth", detail
    )
    assert used["status"] == "semantic_review_required" and "clarification_detail_pending" in _kinds(used)
    assert not used["diagnostics"]["hard_fail"]
    left_out, _ = _wording("Whether and how the specific reef zones relate to depth, which kinds of depth", detail)
    assert left_out["status"] == "candidate"  # nobody has decided it is required, so omitting it fails nothing
    pending = {d["id"] for d in result["manifest"]["pending_researcher_decisions"]}
    assert "RC-Q#detail:documented-direction" in pending


def test_engine_recorded_joining_words_are_pending_and_a_researcher_confirmation_clears_it():
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    clarifications.apply(parent, [CLAR, MEAN])
    row = {"clarification": "RC-Q", "context_link": "the reef zones"}
    clarifications.annotate(parent, [row])
    assert parent["clarifications"][1]["context_link"]["authority"] == requirements.PENDING
    assert any(d["kind"] == "context_link" for d in requirements.pending_decisions(parent))
    clarifications.annotate(parent, [{**row, "context_link_approved_by": "tester"}])
    assert parent["clarifications"][1]["context_link"]["authority"] == requirements.APPROVED
    assert not any(d["kind"] == "context_link" for d in requirements.pending_decisions(parent))


# ---- 3. relationship, pair and reference checks; connectives never license a new relationship -------------------------------------
def _fragment(wording: str, question: str = tt.Q2, clar=tt.CLAR_FRAGMENT, responder=None):
    respond = responder or tt._respond_q2

    def r(prompt, schema):
        if "requirements" in schema["properties"] or "ambiguities" in schema["properties"]:
            return respond(prompt, schema)
        if "using which scales" in base._owned_first_line(prompt):
            return {"question": wording, "unresolved": []}
        return respond(prompt, schema)

    result = run_engine(question, ScriptedModel(r), repair=False, clarifications=[clar], prompt_variant="lean")
    kid = next(c for c in result["pass1"]["children"] if c.get("clarified_fragment"))
    return kid, result


def test_a_fragment_keeps_the_relationship_that_defines_its_referent_without_asking_the_parents_question_again():
    kid, result = _fragment("Using which scales are the specific pigments that relate to shell color")
    assert kid["status"] == "candidate" and not _kinds(kid)
    that = next(o for o in kid["edit_ledger"]["ops"] if o.get("text") == "that")
    assert (
        that["kind"] == "relative_pronoun" and "recorded relationship" in that["relationship_basis"]
    )  # NOT mere adjacency
    states = {r["id"].split("#")[1].split(":")[0]: r["state"] for r in kid["edit_ledger"]["requirements"]}
    assert states == {"pair": "members_present", "referent_relationship": "met_lexically"}
    # the limit of a lexical check is REPORTED, not hidden: presence is not proof the pairing survived
    limits = kid["edit_ledger"]["verification_limits"]
    assert any("intended pairing" in x for x in limits) and any("still relate the same way" in x for x in limits)
    assert any(f["flag"] == "lexical_check_limit" for f in kid["flags"])
    assert kid["child_id"] in result["pass1"]["reconciliation"]["summary"]["unverified_by_lexical_checks"]
    asked_again, _ = _fragment("Which specific pigments relate to shell color, using which scales?")
    assert asked_again["status"] == "semantic_conflict" and "operator_added" in _kinds(
        asked_again
    )  # ancestor's ASK, not context


@pytest.mark.parametrize(
    ("wording", "status", "kind"),
    [
        (
            "Using which scales are the specific pigments",
            "semantic_review_required",
            "referent_relationship_incomplete",
        ),
        (
            "Using which scales are the specific pigments of shell color",
            "semantic_review_required",
            "referent_relationship_incomplete",
        ),
        ("Using which scales", "semantic_conflict", "pair_member_missing"),
        (
            "Using which scales are pigments that relate to shell color",
            "semantic_review_required",
            "pair_member_partial",
        ),
    ],
)
def test_losing_the_referent_the_relationship_or_a_pair_member_never_passes(wording, status, kind):
    kid, result = _fragment(wording)
    assert kid["status"] == status and kind in _kinds(kid)
    assert kid["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]


def test_a_relative_that_joining_pieces_no_source_stretch_or_recorded_relationship_relates_is_review_not_valid_and_not_rejected():
    kid, _ = _fragment("Using which scales are the specific pigments that shell color")
    assert "connective_relationship_unestablished" in _kinds(kid) and kid["status"] == "semantic_review_required"
    assert not kid["diagnostics"]["hard_fail"]  # a natural construction is marked for review, not rejected
    op = next(o for o in kid["edit_ledger"]["ops"] if o.get("text") == "that")
    assert op["op"] == "connective_unestablished"


Q4 = "what kind of specific pigments relate to shell color? and using which scales?"
FRAG4 = "and using which scales?"


def _respond_q4(prompt: str, schema: dict):
    if "requirements" in schema["properties"]:
        part = prompt.split("Part to read:\n", 1)[1] if "Part to read:\n" in prompt else ""
        if part.startswith("what kind"):
            return {
                "requirements": [
                    _item("specific pigments"),
                    _item("specific pigments relate to shell color", kind="relationship"),
                ]
            }
        if part.startswith("and using"):
            return {"requirements": [_item("scales")]}
        return {"requirements": []}
    if "ambiguities" in schema["properties"]:
        return {"ambiguities": []}
    return {"question": "What is asked?", "unresolved": []}


def test_a_connective_borrowed_from_another_source_span_is_flagged_for_review_not_authorized_by_having_appeared_somewhere():
    lo = Q4.index(FRAG4)
    plo = Q4.index("specific pigments")
    clar = {
        "id": "RC-F4",
        "span": [lo, lo + len(FRAG4)],
        "phrase": FRAG4,
        "means": "the scales used to measure the pigments asked about just before",
        "authorized_by": "tester",
        "refers_to": {"span": [plo, plo + 17], "phrase": "specific pigments"},
        "pairs": [
            {"span": [plo, plo + 17], "phrase": "specific pigments"},
            {"span": [Q4.index("which scales"), Q4.index("which scales") + 12], "phrase": "which scales"},
        ],
    }
    kid, _ = _fragment("Using which scales are the specific pigments of shell color", Q4, clar, _respond_q4)
    ops = [o for o in kid["edit_ledger"]["ops"] if o["op"] == "connective_unestablished"]
    assert ops and ops[0]["text"].lower() == "of" and "connective_relationship_unestablished" in _kinds(kid)
    assert kid["status"] == "semantic_review_required"
    kept, _ = _fragment(
        "Using which scales are the specific pigments that relate to shell color", Q4, clar, _respond_q4
    )
    assert "connective_relationship_unestablished" not in _kinds(kept)


def test_a_clarified_reference_left_unresolved_is_reported_and_one_that_is_replaced_is_met():
    result = run_engine(
        Q,
        ScriptedModel(
            base.responder(
                {"whether and how": {"question": "Whether and how they relate to depth, which kinds of depth"}}
            )
        ),
        repair=False,
        clarifications=[CLAR],
    )
    kid = next(c for c in result["pass1"]["children"] if c["question"].startswith("Whether and how they"))
    assert "clarified_reference_unresolved" in _kinds(kid) and kid["status"] != "candidate"
    ok, _ = _wording("Whether and how the specific reef zones relate to depth, which kinds of depth")
    states = {r["id"]: r["state"] for r in ok["edit_ledger"]["requirements"]}
    assert states["RC-T#reference"] == "met"


def test_a_relationship_stated_with_a_verb_outside_the_closed_list_is_review_never_a_silent_success():
    question = "Which drugs frobnicate tinnitus symptoms?"
    model = _scripted(
        {"Which": [_item("Which drugs frobnicate tinnitus symptoms", kind="relationship")]},
        writer=lambda p: {"question": question, "unresolved": []},
    )
    result = run_engine(question, model, repair=False)
    relational = [c for c in result["pass1"]["children"] if c.get("relation_contract")]
    assert relational and relational[0]["relation_contract"]["parse_status"] == "unparsed"
    assert relational[0]["status"] == "semantic_review_required"
    assert relational[0]["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]
    limits = result["manifest"]["known_limitations"]
    assert any(
        "closed, English-only relation-verb list" in x for x in limits
    )  # the limit is stated wherever the run is reported


# ---- 4. output acceptance and preflight -----------------------------------------------------------------------------------------------
class _Live:
    """A fake LIVE provider: every call reports a mode and a stop reason the way a real Ollama response does."""

    label = "live-fake"

    def __init__(self, inner: ScriptedModel, done_reason):
        self.inner, self.done_reason = inner, done_reason

    def call(self, prompt, *, schema, output_cap):
        c = self.inner.call(prompt, schema=schema, output_cap=output_cap)
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


def _live_child(done_reason, variant="lean"):
    question = "Please list the risk factors for stroke and describe the treatments."  # goes through the writer
    inner = _scripted(
        {"Please": [_item("the risk factors for stroke"), _item("the treatments")]},
        writer=lambda p: {"question": question, "unresolved": []},
    )
    result = run_engine(question, _Live(inner, done_reason), repair=False, prompt_variant=variant)
    return next(c for c in result["pass1"]["children"] if c["kind"] == "generated"), result


def test_a_live_call_without_a_confirmed_stop_is_never_treated_as_a_normal_stop():
    for reason, state in (("stop", "confirmed_stop"), (None, "unconfirmed_live"), ("load", "unconfirmed_live")):
        kid, _ = _live_child(reason)
        assert kid["output_budget"]["stop_state"] == state and kid["output_budget"]["live_call"], reason
        flagged = any(f["flag"] == "output_stop_reason_unconfirmed" for f in kid["flags"])
        assert flagged == (state == "unconfirmed_live")
        if state == "unconfirmed_live":
            assert (
                kid["status"] in ("semantic_review_required", "semantic_conflict")
                and kid["output_acceptance"]["review"]
            )
    kid, _ = _live_child("length")
    assert kid["output_budget"]["truncated"] and kid["diagnostics"]["hard_fail"]
    scripted = run_engine(
        CONTROLS[1], _single(CONTROLS[1], "a placebo effect"), passthrough_enabled=False, repair=False
    )
    offline = scripted["pass1"]["children"][0]
    assert (
        offline["output_budget"]["stop_state"] == "not_applicable_offline" and not offline["output_budget"]["live_call"]
    )
    assert not any(
        f["flag"] == "output_stop_reason_unconfirmed" for f in offline["flags"]
    )  # offline is reported as such, not as a stop


def test_a_full_unresolved_list_is_status_bearing_and_positively_known_omission_is_a_constraint_failure():
    base_child = {
        "output_limits": {"question_max": 600, "unresolved_max": 3},
        "output_budget": {"unresolved_at_capacity": True, "stop_state": "confirmed_stop", "final_chars": 40},
    }
    saturated = ch.output_acceptance(copy.deepcopy(base_child), expected_unresolved=2)
    assert saturated["review"] and not saturated["constraint_failure"]
    assert [f["flag"] for f in saturated["findings"]] == ["unresolved_list_at_capacity"]
    omitted = ch.output_acceptance(copy.deepcopy(base_child), expected_unresolved=4)
    assert omitted["constraint_failure"] and omitted["findings"][0]["level"] == "hard"
    quiet = ch.output_acceptance(
        {**copy.deepcopy(base_child), "output_budget": {"stop_state": "confirmed_stop", "final_chars": 40}},
        expected_unresolved=0,
    )
    assert not quiet["findings"] and not quiet["review"]
    kid, result = _live_child("stop")
    assert kid["output_acceptance"]["parse_valid"] and kid["output_acceptance"]["final_chars"] == len(kid["question"])


def test_a_saturated_unresolved_list_changes_the_childs_status_in_a_real_run():
    question = "Please list the risk factors for stroke and describe the treatments."
    full = [{"word": w, "reading_used": "none chosen", "other_readings": []} for w in ("a", "b", "c")]
    inner = _scripted(
        {"Please": [_item("the risk factors for stroke"), _item("the treatments")]},
        writer=lambda p: {"question": question, "unresolved": full},
    )
    result = run_engine(question, inner, repair=False, passthrough_enabled=False, prompt_variant="lean")
    kid = next(c for c in result["pass1"]["children"] if c["kind"] == "generated")
    assert any(f["flag"] == "unresolved_list_at_capacity" for f in kid["flags"])
    assert (
        kid["status"] != "candidate"
        and kid["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]
    )


def _limited(variant: str, question_max: int) -> dict:
    settings = dict(prompts.settings_for(variant))
    settings["limits"] = {**settings["limits"], "question_max": question_max}
    return settings


def test_preflight_fails_only_when_the_indispensable_request_cannot_fit_and_never_on_an_optional_context_estimate():
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    clarifications.apply(parent, [CLAR])
    plans, by_id = ch.plan_children(parent), ch.by_id_map(parent)
    plan = next(p for p in plans if any("whether and how" in by_id[i]["text"] for i in p["owns"]))
    sizes = ch.preflight_sizes(parent, plan, by_id, plans, prompts.settings_for("lean"))
    assert (
        sizes["indispensable_growth_chars"] > 0
        and sizes["indispensable_chars"] == sizes["extract_chars"] + sizes["indispensable_growth_chars"]
    )
    fits_extract_only = _limited(
        "lean", sizes["extract_chars"] + 5 + 1
    )  # the extract fits, its required replacement does not
    blocked = ch._constraint_failure(parent, plan, by_id, plans, fits_extract_only)
    assert blocked and blocked["constraint"] == "restored_question_length"
    assert (
        blocked["needed_chars"] == sizes["indispensable_chars"]
        and blocked["sizes"]["extract_chars"] == sizes["extract_chars"]
    )
    roomy = _limited("lean", sizes["indispensable_chars"] + 5 + 1)
    assert ch._constraint_failure(parent, plan, by_id, plans, roomy) is None
    too_long_extract = _limited("lean", sizes["extract_chars"] + 4)
    assert ch._constraint_failure(parent, plan, by_id, plans, too_long_extract)["constraint"] == "question_length"
    # optional/expected context alone (subject + joining words, or an inherited question) never fails a request
    assert sizes["expected_additional_chars"] >= 0 and "may_exceed_limit_if_all_expected_context_is_added" in sizes


def test_both_prompt_variants_share_one_schema_one_budget_and_one_acceptance_rule():
    full, lean = prompts.settings_for("corrected-full"), prompts.settings_for("lean")
    for key in ("schema", "cap", "limits", "preflight", "extract_mode"):
        assert full[key] == lean[key], key
    outputs = {}
    for variant in ("corrected-full", "lean"):
        kid, _ = _live_child("stop", variant)
        outputs[variant] = {k: v for k, v in kid["output_acceptance"].items() if k != "final_chars"}
    assert outputs["corrected-full"] == outputs["lean"]
    worst = prompts.schema_output_budget(prompts.MATCHED_SCHEMA)["tokens_at_1_5_chars_per_token"]
    assert prompts.MATCHED_OUTPUT_CAP >= worst  # the cap covers what the schema permits
    assert passthrough.DOWNSTREAM["answer_state"] == "not_executed"


# ---- 5. the audited q_aib cases, re-scored offline as a regression (skipped when the local development artifacts are absent) ------
_AIB = Path(__file__).resolve().parents[3] / ".local" / "decompose-runs" / "aib-dev"
_HAVE_AIB = (_AIB / "clarifications" / "q_aib.v5.requirements.json").exists() and (
    _AIB / "reference" / "q_aib.original.v1.txt"
).exists()


def _aib(cid: str, wording: str):
    import json

    from experiments.ask_cli_revised.decompose.engine import rescore
    from experiments.ask_cli_revised.decompose.model import ReplayModel

    q = (_AIB / "reference" / "q_aib.original.v1.txt").read_text(encoding="utf-8")
    rows = clarifications.load(_AIB / "clarifications" / "q_aib.v3.approved.json")
    ann = clarifications.load_annotations(
        _AIB / "clarifications" / "q_aib.v4.annotations.json"
    ) + clarifications.load_annotations(_AIB / "clarifications" / "q_aib.v5.requirements.json")
    calls = [
        json.loads(x)
        for x in (_AIB / "dev-run-2-obligation-qwen35-9b" / "model_calls_LIVE_ORIGINAL.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x.strip()
    ]
    inv = [r for r in calls if r["task"].startswith("parent.")]
    r = rescore(
        q,
        ReplayModel(inv, "x"),
        {cid: {"question": wording, "unresolved": []}},
        clarifications=rows,
        clarification_annotations=ann,
        extract_mode="governing",
    )
    return next(c for c in r["pass1"]["children"] if c["child_id"] == cid)


CTX = "In the context of the anomalous is bad bias, "


@pytest.mark.skipif(not _HAVE_AIB, reason="local q_aib development artifacts are not present")
def test_the_audited_c9_and_c11_false_passes_and_false_flags_are_corrected():
    kept = _aib(
        "c9",
        "using which scales are the specific personality traits that relate to the anomalous is bad bias's manifestation measured?",
    )
    assert "relation_word_added" not in _kinds(kept)  # the false flag on a valid relative "that"
    that = next(o for o in kept["edit_ledger"]["ops"] if o.get("text") == "that")
    assert "recorded relationship" in that["relationship_basis"]
    assert (
        kept["status"] == "pending_researcher_confirmation"
    )  # the engine-recorded joining word "measure" is still pending
    lost = _aib(
        "c9", "using which scales are the specific personality traits of the anomalous is bad bias measured?"
    )  # the false pass
    assert {"connective_relationship_unestablished", "referent_relationship_incomplete"} <= _kinds(lost) and lost[
        "status"
    ] == "semantic_review_required"
    generic = _aib("c9", "using which personality scales?")
    assert generic["status"] != "candidate" and "pair_member_partial" in _kinds(generic)
    no_traits = _aib("c9", "using which scales is the anomalous is bad bias measured?")
    assert no_traits["status"] == "semantic_conflict" and "pair_member_missing" in _kinds(no_traits)
    unresolved = _aib("c11", "which cultures and how was this measured?")  # the false pass
    assert unresolved["status"] == "semantic_review_required" and "clarified_reference_unresolved" in _kinds(unresolved)
    ok = _aib("c11", "which cultures and how was the anomalous is bad bias measured?")
    assert ok["status"] == "candidate" and any(
        "intended pairing" in x for x in ok["edit_ledger"]["verification_limits"]
    )
    half = _aib("c11", "which cultures?")
    assert half["status"] == "semantic_conflict" and "pair_member_missing" in _kinds(half)


@pytest.mark.skipif(not _HAVE_AIB, reason="local q_aib development artifacts are not present")
def test_where_supported_is_expressible_for_4a_and_4b_without_exempting_other_question_words_and_details_stay_pending():
    for cid, tail in (("c5", ", which kinds of behaviors"), ("c6", ", and which kinds of attitudes")):
        target = "behaviors" if cid == "c5" else "attitudes"
        text = CTX + f"please return whether and how specific brain areas relate to {target} where supported{tail}"
        kid = _aib(cid, text)
        assert "operator_added" not in _kinds(kid) and kid["status"] == "pending_researcher_confirmation", (
            cid,
            _kinds(kid),
        )
        pending = _aib(
            cid, CTX + f"please return whether and how specific brain areas and networks relate to {target}{tail}"
        )
        assert "clarification_detail_pending" in _kinds(pending) and pending["status"] == "semantic_review_required"
        bad = _aib(
            cid,
            CTX + f"please return whether and how specific brain areas relate to {target}, where are the areas{tail}",
        )
        assert bad["status"] == "semantic_conflict"
    no_how = _aib(
        "c6", CTX + "please return whether specific brain areas relate to attitudes, and which kinds of attitudes"
    )
    assert no_how["status"] == "semantic_conflict"  # RC-8's approved "how" is still enforced


Q6 = "which specific pigments frobnicate shell color? and using which scales?"


def _respond_q6(prompt: str, schema: dict):
    if "requirements" in schema["properties"]:
        part = prompt.split("Part to read:\n", 1)[1] if "Part to read:\n" in prompt else ""
        if part.startswith("which specific"):
            return {
                "requirements": [
                    _item("specific pigments"),
                    _item("specific pigments frobnicate shell color", kind="relationship"),
                ]
            }
        if part.startswith("and using"):
            return {"requirements": [_item("scales")]}
        return {"requirements": []}
    if "ambiguities" in schema["properties"]:
        return {"ambiguities": []}
    return {"question": "What is asked?", "unresolved": []}


def test_when_the_parents_relationship_cannot_be_parsed_the_fragment_check_says_it_cannot_verify_instead_of_passing():
    def link(text: str) -> dict:
        lo = Q6.index(text)
        return {"span": [lo, lo + len(text)], "phrase": text}

    lo = Q6.index(FRAG4)
    clar = {
        "id": "RC-F6",
        "span": [lo, lo + len(FRAG4)],
        "phrase": FRAG4,
        "means": "the scales used to measure the pigments asked about just before",
        "authorized_by": "tester",
        "refers_to": link("specific pigments"),
        "pairs": [link("specific pigments"), link("which scales")],
    }
    kid, result = _fragment("Using which scales are the specific pigments", Q6, clar, _respond_q6)
    states = {r["kind"]: r["state"] for r in kid["edit_ledger"]["requirements"]}
    assert states["referent_relationship_carried"] == "unverifiable"
    assert any("no parsed relationship" in x for x in kid["edit_ledger"]["verification_limits"])
    owner = next(c for c in result["pass1"]["children"] if c.get("relation_contract"))
    assert owner["relation_contract"]["parse_status"] == "unparsed" and owner["status"] != "candidate"
