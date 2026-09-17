"""Deterministic fabricated rehearsal. No actual frontier or human judgments."""

from .capability import suite, synthetic_evidence
from .core import ROSTER, canonical, require, synthetic_cases
from .manifest import implementation_manifest
from .storage import Store
from .study import Review, SyntheticStudy, synthetic_design


def run_demo():
    packets = suite()
    records = [synthetic_evidence(sid, packets) for sid, _ in ROSTER]
    cases = synthetic_cases(16)
    study = SyntheticStudy(cases)
    study.freeze_a(records, packets)
    store = Store.create()
    store.write("implementation_manifest.json", canonical(implementation_manifest()))
    store.write("synthetic_capabilities.json", canonical(records))
    store.write(
        "synthetic_inputs.json",
        canonical(
            {
                "origin": "SYNTHETIC",
                "unit_count": 16,
                "padding": 64,
                "capability_packets": [p.receipt() for p in packets],
            }
        ),
    )
    for sid, _ in ROSTER:
        # Reasons are fabricated parser/orchestration fixtures, not model judgments.
        rows = [
            {
                "candidate_id": c.candidate_id,
                "label": "UNCERTAIN" if c.index == 9 else "NO_FLAG",
                "reason": "SYNTHETIC concern: invented fixture pattern" if c.index == 9 else "",
            }
            for c in cases
        ]
        raw = canonical(rows)
        store.write(f"fixture_{sid}.json", raw, kind="SYNTHETIC_FRONTIER_RESPONSE")
        study.record_screen(sid, [c.candidate_id for c in cases], raw)
    study.close_frontier()
    private_rows = study.private_frontier()
    study.amend_interstudy(
        findings="SYNTHETIC repeated fixture concern in one region",
        changes="Include the concerned region in a challenge, without showing selection reasons",
        why="Rehearse content-informed interstudy design, not vote-based certification",
        accessed_by=["SYNTHETIC_ORCHESTRATOR"],
    )
    study.freeze_b(synthetic_design(cases))
    for key, value in study.private_artifacts().items():
        store.write(f"simulation_{key}.json", canonical(value), kind="SYNTHETIC_STUDY_ARTIFACT")
    for config in ("fixture_a", "fixture_b"):
        store.write(f"human_{config}.json", canonical(study.human_packet(config)), kind="SYNTHETIC_HUMAN_PACKET")
        session = 0
        while pending := study.next_cases(config):
            session += 1
            for cid in pending:
                study.review(Review(cid, "PROMOTE", f"FAKE_SESSION_{session}"))
        require(study.outcome(config) == "ELIGIBLE_FOR_INTEGRATION_REVIEW", "SYNTHETIC_DEMO_FAILED")
    store.write(
        "simulation_completed_reviews.json", canonical(study.private_artifacts()["reviews"]), kind="SYNTHETIC_REVIEWS"
    )
    store.write(
        "simulation_completion.json",
        canonical(
            {
                "origin": "SYNTHETIC",
                "private_fixture_rows": len(private_rows),
                "not_a_real_qualification": True,
                "inference_calls": 0,
                "real_human_labels": 0,
            }
        ),
    )
    return store
