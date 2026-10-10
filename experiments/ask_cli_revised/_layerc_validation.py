"""Validation of stored support records and selected assignments, never reselection."""

from app.backend.pdf_processing.extraction import canonical_text_contains
from experiments.ask_cli_revised._layerc_common import (
    V8,
    canonical,
    check_span,
    digest,
    outer_source,
    own_source,
    put,
    quote_identity,
    reference,
    require,
    text_hash,
)
from experiments.ask_cli_revised.contract_directed.links import extract_designators
from experiments.ask_cli_revised.sufficiency_engine import validate_evaluated_candidate_support


def normalize_candidate(candidate):
    result = {**candidate, "supporting_proposition_ids": sorted(set(candidate["supporting_proposition_ids"]))}
    if candidate.get("attribution"):
        target = dict(candidate["attribution"].get("target", {}))
        if "supporting_proposition_ids" in target:
            target["supporting_proposition_ids"] = sorted(set(target["supporting_proposition_ids"]))
        result["attribution"] = {**candidate["attribution"], "target": target}
    return result


def _candidate_record(place, candidate, props):
    # Existing engine-owned record schema validation, not support-policy evaluation.
    try:
        validate_evaluated_candidate_support(candidate)
    except (ValueError, TypeError, KeyError) as exc:
        require(False, "invalid stored candidate schema: " + str(exc))
    c = normalize_candidate(candidate)
    ids = c["supporting_proposition_ids"]
    anchor = c["span_proposition_id"]
    quotes = [quote_identity(pid, props) for pid in ids]
    span = c["assertion_span"]
    quote = props.get(anchor, {}).get("quote")
    require(isinstance(c["exact_text"], str), "candidate text")
    for field in ("assertion_span", "predicate_span", "content_span"):
        if c[field] is not None:
            require(quote is not None, "candidate span has no anchor")
            check_span(c[field], quote)
    if span is not None:
        require(anchor in ids and quote[slice(*span)] == c["exact_text"], "candidate assertion mismatch")
        require(all(props[pid]["quote"] == quote for pid in ids), "plural support coordinate mismatch")
        material = {
            "representation": "candidate_assertion",
            "placement": place,
            "span_proposition_id": anchor,
            "sealed_quote_identity": quote_identity(anchor, props),
            "assertion_span": span,
        }
    else:
        material = {
            "representation": "candidate_unlocated",
            "placement": place,
            "span_proposition_id": anchor,
            "supporting_proposition_ids": ids,
            "quote_identities": quotes,
            "exact_text_sha256": text_hash(c["exact_text"]),
            "predicate_span": c["predicate_span"],
            "content_span": c["content_span"],
        }
    if c.get("attribution") and quote is not None:
        require(
            c["attribution"].get("target", {}).get("quote_sha256") == text_hash(quote),
            "attribution quote identity mismatch",
        )
    receipt = {k: c[k] for k in ("admissible", "attachment_ambiguous", "guard_exclusions", "support_policy_evaluation")}
    policy = receipt["support_policy_evaluation"]
    require(type(c["admissible"]) is bool and type(c["attachment_ambiguous"]) is bool, "unevaluated candidate")
    require(
        isinstance(c["guard_exclusions"], list) and len(set(c["guard_exclusions"])) == len(c["guard_exclusions"]),
        "guard receipt shape",
    )
    # Stored gate arithmetic is validation; no policy predicate is executed.
    require(type(policy.get("passed")) is bool, "policy gate receipt")
    require(
        policy.get("schema_version") == "support-policy-evaluation-v1"
        and policy.get("policy_source") in ("absent_default", "authored")
        and isinstance(policy.get("failed_dimensions"), list)
        and policy["passed"] == (not policy["failed_dimensions"]),
        "policy receipt schema/outcome",
    )
    require(c["admissible"] == (not c["guard_exclusions"] and policy["passed"]), "inconsistent gate receipt")
    reason = (
        "guard_and_support_policy_excluded"
        if c["guard_exclusions"] and not policy["passed"]
        else "disqualifying_guard_excluded"
        if c["guard_exclusions"]
        else "support_policy_excluded"
        if not policy["passed"]
        else None
    )
    require(c["inadmissibility_reason"] == reason, "gate reason mismatch")
    record = {
        "identity_material": material,
        "kind": material["representation"],
        "placement": place,
        "span_proposition_id": anchor,
        "supporting_proposition_ids": ids,
        "quote_identities": quotes,
        "assertion_span": span,
        "predicate_span": c["predicate_span"],
        "content_span": c["content_span"],
        "exact_text": c["exact_text"],
        "exact_text_sha256": text_hash(c["exact_text"]),
        "candidate_payload_sha256": digest(c),
    }
    return reference("support-ref-v1", material), record, receipt, c


def validate_supports(bundle, bindings, props, map_hash, output, specs):
    """Single payload-index pass. Compare stored records; never emit an alternative view."""
    known, eligibility, eligible_refs = {}, {}, set()
    semantic = {}
    for role, binding in sorted(bindings.items()):
        place = {**bundle["placement"], "role": role}
        source = own_source(binding)
        item = {"state": binding.get("state"), "source": source, "outer_source": outer_source(binding)}
        if "candidate_supports" in binding:
            require(isinstance(binding["candidate_supports"], list), "candidate list shape")
            normalized = {}
            for candidate in binding["candidate_supports"]:
                validate_gate_contract(candidate, specs[role])
                ref, record, receipt, payload = _candidate_record(place, candidate, props)
                put(known, ref, record)
                er = reference("support-eligibility-v1", receipt)
                put(eligibility, er, receipt)
                if receipt["admissible"] and not receipt["attachment_ambiguous"]:
                    eligible_refs.add((role, ref, er, "evaluated_candidate"))
                normalized[canonical(payload)] = payload
                key = reference(
                    "candidate-metadata-v1",
                    {"map_sha256": map_hash, "placement": place, "candidate_payload_sha256": digest(payload)},
                )
                put(
                    output["candidate_metadata"],
                    key,
                    {
                        "placement": place,
                        "support_ref": ref,
                        "candidate_payload_sha256": digest(payload),
                        "payload": payload,
                        "diagnostic_only": not receipt["admissible"] or receipt["attachment_ambiguous"],
                        "eligibility_receipt_ref": er,
                    },
                )
                put(output["candidate_metadata_by_support"], ref, key)
            item["candidates"] = [normalized[k] for k in sorted(normalized)]
            retained = item["candidates"]
            state = (
                "filled"
                if any(c["admissible"] and not c["attachment_ambiguous"] for c in retained)
                else "ambiguous"
                if any(c["admissible"] and c["attachment_ambiguous"] for c in retained)
                else "missing"
            )
            require(binding["state"] == state, "binding state disagrees with stored gate facts")
        else:
            ids = sorted(set((binding.get("provenance") or {}).get("supporting_proposition_ids") or []))
            item["legacy"] = {k: binding.get(k) for k in ("proposition_id", "exact_text")}
            item["legacy"]["support_ids"] = ids
            if binding.get("state") == "filled":
                ids = sorted(set(ids) | ({binding["proposition_id"]} if binding.get("proposition_id") else set()))
                for pid in ids:
                    quote_identity(pid, props)
                material = {
                    "placement": place,
                    "representation": "legacy_binding",
                    "primary_proposition_id": binding.get("proposition_id"),
                    "supporting_proposition_ids": ids,
                    "exact_text_sha256": text_hash(binding.get("exact_text")),
                    "immediate_operand_source": source,
                    "outer_source_identity": outer_source(binding),
                }
                ref = reference("legacy-support-ref-v1", material)
                known[ref] = {
                    "identity_material": material,
                    "kind": "legacy_unit",
                    "placement": place,
                    "span_proposition_id": binding.get("proposition_id"),
                    "supporting_proposition_ids": ids,
                    "exact_text": binding.get("exact_text"),
                    "exact_text_sha256": text_hash(binding.get("exact_text")),
                    "assertion_span": None,
                    "predicate_span": None,
                    "content_span": None,
                }
                eligible_refs.add((role, ref, None, "legacy_binding"))
        semantic[role] = item
    require(known == bundle["support_records"], "stored support registry mismatch")
    require(eligibility == bundle["eligibility_receipts"], "stored eligibility registry mismatch")
    seen = set()
    for vid, view in bundle["support_views"].items():
        place = view["placement"]
        role = place["role"]
        require(role in bindings and place == {**bundle["placement"], "role": role}, "foreign view placement")
        binding = bindings[role]
        ref = view["support_ref"]
        require(ref in known and binding["state"] == "filled", "view outside filled binding")
        record = known[ref]
        er = view["eligibility_receipt_ref"]
        kind = view["representation_kind"]
        require((role, ref, er, kind) in eligible_refs, "excluded support used as eligible view")
        body = {
            "support_ref": ref,
            "representation_kind": kind,
            "immediate_operand_source": own_source(binding),
            "outer_source_identity": outer_source(binding),
            "eligibility_receipt_ref": er,
        }
        require(vid == view["support_view_id"] == reference("support-view-v1", body), "view identity/source mismatch")
        require(view["schema_version"] == "support-view-v1", "view schema")
        require(view["immediate_operand_source"] == own_source(binding), "inherited relabeled own")
        require(view["supporting_proposition_ids"] == record["supporting_proposition_ids"], "view support mismatch")
        require(view["primary_proposition_id"] == record["span_proposition_id"], "view primary mismatch")
        require(
            view["operand_text_ref"]
            == {"support_ref": ref, "field": "exact_text", "sha256": record["exact_text_sha256"]},
            "operand text ref mismatch",
        )
        require(view["evidence_locator_ref"] == ref, "view locator mismatch")
        require(view["candidate_ref"] == (ref if kind == "evaluated_candidate" else None), "view candidate ref")
        require(view["source_provenance_ref"] == {"placement": place, "field": "provenance"}, "source provenance ref")
        seen.add((role, ref, er, kind))
    require(seen == {e for e in eligible_refs if bindings[e[0]]["state"] == "filled"}, "missing stored eligible view")
    return semantic


def validate_gate_contract(candidate, spec):
    """Compare stored policy/guard receipt identities to authoring, without executing a policy."""
    default = {
        "kind": "empirical_default",
        "required_assertion_kind": "result",
        "excluded_relation_aggregation": {
            "assertion_relation": "unresolved",
            "aggregation": "non_synthetic_or_unspecified",
        },
    }
    require(set(candidate["guard_exclusions"]) <= set(spec["disqualifying_guards"]), "unauthored guard receipt")
    receipt = candidate["support_policy_evaluation"]
    authored = spec.get("support_policy")
    expected = authored if authored is not None else default
    require(receipt["policy_snapshot"] == expected, "policy snapshot disagrees with authoring")
    source = "authored" if authored is not None else "absent_default"
    identity = (
        "authored-support-policy-v1:sha256:" + digest(expected) if authored is not None else "empirical-default-v1"
    )
    require(receipt["policy_source"] == source and receipt["policy_identity"] == identity, "policy identity mismatch")


def validate_proofs(requirement, instance, props, output, contexts):
    b = instance["witness_bundle"]
    place, views, records = b["placement"], b["support_views"], b["support_records"]
    rc = requirement["role_completion"]
    completion = sorted(set(rc["required_roles"]) | {r for g in rc["alternative_role_groups"] for r in g})
    own = sorted(
        r
        for r in completion
        if instance["role_bindings"].get(r, {}).get("state") == "filled"
        and own_source(instance["role_bindings"][r]) == "own"
    )
    for key, p in b["proofs"].items():
        body = {k: v for k, v in p.items() if k != "proof_id"}
        require(key == p["proof_id"] == "witness-proof-v1:sha256:" + digest(body), "proof digest mismatch")
        require(p["schema_version"] == "relationship-proof-v1" and p["semantic_version"] == V8, "proof schema")
        require(
            p["placement"] == place and p["participating_roles"] == sorted(p["assignment"]), "proof placement/roles"
        )
        purpose = p["purpose"]
        require(purpose in ("completion_joint", "i1_relation_witness"), "proof purpose")
        roles = sorted(rc["required_roles"]) if purpose == "i1_relation_witness" else own
        require(p["participating_roles"] == roles, "wrong proof tuple")
        require(
            p["verifier_id"] == "operand_source_witness"
            if purpose == "i1_relation_witness"
            else p["verifier_id"] in requirement["relationship_verifiers"],
            "unauthored verifier",
        )
        join = p["join"]
        require(join["kind"] in ("same_proposition", "shared_designator"), "proof join")
        selected = []
        for role, a in p["assignment"].items():
            require(a["support_view_id"] in views, "unknown selected view")
            v = views[a["support_view_id"]]
            require(
                v["placement"]["role"] == role
                and a["evidence_ref"] == v["support_ref"]
                and a["immediate_operand_source"] == v["immediate_operand_source"],
                "proof selected reference",
            )
            if purpose == "completion_joint":
                require(v["immediate_operand_source"] == "own", "inherited completion operand")
            if join["kind"] == "same_proposition" and v["immediate_operand_source"] == "own":
                require(join["proposition_id"] in v["supporting_proposition_ids"], "join outside selected support")
            selected.append(v)
        if purpose == "i1_relation_witness":
            require(
                join["kind"] == "same_proposition" and any(v["immediate_operand_source"] == "own" for v in selected),
                "invalid I1 source/join",
            )
            prop = props[join["proposition_id"]]
            require(
                prop.get("verification", {}).get("status") == "verified"
                and all(a.get("verbatim") is True for a in prop.get("anchors", [])),
                "unverified I1 source",
            )
            checks = p["checks"]
            require(
                checks["sealed_verification"] == prop.get("verification")
                and checks["continuation_anchors"] == prop.get("anchors")
                and checks["containment_rule"] == "casefolded_canonical_full_quote",
                "stale proof checks",
            )
            inherited = {}
            for v in selected:
                if v["immediate_operand_source"] == "inherited":
                    text = records[v["support_ref"]]["exact_text"]
                    require(
                        bool(text)
                        and canonical_text_contains(needle=text.casefold(), haystack=prop["quote"].casefold()),
                        "inherited referent absent",
                    )
                    inherited[v["placement"]["role"]] = {"operand_text_ref": v["operand_text_ref"], "present": True}
            require(checks["inherited"] == inherited, "inherited receipt mismatch")
        elif join["kind"] == "same_proposition":
            require(p["verifier_id"] == "same_proposition", "join verifier mismatch")
        else:
            require(p["verifier_id"] == "contract_directed_links", "link verifier mismatch")
            sets = [
                {d.surface.lower() for d in extract_designators(records[v["support_ref"]]["exact_text"] or "")}
                for v in selected
            ]
            require(
                bool(sets) and set(join["designators"]) == set.intersection(*sets) and bool(join["designators"]),
                "stored designators mismatch",
            )
            _link_context(key, join, contexts, props, output)
        put(output["proofs"], key, p)
    joint = sorted(k for k, p in b["proofs"].items() if p["purpose"] == "completion_joint")
    i1 = sorted(k for k, p in b["proofs"].items() if p["purpose"] == "i1_relation_witness")
    g = instance["joint_grounding"]
    require(
        g["schema_version"] == "joint-grounding-v1"
        and g["proof_refs"] == joint
        and g["participating_roles"] == own
        and g["verifier_ids"] == sorted(set(requirement["relationship_verifiers"])),
        "joint receipt mismatch",
    )
    require(
        g["status"] in ("blocked_prerequisite", "bypassed_lt_two_own", "proved", "unproved")
        and (g["status"] == "proved") == bool(joint),
        "joint status mismatch",
    )
    require(instance["witness_proofs"] == i1, "I1 membership mismatch")
    bindings = instance["role_bindings"]

    def filled(role):
        return bindings.get(role, {}).get("state") == "filled"

    prerequisite = all(filled(r) for r in rc["required_roles"]) and all(
        any(filled(r) for r in group) for group in rc["alternative_role_groups"]
    )
    if "category_observations" in instance:
        prerequisite = prerequisite and any(
            o["observation_polarity"] == "positive_finding" for o in instance["category_observations"]
        )
    expected_status = (
        "blocked_prerequisite"
        if not prerequisite
        else "bypassed_lt_two_own"
        if len(own) < 2
        else "proved"
        if joint
        else "unproved"
    )
    require(g["status"] == expected_status, "joint prerequisite receipt inconsistent")
    if len(rc["required_roles"]) >= 2:
        require(instance["relation_witnessed"] == bool(i1), "stored relation truth mismatch")
        require(
            instance["witness_ids"] == sorted({b["proofs"][k]["join"]["proposition_id"] for k in i1}),
            "stored witness IDs mismatch",
        )


def _link_context(proof_id, join, contexts, props, output):
    records = [c for c in contexts if c["proof_id"] == proof_id]
    status = {
        "proof_ref": proof_id,
        "context_sha256": join["context_sha256"],
        "status": "missing",
        "display_context_refs": [],
        "citation_refs": [],
        "limitation": "context_unavailable",
    }
    for c in records:
        require(digest(c["attachment_pieces"]) == join["context_sha256"], "link context hash mismatch")
        for piece in c["attachment_pieces"]:
            require(
                isinstance(piece.get("text"), str)
                and type(piece.get("start")) is int
                and type(piece.get("end")) is int
                and 0 <= piece["start"] < piece["end"],
                "invalid context piece",
            )
        ref = reference("link-context-v1", {"attachment_pieces": c["attachment_pieces"]})
        put(output["link_context_records"], ref, c["attachment_pieces"])
        status.update(status="present", limitation=None)
        status["display_context_refs"].append(ref)
        for loc in c.get("source_locators", []):
            pid = loc["proposition_id"]
            require(pid in props and loc["quote_sha256"] == text_hash(props[pid]["quote"]), "context locator mismatch")
            require(
                any(
                    piece["text"] == props[pid]["quote"] and piece["chunk_id"] == props[pid]["evidence_anchor_chunk_id"]
                    for piece in c["attachment_pieces"]
                ),
                "context citation not in supplied bytes",
            )
            status["citation_refs"].append(pid)
    status["display_context_refs"] = sorted(set(status["display_context_refs"]))
    status["citation_refs"] = sorted(set(status["citation_refs"]))
    put(output["link_context_status"], proof_id, status)
