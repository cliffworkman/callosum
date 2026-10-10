"""Value-specific permissions derived from validated stored paths, without presentation decisions."""

from experiments.ask_cli_revised._layerc_common import (
    STRATEGIES,
    body_reference,
    display_envelope,
    put,
    require,
    text_hash,
)

POLARITIES = frozenset({"positive_finding", "null_finding", "mentioned_only", "unknown"})
PRESENTATION_CHECKS = (
    "caption_source",
    "passage_complete",
    "passage_not_generic_summary",
    "attribution",
    "referentially_closed",
    "requested_construct_direct",
    "authored_facet_display_constraints",
)


def category_refs(requirement, instance, props, output):
    if "category_observations" not in instance:
        return []
    specs = requirement["role_specs"]
    require(len(specs) == 1 and requirement["instance_quantifier"] == "all_requested_categories", "category role scope")
    role, spec = next(iter(specs.items()))
    require(spec["mapping_strategy"] == "explicit_category_terms", "category strategy")
    term = instance["instance_key"]
    require(term in spec["requested_category_terms"], "category instance outside authored scope")
    place = {**instance["witness_bundle"]["placement"], "role": role}
    refs = []
    positives = False
    for obs in instance["category_observations"]:
        require(
            obs["term"] == term
            and obs["competing_terms"] == [t for t in spec["requested_category_terms"] if t != term],
            "wrong category term/scope",
        )
        require(obs["observation_polarity"] in POLARITIES, "unsupported category polarity")
        require(obs["classifier"] == "observation-polarity/i2-1", "stale category classifier")
        require(
            isinstance(obs["classifier_audit"], dict)
            and isinstance(obs["guard"], dict)
            and isinstance(obs["rule"], str),
            "category audit missing",
        )
        require(obs["ambiguity"] is None or isinstance(obs["ambiguity"], str), "category ambiguity shape")
        require(not any(obs["guard"].get(g) for g in spec["disqualifying_guards"]), "category guard contradiction")
        pid = obs["proposition_id"]
        require(pid in props and obs["source_passage"] == props[pid]["quote"], "category source passage mismatch")
        require(props[pid].get("verification", {}).get("status") == "verified", "category unverified source")
        require(obs["exact_text"].casefold() == term.casefold(), "category exact surface")
        audit = obs["classifier_audit"]
        require(
            type(audit.get("term_occurrences")) is int and audit["term_occurrences"] >= 1, "category occurrence audit"
        )
        if obs["observation_polarity"] in ("positive_finding", "null_finding"):
            require(
                audit["term_occurrences"] == 1 and isinstance(audit.get("term_clause"), str),
                "finding lacks bounded category audit",
            )
        body = {
            "schema": "category-observation-ref-v1",
            "placement": place,
            "observation": obs,
            "source_identity": {
                k: props[pid].get(k) for k in ("paper_id", "evidence_anchor_chunk_id", "evidence_span_id")
            },
            "quote_sha256": text_hash(obs["source_passage"]),
        }
        require(all(v is not None for v in body["source_identity"].values()), "category source locator missing")
        key = body_reference("category-observation-ref-v1", body)
        put(output["category_observations"], key, body)
        refs.append(key)
        positives |= obs["observation_polarity"] == "positive_finding"
    binding = instance["role_bindings"][role]
    require(not refs or binding["state"] == "filled", "category observations on missing binding")
    require(instance["complete"] == (binding["state"] == "filled" and positives), "category goal receipt mismatch")
    return sorted(set(refs))


def _value(place, spec, record, independent, candidate):
    strategy = spec["mapping_strategy"]
    require(strategy in STRATEGIES, "unsupported value strategy")
    text = record["exact_text"]
    if not isinstance(text, str) or not text:
        return None
    if strategy == "explicit_category_terms":
        require(text in spec["requested_category_terms"], "category value outside authored terms")
        kind = "authored_category"
    elif strategy == "achieved_outcome_predicate":
        kind = "evidence_slot" if independent else "literal_assertion"
    else:
        kind = "literal_assertion" if candidate else "literal_value"
    body = {
        "schema": "semantic-value-v1",
        "scope": {"owner_id": place["child_id"], "requirement_id": place["requirement_id"], "role": place["role"]},
        "kind": kind,
    }
    if kind == "authored_category":
        body.update(category_identity={"term": text, "role": place["role"]}, literal=text)
    elif kind == "evidence_slot":
        body.update(slot=spec["category_description"], operand_tuple=independent)
    else:
        body["literal"] = text
    return body


def project_values(requirement, instance, props, category_ids, output):
    b = instance["witness_bundle"]
    views, records = b["support_views"], b["support_records"]
    # A stored proof assignment supplies independent operands. Never form alternative products.
    independent_by_view = {}
    for proof in b["proofs"].values():
        assignment = proof["assignment"]
        independent = []
        for role, a in sorted(assignment.items()):
            view = views[a["support_view_id"]]
            spec = requirement["role_specs"][role]
            text = records[view["support_ref"]]["exact_text"]
            if spec["mapping_strategy"] != "achieved_outcome_predicate" and isinstance(text, str) and text:
                independent.append({"role": role, "literal": text})
        for a in assignment.values():
            independent_by_view.setdefault(a["support_view_id"], {})[str(independent)] = independent
    for vid, view in sorted(views.items()):
        role = view["placement"]["role"]
        spec = requirement["role_specs"][role]
        record = records[view["support_ref"]]
        variants = list(independent_by_view.get(vid, {}).values()) or [[]]
        for independent in variants:
            independent = [p for p in independent if p["role"] != role]
            body = _value(
                view["placement"], spec, record, independent, view["representation_kind"] == "evaluated_candidate"
            )
            if body is None:
                output["diagnostics"].append(
                    {
                        "reason": "value_unresolvable",
                        "kind": "value_unresolvable",
                        "placement": view["placement"],
                        "support_view_ref": vid,
                        "evidence_ref": view["support_ref"],
                        "renderable": False,
                    }
                )
                continue
            value_id = body_reference("semantic-value-v1", body)
            put(output["semantic_values"], value_id, body)
            _coverage(value_id, body, view, record, requirement, instance, category_ids, props, output)
    _group(requirement, instance, output)


def _source(pid, authority, span, props, output, source):
    prop = props[pid]
    body = {
        "authority_ref": authority,
        "proposition_id": pid,
        "source_identity": {
            k: prop.get(k) for k in ("paper_id", "evidence_anchor_chunk_id", "evidence_span_id", "anchors")
        },
        "quote_sha256": text_hash(prop["quote"]),
        "evidence_span": span,
        "immediate_operand_source": source,
    }
    key = body_reference("layerc-source-v1", body)
    put(output["sources"], key, body)
    envelope = None
    if span is not None:
        eid, eb = display_envelope(key, prop["quote"], span)
        put(output["display_envelopes"], eid, eb)
        envelope = eid
    return {
        "source_ref": key,
        "authority_ref": authority,
        "display_envelope_ref": envelope,
        "proposition_id": pid,
        "immediate_operand_source": source,
    }


def _coverage(value_id, value, view, record, requirement, instance, category_ids, props, output):
    vid, role = view["support_view_id"], view["placement"]["role"]
    goal, finding = "established", "not_applicable"
    selected_edge = {
        "kind": "selected_support_view",
        "ref": vid,
        "placement": view["placement"],
        "immediate_operand_source": view["immediate_operand_source"],
    }
    establishment = [selected_edge]
    scientific, reporting, display, citations, limitations = [], [], [], [], []
    relevant = [ref for ref in category_ids if output["category_observations"][ref]["placement"] == view["placement"]]
    if value["kind"] == "authored_category":
        positive = [
            ref
            for ref in relevant
            if output["category_observations"][ref]["observation"]["observation_polarity"] == "positive_finding"
        ]
        nulls = [
            ref
            for ref in relevant
            if output["category_observations"][ref]["observation"]["observation_polarity"] == "null_finding"
        ]
        goal = "established" if positive else "unestablished"
        mentioned = any(
            output["category_observations"][ref]["observation"]["observation_polarity"] == "mentioned_only"
            for ref in relevant
        )
        finding = (
            "positive_finding"
            if positive
            else "null_finding"
            if nulls
            else "mentioned_only"
            if mentioned
            else "unknown"
        )
        for ref in relevant:
            obs = output["category_observations"][ref]["observation"]
            polarity = obs["observation_polarity"]
            if obs["ambiguity"] is not None:
                continue
            # Null reporting remains through that category's already selected legacy path.
            authorized = polarity == "positive_finding" and instance["complete"]
            null_report = polarity == "null_finding" and obs["proposition_id"] in view["supporting_proposition_ids"]
            if not (authorized or null_report):
                continue
            edge = {
                "kind": "category_observation",
                "ref": ref,
                "placement": view["placement"],
                "immediate_operand_source": view["immediate_operand_source"],
                "polarity": polarity,
            }
            if authorized:
                scientific.append(edge)
                establishment.append({**edge, "kind": "upstream_goal_basis"})
            reporting.append(edge)
            src = _source(
                obs["proposition_id"],
                ref,
                [0, len(obs["source_passage"])],
                props,
                output,
                view["immediate_operand_source"],
            )
            display.append(src)
            citations.append(src)
        if goal == "unestablished":
            limitations.append("goal_unsatisfied_null" if nulls else "goal_unsatisfied_unknown")
    else:
        scientific.append(selected_edge)
        reporting.append(selected_edge)
        for pid in record["supporting_proposition_ids"]:
            if record["kind"] == "legacy_unit":
                span = [0, len(props[pid]["quote"])]
            else:
                span = record["assertion_span"]
            src = _source(pid, vid, span, props, output, view["immediate_operand_source"])
            if span is None:
                limitations.append("source_unlocated")
            else:
                display.append(src)
                citations.append(src)
    proof_refs = sorted(
        k
        for k, p in instance["witness_bundle"]["proofs"].items()
        if any(a["support_view_id"] == vid for a in p["assignment"].values())
    )
    body = {
        "schema": "value-coverage-v1",
        "value_id": value_id,
        "placement": view["placement"],
        "establishment_refs": establishment,
        "scientific_coverage_refs": scientific,
        "typed_reporting_refs": reporting,
        "authorized_display_source_refs": display,
        "citation_source_refs": citations,
        "relation_proof_refs": proof_refs,
        "observation_refs": sorted(
            oid
            for oid, observation in output["observations"].items()
            if any(
                vid in path["selected_support_view_refs"].values()
                for path in observation["record"]["evidence_alignment"]["paths"]
            )
        ),
        "role_state": instance["role_bindings"][role]["state"],
        "instance_state": instance["state"],
        "scientific_goal_state": goal,
        "reported_finding": finding,
        "limitations": sorted(set(limitations)),
        "presentation": {"finalization_required": True, "required_checks": list(PRESENTATION_CHECKS)},
    }
    ref = body_reference("value-coverage-v1", body)
    put(output["value_coverage"], ref, body)
    output["value_paths"].setdefault(value_id, []).append(ref)


def _group(requirement, instance, output):
    if requirement["instance_quantifier"] not in (
        "exists",
        "open_list",
        "for_each_discovered_instance",
        "all_requested_categories",
    ):
        return
    for role in requirement["role_specs"]:
        body = {
            "requirement_id": requirement["id"],
            "owner_id": instance["witness_bundle"]["placement"]["child_id"],
            "role": role,
            "instance_quantifier": requirement["instance_quantifier"],
            "quantifier_n": requirement.get("quantifier_n"),
        }
        key = body_reference("value-group-v1", body)
        group = output["grouping"].setdefault(key, {"identity": body, "members": {}})
        for ref, receipt in output["value_coverage"].items():
            p = receipt["placement"]
            if (p["requirement_id"], p["role"], p["child_id"]) == (requirement["id"], role, body["owner_id"]):
                group["members"].setdefault(receipt["value_id"], []).append(ref)
