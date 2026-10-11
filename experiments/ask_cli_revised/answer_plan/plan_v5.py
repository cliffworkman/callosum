"""Explicit proof-aligned reporting plan; v4 remains the default."""

from experiments.ask_cli_revised._layerc_common import PROFILE, digest, plain
from experiments.ask_cli_revised.claim_v2 import place_key, requirements


def reporting_complete(req, placements, display, units):
    """Apply authored reporting obligations per placement, never a cross-instance union."""
    completion = req["role_completion"]
    passing = []
    for placement in placements:
        key = place_key(placement["placement"])
        roles = {p["placement"]["role"] for p in display.values() if place_key(p["placement"]) == key}
        rendered_relation = any(
            place_key(u["placement"]) == key
            and u["relation_witnessed"]
            and any(p["purpose"] == "i1_relation_witness" and p["display_state"] == "supported" for p in u["paths"])
            for u in units.values()
        )
        passing.append(
            bool(roles)
            and set(completion["required_roles"]) <= roles
            and all(set(g) & roles for g in completion["alternative_role_groups"])
            and (req["kind"] != "relational" or rendered_relation)
        )
    policy = req["instance_quantifier"]
    if policy == "open_list":
        return False  # Reportable examples cannot certify an exhaustive list.
    if policy == "for_each_discovered_instance":
        return bool(passing) and all(passing)
    if policy == "at_least_n":
        return sum(passing) >= req["quantifier_n"]
    return policy == "exists" and any(passing)


PLAN_VERSION = "answer-plan-step2-v5"


def build_plan(projection, authored, claims, receipts, units, finalized, synthesis, producer_authorization):
    r, facets = projection.records, {}
    for (child, rid), req in requirements(authored).items():
        placements = [
            p
            for p in r["placements"].values()
            if p["placement"]["child_id"] == child and p["placement"]["requirement_id"] == rid
        ]
        paths = {
            k: p
            for k, p in r["value_coverage"].items()
            if p["placement"]["child_id"] == child and p["placement"]["requirement_id"] == rid
        }
        own = {k: p for k, p in paths.items() if p["establishment_refs"][0]["immediate_operand_source"] == "own"}
        display = {k: p for k, p in own.items() if finalized[k]["display_state"] == "supported"}
        applicable = {
            k: u
            for k, u in units.items()
            if u["placement"]["child_id"] == child and u["placement"]["requirement_id"] == rid
        }
        covered = {p["placement"]["role"] for p in display.values()}
        relation_required = req["kind"] == "relational"
        i1 = any(u["relation_witnessed"] for u in applicable.values())
        target = i1 if relation_required else any(p["complete"] for p in placements)
        category = req["instance_quantifier"] == "all_requested_categories"
        category_axes = {}
        if category:
            requested = {term for spec in req["role_specs"].values() for term in spec["requested_category_terms"]}
            category_axes = {
                r["semantic_values"][p["value_id"]]["literal"]: {
                    "scientific_goal_state": p["scientific_goal_state"],
                    "reported_finding": p["reported_finding"],
                    "display_state": finalized[k]["display_state"],
                    "value_ref": p["value_id"],
                }
                for k, p in own.items()
            }
            categories = {
                r["semantic_values"][p["value_id"]]["literal"]
                for p in display.values()
                if p["reported_finding"] in ("positive_finding", "null_finding")
            }
            answered = requested <= categories
            goal = (
                "complete"
                if all(category_axes.get(t, {}).get("scientific_goal_state") == "established" for t in requested)
                else "incomplete"
            )
        else:
            categories = set()
            answered = reporting_complete(req, placements, display, applicable)
            goal = "established" if target else "unestablished"
        state = "answered" if answered else "partial" if target or display else "not_established"
        facets[rid] = {
            "facet_id": rid,
            "child_id": child,
            "state": state,
            "report_state": state,
            "map_requirement_state": sorted({p["requirement_state"] for p in placements}),
            "scientific_goal_state": goal,
            "relation_established": i1 if relation_required else None,
            "category_axes": category_axes,
            "covered_categories": sorted(categories),
            "covered_roles": sorted(covered),
            "value_coverage_refs": sorted(paths),
            "reported_value_refs": sorted({p["value_id"] for p in display.values()}),
            "relation_unit_refs": sorted(applicable),
            "claim_refs": sorted(
                c["claim_id"]
                for c in claims
                if c["semantic_identity"]["scope"] == {"owner_ids": [child], "requirement_ids": [rid]}
            ),
            "claim_evidence_refs": sorted(k for k, receipt in receipts.items() if receipt["coverage_ref"] in paths),
            "recovery_closed_by_reporting": False,
        }
    nodes = []
    for node in authored["overlay"]["nodes"]:
        owned = [f for f in facets.values() if f["child_id"] in node["owning_child_ids"]]
        states = [f["state"] for f in owned]
        state = (
            "answered"
            if states and all(s == "answered" for s in states)
            else "partial"
            if any(s in ("answered", "partial") for s in states)
            else "not_established"
        )
        nodes.append(
            {
                "label": node["label"],
                "literal_text": node["literal_text"],
                "parent": node.get("parent"),
                "state": state,
                "report_state": state,
                "facets": owned,
            }
        )
    plan = {
        "plan_version": PLAN_VERSION,
        "layerc_profile": PROFILE,
        "verified_producer_authorization_ref": producer_authorization.authorization_ref,
        "projection_ref": projection.projection_id,
        "projection_sha256": digest({"schema_version": projection.schema_version, "records": plain(r)}),
        "schemas": {
            "projection": projection.schema_version,
            "semantic_value": "semantic-value-v1",
            "value_coverage": "value-coverage-v1",
            "parent_claim": "parent-claim-v2",
            "claim_evidence": "claim-evidence-v1",
            "relation_unit": "relation-unit-v2",
            "parent_synthesis": "parent-synthesis-v2",
        },
        "sufficiency_identity": plain(producer_authorization.identities["sufficiency_identity"]),
        "producer_profile_ref": producer_authorization.identities["profile_ref"],
        "claim_ledger_sha256": digest(claims),
        "claim_evidence_sha256": digest(receipts),
        "relation_units_sha256": digest(units),
        "parent_synthesis_sha256": synthesis["record_sha256"],
        "nodes": nodes,
        "evidence_diagnostics": plain(r["diagnostics"]),
    }
    plan["plan_sha256"] = digest(plan)
    return plan
