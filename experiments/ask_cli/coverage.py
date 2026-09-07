"""Stage 9: deterministic coverage audit over the ledger (no Qwen).

An obligation is `answered` iff a VERIFIED proposition maps to it; `unresolved` if some proposition mapped
but none verified; `unanswered` if nothing mapped. A subquestion rolls up to answered / partial / unanswered.
The uncovered obligations feed the single bounded gap-recovery pass.
"""

from __future__ import annotations


def _verified(rec: dict) -> bool:
    return rec.get("verification", {}).get("status") == "verified"


def audit_coverage(subquestions: list[dict], records: list[dict]) -> dict:
    """Return {obligations:[{field_id, subquestion_id, kind, state}], subquestions:[{id, state}], gaps:[...]}."""
    verified_by_ob: dict[str, int] = {}
    mapped_by_ob: dict[str, int] = {}
    for rec in records:
        v = _verified(rec)
        for fid in rec.get("obligation_ids", []):
            mapped_by_ob[fid] = mapped_by_ob.get(fid, 0) + 1
            if v:
                verified_by_ob[fid] = verified_by_ob.get(fid, 0) + 1

    obligations_out: list[dict] = []
    per_subq_states: dict[str, list[str]] = {}
    gaps: list[dict] = []
    for sq in subquestions:
        sid = sq["subquestion_id"]
        for ob in sq.get("obligations", []):
            fid = ob["field_id"]
            if verified_by_ob.get(fid, 0) > 0:
                state = "answered"
            elif mapped_by_ob.get(fid, 0) > 0:
                state = "unresolved"
            else:
                state = "unanswered"
            obligations_out.append(
                {"field_id": fid, "subquestion_id": sid, "kind": ob["kind"], "note": ob.get("note", ""), "state": state}
            )
            per_subq_states.setdefault(sid, []).append(state)
            if state in {"unresolved", "unanswered"}:
                gaps.append(
                    {
                        "field_id": fid,
                        "subquestion_id": sid,
                        "kind": ob["kind"],
                        "note": ob.get("note", ""),
                        "state": state,
                    }
                )

    subquestions_out = []
    for sq in subquestions:
        states = per_subq_states.get(sq["subquestion_id"], [])
        if not states:
            roll = "unanswered"  # no obligations -> nothing to answer
        elif all(s == "answered" for s in states):
            roll = "answered"
        elif all(s == "unanswered" for s in states):
            roll = "unanswered"
        else:
            roll = "partial"
        subquestions_out.append({"subquestion_id": sq["subquestion_id"], "text": sq["text"], "state": roll})

    return {"obligations": obligations_out, "subquestions": subquestions_out, "gaps": gaps}
