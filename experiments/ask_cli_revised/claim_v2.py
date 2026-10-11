"""Projection-only scientific consumers: semantic claims and typed value evidence."""

from experiments.ask_cli_revised._layerc_common import (
    body_reference,
    canonical,
    plain,
    require,
    semantic_claim_id,
)


def requirements(authored):
    return {(child, q["id"]): q for child, rows in authored["requirements"].items() for q in rows}


def place_key(place):
    return canonical({k: place[k] for k in ("child_id", "requirement_id", "instance_key")})


def value_for_assignment(records, assignment):
    """Resolve an already selected tuple. No candidate search or alternative product."""
    literals = {
        role: records["support_records"][records["support_views"][a["support_view_id"]]["support_ref"]]["exact_text"]
        for role, a in assignment.items()
    }
    result = {}
    for role, a in assignment.items():
        matching = set()
        for path in records["value_coverage"].values():
            if path["establishment_refs"][0]["ref"] != a["support_view_id"]:
                continue
            value = records["semantic_values"][path["value_id"]]
            if value["kind"] == "evidence_slot" and any(
                literals.get(operand["role"]) != operand["literal"] for operand in value["operand_tuple"]
            ):
                continue
            matching.add(path["value_id"])
        require(len(matching) == 1, "selected proof operand has no unique semantic value")
        result[role] = matching.pop()
    return dict(sorted(result.items()))


def _contract(q):
    return {
        "required_roles": sorted(q["role_completion"]["required_roles"]),
        "alternative_role_groups": sorted(sorted(g) for g in q["role_completion"]["alternative_role_groups"]),
        "relationship_verifiers": sorted(q["relationship_verifiers"]),
    }


def _add(claims, family, child, req, content, values, paths, proofs=()):
    scope = {"owner_ids": [child], "requirement_ids": [req]}
    identity = {"schema": "parent-claim-v2", "family": family, "scope": scope, "content": content}
    cid = semantic_claim_id(family, scope, content)
    row = claims.setdefault(
        cid,
        {
            "schema": "parent-claim-v2",
            "claim_id": cid,
            "semantic_identity": identity,
            "member_value_refs": sorted(values),
            "value_coverage_refs": [],
            "relation_proof_refs": [],
        },
    )
    row["value_coverage_refs"] = sorted(set(row["value_coverage_refs"]) | set(paths))
    row["relation_proof_refs"] = sorted(set(row["relation_proof_refs"]) | set(proofs))


def build_claims(projection, authored):
    r = projection.records
    reqs, claims, used = requirements(authored), {}, set()
    complete = {place_key(p["placement"]) for p in r["placements"].values() if p["complete"]}
    # Completion and I1 remain separate. Completion proves the own tuple, including C1.
    for pid, proof in sorted(r["proofs"].items()):
        inherited_relation = proof["purpose"] == "i1_relation_witness" and any(
            a["immediate_operand_source"] == "inherited" for a in proof["assignment"].values()
        )
        if (proof["purpose"] != "completion_joint" and not inherited_relation) or len(proof["assignment"]) < 2:
            continue
        if place_key(proof["placement"]) not in complete:
            continue
        p = proof["placement"]
        values = value_for_assignment(r, proof["assignment"])
        views = {a["support_view_id"] for a in proof["assignment"].values()}
        paths = [
            ref
            for ref, path in r["value_coverage"].items()
            if path["value_id"] in values.values() and path["establishment_refs"][0]["ref"] in views
        ]
        used.update(paths)
        _add(
            claims,
            "relational",
            p["child_id"],
            p["requirement_id"],
            {
                "relation_kind": "required_role_relation" if inherited_relation else "joint_own_completion",
                "operands": values,
                "relation_contract": _contract(reqs[p["child_id"], p["requirement_id"]]),
            },
            values.values(),
            paths,
            [pid],
        )
    # Attach I1 as an independent purpose only to the already established same tuple.
    # This never substitutes a completion proof for relationship authority.
    for pid, proof in sorted(r["proofs"].items()):
        if proof["purpose"] != "i1_relation_witness":
            continue
        values = value_for_assignment(r, proof["assignment"])
        p = proof["placement"]
        for claim in claims.values():
            identity = claim["semantic_identity"]
            if (
                identity["family"] == "relational"
                and identity["scope"] == {"owner_ids": [p["child_id"]], "requirement_ids": [p["requirement_id"]]}
                and identity["content"]["operands"] == values
            ):
                claim["relation_proof_refs"] = sorted(set(claim["relation_proof_refs"]) | {pid})
    remaining = {}
    for ref, path in r["value_coverage"].items():
        if ref in used or path["establishment_refs"][0]["immediate_operand_source"] != "own":
            continue
        p = path["placement"]
        remaining.setdefault((p["child_id"], p["requirement_id"], p["role"]), []).append(ref)
    for (child, req, role), paths in sorted(remaining.items()):
        q = reqs[child, req]
        values = sorted({r["value_coverage"][ref]["value_id"] for ref in paths})
        places = {place_key(r["value_coverage"][ref]["placement"]) for ref in paths}
        list_like = q["instance_quantifier"] in (
            "exists",
            "open_list",
            "for_each_discovered_instance",
            "all_requested_categories",
        )
        if list_like and (len(values) > 1 or len(places) > 1):
            _add(
                claims,
                "category_list",
                child,
                req,
                {
                    "role": role,
                    "member_value_ids": values,
                    "grouping": {
                        "instance_quantifier": q["instance_quantifier"],
                        "quantifier_n": q.get("quantifier_n"),
                        "requested_category_terms": sorted(q["role_specs"][role].get("requested_category_terms", [])),
                    },
                },
                values,
                paths,
            )
        else:
            for value in values:
                _add(
                    claims,
                    "role_value",
                    child,
                    req,
                    {"role": role, "value_id": value},
                    [value],
                    [ref for ref in paths if r["value_coverage"][ref]["value_id"] == value],
                )
    for summary_ref, summary in sorted(r["summaries"].items()):
        if not summary["observation_refs"]:
            continue
        q = reqs[summary["child_id"], summary["requirement_id"]]
        tuples, paths, proofs = {}, set(), set()
        for oid in summary["observation_refs"]:
            for path in r["observations"][oid]["record"]["evidence_alignment"]["paths"]:
                assignment = {
                    role: {"support_view_id": vid} for role, vid in path["selected_support_view_refs"].items()
                }
                values = value_for_assignment(r, assignment)
                tuples[canonical(values)] = values
                proofs.update(path["witness_proof_refs"])
                paths.update(
                    ref
                    for ref, coverage in r["value_coverage"].items()
                    if coverage["value_id"] in values.values() and oid in coverage["observation_refs"]
                )
        stored = summary["stored_summary"]
        # Keep requirement scope, all participating tuples, and the producer's conflict axes.
        # A summary never broadcasts a sign to a tuple that did not contribute.
        content = {
            "summary_kind": summary["kind"],
            "operands": [tuples[k] for k in sorted(tuples)],
            "target_contract": plain(q[summary["kind"]]),
            "consensus": stored["consensus_value"],
            "conflict": {
                key: stored[key] for key in ("has_within_instance_conflict", "has_across_instance_heterogeneity")
            },
        }
        values = {v for t in tuples.values() for v in t.values()}
        _add(
            claims,
            "direction_or_effectiveness",
            summary["child_id"],
            summary["requirement_id"],
            content,
            values,
            paths,
            proofs,
        )
        cid = semantic_claim_id(
            "direction_or_effectiveness",
            {"owner_ids": [summary["child_id"]], "requirement_ids": [summary["requirement_id"]]},
            content,
        )
        claims[cid]["summary_ref"] = summary_ref
        claims[cid]["observation_refs"] = plain(summary["observation_refs"])
    return [claims[k] for k in sorted(claims)]


def evidence_receipts(projection, claims, finalized):
    """One receipt per claim/member/path. No flat union is an establishment edge."""
    result = {}
    for claim in claims:
        for path_ref in claim["value_coverage_refs"]:
            path = projection.records["value_coverage"][path_ref]
            display = finalized[path_ref]
            body = {
                "schema": "claim-evidence-v1",
                "claim_ref": claim["claim_id"],
                "value_ref": path["value_id"],
                "coverage_ref": path_ref,
                "establishment": plain(path["establishment_refs"]),
                "scientific_coverage": plain(path["scientific_coverage_refs"]),
                "display_envelope": [a["display_envelope_ref"] for a in display["accepted"]],
                "citation": [a["source_ref"] for a in display["accepted"]],
                "relation_proof": sorted(set(path["relation_proof_refs"]) & set(claim["relation_proof_refs"])),
                "observation": plain(path["observation_refs"]),
                "reported_finding": path["reported_finding"],
                "scientific_goal_state": path["scientific_goal_state"],
                "display_state": display["display_state"],
            }
            result[body_reference("claim-evidence-v1", body)] = body
    return result
