"""Model-free proof for the scoped wording stage, written before any model call.

Uses the synthetic request and scripted writer from ``test_decompose``; no real model, library or protected request.
"""

from __future__ import annotations

import copy
import json

import experiments.ask_cli_revised.decompose.test_decompose as base
from experiments.ask_cli_revised.decompose import checks
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ReplayModel, ScriptedModel

Q, U1 = base.Q, base.U1
NL = chr(10)
SCALES_Q = Q + " and using which scales?"
SUBJECT_FRAME = [
    {"kind": "requested_item", "quotes": ["show up in"], "note": ""},
    {"kind": "population", "quotes": ["growth, color, and survival"], "note": ""},
]


def _child_prompts(model, needle=None):
    out = [
        c["prompt"]
        for c in model.calls
        if "What this question must ask" in c["prompt"] and "Problems found" not in c["prompt"]
    ]
    if needle is None:
        return out
    return [p for p in out if needle in p.split("What this question must ask", 1)[1].split(NL * 2)[0].lower()]


def test_child_prompts_carry_the_owned_words_and_scoped_context_but_never_the_whole_request(monkeypatch):
    monkeypatch.setitem(base.UNIT_OBLIGATIONS, "how does the coral effect", SUBJECT_FRAME)
    monkeypatch.setattr(
        base, "WHOLE", [w for w in base.WHOLE if w["kind"] == "output_expectation"]
    )  # nothing else accounts for the subject words
    _result, model = base.run(repair=False)
    prompts = _child_prompts(model)
    assert prompts and all(
        Q not in p and U1 not in p for p in prompts
    )  # nobody is shown the whole request, or even a whole unit
    zones = _child_prompts(model, "whether and how they relate to depth")[0]
    assert (
        '"whether and how they relate to depth" (chars' in zones and "which kinds of depth" in zones
    )  # owned words with exact offsets
    for unrelated in ("pigments", "juveniles", "growth", "survival"):
        assert unrelated not in zones  # unrelated parent obligations are absent
    facet = _child_prompts(model, "growth")[0]
    assert "coral effect" in facet and "show up in" in facet and "growth" in facet  # its own frame and the subject
    assert (
        "survival" not in facet and "color" not in facet and "pigments" not in facet
    )  # siblings' items are not carried into it


def test_the_subject_is_an_anchored_referent_never_an_obligation(monkeypatch):
    monkeypatch.setitem(base.UNIT_OBLIGATIONS, "how does the coral effect", SUBJECT_FRAME)
    monkeypatch.setattr(
        base, "WHOLE", [w for w in base.WHOLE if w["kind"] == "output_expectation"]
    )  # nothing else accounts for the subject words
    result, model = base.run(repair=False)
    parent = result["parent_contract"]
    subject = parent["referents"][0]
    assert subject["text"] == "coral effect" and subject["status"] == "candidate_referent"
    assert Q[subject["spans"][0][0] : subject["spans"][0][1]] == "coral effect"
    assert subject["id"] not in {r["id"] for r in parent["requirements"]}  # it is not in the obligation list
    kids = [c for c in result["pass1"]["children"] if c["kind"] == "generated"]
    assert all(subject["id"] not in c["owns"] and subject["id"] in c["context_referents"] for c in kids)
    assert "do NOT ask about it" in _child_prompts(model)[0]
    broken = copy.deepcopy(result["pass1"])
    broken["children"][0]["owns"].append(subject["id"])
    assert not checks.verify_traceability(parent, broken)["ok"]  # owning a referent is a traceability violation
    assert result["pass1"]["verified_traceability"]["ok"]


def test_cross_unit_relationships_still_receive_their_context_from_every_unit_they_span():
    result, model = base.run(repair=False)
    cross = next(c for c in result["pass1"]["children"] if len(c["origin"]["source_unit_ids"]) >= 2)
    prompt = _child_prompts(model, "coral effect")[0]
    assert "[u1]" in prompt and "[u2]" in prompt and "coral effect" in prompt and "its expression" in prompt
    assert cross["origin"]["source_unit_ids"] == ["u1", "u2"]
    scoped = prompt.split("Unresolved wording (NOT settled")[0]
    for unrelated in ("juveniles", "reef zones"):
        assert unrelated not in scoped


def test_whether_and_how_must_stay_attached_to_the_relationship_they_qualify():
    result, _ = base.run(repair=False)
    parent = result["parent_contract"]
    by = {r["id"]: r for r in parent["requirements"]}
    rel = next(r for r in parent["requirements"] if r["kind"] == "relationship" and "whether and how" in r["text"])
    pol = next(r for r in parent["requirements"] if r.get("part_of") == rel["id"] and r["kind"] == "polarity")
    man = next(r for r in parent["requirements"] if r.get("part_of") == rel["id"] and r["kind"] == "manner")
    good = "Do the specific reef zones relate to depth, and if so how?"
    detached = "Does the effect show up, and which reef zones relate to depth, and how?"  # "Does" appears, but not on the relationship's clause
    assert (
        checks.obligation_preservation(pol, good, by)["preserved"]
        and checks.obligation_preservation(man, good, by)["preserved"]
    )
    d = checks.obligation_preservation(pol, detached, by)
    assert d["preserved"] is False and "not in the clause" in d["note"]
    assert (
        checks.obligation_preservation(man, detached, by)["preserved"] is True
    )  # "and how" follows the relationship clause
    assert (
        checks.obligation_preservation(man, "How do the zones matter, and do they relate to depth?", by)["preserved"]
        is False
    )
    result2, _ = base.run({"whether and how": {"question": detached}}, repair=False)
    kid = next(c for c in result2["pass1"]["children"] if c["question"] == detached)
    assert any(f["flag"] == "obligation_not_lexically_preserved" and f["kind"] == "polarity" for f in kid["flags"])


def test_a_repair_that_reproduces_a_word_but_detaches_it_or_loses_another_obligation_is_rejected():
    first = (
        "Does the effect show up, and which reef zones relate to depth, and how?"  # polarity detached, manner attached
    )

    def overrides(prompt):
        if "Problems found" in prompt:  # attaches polarity but drops "how": a regression on a preserved obligation
            return {"question": "Do the specific reef zones relate to depth, and to which kinds of depth?"}
        return {"question": first}

    result, _ = base.run({"whether and how": overrides}, repair=True)
    rep = next(r for r in result["pass2"]["repairs"] if r["attempted"] and r["before"] == first)
    assert rep["accepted"] is False and (
        "loses previously preserved" in rep["rejected_reason"]
        or "hard failure" in rep["rejected_reason"]
        or "departs from the researcher's wording" in rep["rejected_reason"]
    )
    assert next(c for c in result["pass2"]["children"] if c["child_id"] == rep["child_id"])["question"] == first
    blank = {
        "lost": [],
        "unsupported_additions": [],
        "deixis": [],
        "possible_bundling_of_other_obligations": [],
        "assumed_readings": [],
        "silent_resolution": [],
        "hard_fail": False,
    }
    before = {**blank, "preservation": {"a": {"preserved": True}}, "unsupported_additions": ["x"]}
    after = {**blank, "preservation": {"a": {"preserved": False}}, "lost": ["a"]}
    assert checks.repair_acceptable(before, after)[0] is False  # fewer additions never buys back a lost obligation


def test_an_unresolved_referent_is_offered_only_as_candidate_readings_and_never_silently_approved():
    result, model = base.run(repair=False)
    rel_prompt = _child_prompts(model, "whether and how they relate to depth")[0]
    block = rel_prompt.split("Unresolved wording (NOT settled", 1)[1]
    assert (
        "NOT settled; no reading is approved" in rel_prompt
        and '"they"' in block
        and "specific reef zones" in block.split(NL * 2)[0]
    )
    kid = next(c for c in result["pass1"]["children"] if "whether and how" in c["question"].lower())
    read = next(i for i in kid["interpretations"] if i["kind"] == "reference_resolved_by_rewrite")
    assert read["status"] == "assumed_not_approved" and read["declared_by_writer"] and read["other_readings"]
    assert kid["status"] == "conditional_on_unresolved_reading"
    assert kid["child_id"] not in result["pass1"]["reconciliation"]["summary"]["successful_children"]
    rows = {r["id"]: r for r in result["pass1"]["reconciliation"]["rows"]}
    assert rows[kid["owns"][0]]["status"] == "owned_conditional_on_unresolved_reading"
    # the same wording WITHOUT reporting the reading is a silent resolution: a hard failure, never a success
    silent, _ = base.run(
        {"whether and how": {"question": base.CHILDREN["whether and how"], "unresolved": []}}, repair=False
    )
    bad = next(c for c in silent["pass1"]["children"] if "whether and how" in c["question"].lower())
    assert bad["diagnostics"]["silent_resolution"] == ["they"] and bad["diagnostics"]["hard_fail"]
    assert any(f["flag"] == "silent_resolution_of_referent" for f in bad["flags"])


def test_an_elliptical_fragment_is_kept_unresolved_not_rewritten():
    model = ScriptedModel(base.responder())
    result = run_engine(SCALES_Q, model, repair=False)
    kids = result["pass1"]["children"]
    ell = next(c for c in kids if c["kind"] == "unresolved_elliptical")
    assert (
        ell["question"] == "and using which scales?"
        and ell["status"] == "elliptical_unresolved"
        and ell["is_decomposition"] is False
    )
    assert ell["candidate_targets"] and any(f["flag"] == "elliptical_fragment_target_not_stated" for f in ell["flags"])
    writes = [c for c in model.calls if "What this question must ask" in c["prompt"]]
    assert len(writes) == sum(
        1 for c in kids if c["kind"] == "generated"
    )  # no model call was spent on the unresolved item
    rec = result["pass1"]["reconciliation"]
    assert {r["id"]: r["status"] for r in rec["rows"]}[ell["owns"][0]] == "elliptical_unresolved"
    assert (
        ell["child_id"] not in rec["summary"]["successful_children"] and result["pass1"]["verified_traceability"]["ok"]
    )


def test_the_cli_writes_all_artifacts_without_a_stale_key_crash(tmp_path):
    from experiments.ask_cli_revised.decompose.__main__ import main, write_artifacts

    result, _ = base.run(repair=True)
    write_artifacts(result, tmp_path / "with_repair")
    names = (
        "00_request.json",
        "01_parent_contract.json",
        "02_pass1_children.json",
        "03_pass1_audit.json",
        "04_pass2_repaired.json",
        "05_pass2_audit.json",
        "06_final_reconciliation.json",
        "model_calls.jsonl",
        "engine_manifest.json",
        "REPORT.md",
    )
    for name in names:
        assert (tmp_path / "with_repair" / name).stat().st_size > 0, name
    no_repair, _ = base.run(repair=False)
    write_artifacts(no_repair, tmp_path / "no_repair")
    assert not (tmp_path / "no_repair" / "04_pass2_repaired.json").exists()
    calls = (
        tmp_path / "calls.jsonl"
    )  # end to end through main(): recorded calls replayed for every stage (no model, no network)
    calls.write_text("".join(json.dumps(r) + NL for r in result["calls"]), encoding="utf-8")
    code = main(
        ["--question", Q, "--replay-calls", str(calls), "--out", str(tmp_path / "replayed"), "--max-calls", "40"]
    )
    assert code == 0 and (tmp_path / "replayed" / "REPORT.md").read_text(encoding="utf-8").startswith(
        "# Decomposition report"
    )


def test_the_engine_can_take_its_inventory_from_recorded_calls_and_spend_live_calls_only_on_wording():
    first, _ = base.run(repair=False)
    recorded = [r for r in first["calls"] if r["task"].startswith("parent.")]
    live = ScriptedModel(base.responder())
    again = run_engine(Q, live, repair=False, max_calls=25, inventory_model=ReplayModel(recorded, "recorded"))
    assert all(
        "Part to read" not in c["prompt"] and "Question:" not in c["prompt"] for c in live.calls
    )  # no inventory call reached the live model
    assert again["manifest"]["call_summary"]["calls"] == len(live.calls) <= 25
    assert again["manifest"]["inventory_model"]["new_model_calls"] == 0
    assert [c["question"] for c in again["pass1"]["children"]] == [c["question"] for c in first["pass1"]["children"]]
