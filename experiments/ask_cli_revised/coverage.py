"""Stage 9 deterministic coverage audit over the proposition ledger.

Legacy natural-language obligations retain historical mapping states for replay.
Literal 0.6.0 units report evidence association without certifying completeness;
the separate original-request audit retains the higher-fidelity denominator.
"""

from __future__ import annotations


def _verified(rec: dict) -> bool:
    return rec.get("verification", {}).get("status") == "verified"


def audit_coverage(subquestions: list[dict], records: list[dict]) -> dict:
    """Return obligation and subquestion coverage plus the inputs to one bounded recovery pass."""
    verified_by_ob: dict[str, int] = {}
    mapped_by_ob: dict[str, int] = {}
    for rec in records:
        is_verified = _verified(rec)
        for field_id in rec.get("obligation_ids", []):
            mapped_by_ob[field_id] = mapped_by_ob.get(field_id, 0) + 1
            if is_verified:
                verified_by_ob[field_id] = verified_by_ob.get(field_id, 0) + 1

    obligations_out: list[dict] = []
    per_subq_states: dict[str, list[str]] = {}
    gaps: list[dict] = []
    for subquestion in subquestions:
        sid = subquestion["subquestion_id"]
        for obligation in subquestion.get("obligations", []):
            field_id = obligation["field_id"]
            if verified_by_ob.get(field_id, 0) > 0:
                state = "answered"
            elif mapped_by_ob.get(field_id, 0) > 0:
                state = "unresolved"
            else:
                state = "unanswered"
            if obligation.get("coverage_basis") == "literal_unit" and state == "answered":
                # A mapped verified claim may answer only one part of a compound
                # source unit. Mapping is evidence association, not completion.
                state = "evidence_mapped_completeness_unassessed"
            row = {
                "field_id": field_id,
                "subquestion_id": sid,
                "note": obligation.get("note", ""),
                "state": state,
            }
            if obligation.get("kind"):
                row["kind"] = obligation["kind"]
            obligations_out.append(row)
            per_subq_states.setdefault(sid, []).append(state)
            if state in {"unresolved", "unanswered", "evidence_mapped_completeness_unassessed"}:
                gaps.append(dict(row))

    subquestions_out: list[dict] = []
    for subquestion in subquestions:
        states = per_subq_states.get(subquestion["subquestion_id"], [])
        if not states:
            rollup = "unanswered"
        elif all(state == "answered" for state in states):
            rollup = "answered"
        elif all(state == "unanswered" for state in states):
            rollup = "unanswered"
        else:
            rollup = "partial"
        subquestions_out.append(
            {
                "subquestion_id": subquestion["subquestion_id"],
                "text": subquestion["text"],
                "state": rollup,
            }
        )

    return {"obligations": obligations_out, "subquestions": subquestions_out, "gaps": gaps}
