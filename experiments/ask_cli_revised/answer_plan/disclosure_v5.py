"""Presentation of stored Layer C facts; no scientific selection or inference."""

from experiments.ask_cli_revised._layerc_common import plain


def prefix_for(relation, aggregation):
    """The visible qualifier for evidence the scientific record does not attribute to the citing study's own result."""
    synthesis = aggregation == "literature_synthesis"
    if relation == "attributed_external":
        return (
            "The source reports a synthesis of prior evidence: " if synthesis else "The source reports prior evidence: "
        )
    if synthesis:
        return "The source reports a synthesis: " if relation == "current_document" else "Synthesis evidence: "
    if relation == "unresolved":
        return "Evidence with unresolved source attribution: "
    return ""


def source_qualifications(records):
    """Follow each existing value path to its own candidate, never a representative."""
    result = {}
    for ref, path in records["value_coverage"].items():
        view = records["support_views"][path["establishment_refs"][0]["ref"]]
        metadata_ref = records["candidate_metadata_by_support"].get(view["support_ref"])
        if metadata_ref is None:
            continue
        payload = records["candidate_metadata"][metadata_ref]["payload"]
        relation, aggregation = payload["assertion_relation"], payload["aggregation"]
        text = prefix_for(relation, aggregation)
        if text:
            result[ref] = {
                "candidate_metadata_ref": metadata_ref,
                "assertion_relation": relation,
                "aggregation": aggregation,
                "prefix": text,
            }
    return result


def facet_disclosures(facet, req, records, finalized, recovery, search, units):
    """Explain existing states, retaining exact references for supporting evidence/audit."""
    child, rid = facet["child_id"], facet["facet_id"]
    paths = {ref: records["value_coverage"][ref] for ref in facet["value_coverage_refs"]}
    own = {ref: p for ref, p in paths.items() if p["establishment_refs"][0]["immediate_operand_source"] == "own"}
    result = []

    def add(kind, text, refs=()):
        result.append({"kind": kind, "facet_id": rid, "text": text, "evidence_refs": sorted(refs)})

    nulls = [
        ref
        for ref, p in own.items()
        if p["reported_finding"] == "null_finding"
        and p["scientific_goal_state"] == "unestablished"
        and finalized[ref]["display_state"] == "supported"
    ]
    if nulls:
        add(
            "null_goal_unsatisfied",
            "The null finding can answer what was found; it does not establish the positive finding sought.",
            nulls,
        )
    displayed_established = {
        p["value_id"]
        for ref, p in own.items()
        if p["scientific_goal_state"] == "established" and finalized[ref]["display_state"] == "supported"
    }
    limited = [
        ref
        for ref, p in own.items()
        if p["scientific_goal_state"] == "established" and p["value_id"] not in displayed_established
    ]
    # Evidence withheld because it describes the people being judged, not the people judging, is a limit of the
    # evidence for this part. Calling it a presentation limit would misstate why it is not reported.
    off_target = [
        ref
        for ref in limited
        if finalized[ref]["attempts"] and all("not_stimulus_rating" in a["reasons"] for a in finalized[ref]["attempts"])
    ]
    if off_target:
        add(
            "responsiveness_limitation",
            "Evidence mapped to this part reports how the people being judged were rated, not characteristics of the people judging, so it is not reported as an answer here. This does not show that the library holds no relevant evidence.",
            off_target,
        )
    if len(limited) > len(off_target):
        add(
            "presentation_limitation",
            "An evidence-supported value cannot be displayed with an authorized quotation here; this is a presentation limitation, not scientific absence.",
            [ref for ref in limited if ref not in off_target],
        )
    relation_display_limited = facet["relation_established"] is True and not any(
        p["purpose"] == "i1_relation_witness" and p["display_state"] == "supported"
        for ref in facet["relation_unit_refs"]
        for p in units[ref]["paths"]
    )
    if relation_display_limited:
        add(
            "relation_presentation_limitation",
            "The requested relationship is established, but its supporting quotation cannot be displayed here.",
            facet["relation_unit_refs"],
        )
    elif facet["relation_established"] is False:
        add(
            "relation_unestablished",
            "The available evidence does not establish the requested relationship; separately supported findings do not suffice.",
            facet["relation_unit_refs"],
        )
    elif facet["state"] == "not_established" and not limited:
        add("not_established", "The available evidence does not establish an answer to this part.")
    elif facet["state"] == "partial" and not limited and req["instance_quantifier"] != "open_list":
        add("incomplete_reporting", "The evidence answers only part of this question.")
    if req["instance_quantifier"] == "open_list" and facet["reported_value_refs"]:
        add(
            "open_list",
            "These are reported examples; completeness of the list is not established.",
            facet["reported_value_refs"],
        )

    # Excluded/uncertain candidates remain diagnostic. They never supply a quote or citation.
    if facet["state"] != "answered":
        ambiguous, excluded, attributed = [], [], []
        for ref, metadata in records["candidate_metadata"].items():
            place, payload = metadata["placement"], metadata["payload"]
            if (place["child_id"], place["requirement_id"]) != (child, rid):
                continue
            if payload["attachment_ambiguous"]:
                ambiguous.append(ref)
            if payload["guard_exclusions"] or not payload["support_policy_evaluation"]["passed"]:
                excluded.append(ref)
            if not metadata["diagnostic_only"] and payload["assertion_relation"] == "attributed_external":
                attributed.append(ref)
        if ambiguous:
            add(
                "attachment_uncertainty",
                "Some evidence could not be attached unambiguously to the requested finding and is not used as support.",
                ambiguous,
            )
        if excluded:
            add(
                "excluded_evidence",
                "Some relevant evidence does not meet this requirement's support rules and is not used as support.",
                excluded,
            )
        if attributed and not facet["reported_value_refs"]:
            add(
                "attributed_evidence",
                "The retained evidence reports prior work; it is not a finding of the citing study.",
                attributed,
            )

    for ref, summary in records["summaries"].items():
        if (summary["child_id"], summary["requirement_id"]) != (child, rid):
            continue
        stored = summary["stored_summary"]
        subject = "Direction" if summary["kind"] == "direction" else "Effectiveness"
        if stored["has_within_instance_conflict"]:
            add(
                "observation_conflict",
                subject + " observations conflict for the same finding; a single conclusion is not established.",
                [ref],
            )
        elif stored["has_across_instance_heterogeneity"]:
            add(
                "observation_heterogeneity",
                subject + " differs across findings; one conclusion should not be applied to all of them.",
                [ref],
            )

    pending = {
        ref: target
        for ref, target in recovery.items()
        if target["search_child_id"] == child and target["requirement_id"] == rid
    }
    if facet["state"] != "answered" or nulls or pending:
        status = search.get(rid, {})
        if status.get("terminal") is True and status.get("completed") is True:
            message = "The completed scoped search found no satisfying evidence; this does not establish absence beyond that search."
        elif status.get("completed") is True:
            message = "The scoped search completed, but this obligation remains unresolved."
        elif any(s["state"] == "not_completed" for s in status.get("target_states", {}).values()):
            message = "Recovery was attempted, but the scoped search is incomplete."
        elif status.get("target_states"):
            message = "Recovery has not completed the scoped search for this obligation."
        else:
            message = "A completed scoped search is not recorded for this unresolved obligation."
        # Display-only restrictions must not manufacture a scientific search obligation.
        if facet["scientific_goal_state"] not in ("established", "complete") or pending:
            add("search_status", message, pending)
    return plain(result)
