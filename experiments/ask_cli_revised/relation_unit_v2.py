"""Stored-proof relation units. Completion, I1, operands and display remain separate."""

from experiments.ask_cli_revised._layerc_common import body_reference, canonical, plain
from experiments.ask_cli_revised.answer_plan.text import contains
from experiments.ask_cli_revised.claim_v2 import place_key, requirements, value_for_assignment


def joint_display(proof, coverage, records, finalized):
    """Restrict existing member paths to a joint sentence at the stored proof's source.

    Text validation occurs after the assignment and value association are authorized.
    An inherited operand can be checked in the child's own witness sentence; its parent
    source never becomes the child's citation authority.
    """
    pid = proof["join"].get("proposition_id")
    if not pid:
        return []
    own = [
        k
        for k in coverage
        if records["value_coverage"][k]["establishment_refs"][0]["immediate_operand_source"] == "own"
    ]
    if not own:
        return []
    sentences = None
    for key in own:
        available = {a["sentence"] for a in finalized[key]["accepted"] if a["proposition_id"] == pid}
        sentences = available if sentences is None else sentences & available
    literals = [
        records["support_records"][records["support_views"][a["support_view_id"]]["support_ref"]]["exact_text"]
        for a in proof["assignment"].values()
        if a["immediate_operand_source"] == "inherited"
    ]
    return sorted(s for s in sentences or () if all(contains(literal, s) for literal in literals))


def build_relation_units(projection, authored, claims, receipts, finalized):
    r, reqs, result = projection.records, requirements(authored), {}
    for placement in r["placements"].values():
        p = placement["placement"]
        q = reqs[p["child_id"], p["requirement_id"]]
        required = list(q["role_completion"]["required_roles"])
        proofs = {k: v for k, v in r["proofs"].items() if v["placement"] == p}
        completion_only = len(required) < 2
        if completion_only:
            proofs = {
                k: v for k, v in proofs.items() if v["purpose"] == "completion_joint" and len(v["assignment"]) >= 2
            }
            if not proofs:
                continue
        tuples = {}
        for proof_ref, proof in sorted(proofs.items()):
            values = value_for_assignment(r, proof["assignment"])
            group = tuples.setdefault(canonical(values), {"values": values, "proofs": []})
            group["proofs"].append(proof_ref)
        if not tuples:
            # An incomplete diagnostic unit records the available value sets. It asserts no
            # join and never forms a Cartesian product or elevates a representative.
            values = {
                role: sorted(
                    {
                        path["value_id"]
                        for path in r["value_coverage"].values()
                        if place_key(path["placement"]) == place_key(p) and path["placement"]["role"] == role
                    }
                )
                for role in required
            }
            tuples[canonical(values)] = {"values": values, "proofs": []}
        for group in tuples.values():
            proof_refs = group["proofs"]
            completion = [k for k in proof_refs if r["proofs"][k]["purpose"] == "completion_joint"]
            i1 = [k for k in proof_refs if r["proofs"][k]["purpose"] == "i1_relation_witness"]
            paths = []
            for ref in proof_refs:
                proof = r["proofs"][ref]
                selected = {role: a["support_view_id"] for role, a in proof["assignment"].items()}
                coverage = sorted(
                    k
                    for k, path in r["value_coverage"].items()
                    if path["establishment_refs"][0]["ref"] in selected.values()
                    and path["value_id"] in group["values"].values()
                )
                pid = proof["join"].get("proposition_id")
                sentences = joint_display(proof, coverage, r, finalized)
                paths.append(
                    {
                        "proof_ref": ref,
                        "purpose": proof["purpose"],
                        "selected_support_refs": selected,
                        "operand_text_refs": {
                            role: plain(r["support_views"][vid]["operand_text_ref"]) for role, vid in selected.items()
                        },
                        "operand_sources": {
                            role: a["immediate_operand_source"] for role, a in proof["assignment"].items()
                        },
                        "coverage_refs": coverage,
                        "join": plain(proof["join"]),
                        "own_witness_citations": [pid] if pid and proof["purpose"] == "i1_relation_witness" else [],
                        "context_status": plain(r["link_context_status"].get(ref)),
                        "joint_sentences": sentences,
                        "display_state": "supported" if sentences else "restricted",
                    }
                )
            linked_claims = sorted(c["claim_id"] for c in claims if set(c["relation_proof_refs"]) & set(proof_refs))
            observations = sorted(
                oid
                for oid, obs in r["observations"].items()
                if obs["placement"] == p
                and (
                    not proof_refs
                    or any(
                        set(path["witness_proof_refs"]) & set(proof_refs)
                        or set(path["selected_support_view_refs"].values())
                        <= {a["support_view_id"] for ref in proof_refs for a in r["proofs"][ref]["assignment"].values()}
                        for path in obs["record"]["evidence_alignment"]["paths"]
                    )
                )
            )
            body = {
                "schema": "relation-unit-v2",
                "placement": plain(p),
                "semantic_tuple": group["values"],
                "required_roles": required,
                "engine_complete": placement["complete"],
                "completion_status": placement["joint_grounding"]["status"],
                "completion_proofs": completion,
                "i1_status": "not_applicable" if completion_only else "proved" if i1 else "unestablished",
                "i1_proofs": i1,
                "relation_witnessed": None if completion_only else bool(i1),
                "witness_ids": sorted({pid for path in paths for pid in path["own_witness_citations"]}),
                "semantic_establishedness": "established" if proof_refs else "unestablished",
                "renderability": "supported"
                if any(path["display_state"] == "supported" for path in paths)
                else "restricted"
                if proof_refs
                else "unavailable",
                "paths": paths,
                "claim_refs": linked_claims,
                "receipt_refs": sorted(
                    k
                    for k, receipt in receipts.items()
                    if receipt["claim_ref"] in linked_claims and set(receipt["relation_proof"]) & set(proof_refs)
                ),
                "observation_refs": observations,
                "summary_refs": sorted(
                    k
                    for k, s in r["summaries"].items()
                    if s["child_id"] == p["child_id"] and s["requirement_id"] == p["requirement_id"]
                ),
                "diagnostics": [plain(d) for d in r["diagnostics"] if place_key(d["placement"]) == place_key(p)],
            }
            key = body_reference("relation-unit-v2", {"placement": plain(p), "semantic_tuple": group["values"]})
            result[key] = body
    return result
