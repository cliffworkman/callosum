"""Pure pinned producer verification. Repository enrollment is the A-D trust root.

Threat E (replacement of repository/verifier/process code) is outside this model.
No signatures, producer execution, filesystem access or downstream activation.
"""

from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised._producer_inputs import validate_input_bundle
from experiments.ask_cli_revised._producer_schema import (
    IDENTITY,
    PREFIX,
    PURPOSE,
    V8,
    ProducerAuthorizationError,
    ProducerInputBundle,
    TrustedProducerRegistry,
    VerifiedProducerAuthorization,
    _verified_authorization,
    byte_hash,
    canonical,
    decode,
    digest,
    lifecycle,
    plain,
    reference,
    require,
    require_trusted,
    validate_material,
)

__all__ = [
    "verify_producer_authorization",
    "VerifiedProducerAuthorization",
    "ProducerAuthorizationError",
    "ProducerInputBundle",
    "TrustedProducerRegistry",
]


def _material(registry, ref, schema):
    require(ref in registry.materials, "missing trusted material")
    value = registry.materials[ref]
    require(value["schema"] == schema, "incompatible referenced material")
    validate_material(value, ref)
    return value


def resolve_authority(registry, receipt, *, issuance=False):
    """Internal shared resolution; exact event enrollment is independent of profile permission."""
    require_trusted(registry)
    require(isinstance(receipt, dict) or hasattr(receipt, "keys"), "producer receipt required")
    profile_ref = receipt.get("profile_ref")
    require(profile_ref in registry.body["profiles"], "unknown authorized producer profile")
    entry = registry.body["profiles"][profile_ref]
    lifecycle(entry)
    profile = _material(registry, profile_ref, "qualified-producer-profile-v1")
    require(entry["producer_id"] == profile["producer_id"], "registry producer identity")
    require(entry["consume"], "profile consumption revoked")
    if issuance:
        require(entry["issue"], "profile issuance retired/revoked")
    validate_material(receipt)
    require(receipt["schema"] == "producer-output-receipt-v1", "producer receipt schema")
    receipt_ref = reference(receipt)
    require(receipt_ref in registry.body["accepted_receipts"], "unenrolled producer output receipt")
    accepted = registry.body["accepted_receipts"][receipt_ref]
    require(
        accepted["profile_ref"] == profile_ref
        and accepted["input_manifest_ref"] == receipt["input_manifest_ref"]
        and accepted["purpose"] == PURPOSE,
        "accepted receipt binding/purpose",
    )
    enrolled = _material(registry, receipt_ref, "producer-output-receipt-v1")
    require(canonical(enrolled) == canonical(receipt), "receipt differs from enrolled body")
    require(receipt["producer_id"] == profile["producer_id"], "unknown producer identity")
    return profile, receipt_ref


def verify_producer_authorization(
    smap, sealed_bytes, authored_contract, producer_receipt, *, input_bundle, trusted_registry
):
    """Verify actual snapshots, not caller-selected hashes or caller-provided authority."""
    try:
        return _verify(smap, sealed_bytes, authored_contract, producer_receipt, input_bundle, trusted_registry)
    except ProducerAuthorizationError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ProducerAuthorizationError("malformed producer authorization: " + str(exc)) from exc


def _verify(smap, sealed_bytes, authored_contract, receipt, bundle, registry):
    require_trusted(registry)
    if type(receipt) is bytes:
        receipt = decode(receipt)
    profile, receipt_ref = resolve_authority(registry, receipt)
    require(type(bundle) is ProducerInputBundle, "actual immutable input bundle required")
    event = _material(registry, receipt["input_manifest_ref"], "producer-event-input-manifest-v1")
    authored = _material(registry, receipt["authored_inputs_ref"], "reviewed-authored-inputs-v1")
    nominations = _material(registry, receipt["nomination_inputs_ref"], "preserved-nomination-input-manifest-v1")
    code = _material(registry, receipt["producer_code_manifest_ref"], "producer-code-input-manifest-v1")
    require(
        event["authored_inputs_ref"] == profile["authored_inputs_ref"] == receipt["authored_inputs_ref"],
        "authored reference chain",
    )
    require(event["nomination_inputs_ref"] == receipt["nomination_inputs_ref"], "nomination reference chain")
    validate_input_bundle(bundle, sealed_bytes, authored_contract, event, authored, nominations)
    require(plain(receipt["sufficiency_identity"]) == IDENTITY, "exact noncurrent/v8 disposition required")
    require(plain(profile["permitted_identities"]) == [IDENTITY], "incompatible profile disposition")
    si.check_authorization_binding(plain(receipt["sufficiency_identity"]), smap)
    require(receipt["map_canonical_sha256"] == digest(smap), "output map binding")
    require(receipt["sealed_artifact_bytes_sha256"] == byte_hash(sealed_bytes), "sealed bytes binding")
    for key in ("sealed_proposition_index_sha256", "overlay_canonical_sha256", "ownership_context_manifest_sha256"):
        require(receipt[key] == event[key], "receipt input binding: " + key)
    require(receipt["authored_requirements_sha256"] == authored["requirements_sha256"], "authored receipt binding")
    require(
        receipt["producer_code_manifest_ref"] == profile["producer_code_manifest_ref"] == reference(code),
        "producer code binding",
    )
    require(receipt["rulesets"] == profile["rulesets"], "ruleset substitution")
    require(
        all(
            profile["rulesets"][k] == V8
            for k in ("witness_semantics", "containment_semantics", "direction_semantics", "effectiveness_semantics")
        ),
        "v8 ruleset compatibility",
    )
    require(profile["issuer_contract"] == "reproduce-pinned-v8-then-issue-v1", "issuer contract")
    require(profile["issuance_mode"] == "registry-enrolled-reproduction-only", "issuance mode")
    require(
        profile["nomination_adapter_contract"] == "scope-requirement-role-request-context-held-bindings-v1",
        "nomination adapter",
    )
    require(profile["required_input_provenance"] == nominations["provenance_class"], "nomination provenance")
    require(profile["implementation_id"] == "diagnostic-map-plus-aligned-observations/v8", "producer implementation")
    require(
        receipt["output_shape"]
        == profile["permitted_output_shape"]
        == "bare-child-keyed-sufficiency-map-with-v8-identity",
        "output shape",
    )
    require(
        receipt["event_kind"] == "post_hoc_deterministic_reproduction"
        and receipt["historical_receipt_existed"] is False,
        "event truthfulness",
    )
    require(digest(bundle.recovery_targets) == receipt["recovery_targets_sha256"], "recovery binding")
    evidence = profile["qualification_evidence"]
    require(
        receipt["qualification_combined_sha256"] == evidence["i4_3c_combined_characterization_sha256"],
        "qualification binding",
    )
    for key, path in (
        ("i4_3c_baseline_file_sha256", PREFIX + "witness_i4_3c_replay_baseline.json"),
        ("i4_2b3_context_baseline_file_sha256", PREFIX + "attribution_i4_2b3_replay_baseline.json"),
    ):
        require(evidence[key] == byte_hash(bundle.files[path]), "qualification evidence bytes")
    identities = {
        "schema": "verified-producer-authorization-v1",
        "registry_ref": registry.registry_ref,
        "profile_ref": receipt["profile_ref"],
        "receipt_ref": receipt_ref,
        "input_manifest_ref": receipt["input_manifest_ref"],
        "map_canonical_sha256": digest(smap),
        "sealed_artifact_bytes_sha256": byte_hash(sealed_bytes),
        "sealed_proposition_index_sha256": receipt["sealed_proposition_index_sha256"],
        "authored_inputs_ref": receipt["authored_inputs_ref"],
        "nomination_inputs_ref": receipt["nomination_inputs_ref"],
        "producer_code_manifest_ref": receipt["producer_code_manifest_ref"],
        "rulesets": plain(receipt["rulesets"]),
        "sufficiency_identity": IDENTITY,
    }
    return _verified_authorization(identities)
