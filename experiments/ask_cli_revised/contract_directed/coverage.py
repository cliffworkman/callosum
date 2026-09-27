"""Coverage per frozen obligation unit, and the evidence set each child is given. Deterministic; no model, no score.

A unit is `evidence_attached` only if some finding bundle CLOSED it (closure.py: every required slot, own-study attribution, no
unresolved seam, one bundle). `partial_only` means relevant material exists that cannot close it; the unit is not resolved.
`unresolved_mechanical` means model calls failed for this child, so "searched and found nothing" cannot be claimed;
`unresolved_budget` means eligible work was capped or not run; only `unresolved_searched` says the bounded search found
nothing, and even then it is silence, not a certificate: completeness is always `not_certified`.
"""

from __future__ import annotations

from experiments.ask_cli_revised.contract_directed import closure
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract

ATTACHED = "evidence_attached"
PARTIAL_ONLY = "partial_only"
UNRESOLVED_MECHANICAL = "unresolved_mechanical"
UNRESOLVED_BUDGET = "unresolved_budget"
UNRESOLVED_SEARCHED = "unresolved_searched"


def coverage_rows(child: ChildContract, eligibility: list[dict], *, search: dict) -> list[dict]:
    """One row per content unit, plus one row per condition unit mirroring its parent's state.

    `eligibility`: judge_packet records for THIS child. `search`: {papers_nominated, papers_inspected, papers_deferred,
    not_inspectable_no_chunks, neighborhoods_read, none_established, budget_capped, not_run_budget, no_answer_calls, recovery_run}.
    """
    usable = [e for e in eligibility if e.get("state") == "usable"]
    mechanical = sum(1 for e in eligibility if e.get("state") == "no_answer") + int(search.get("no_answer_calls", 0))
    capped = int(search.get("budget_capped", 0)) + int(search.get("not_run_budget", 0))
    rows: list[dict] = []
    for unit in child.content_units:
        closing, partial, missing = [], [], {}
        for record in usable:
            entry = record["per_unit"].get(unit.unit_id)
            if entry is None:
                continue
            if entry["status"] == closure.DIRECTLY:
                closing.append(record["packet_id"])
            elif entry["status"] == closure.PARTIAL:
                partial.append(record["packet_id"])
                missing[record["packet_id"]] = {"missing": entry["missing"], "reasons": entry["reasons"]}
        if closing:
            state = ATTACHED
        elif partial:
            state = PARTIAL_ONLY
        elif mechanical:
            state = UNRESOLVED_MECHANICAL
        elif capped:
            state = UNRESOLVED_BUDGET
        else:
            state = UNRESOLVED_SEARCHED
        rows.append(
            {
                "child_id": child.child_id, "unit_id": unit.unit_id, "unit_kind": unit.kind, "unit_text": unit.text,
                "state": state, "closing_packet_ids": closing, "partial_packet_ids": partial, "missing_by_partial_packet": missing,
                "search": dict(search), "completeness": "not_certified", "row_type": "content",
            }
        )  # fmt: skip
    parent = next(r for r in rows if r["unit_id"] == child.primary_unit_id)
    polarity_seen = sorted(
        {
            e["per_unit"][child.primary_unit_id].get("polarity")
            for e in usable
            if child.primary_unit_id in e["per_unit"] and e["per_unit"][child.primary_unit_id].get("polarity")
        }
    )
    for unit in child.condition_units:
        rows.append(
            {
                "child_id": child.child_id, "unit_id": unit.unit_id, "unit_kind": unit.kind, "unit_text": unit.text,
                "state": parent["state"], "parent_unit_id": child.primary_unit_id, "polarity_values_seen": polarity_seen,
                "completeness": "not_certified", "row_type": "condition",
                "note": "a condition (whether/how/specific/any/effective) is evaluated on its parent unit's row, never closed alone",
            }
        )  # fmt: skip
    return rows


def unresolved_content_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["row_type"] == "content" and r["state"] != ATTACHED]


def child_evidence(child: ChildContract, packets_by_id: dict[str, dict], eligibility: list[dict]) -> list[dict]:
    """The packets a child is given: any packet that closes or partially establishes at least one of ITS OWN units.

    Closing packets first (more closed units first), then partial ones; ties broken by paper then packet id, so the order is
    stable and never a hidden relevance score. Whole packets move; nothing from a sibling's answer travels.
    """
    ranked = []
    for record in eligibility:
        if record.get("state") != "usable" or record["packet_id"] not in packets_by_id:
            continue
        statuses = [e["status"] for e in record["per_unit"].values()]
        closed = statuses.count(closure.DIRECTLY)
        partial = statuses.count(closure.PARTIAL)
        if closed or partial:
            packet = packets_by_id[record["packet_id"]]
            ranked.append((-closed, -partial, packet["paper_id"], record["packet_id"], packet))
    ranked.sort(key=lambda t: t[:4])
    return [t[4] for t in ranked]


def assignment_matrix(child_ids: list[str], eligibility_by_child: dict[str, list[dict]]) -> dict:
    """packet_id -> child_id -> {unit_id: status, route_relation}: the inspectable record of which child got which packet and why."""
    matrix: dict[str, dict] = {}
    for child_id in child_ids:
        for record in eligibility_by_child.get(child_id, []):
            if record.get("state") != "usable":
                matrix.setdefault(record["packet_id"], {})[child_id] = {
                    "state": record.get("state"),
                    "outcome": record.get("outcome"),
                }
                continue
            matrix.setdefault(record["packet_id"], {})[child_id] = {
                "route_relation": record["route_relation"],
                "units": {
                    uid: {"status": e["status"], "missing": e["missing"]} for uid, e in record["per_unit"].items()
                },
            }
    return matrix
