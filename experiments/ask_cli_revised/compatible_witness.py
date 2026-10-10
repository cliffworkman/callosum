"""Explicit v8 compatible support assignments. Pure; no evidence collection or policy evaluation."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised.contract_directed.links import extract_designators

VERSION = "sufficiency-semantics-v8"


class WitnessIntegrityError(ValueError):
    """Malformed, conflicting or stale witness evidence; never silently repaired."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def text_hash(text):
    if text is not None and not isinstance(text, str):
        raise WitnessIntegrityError("operand text must be string or null")
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None


def reference(scheme, material):
    return scheme + ":sha256:" + digest({"scheme": scheme, **material})


def source_identity(prop):
    return {
        k: copy.deepcopy(prop.get(k)) for k in ("paper_id", "evidence_anchor_chunk_id", "evidence_span_id", "anchors")
    }


def outer_source(binding):
    provenance = binding.get("provenance") or {}
    return {
        k: copy.deepcopy(provenance.get(k))
        for k in ("candidate_source", "model", "upstream_model_dependent", "source_lineage")
    }


def operand_source(binding):
    return "inherited" if outer_source(binding)["candidate_source"] == "parent_context" else "own"


def normalize_candidate(candidate):
    result = copy.deepcopy(candidate)
    result["supporting_proposition_ids"] = sorted(set(result["supporting_proposition_ids"]))
    if result.get("attribution"):
        target = result["attribution"].get("target", {})
        if "supporting_proposition_ids" in target:
            target["supporting_proposition_ids"] = sorted(set(target["supporting_proposition_ids"]))
    return result


def _quote_identity(pid, props):
    prop = props.get(pid)
    if not isinstance(prop, dict) or not isinstance(prop.get("quote"), str):
        raise WitnessIntegrityError("missing sealed proposition/quote: " + str(pid))
    return {"proposition_id": pid, "quote_sha256": text_hash(prop["quote"]), "source_identity": source_identity(prop)}


def _span(span, quote, name):
    if span is None:
        return
    if (
        not isinstance(span, list)
        or len(span) != 2
        or any(type(n) is not int for n in span)
        or not 0 <= span[0] < span[1] <= len(quote)
    ):
        raise WitnessIntegrityError("invalid " + name)


def _put(registry, key, value):
    if key in registry and registry[key] != value:
        raise WitnessIntegrityError("conflicting reference: " + key)
    registry[key] = value


def _candidate_record(placement, candidate, props):
    try:
        se.validate_evaluated_candidate_support(candidate)
    except (ValueError, TypeError, KeyError) as exc:
        raise WitnessIntegrityError("invalid evaluated candidate") from exc
    c = normalize_candidate(candidate)
    ids = c["supporting_proposition_ids"]
    anchor = c["span_proposition_id"]
    quotes = [_quote_identity(pid, props) for pid in ids]
    span = c["assertion_span"]
    quote = props[anchor]["quote"] if anchor in props else None
    if span is not None:
        if anchor not in ids or quote is None:
            raise WitnessIntegrityError("candidate anchor missing from support")
        for field in ("assertion_span", "predicate_span", "content_span"):
            _span(c[field], quote, field)
        if quote[slice(*span)] != c["exact_text"]:
            raise WitnessIntegrityError("assertion exact-text/locator mismatch")
        if any(props[pid]["quote"] != quote for pid in ids):
            raise WitnessIntegrityError("plural support coordinate mismatch")
        material = {
            "representation": "candidate_assertion",
            "placement": placement,
            "span_proposition_id": anchor,
            "sealed_quote_identity": _quote_identity(anchor, props),
            "assertion_span": span,
        }
    else:
        if quote is not None:
            for field in ("predicate_span", "content_span"):
                _span(c[field], quote, field)
        material = {
            "representation": "candidate_unlocated",
            "placement": placement,
            "span_proposition_id": anchor,
            "supporting_proposition_ids": ids,
            "quote_identities": quotes,
            "exact_text_sha256": text_hash(c["exact_text"]),
            "predicate_span": c["predicate_span"],
            "content_span": c["content_span"],
        }
    attribution = c.get("attribution")
    if attribution and quote is not None and attribution.get("target", {}).get("quote_sha256") != text_hash(quote):
        raise WitnessIntegrityError("attribution quote hash mismatch")
    ref = reference("support-ref-v1", material)
    record = {
        "identity_material": material,
        "kind": material["representation"],
        "placement": placement,
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
    receipt = {
        k: copy.deepcopy(c[k])
        for k in ("admissible", "attachment_ambiguous", "guard_exclusions", "support_policy_evaluation")
    }
    return ref, record, receipt


def build_support_views(placement, role_bindings, sealed_proposition_index):
    """Sole adapter. Validate retained exclusions and duplicate payloads before filtering."""
    if set(placement) != {"child_id", "requirement_id", "instance_key"}:
        raise WitnessIntegrityError("explicit complete placement required")
    if not all(isinstance(placement[k], str) and placement[k] for k in ("child_id", "requirement_id")):
        raise WitnessIntegrityError("invalid placement")
    if placement["instance_key"] is not None and not isinstance(placement["instance_key"], str):
        raise WitnessIntegrityError("invalid instance placement key")
    registry = {"support_records": {}, "eligibility_receipts": {}, "support_views": {}, "diagnostics": []}
    for role, binding in sorted(role_bindings.items()):
        place = {**placement, "role": role}
        source = operand_source(binding)
        records = []
        if "candidate_supports" in binding:
            candidates = binding["candidate_supports"]
            if not isinstance(candidates, list):
                raise WitnessIntegrityError("candidate_supports must be a list")
            for candidate in candidates:
                ref, record, receipt = _candidate_record(place, candidate, sealed_proposition_index)
                _put(registry["support_records"], ref, record)
                receipt_ref = reference("support-eligibility-v1", receipt)
                _put(registry["eligibility_receipts"], receipt_ref, receipt)
                if record["assertion_span"] is None:
                    registry["diagnostics"].append(
                        {"reason": "candidate_assertion_locator_unavailable", "support_ref": ref}
                    )
                if receipt["admissible"] is True and receipt["attachment_ambiguous"] is False:
                    records.append((ref, record, receipt_ref, "evaluated_candidate"))
        elif binding.get("state") == "filled":
            ids = set((binding.get("provenance") or {}).get("supporting_proposition_ids") or [])
            if binding.get("proposition_id") is not None:
                ids.add(binding["proposition_id"])
            ids = sorted(ids)
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
            record = {
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
            _put(registry["support_records"], ref, record)
            records.append((ref, record, None, "legacy_binding"))
        if binding.get("state") != "filled":
            continue
        for ref, record, receipt_ref, kind in records:
            material = {
                "support_ref": ref,
                "representation_kind": kind,
                "immediate_operand_source": source,
                "outer_source_identity": outer_source(binding),
                "eligibility_receipt_ref": receipt_ref,
            }
            view_id = reference("support-view-v1", material)
            view = {
                "schema_version": "support-view-v1",
                "support_view_id": view_id,
                "placement": place,
                "immediate_operand_source": source,
                "representation_kind": kind,
                "support_ref": ref,
                "supporting_proposition_ids": record["supporting_proposition_ids"],
                "primary_proposition_id": record["span_proposition_id"],
                "operand_text_ref": {"support_ref": ref, "field": "exact_text", "sha256": record["exact_text_sha256"]},
                "evidence_locator_ref": ref,
                "candidate_ref": ref if kind == "evaluated_candidate" else None,
                "eligibility_receipt_ref": receipt_ref,
                "source_provenance_ref": {"placement": place, "field": "provenance"},
            }
            _put(registry["support_views"], view_id, view)
        if not records:
            registry["diagnostics"].append({"reason": "no_eligible_support_views", "placement": place})
    registry["diagnostics"] = sorted({canonical(x): x for x in registry["diagnostics"]}.values(), key=canonical)
    return registry


def semantic_input(role_completion, bindings, verifiers):
    result = {}
    for role, binding in sorted(bindings.items()):
        item = {"state": binding.get("state"), "source": operand_source(binding), "outer_source": outer_source(binding)}
        if "candidate_supports" in binding:
            normalized = [normalize_candidate(c) for c in binding["candidate_supports"]]
            item["candidates"] = sorted({canonical(c): c for c in normalized}.values(), key=canonical)
        else:
            item["legacy"] = {k: copy.deepcopy(binding.get(k)) for k in ("proposition_id", "exact_text")}
            item["legacy"]["support_ids"] = sorted(
                set((binding.get("provenance") or {}).get("supporting_proposition_ids") or [])
            )
        result[role] = item
    return {"role_completion": role_completion, "bindings": result, "relationship_verifiers": sorted(set(verifiers))}


def role_views(registry, roles):
    return {
        role: sorted(
            (v for v in registry["support_views"].values() if v["placement"]["role"] == role),
            key=lambda v: v["support_view_id"],
        )
        for role in sorted(roles)
    }


def common_assignments(registry, roles):
    roles = sorted(set(roles))
    if not roles:
        return []
    indices = {role: {} for role in roles}
    for role, views in role_views(registry, roles).items():
        for view in views:
            for pid in view["supporting_proposition_ids"]:
                indices[role].setdefault(pid, []).append(view)
    shared = set.intersection(*(set(indices[role]) for role in roles))
    return [
        (pid, dict(zip(roles, selected, strict=True)))
        for pid in sorted(shared)
        for selected in itertools.product(*(indices[role][pid] for role in roles))
    ]


def _proof(placement, purpose, verifier, assignment, join, checks=None):
    body = {
        "schema_version": "relationship-proof-v1",
        "purpose": purpose,
        "placement": placement,
        "verifier_id": verifier,
        "participating_roles": sorted(assignment),
        "assignment": {
            role: {
                "support_view_id": view["support_view_id"],
                "immediate_operand_source": view["immediate_operand_source"],
                "evidence_ref": view["support_ref"],
            }
            for role, view in sorted(assignment.items())
        },
        "join": join,
        "checks": checks or {},
        "semantic_version": VERSION,
    }
    return {"proof_id": "witness-proof-v1:sha256:" + digest(body), **body}


def operand_text(registry, view):
    return registry["support_records"][view["support_ref"]]["exact_text"]


def select_completion_proofs(registry, own_roles, verifier_ids, verifier_context):
    output = {}
    place = registry["placement"]
    for verifier in sorted(set(verifier_ids)):
        if verifier == "same_proposition":
            for pid, assignment in common_assignments(registry, own_roles):
                proof = _proof(
                    place, "completion_joint", verifier, assignment, {"kind": "same_proposition", "proposition_id": pid}
                )
                _put(output, proof["proof_id"], proof)
        elif verifier == "contract_directed_links":
            if not verifier_context or not verifier_context.get("attachment_pieces"):
                continue
            roles = sorted(own_roles)
            for values in itertools.product(*(role_views(registry, roles)[r] for r in roles)):
                texts = [operand_text(registry, v) for v in values]
                if any(not text for text in texts):
                    continue
                shared = set.intersection(*({d.surface.lower() for d in extract_designators(t)} for t in texts))
                if shared:
                    proof = _proof(
                        place,
                        "completion_joint",
                        verifier,
                        dict(zip(roles, values, strict=True)),
                        {
                            "kind": "shared_designator",
                            "designators": sorted(shared),
                            "context_sha256": digest(verifier_context["attachment_pieces"]),
                        },
                    )
                    _put(output, proof["proof_id"], proof)
        else:
            raise WitnessIntegrityError("unknown relationship verifier")
    return output


def proof_truth(proofs):
    return bool(proofs)


def proof_proposition_ids(proofs):
    return sorted({p["join"]["proposition_id"] for p in proofs.values() if p["join"]["kind"] == "same_proposition"})


def initialize_instance(
    role_completion, instance, verifiers, witness_context, prerequisites, own_roles, verifier_context=None
):
    if not witness_context or not isinstance(witness_context.get("proposition_index"), dict):
        raise WitnessIntegrityError("v8 requires explicit sealed witness_context")
    place = {k: witness_context[k] for k in ("child_id", "requirement_id")}
    place["instance_key"] = instance["instance_key"]
    props = witness_context["proposition_index"]
    bindings = instance["role_bindings"]
    bundle = {
        "schema_version": "witness-bundle-v1",
        "semantic_version": VERSION,
        "placement": place,
        "sealed_input_sha256": digest(props),
        "binding_semantic_input_sha256": digest(semantic_input(role_completion, bindings, verifiers)),
        **build_support_views(place, bindings, props),
        "proofs": {},
        "observation_bases": {},
    }
    roles = own_roles
    status = "blocked_prerequisite" if not prerequisites else "bypassed_lt_two_own"
    if prerequisites and len(roles) >= 2:
        bundle["proofs"] = select_completion_proofs(bundle, roles, verifiers, verifier_context)
        status = "proved" if bundle["proofs"] else "unproved"
    receipt = {
        "schema_version": "joint-grounding-v1",
        "status": status,
        "participating_roles": sorted(roles),
        "verifier_ids": sorted(set(verifiers)),
        "proof_refs": sorted(bundle["proofs"]),
    }
    if not prerequisites:
        receipt["reason"] = "completion_or_category_prerequisite"
    return bundle, receipt


def select_i1_proofs(registry, required_roles, bindings, proposition_index, verified_predicate, referent_predicate):
    required = sorted(required_roles)
    sources = {r: operand_source(bindings.get(r) or {}) for r in required}
    own = [r for r in required if sources[r] == "own"]
    inherited = [r for r in required if sources[r] == "inherited"]
    views = role_views(registry, required)
    provenance = {
        "rule": "operand_source_witness",
        "own_roles": own,
        "inherited_roles": inherited,
        "own_support": {},
        "inherited_referents": {},
        "candidate_ids": [],
        "candidate_checks": [],
        "failure_reason": None,
    }
    output = {}

    def finish(reason):
        provenance["failure_reason"] = reason
        return output, {
            "relation_witnessed": reason is None,
            "witness_ids": proof_proposition_ids(output),
            "witness_provenance": provenance,
        }

    if any(bindings.get(r, {}).get("state") != "filled" for r in required):
        return finish("incomplete_operands")
    if any(not views[r] for r in required):
        return finish("no_eligible_operand_support")
    if not own:
        return finish("no_own_operand")
    for role in own:
        provenance["own_support"][role] = sorted({pid for v in views[role] for pid in v["supporting_proposition_ids"]})
    for role in inherited:
        provenance["inherited_referents"][role] = [
            {"support_view_id": v["support_view_id"], "operand_text_ref": v["operand_text_ref"]} for v in views[role]
        ]
    assignments = common_assignments(registry, own)
    provenance["candidate_ids"] = sorted({pid for pid, _ in assignments})
    if not assignments:
        return finish("no_single_proposition")
    any_verified = False
    for pid, assignment in assignments:
        prop = proposition_index.get(pid)
        verified = verified_predicate(prop)
        check = {"proposition_id": pid, "admissible": verified, "inherited_referent_present": {}}
        if verified:
            any_verified = True
            choices = []
            for role in inherited:
                checks = {
                    v["support_view_id"]: referent_predicate(operand_text(registry, v), prop["quote"])
                    for v in views[role]
                }
                check["inherited_referent_present"][role] = checks
                choices.append([v for v in views[role] if checks[v["support_view_id"]]])
            for chosen in itertools.product(*choices):
                selected = {**assignment, **dict(zip(inherited, chosen, strict=True))}
                proof = _proof(
                    registry["placement"],
                    "i1_relation_witness",
                    "operand_source_witness",
                    selected,
                    {"kind": "same_proposition", "proposition_id": pid},
                    {
                        "sealed_verification": copy.deepcopy(prop.get("verification")),
                        "continuation_anchors": copy.deepcopy(prop.get("anchors")),
                        "containment_rule": "casefolded_canonical_full_quote",
                        "inherited": {
                            r: {"operand_text_ref": v["operand_text_ref"], "present": True}
                            for r, v in selected.items()
                            if r in inherited
                        },
                    },
                )
                _put(output, proof["proof_id"], proof)
        provenance["candidate_checks"].append(check)
    if not any_verified:
        return finish("no_admissible_candidate")
    return finish(None if output else "inherited_referent_absent")


def build_observation_bases(registry, own_roles, required_roles, bindings):
    output = {}
    views = registry["support_views"]
    proofs = registry["proofs"]
    for pid, own_assignment in common_assignments(registry, own_roles):
        own_ids = {r: v["support_view_id"] for r, v in own_assignment.items()}

        def matches(proof, pid=pid, own_ids=own_ids):
            return proof["join"].get("proposition_id") == pid and all(
                r not in proof["assignment"] or proof["assignment"][r]["support_view_id"] == vid
                for r, vid in own_ids.items()
            )

        joint = [key for key, p in proofs.items() if p["purpose"] == "completion_joint" and matches(p)]
        i1 = [key for key, p in proofs.items() if p["purpose"] == "i1_relation_witness" and matches(p)]
        paths = []
        if i1:
            for key in sorted(i1):
                chosen = {**own_ids, **{r: a["support_view_id"] for r, a in proofs[key]["assignment"].items()}}
                paths.append({"selected_views": chosen, "i1_proof_refs": [key]})
        else:
            other = sorted(
                r for r in required_roles if r not in own_ids and bindings.get(r, {}).get("state") == "filled"
            )
            choices = role_views(registry, other)
            # No eligible view for a stale filled role means no surface, not a legacy fallback.
            other = [r for r in other if choices[r]]
            for selected in itertools.product(*(choices[r] for r in other)):
                paths.append(
                    {
                        "selected_views": {
                            **own_ids,
                            **{r: v["support_view_id"] for r, v in zip(other, selected, strict=True)},
                        },
                        "i1_proof_refs": [],
                    }
                )
        for path in paths:
            path["operand_text_refs"] = {
                r: views[vid]["operand_text_ref"] for r, vid in path["selected_views"].items() if r in required_roles
            }
        body = {
            "schema_version": "observation-basis-v1",
            "placement": registry["placement"],
            "basis_kind": "single_own_support" if len(own_roles) == 1 else "common_own_support",
            "participating_own_roles": sorted(own_roles),
            "selected_views": own_ids,
            "common_proposition_id": pid,
            "completion_proof_refs": sorted(joint),
            "i1_proof_refs": sorted(i1),
            "direction_paths": sorted(paths, key=canonical),
            "semantic_version": VERSION,
        }
        key = reference("observation-basis-v1", body)
        _put(output, key, {"basis_id": key, **body})
    return output


def validate_witness_bundle(bundle, role_completion, bindings, verifiers, props):
    if bundle.get("schema_version") != "witness-bundle-v1" or bundle.get("semantic_version") != VERSION:
        raise WitnessIntegrityError("invalid bundle schema/version")
    if bundle.get("sealed_input_sha256") != digest(props):
        raise WitnessIntegrityError("stale sealed input")
    if bundle.get("binding_semantic_input_sha256") != digest(semantic_input(role_completion, bindings, verifiers)):
        raise WitnessIntegrityError("stale semantic input")
    rebuilt = build_support_views(bundle["placement"], bindings, props)
    for key in rebuilt:
        if bundle.get(key) != rebuilt[key]:
            raise WitnessIntegrityError("bundle registry mismatch: " + key)
    views = bundle["support_views"]
    for key, proof in bundle["proofs"].items():
        body = {k: v for k, v in proof.items() if k != "proof_id"}
        if key != proof.get("proof_id") or key != ("witness-proof-v1:sha256:" + digest(body)):
            raise WitnessIntegrityError("proof digest mismatch")
        if (
            proof["purpose"] not in ("completion_joint", "i1_relation_witness")
            or proof["placement"] != bundle["placement"]
            or proof.get("schema_version") != "relationship-proof-v1"
            or proof.get("semantic_version") != VERSION
            or proof["participating_roles"] != sorted(proof["assignment"])
        ):
            raise WitnessIntegrityError("proof purpose/placement mismatch")
        required = sorted(role_completion["required_roles"])
        if proof["purpose"] == "i1_relation_witness":
            if proof["participating_roles"] != required or proof["verifier_id"] != "operand_source_witness":
                raise WitnessIntegrityError("I1 participation/verifier mismatch")
            if not any(a["immediate_operand_source"] == "own" for a in proof["assignment"].values()):
                raise WitnessIntegrityError("all-inherited I1 proof")
        elif proof["verifier_id"] not in verifiers:
            raise WitnessIntegrityError("unauthored completion verifier")
        if proof["join"]["kind"] not in ("same_proposition", "shared_designator"):
            raise WitnessIntegrityError("unknown proof join")
        for role, chosen in proof["assignment"].items():
            view = views.get(chosen["support_view_id"])
            if (
                view is None
                or view["placement"]["role"] != role
                or chosen["evidence_ref"] != view["support_ref"]
                or chosen["immediate_operand_source"] != view["immediate_operand_source"]
            ):
                raise WitnessIntegrityError("invalid proof view reference")
            if (
                view["immediate_operand_source"] == "own"
                and proof["join"]["kind"] == "same_proposition"
                and proof["join"]["proposition_id"] not in view["supporting_proposition_ids"]
            ):
                raise WitnessIntegrityError("proof join outside selected support")
    for key, basis in bundle["observation_bases"].items():
        if key != basis.get("basis_id") or key != reference(
            "observation-basis-v1", {k: v for k, v in basis.items() if k != "basis_id"}
        ):
            raise WitnessIntegrityError("basis digest mismatch")
        if any(ref not in bundle["proofs"] for ref in basis["completion_proof_refs"] + basis["i1_proof_refs"]):
            raise WitnessIntegrityError("basis references unknown proof")
        if any(ref not in views for ref in basis["selected_views"].values()):
            raise WitnessIntegrityError("basis references unknown support view")
        if basis["placement"] != bundle["placement"] or basis["semantic_version"] != VERSION:
            raise WitnessIntegrityError("basis placement/version mismatch")
        for role, ref in basis["selected_views"].items():
            view = views[ref]
            if (
                view["placement"]["role"] != role
                or view["immediate_operand_source"] != "own"
                or basis["common_proposition_id"] not in view["supporting_proposition_ids"]
            ):
                raise WitnessIntegrityError("basis assignment mismatch")
        for path in basis["direction_paths"]:
            for role, ref in path["selected_views"].items():
                if ref not in views or views[ref]["placement"]["role"] != role:
                    raise WitnessIntegrityError("direction path view mismatch")
            if any(path["selected_views"].get(r) != ref for r, ref in basis["selected_views"].items()):
                raise WitnessIntegrityError("direction path changed own basis")
            for role, ref in path["operand_text_refs"].items():
                view = views[path["selected_views"][role]]
                if role not in role_completion["required_roles"] or ref != view["operand_text_ref"]:
                    raise WitnessIntegrityError("direction operand reference mismatch")
            for ref in path["i1_proof_refs"]:
                proof = bundle["proofs"].get(ref)
                if (
                    proof is None
                    or proof["purpose"] != "i1_relation_witness"
                    or proof["join"].get("proposition_id") != basis["common_proposition_id"]
                    or any(
                        path["selected_views"].get(r) != a["support_view_id"] for r, a in proof["assignment"].items()
                    )
                ):
                    raise WitnessIntegrityError("direction path proof mismatch")


def finalize_instance(requirement, instance, props, own_roles, verified_predicate, referent_predicate):
    bundle = copy.deepcopy(instance["witness_bundle"])
    if (
        bundle["placement"]["instance_key"] != instance["instance_key"]
        or bundle["placement"]["requirement_id"] != requirement["id"]
    ):
        raise WitnessIntegrityError("instance/bundle placement mismatch")
    receipt = instance.get("joint_grounding")
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "joint-grounding-v1":
        raise WitnessIntegrityError("missing joint grounding receipt")
    joint_refs = sorted(k for k, p in bundle["proofs"].items() if p["purpose"] == "completion_joint")
    if (
        receipt["proof_refs"] != joint_refs
        or receipt["participating_roles"] != sorted(own_roles)
        or receipt["verifier_ids"] != sorted(set(requirement["relationship_verifiers"]))
        or receipt["status"] not in ("blocked_prerequisite", "bypassed_lt_two_own", "proved", "unproved")
        or (receipt["status"] == "proved") != bool(joint_refs)
    ):
        raise WitnessIntegrityError("joint grounding receipt mismatch")
    old_i1_refs = sorted(k for k, p in bundle["proofs"].items() if p["purpose"] == "i1_relation_witness")
    if instance.get("witness_proofs") != old_i1_refs:
        raise WitnessIntegrityError("I1 proof reference mismatch")
    for ref in joint_refs:
        proof = bundle["proofs"][ref]
        if proof["participating_roles"] != sorted(own_roles) or any(
            a["immediate_operand_source"] != "own" for a in proof["assignment"].values()
        ):
            raise WitnessIntegrityError("completion proof participation mismatch")
    rc = requirement["role_completion"]
    bindings = instance["role_bindings"]
    validate_witness_bundle(bundle, rc, bindings, requirement["relationship_verifiers"], props)
    # Re-finalization is deterministic, not additive stale proof accumulation.
    bundle["proofs"] = {k: p for k, p in bundle["proofs"].items() if p["purpose"] == "completion_joint"}
    result = {}
    proofs = {}
    if len(rc["required_roles"]) >= 2:
        proofs, result = select_i1_proofs(
            bundle, rc["required_roles"], bindings, props, verified_predicate, referent_predicate
        )
    if old_i1_refs and {k: instance["witness_bundle"]["proofs"][k] for k in old_i1_refs} != proofs:
        raise WitnessIntegrityError("stored I1 proof verification mismatch")
    for key, proof in proofs.items():
        _put(bundle["proofs"], key, proof)
    bundle["observation_bases"] = build_observation_bases(bundle, own_roles, rc["required_roles"], bindings)
    if instance["witness_bundle"]["observation_bases"] and (
        instance["witness_bundle"]["observation_bases"] != bundle["observation_bases"]
    ):
        raise WitnessIntegrityError("stored observation basis mismatch")
    validate_witness_bundle(bundle, rc, bindings, requirement["relationship_verifiers"], props)
    return {**result, "witness_bundle": bundle, "witness_proofs": sorted(proofs)}
