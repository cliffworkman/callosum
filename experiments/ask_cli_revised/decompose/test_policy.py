"""Model-free tests for three corrections made after reading the first scoped-wording run."""

from __future__ import annotations

import experiments.ask_cli_revised.decompose.test_decompose as base
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ScriptedModel
from experiments.ask_cli_revised.decompose.test_scoped_wording import SCALES_Q

Q = base.Q


def test_a_child_equal_to_a_unit_that_is_one_atomic_ask_is_not_a_copy_but_a_repeated_compound_still_is():
    atomic = "is there any evidence for the effect in juveniles?"
    result, _ = base.run({"is there any": {"question": atomic}}, repair=False)
    kid = next(c for c in result["pass1"]["children"] if c["question"] == atomic)
    assert not kid["diagnostics"]["copies_of_source_text"] and not kid["diagnostics"]["hard_fail"]
    compound = "Please return specific reef zones and whether and how they relate to depth, which kinds of depth."
    bad, _ = base.run({"whether and how": {"question": compound}}, repair=False)
    repeated = next(c for c in bad["pass1"]["children"] if c["question"] == compound)
    assert repeated["diagnostics"]["copies_of_source_text"] and repeated["diagnostics"]["hard_fail"]


def test_candidate_targets_for_an_elliptical_fragment_are_the_anchors_nearest_it():
    result = run_engine(SCALES_Q, ScriptedModel(base.responder()), repair=False)
    ell = next(c for c in result["pass1"]["children"] if c["kind"] == "unresolved_elliptical")
    previous_unit_anchors = [
        r for r in result["parent_contract"]["requirements"] if r["kind"] == "existence" and r["unit_ids"] == ["u3"]
    ]
    assert [t["id"] for t in ell["candidate_targets"]] == [r["id"] for r in previous_unit_anchors][-3:]


def test_a_lexically_acceptable_repair_is_only_a_proposal_and_never_becomes_the_final():
    def overrides(prompt):
        if "Problems found" in prompt:
            return {"question": "Whether and how the specific reef zones relate to depth, which kinds of depth"}
        return {"question": "What is the relation of the specific reef zones to depth?"}

    result, _ = base.run({"whether and how": overrides}, repair=True)
    proposal = next(r for r in result["pass2"]["repairs"] if r["attempted"] and r["accepted"])
    assert proposal["pending_human_review"] is True
    assert result["final_pass"] == 1 and result["final"] is result["pass1"]
    first = next(c for c in result["final"]["children"] if c["child_id"] == proposal["child_id"])
    assert (
        first["question"] == proposal["before"] and first["question"] != proposal["after"]
    )  # the proposal is stored beside it, not applied
    assert any(c.get("pending_human_review") for c in result["pass2"]["children"])
