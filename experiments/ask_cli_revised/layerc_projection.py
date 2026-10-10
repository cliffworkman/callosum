"""I4-4C: pure v8 reference validation and value coverage, with no consumer activation.

sealed is the original UTF-8 artifact bytes (not reserialized JSON). authored_contract is
{requirements: {child_id: [authored requirement without runtime instances/state/observations]},
 overlay: <authored overlay>}. profile is an explicit caller authorization receipt.
Hashes bind exact inputs; callers remain responsible for authenticating producer authorization.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from experiments.ask_cli_revised._layerc_common import (
    PROFILE,
    STRATEGIES,
    V8,
    ProjectionIntegrityError,
    canonical,
    digest,
    freeze,
    put,
    reference,
    require,
    text_hash,
)
from experiments.ask_cli_revised._layerc_observations import validate_observations, validate_summary_refs
from experiments.ask_cli_revised._layerc_validation import validate_proofs, validate_supports
from experiments.ask_cli_revised._layerc_values import category_refs, project_values

__all__ = ["validate_layerc_inputs", "LayerCProjectionV1", "ProjectionIntegrityError"]

REGISTRIES = (
    "placements",
    "role_specs",
    "support_records",
    "support_views",
    "eligibility_receipts",
    "candidate_metadata",
    "candidate_metadata_by_support",
    "category_observations",
    "proofs",
    "observation_bases",
    "observations",
    "summaries",
    "semantic_values",
    "value_coverage",
    "value_paths",
    "sources",
    "display_envelopes",
    "link_context_status",
    "link_context_records",
    "grouping",
)
RUNTIME_REQUIREMENT_FIELDS = frozenset(
    {
        "instances",
        "state",
        "reason",
        "direction_summary",
        "effectiveness_summary",
    }
)


@dataclass(frozen=True)
class LayerCProjectionV1:
    """Detached recursively immutable mapping registries, never a mutable map/bundle."""

    schema_version: str
    projection_id: str
    records: Mapping


def _profile(smap, sealed_bytes, ledger, authored, profile, contexts):
    require(type(sealed_bytes) is bytes, "sealed must be original UTF-8 artifact bytes")
    require(
        set(profile)
        == {
            "name",
            "sufficiency_identity",
            "map_sha256",
            "sealed_artifact_sha256",
            "sealed_proposition_index_sha256",
            "authored_contract_sha256",
            "overlay_sha256",
            "context_manifest_sha256",
            "containment_semantics",
            "direction_semantics",
            "producer",
            "authorization_sha256",
        },
        "profile fields",
    )
    require(profile["name"] == PROFILE, "unsupported projection profile")
    require(
        profile["sufficiency_identity"] == {"status": "supported_noncurrent", "version": V8},
        "noncurrent semantics identity required",
    )
    require(profile["containment_semantics"] == profile["direction_semantics"] == V8, "profile semantics mismatch")
    props = {p["proposition_id"]: p for p in ledger["verified_propositions"]}
    require(len(props) == len(ledger["verified_propositions"]), "duplicate sealed proposition")
    require(profile["map_sha256"] == digest(smap), "map hash mismatch")
    # Bytes are decoded only after the exact artifact receipt has been checked.
    require(profile["sealed_artifact_sha256"] == text_hash(sealed_bytes.decode("utf-8")), "sealed artifact byte hash")
    require(profile["sealed_proposition_index_sha256"] == digest(props), "sealed index hash")
    require(
        profile["authored_contract_sha256"] == digest(authored["requirements"])
        and profile["overlay_sha256"] == digest(authored["overlay"]),
        "authored input hash",
    )
    require(profile["context_manifest_sha256"] == digest(contexts), "context manifest mismatch")
    producer = profile["producer"]
    require(
        set(producer) == {"identity", "output_map_sha256", "receipt_sha256"}
        and isinstance(producer["identity"], str)
        and bool(producer["identity"]),
        "producer identity",
    )
    require(
        producer["output_map_sha256"] == digest(smap)
        and producer["receipt_sha256"] == digest({k: v for k, v in producer.items() if k != "receipt_sha256"}),
        "producer receipt",
    )
    require(
        profile["authorization_sha256"] == digest({k: v for k, v in profile.items() if k != "authorization_sha256"}),
        "profile authorization digest",
    )
    return props


def _sealed_sources(ledger):
    catalog = {}
    for s in ledger.get("evidence_spans", []):
        # Span labels are extraction-local in the preserved ledger. The sealed quote hash
        # is part of the existing identity and disambiguates reused labels without selection.
        key = (s["paper_id"], s["chunk_id"], s["span_id"], text_hash(s["text"]))
        require(key not in catalog or catalog[key] == s["text"], "conflicting sealed source locator")
        catalog[key] = s["text"]
    for prop in ledger["verified_propositions"]:
        require(prop.get("verification", {}).get("status") == "verified", "unverified sealed proposition")
        loc = (prop["paper_id"], prop["evidence_anchor_chunk_id"], prop["evidence_span_id"], text_hash(prop["quote"]))
        if not prop.get("anchors"):
            require(loc in catalog and catalog[loc] == prop["quote"], "sealed source locator mismatch")
        else:
            require(all(a.get("verbatim") is True for a in prop["anchors"]), "unverified continuation")
            for anchor in prop["anchors"]:
                require(
                    any(k[:3] == (prop["paper_id"], anchor["chunk_id"], anchor["span_id"]) for k in catalog),
                    "continuation source missing",
                )


def _validate(smap, ledger, authored, profile, contexts, props):
    output = {k: {} for k in REGISTRIES}
    output.update(input_profile=profile, diagnostics=[])
    _sealed_sources(ledger)
    require(
        set(authored) == {"requirements", "overlay"} and set(authored["requirements"]) == set(smap),
        "authored scope mismatch",
    )
    known_context_proofs = set()
    for child_id, child in sorted(smap.items()):
        require(child["sufficiency_semantics_version"] == V8, "mixed map version")
        authored_reqs = {r["id"]: r for r in authored["requirements"][child_id]}
        require(
            len(authored_reqs) == len(authored["requirements"][child_id])
            and set(authored_reqs) == {r["id"] for r in child["requirements"]},
            "authored requirements mismatch",
        )
        for requirement in child["requirements"]:
            authored_req = {k: v for k, v in requirement.items() if k not in RUNTIME_REQUIREMENT_FIELDS}
            require(authored_reqs[requirement["id"]] == authored_req, "runtime requirement changed authored contract")
            for spec in requirement["role_specs"].values():
                require(spec["mapping_strategy"] in STRATEGIES, "unsupported value strategy")
            for instance in requirement["instances"]:
                b = instance["witness_bundle"]
                place = {
                    "child_id": child_id,
                    "requirement_id": requirement["id"],
                    "instance_key": instance["instance_key"],
                }
                require(b["placement"] == place, "foreign bundle placement")
                require(b["schema_version"] == "witness-bundle-v1" and b["semantic_version"] == V8, "bundle schema")
                require(b["sealed_input_sha256"] == digest(props), "stale bundle sealed input")
                bindings = instance["role_bindings"]
                require(set(bindings) <= set(requirement["role_specs"]), "unknown bound role")
                semantic = validate_supports(
                    b, bindings, props, profile["map_sha256"], output, requirement["role_specs"]
                )
                material = {
                    "role_completion": requirement["role_completion"],
                    "bindings": semantic,
                    "relationship_verifiers": sorted(set(requirement["relationship_verifiers"])),
                }
                require(b["binding_semantic_input_sha256"] == digest(material), "stale binding semantic input")
                validate_proofs(requirement, instance, props, output, contexts)
                validate_observations(requirement, instance, props, output)
                known_context_proofs.update(
                    p for p, proof in b["proofs"].items() if proof["join"]["kind"] == "shared_designator"
                )
                for key in ("support_records", "support_views", "eligibility_receipts"):
                    for ref, record in b[key].items():
                        put(output[key], ref, record)
                placement_id = reference("layerc-placement-v1", place)
                require(placement_id not in output["placements"], "duplicate instance placement")
                output["placements"][placement_id] = {
                    "placement": place,
                    "state": instance["state"],
                    "complete": instance["complete"],
                    "requirement_state": requirement["state"],
                    "binding_states": {r: v["state"] for r, v in bindings.items()},
                    "joint_grounding": instance["joint_grounding"],
                    "witness_proofs": instance["witness_proofs"],
                    "relation_witnessed": instance.get("relation_witnessed"),
                }
                for role, spec in requirement["role_specs"].items():
                    key = reference(
                        "layerc-role-spec-v1", {"child_id": child_id, "requirement_id": requirement["id"], "role": role}
                    )
                    put(output["role_specs"], key, spec)
                categories = category_refs(requirement, instance, props, output)
                project_values(requirement, instance, props, categories, output)
            validate_summary_refs(child_id, requirement, output)
    require(all(c["proof_id"] in known_context_proofs for c in contexts), "orphan context receipt")
    for group in output["grouping"].values():
        group["members"] = {k: sorted(set(v)) for k, v in sorted(group["members"].items())}
    output["value_paths"] = {k: sorted(set(v)) for k, v in sorted(output["value_paths"].items())}
    output["diagnostics"] = sorted(output["diagnostics"], key=canonical)
    return output


def validate_layerc_inputs(smap, sealed, authored_contract, *, profile, optional_context_receipts=()):
    """Single validation/projection authority. No scientific selection or presentation execution."""
    before = canonical([smap, authored_contract, profile, optional_context_receipts])
    try:
        require(type(sealed) is bytes, "sealed must be original UTF-8 artifact bytes")
        ledger = json.loads(sealed.decode("utf-8"))
        props = _profile(smap, sealed, ledger, authored_contract, profile, optional_context_receipts)
        output = _validate(smap, ledger, authored_contract, profile, optional_context_receipts, props)
        require(before == canonical([smap, authored_contract, profile, optional_context_receipts]), "input mutation")
        body = {"schema_version": "layerc-validated-projection-v1", "records": output}
        return LayerCProjectionV1(
            body["schema_version"], reference("layerc-validated-projection-v1", body), freeze(output)
        )
    except (KeyError, TypeError, IndexError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectionIntegrityError("malformed projection input: " + str(exc)) from exc
