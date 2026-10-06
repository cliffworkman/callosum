"""Phase-30 offline regression over the preserved Phase-28 Attempt-2 artifacts (structure and invariants, not prose).

Skips when the gitignored run directory is absent. It never tunes expectations to the human Phase-29 prototype.
"""

from __future__ import annotations

import json

import pytest

from experiments.ask_cli_revised.answer_plan import overlay as ov
from experiments.ask_cli_revised.answer_plan import replay as rp

RUN = rp.DEFAULT_RUN
pytestmark = pytest.mark.skipif(not (RUN / "11_verified_ledger.json").exists(), reason="preserved Phase-28 run absent")


@pytest.fixture(scope="module")
def replay_out(tmp_path_factory):
    out = tmp_path_factory.mktemp("phase30_replay")
    assert rp.main(["--run-dir", str(RUN), "--out-dir", str(out), "--allow-historical-unversioned-map"]) == 0
    return out


@pytest.fixture(scope="module")
def audit(replay_out):
    return json.loads((replay_out / "answer_plan_audit.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plan(replay_out):
    return json.loads((replay_out / "answer_plan.json").read_text(encoding="utf-8"))


def test_every_invariant_passes(audit):
    assert audit["failed_checks"] == []
    assert audit["plan_deterministic"] is True
    assert audit["parent_claim_ledger_identical_to_phase28_record"] is True


def test_node_states_are_the_conservative_replay_outcome(plan):
    states = {n["label"]: n["status"] for n in plan["nodes"]}
    assert states == {
        "1": "not_established",
        "2": "not_established",
        "3": "partial",
        "4": "not_established",
        "4A": "not_established",
        "4B": "partial",
        "5": "not_established",
        "6": "not_established",
        "7": "partial",
    }


def test_every_confirmed_node_is_present_with_its_literal_wording_in_order(plan):
    labels = [n["label"] for n in plan["nodes"]]
    assert labels == ["1", "2", "3", "4", "4A", "4B", "5", "6", "7"]
    assert all(n["literal_text"] for n in plan["nodes"])


def test_engine_complete_but_unwitnessed_relations_are_recorded_not_claimed(audit, plan):
    disagreements = audit["disagreements_engine_complete_vs_witnessed"]
    assert {d["child_id"] for d in disagreements} == {"c5", "c6"}
    assert len(disagreements) == 4
    assert all(d["answerplan_relation_witnessed"] is False for d in disagreements)
    assert not any(
        s["kind"] == "relation_sentence" for n in plan["nodes"] if n["label"] in ("4A", "4B") for s in n["statements"]
    )


def test_negated_implicit_result_is_rendered_verbatim_not_as_bare_evidence(plan):
    texts = [s["text"] for n in plan["nodes"] for s in n["statements"]]
    assert any("implicit biases were slight and not significant" in t for t in texts)
    assert not any(t.strip().rstrip(".").lower() in {"implicit", "explicit"} for t in texts)


def test_generic_summary_and_adjacent_construct_never_answer_a_facet(plan):
    texts = " ".join(s["text"] for n in plan["nodes"] for s in n["statements"])
    assert "earlier reports" not in texts
    node2 = next(n for n in plan["nodes"] if n["label"] == "2")
    assert node2["statements"] == []


def test_direction_is_only_ever_a_value_level_sentence_with_its_subject(plan):
    valence = [s for n in plan["nodes"] for s in n["statements"] if s["kind"] == "value_level_valence"]
    # I3: the preserved c6 valence came from the removed single-operand fallback, so no value-level valence is rendered on
    # this map. Any valence that is rendered must still name its subject, and that subject must appear in its text.
    assert valence == []
    assert all(s["subject"] and s["subject"] in s["text"] for s in valence)


def test_layer_one_has_no_internal_identifiers_or_templates(replay_out):
    text = (replay_out / "deterministic_layer1.md").read_text(encoding="utf-8")
    for token in (
        "::",
        "no_grounded_sentences",
        "relationship_unverified",
        "A direction finding",
        "individual_difference",
    ):
        assert token not in text
    assert "NAME" in text and "“" in text


def test_replay_authorization_is_bound_to_the_overlay_and_does_not_claim_the_live_run(replay_out):
    auth = json.loads((replay_out / "replay_decomposition_authorization.json").read_text(encoding="utf-8"))
    overlay = ov.load_overlay()
    assert auth["overlay_sha256"] == ov.overlay_sha256(overlay)
    assert auth["postdates_phase28_attempt2_live_run"] is True
    assert "does_not_claim" in auth
    assert len(auth["historical_decomposition_status"]) == 11


def test_plan_is_identical_across_two_builds(replay_out, tmp_path):
    assert rp.main(["--run-dir", str(RUN), "--out-dir", str(tmp_path), "--allow-historical-unversioned-map"]) == 0
    first = json.loads((replay_out / "answer_plan.json").read_text(encoding="utf-8"))
    second = json.loads((tmp_path / "answer_plan.json").read_text(encoding="utf-8"))
    assert first["plan_sha256"] == second["plan_sha256"]
