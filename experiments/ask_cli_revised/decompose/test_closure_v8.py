"""Model-free proof of the closure_v8 decision mechanics: an optional-scope AMENDMENT that leaves the historical record untouched, a definite-description
reference resolved from an approved clarification, approvals of exact wordings with a provenance that approval never changes, and a researcher-supplied
wording that runs only through its own exact approval.

Synthetic, unrelated requests only (reef zones, coral effect), except the tests marked as reading the preserved local q_aib artifacts, which skip
themselves when those are absent. No model is called and nothing is sent anywhere. A scripted test shows a decision PATH; it never shows what a real
inventory model will return.
"""

from __future__ import annotations

import functools
import hashlib
import json
from pathlib import Path

import pytest

import experiments.ask_cli_revised.decompose.test_correction_pass as cp
import experiments.ask_cli_revised.decompose.test_decompose as base
import experiments.ask_cli_revised.decompose.test_prepared as tp
from experiments.ask_cli_revised.decompose import clarifications, execution, integrated, prompts_prepared
from experiments.ask_cli_revised.decompose.calllog import CallLog
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ReplayModel, ScriptedModel

ROOT = Path(__file__).resolve().parents[3]
AIB = ROOT / ".local" / "decompose-runs" / "aib-dev"
CLOSURE = AIB / "clarifications" / "q_aib.v8.closure_decisions.json"
APPROVALS = AIB / "closure_v8" / "CLOSURE_APPROVALS.json"

# the exact strings the researcher approved, typed here independently of the recorded file so a wrong recorded string or digest cannot hide
APPROVED = {
    "c9": "which scales measure the specific personality traits that relate to the anomalous is bad bias's manifestation?",
    "c11": "in which cultures is there evidence for the anomalous is bad bias, and how was the anomalous is bad bias measured in each?",
    "c4": "Please return the specific brain areas in which the anomalous-is-bad bias manifests.",
    "c5": "In the context of the anomalous is bad bias, please return whether and how specific brain areas relate to behaviors, which kinds of behaviors",
    "c12": "are there effective interventions aimed at reducing the anomalous is bad bias?",
}
PROVENANCE = {
    "c9": "deterministic_scaffold",
    "c11": "deterministic_scaffold",
    "c4": "researcher_supplied",
    "c5": "deterministic_preparation",
    "c12": "deterministic_preparation",
}


# ---- 1. an optional-scope amendment: one item's state changes, the historical record and every other item do not ---------------------------------
def _scope(rid, text, phrases):
    return {"kind": "scope_item", "id": rid, "text": text, "phrases": phrases, "approved_by": "tester"}


def _scope_rows():
    return [
        {
            "clarification": "RC-Q",
            "requirements": [
                _scope("RC-Q#scope:a", "the documented direction", ["documented direction", "direction"]),
                _scope("RC-Q#scope:b", "the reef zones", ["reef zones"]),
                _scope("RC-Q#scope:c", "the documented direction where supported", ["where supported"]),
            ],
        }
    ]


def _amend(**kw):
    row = {
        "amends": "RC-Q#scope:a",
        "decision": "D-X",
        "effect": "optional_scope_expansion",
        "optional_phrases": ["documented direction"],
        "approved_by": "tester",
        "note": "an optional, researcher-selected expansion",
    }
    return {"clarification": "RC-Q", "amendments": [{**row, **kw}]}


def _states(text, rows):
    kid, result = cp._wording(text, rows)
    return {r["id"].split("#")[1]: r["state"] for r in kid["edit_ledger"]["requirements"]}, kid, result


SCOPED = "Whether and how the specific reef zones relate to depth, which kinds of depth"


def test_an_amendment_makes_only_the_amended_scope_item_optional_and_leaves_every_other_item_as_it_was():
    before, _, _ = _states(SCOPED, _scope_rows())
    after, kid, _ = _states(SCOPED, [*_scope_rows(), _amend()])
    assert before["scope:a"] == "meaning_not_lexically_verified" and after["scope:a"] == "optional_by_amendment"
    for other in ("scope:b", "scope:c"):
        assert after[other] == before[other]  # the un-amended items keep their earlier state
    assert (before["scope:b"], before["scope:c"]) == ("approved_words_present", "meaning_not_lexically_verified")
    row = {r["id"]: r for r in kid["edit_ledger"]["requirements"]}
    assert row["RC-Q#scope:a"]["amended_by"][0]["decision"] == "D-X"
    assert not any("amended_by" in r for i, r in row.items() if i != "RC-Q#scope:a")


def test_an_amended_item_whose_words_are_present_is_reported_as_present_not_as_optional():
    text = "Whether and how the specific reef zones relate to depth, including the documented direction, which kinds of depth"
    states, _, _ = _states(text, [*_scope_rows(), _amend()])
    assert (
        states["scope:a"] == "approved_words_present"
    )  # optional means permitted to be absent, never that it is hidden when present


def test_an_amendment_adds_a_record_beside_the_historical_one_and_rewrites_nothing():
    _, _, plain = _states(SCOPED, _scope_rows())
    _, _, amended = _states(SCOPED, [*_scope_rows(), _amend()])

    def rq(result):
        return next(c for c in result["parent_contract"]["clarifications"] if c["id"] == "RC-Q")

    assert (
        rq(plain)["annotated_requirements"] == rq(amended)["annotated_requirements"]
    )  # the D4-style record, unchanged
    assert "amendments" not in rq(plain) and rq(amended)["amendments"][0]["approved_by"] == "tester"
    scope_c = [r for r in rq(amended)["requirements"] if r["id"] == "RC-Q#scope:c"][0]
    assert scope_c == [r for r in rq(plain)["requirements"] if r["id"] == "RC-Q#scope:c"][0]


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"amends": "RC-Q#scope:zz"}, "unknown requirement"),
        ({"approved_by": " "}, "approved_by is mandatory"),
        ({"effect": "drop_requirement"}, "the only amendment"),
        ({"optional_phrases": ["lagoons"]}, "optional_phrases must be phrases"),
        ({"optional_phrases": []}, "optional_phrases must be phrases"),
    ],
)
def test_an_amendment_must_name_a_known_scope_item_a_researcher_and_its_own_phrases(change, match):
    parent = cp.build_parent_contract(CallLog(ScriptedModel(cp.base.responder())), cp.Q)
    clarifications.apply(parent, [cp.CLAR, cp.MEAN])
    clarifications.annotate(parent, _scope_rows())
    with pytest.raises(clarifications.ClarificationError, match=match):
        clarifications.annotate(parent, [_amend(**change)])


def test_a_constraint_can_never_be_amended_away():
    parent = cp.build_parent_contract(CallLog(ScriptedModel(cp.base.responder())), cp.Q)
    clarifications.apply(parent, [cp.CLAR, cp.MEAN])
    rows = [
        {
            "clarification": "RC-Q",
            "requirements": [
                {
                    "kind": "constraint",
                    "id": "RC-Q#constraint:k",
                    "text": "whether and how",
                    "approved_by": "tester",
                }
            ],
        }
    ]
    clarifications.annotate(parent, rows)
    with pytest.raises(clarifications.ClarificationError, match="the only amendment"):
        clarifications.annotate(parent, [_amend(amends="RC-Q#constraint:k")])


# ---- 2. a definite description resolved from an approved clarification (no engine inference) ------------------------------------------------------
Q = base.Q
DEF_PHRASE = "is there any evidence for the effect in juveniles"
_DLO = Q.index(DEF_PHRASE)
CLAR_DEF = {
    "id": "RC-D",
    "span": [_DLO, _DLO + len(DEF_PHRASE)],
    "phrase": DEF_PHRASE,
    "reference_word": "the effect",
    "means": "the coral effect",
    "authorized_by": "tester",
    "refers_to": tp._link(Q, "coral effect"),
}


def test_an_approved_definite_description_is_replaced_at_its_own_source_span_by_the_referent_and_the_edit_cites_the_approval():
    _, _, _, preps = tp._preps(Q, base.responder(), [CLAR_DEF])
    prep = tp._find(preps, "is there any")
    (edit,) = [e for e in prep["edits"] if e["clarification"] == "RC-D"]
    assert edit["rule"] == "definite_description_replaced_by_approved_referent" and edit["op"] == "reference_resolved"
    assert Q[edit["replaces"]["source_span"][0] : edit["replaces"]["source_span"][1]] == "the effect"
    assert edit["supplied"] == []  # no word that was not in the source or the approved clarification
    text = tp._text(prep)
    assert "the coral effect" in text and "the effect" not in text
    assert not prep["not_applied"] and not prep["not_prepared"]


def test_a_reference_word_of_a_shape_the_preparation_does_not_handle_is_left_as_written_and_the_reason_is_recorded():
    clar = {**CLAR_DEF, "id": "RC-E", "reference_word": "evidence for the effect"}
    _, _, _, preps = tp._preps(Q, base.responder(), [clar])
    prep = tp._find(preps, "is there any")
    assert "evidence for the effect" in tp._text(prep) and not [
        e for e in prep["edits"] if e["clarification"] == "RC-E"
    ]
    assert any("not a reference shape" in x["reason"] for x in prep["not_applied"])


def _writer_for(text):
    return {"is there any": {"question": text}}


def test_a_multiword_reference_left_in_the_wording_is_reported_and_a_resolved_one_is_met():
    left, _ = base.run(
        _writer_for("Is there any evidence for the effect in juveniles?"), repair=False, clarifications=[CLAR_DEF]
    )
    kid = next(c for c in left["pass1"]["children"] if c["question"].startswith("Is there any"))
    assert "clarified_reference_unresolved" in {f["kind"] for f in kid["edit_ledger"]["flags"]}
    assert kid["status"] != "candidate"
    done, _ = base.run(
        _writer_for("Is there any evidence for the coral effect in juveniles?"), repair=False, clarifications=[CLAR_DEF]
    )
    ok = next(c for c in done["pass1"]["children"] if c["question"].startswith("Is there any"))
    assert {r["id"]: r["state"] for r in ok["edit_ledger"]["requirements"]}["RC-D#reference"] == "met"


# ---- 3. approvals of exact wordings: provenance is kept, a different string is not approved, a researcher-supplied wording needs its own approval -----------
def _approval(child_id, wording, **kw):
    return {
        "child_id": child_id,
        "wording": wording,
        "wording_sha256": execution.wording_sha256(wording),
        "approved_by": "tester",
        "authorization_quote": f"approve: {wording}",
        **kw,
    }


def _scaffolded(question, status="pending_researcher_confirmation"):
    return {
        "child_id": "cS",
        "kind": "generated",
        "status": status,
        "question": question,
        "preparation": {
            "prepared_request": question,
            "carry": None,
            "join": None,
            "scaffold": {
                "built": True,
                "template": "t",
                "text": question,
                "pending": [{"kind": "fragment_rewritten_as_question"}],
            },
        },
    }


def test_an_approved_deterministic_scaffold_stays_a_deterministic_scaffold_and_carries_its_qualifications():
    child = _scaffolded("which scales measure the traits?")
    assert execution.readiness(child)["state"] == execution.REQUIRES_APPROVAL  # pending parts wait for the researcher
    qual = [{"id": "cS#constraint:x", "text": "it does not ask the traits again", "approved_by": "tester"}]
    approval = _approval(
        "cS",
        child["question"],
        wording_provenance="deterministic_scaffold",
        approval_ref="CD-T",
        confirms_pending=["fragment_rewritten_as_question"],
        qualifications=qual,
    )
    ex = execution.readiness(child, approvals=[approval])
    assert ex["state"] == execution.RESEARCHER_APPROVED and ex["executable"]
    assert (
        ex["approval"]["wording_provenance"] == "deterministic_scaffold"
    )  # approval never turns it into researcher wording
    assert ex["approval"]["approval_ref"] == "CD-T" and ex["qualifications"] == qual
    assert child["preparation"]["scaffold"]["pending"]  # and the pending record itself is left as it was


def test_an_approval_of_one_string_does_not_approve_a_near_variant_or_another_child():
    child = _scaffolded("which scales measure the traits?")
    approval = _approval("cS", child["question"], wording_provenance="deterministic_scaffold")
    for other in (
        {**child, "question": "which scales measure the traits ?"},
        {**child, "question": "Which scales measure the traits?"},
        {**child, "child_id": "cT"},
    ):
        assert execution.readiness(other, approvals=[approval])["state"] == execution.REQUIRES_APPROVAL


def test_a_researcher_supplied_wording_runs_only_through_its_own_exact_approval_and_never_by_label():
    wording = "Please return the reef zones in which the coral effect appears."
    child = {"child_id": "cR", "kind": "researcher_supplied", "status": "researcher_supplied", "question": wording}
    assert execution.readiness(child)["state"] == execution.REQUIRES_APPROVAL
    approval = _approval("cR", wording, wording_provenance="researcher_supplied", approval_ref="CD-R")
    assert execution.readiness(child, approvals=[approval])["state"] == execution.RESEARCHER_APPROVED
    assert (
        execution.readiness({**child, "question": wording + " "}, approvals=[approval])["state"]
        == execution.REQUIRES_APPROVAL
    )
    assert execution.readiness({**child, "status": "semantic_conflict"}, approvals=[approval])["state"] == (
        execution.NOT_EXECUTABLE
    )  # an approval never overrides a hard failure


def test_the_approval_loader_rejects_an_unknown_provenance_and_a_wording_that_does_not_hash_to_its_digest(tmp_path):
    good = _approval("cS", "which scales measure the traits?", wording_provenance="deterministic_scaffold")
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps({"approvals": [good]}), encoding="utf-8")
    assert execution.load_approvals(path) == [good]
    for bad in (
        {**good, "wording_provenance": "model_endorsed"},
        {**good, "wording": good["wording"] + "!"},
    ):
        path.write_text(json.dumps({"approvals": [bad]}), encoding="utf-8")
        with pytest.raises(ValueError, match="wording_provenance|does not hash"):
            execution.load_approvals(path)
    assert execution.verify_approvals([good]) == []
    assert execution.verify_approvals([good, {**good}]) == ["cS: more than one approval"]
    assert execution.verify_approvals([{**good, "wording": "different"}])


# ---- 4. the recorded q_aib decisions (skip when the local artifacts are absent) ------------------------------------------------------------------
def _needs_closure():
    if not (
        CLOSURE.exists()
        and APPROVALS.exists()
        and (AIB / "followup_v7" / "inputs" / "primary_request.txt").exists()
        and (AIB / "clarifications" / "q_aib.v3.approved.json").exists()
    ):
        pytest.skip("the local q_aib closure artifacts are not present")


def _clar_files(with_closure: bool) -> dict:
    files = {
        "approved": AIB / "clarifications" / "q_aib.v3.approved.json",
        "decisions": AIB / "clarifications" / "q_aib.v6.researcher_decisions.json",
    }
    return {**files, "closure": CLOSURE} if with_closure else files


@functools.cache
def _closure_state():
    """The recorded inventory replayed under the closure clarification set, with a scripted writer that returns each deterministic preparation
    verbatim (an offline scoring of the wording as if a writer had returned it; no model is called)."""
    from experiments.ask_cli_revised.decompose import wording_check as w

    inp = w.load_inputs(AIB / "followup_v7" / "inputs", _clar_files(True))
    approvals = execution.load_approvals(APPROVALS)
    parent, plans, by_id, _ = w.rebuild_state(inp)
    prep = {}
    for plan in plans:
        if plan["kind"] == "anchor":
            sub, p = prompts_prepared.prepared_for(parent, plan, plans, by_id)
            prep[plan["child_id"]] = (p, prompts_prepared.render_prepared(parent, sub, p))
    wordings = {cid: prep[cid][0]["prepared_request"] for cid in ("c5", "c9", "c10", "c11", "c12")}
    by_prompt = {prep[cid][1]: cid for cid in wordings}

    def respond(prompt, schema):
        cid = by_prompt.get(prompt)
        return {"question": wordings[cid], "unresolved": []} if cid else None

    result = run_engine(
        inp["question"],
        ScriptedModel(respond),
        repair=False,
        inventory_model=ReplayModel(inp["inventory"], "frozen-v6"),
        clarifications=inp["rows"],
        clarification_annotations=inp["annotations"],
        researcher_decisions=inp["decisions"],
        prompt_variant="prepared",
        only=sorted(wordings),
        max_calls=len(wordings),
    )
    kids = {c["child_id"]: c for c in result["pass1"]["children"] if c["kind"] != "not_selected"}
    return inp, parent, plans, prep, kids, approvals


def test_each_approved_wording_hashes_to_the_exact_string_the_researcher_approved_and_each_child_has_its_own_approval():
    _needs_closure()
    rows = {a["child_id"]: a for a in execution.load_approvals(APPROVALS)}
    for cid, wording in APPROVED.items():
        row = rows[cid]
        assert row["wording"] == wording and row["wording_sha256"] == hashlib.sha256(wording.encode()).hexdigest()
        assert row["wording_provenance"] == PROVENANCE[cid]
        assert row["approved_by"] == "Cliff" and row["approval_ref"].startswith("CD-")
        assert wording in row["authorization_quote"]  # the recorded quote contains the approved string itself
    assert len({r["wording_sha256"] for r in rows.values()}) == len(
        rows
    )  # c5's approval is not c6's, and no two children share one
    assert execution.verify_approvals(list(rows.values())) == []
    c6 = rows["c6"]
    assert c6["wording_sha256"] != rows["c5"]["wording_sha256"]
    other = {"child_id": "c5", "kind": "generated", "status": "candidate", "question": c6["wording"]}
    assert execution.readiness(other, approvals=list(rows.values()))["state"] != execution.RESEARCHER_APPROVED


def test_rc10_is_the_researchers_own_clarification_added_beside_the_historical_files_and_rewrites_none_of_them():
    _needs_closure()
    from experiments.ask_cli_revised.decompose import wording_check as w

    with_closure = w.load_inputs(AIB / "followup_v7" / "inputs", _clar_files(True))
    without = w.load_inputs(AIB / "followup_v7" / "inputs", _clar_files(False))
    assert [r["id"] for r in with_closure["rows"]][:-1] == [r["id"] for r in without["rows"]]
    assert with_closure["rows"][:-1] == without["rows"]  # RC-1..RC-9 exactly as recorded
    assert with_closure["annotations"][: len(without["annotations"])] == without["annotations"]
    _, parent, *_ = _closure_state()
    rc10 = next(c for c in parent["clarifications"] if c["id"] == "RC-10")
    assert (rc10["authorized_by"], rc10["status"], rc10["kind"]) == ("Cliff", "user_authorized", "reference")
    assert (rc10["target_text"], rc10["refers_to"]["text"]) == ("the bias", "anomalous is bad bias")
    assert rc10["requirements"][0]["provenance"]["source"] == "approved_clarification"  # not an engine inference


def test_the_closure_decisions_leave_the_hierarchy_ownership_and_nesting_exactly_as_the_frozen_run_recorded_them():
    _needs_closure()
    inp, _, plans, *_ = _closure_state()
    assert json.loads(json.dumps(plans, default=str)) == inp["frozen_children"]["plans"]


def test_c10_is_derived_from_the_source_words_and_rc10_and_c11_keeps_c10s_cross_cultural_scope_through_its_parent_link():
    _needs_closure()
    _, _, plans, prep, kids, _ = _closure_state()
    assert prep["c10"][0]["prepared_request"] == "is there any cross-cultural evidence for the anomalous is bad bias?"
    states = {r["id"]: r["state"] for r in kids["c10"]["edit_ledger"]["requirements"]}
    assert states["RC-10#reference"] == "met"
    c11 = next(p for p in plans if p["child_id"] == "c11")["node"]
    assert c11["parent"] == "c10" and any(d["node"] == "c10" and d["via"] == "RC-6" for d in c11["depends_on"])
    inherited = [i for i in c11["inherited"] if i["role"] == "fragment_target"]
    assert inherited and "cross-cultural" in " ".join(i["text"] for i in inherited)
    assert not {"any", "cross-cultural"} & set(
        APPROVED["c11"].replace(",", " ").split()
    )  # the words are gone; the link carries them


def test_the_pending_inference_about_the_bias_is_gone_under_rc10_and_every_remaining_pending_part_is_the_one_the_approval_confirms():
    _needs_closure()
    _, _, _, prep, _, approvals = _closure_state()
    by_child = {a["child_id"]: a for a in approvals}
    for cid in ("c9", "c11"):
        pending = {p["kind"] for p in prep[cid][0]["scaffold"]["pending"]}
        assert "inferred_reference" not in pending
        assert pending <= set(by_child[cid]["confirms_pending"])  # nothing pending is left unconfirmed
    assert {p["kind"] for p in prep["c11"][0]["scaffold"]["pending"]} == {"scope_words_dropped_and_supplied"}
    assert by_child["c11"]["supersedes_pending"]["inferred_reference"]


def test_the_five_rescored_children_have_the_recorded_readiness_and_the_approved_wordings_are_the_scaffolds_and_preparations():
    _needs_closure()
    _, _, _, prep, kids, approvals = _closure_state()
    state = {cid: execution.readiness(k, approvals=approvals)["state"] for cid, k in kids.items()}
    assert state == {
        "c5": execution.RESEARCHER_APPROVED,
        "c9": execution.RESEARCHER_APPROVED,
        "c10": execution.RUNNABLE_BY_CONSTRUCTION,
        "c11": execution.RESEARCHER_APPROVED,
        "c12": execution.RESEARCHER_APPROVED,
    }
    for cid in ("c5", "c9", "c11", "c12"):
        assert (
            kids[cid]["question"] == APPROVED[cid] == prep[cid][0]["prepared_request"]
        )  # the approved string IS the deterministic wording
        assert (
            execution.readiness(kids[cid])["state"] != execution.RESEARCHER_APPROVED
        )  # and it needs the approval to be one
    assert (
        execution.readiness(kids["c10"])["state"] == execution.RUNNABLE_BY_CONSTRUCTION
    )  # c10 needs no approval, nor is it given one


def test_networks_are_optional_for_rc8_and_rc9_only_and_every_other_d4_state_is_what_it_was_before_d10():
    _needs_closure()
    from experiments.ask_cli_revised.decompose import wording_check as w

    _, _, _, _, kids, _ = _closure_state()
    after = {r["id"]: r["state"] for r in kids["c5"]["edit_ledger"]["requirements"]}
    assert after["RC-9#scope:areas-and-networks"] == "optional_by_amendment"
    inp = w.load_inputs(AIB / "followup_v7" / "inputs", _clar_files(False))
    parent, plans, by_id, _ = w.rebuild_state(inp)
    (plan,) = [p for p in plans if p["child_id"] == "c5"]
    sub, prepared = prompts_prepared.prepared_for(parent, plan, plans, by_id)
    prompt = prompts_prepared.render_prepared(parent, sub, prepared)

    def respond(p, schema):
        return {"question": prepared["prepared_request"], "unresolved": []} if p == prompt else None

    before_run = run_engine(
        inp["question"],
        ScriptedModel(respond),
        repair=False,
        inventory_model=ReplayModel(inp["inventory"], "frozen-v6"),
        clarifications=inp["rows"],
        clarification_annotations=inp["annotations"],
        researcher_decisions=inp["decisions"],
        prompt_variant="prepared",
        only=["c5"],
        max_calls=1,
    )
    kid = next(c for c in before_run["pass1"]["children"] if c["child_id"] == "c5")
    before = {r["id"]: r["state"] for r in kid["edit_ledger"]["requirements"]}
    assert before["RC-9#scope:areas-and-networks"] == "meaning_not_lexically_verified"
    for rid, st in before.items():
        if rid != "RC-9#scope:areas-and-networks" and rid.startswith("RC-9#"):
            assert (
                after[rid] == st
            )  # measures, documented nature/direction, no-presupposition, where-supported: untouched
    assert (
        after["RC-9#scope:measures-of-behavior"] == "meaning_not_lexically_verified"
    )  # still unverified, still human-reviewed


def test_the_frozen_v6_and_v7_run_outputs_are_still_byte_identical_to_their_freeze_records():
    _needs_closure()
    for root in (AIB / "integrated_test_v6" / "run", AIB / "followup_v7" / "run"):
        assert integrated.outputs_unchanged(root) == []


def test_the_assembled_hierarchy_receipt_reports_every_child_executable_with_the_recorded_wordings():
    _needs_closure()
    path = AIB / "closure_v8" / "ASSEMBLED_HIERARCHY.json"
    if not path.exists():
        pytest.skip("the assembled hierarchy has not been generated")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["offline_assembly"] and data["not_a_live_run"]
    nodes = {n["child_id"]: n for n in data["nodes"]}
    assert list(nodes) == ["c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12"]  # c7 is folded into c8
    assert data["execution_summary"]["all_executable"] and not data["execution_summary"]["not_executable"]
    for cid, wording in APPROVED.items():
        assert nodes[cid]["wording"] == wording and "HUMAN" in nodes[cid]["provenance"]
    assert (
        "DET" in nodes["c9"]["provenance"]
        and "DET" in nodes["c11"]["provenance"]
        and "SUPPLIED" in nodes["c4"]["provenance"]
    )
    assert nodes["c6"]["execution"]["state"] == execution.RESEARCHER_APPROVED  # c6 keeps its own v7 acceptance
    recon = data["contract_reconciliation"]
    assert recon["plans_identical_to_frozen"] and not recon["missing"] and not recon["unaccounted"]
    assert recon["c11_inherited_scope"]["retained_through_parent_link"]
    assert all(recon["c9_pairing"]["members_present"].values()) and not recon["c9_pairing"]["asks_traits_again"]
