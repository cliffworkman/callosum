"""Closed producer-authority material and immutable types (repository trust, not signatures)."""

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

V8 = "sufficiency-semantics-v8"
IDENTITY = {"status": "supported_noncurrent", "version": V8}
PURPOSE = "profile-b-offline-prerequisite"
ROOT_SCHEMA = "producer-authorization-registry-v1"
_LOADER_TOKEN = object()
ID_PATTERN = re.compile(r"([a-z][a-z0-9-]*):sha256:([0-9a-f]{64})")
FIELDS = {
    "producer-authorization-registry-v1": "schema profiles accepted_receipts",
    "qualified-producer-profile-v1": (
        "schema producer_id implementation_id runtime_contract permitted_identities producer_code_manifest_ref "
        "authored_inputs_ref required_input_provenance nomination_adapter_contract issuer_contract issuance_mode "
        "permitted_output_shape rulesets qualification_evidence fresh_model_retrieval_nli_permitted"
    ),
    "producer-output-receipt-v1": (
        "schema producer_id profile_ref event_kind event_key historical_receipt_existed sufficiency_identity "
        "producer_code_manifest_ref input_manifest_ref authored_inputs_ref nomination_inputs_ref map_canonical_sha256 "
        "sealed_artifact_bytes_sha256 sealed_proposition_index_sha256 authored_requirements_sha256 "
        "overlay_canonical_sha256 ownership_context_manifest_sha256 rulesets output_shape recovery_targets_sha256 "
        "qualification_combined_sha256"
    ),
    "producer-code-input-manifest-v1": "schema encoding files",
    "reviewed-authored-inputs-v1": (
        "schema contract_version question_key frozen_file_sha256 review_file_sha256 combined_hash "
        "requirements_sha256 hierarchy_frozen_sha256 hierarchy_review_sha256 hierarchy_source_hashes parent_map_sha256"
    ),
    "preserved-nomination-input-manifest-v1": (
        "schema provenance_class final_map_bytes_sha256 initial_map_bytes_sha256 model_assist_bytes_sha256 "
        "qwen_calls_bytes_sha256 held_bindings_sha256 replay_request_manifest_sha256 scope_context_count "
        "binding_count replay_request_count fresh_calls_permitted"
    ),
    "producer-event-input-manifest-v1": (
        "schema files authored_inputs_ref nomination_inputs_ref sealed_proposition_index_sha256 "
        "ownership_context_manifest_sha256 ownership_context_full_sha256 overlay_canonical_sha256 overlay_authority_kind"
    ),
}
RULE_FIELDS = (
    "ownership_context_schema ownership_rule attribution_schema attribution_classifier attribution_ruleset "
    "grounding_semantics support_policy_semantics support_policy_evaluation_schema guard_semantics category_classifier "
    "witness_semantics proof_schema support_view_schema observation_basis_schema containment_semantics "
    "direction_semantics effectiveness_semantics"
)
PREFIX = "experiments/ask_cli_revised/"


class ProducerAuthorizationError(ValueError):
    """Untrusted, inconsistent, stale or unenrolled producer data."""


def require(condition, message):
    if not condition:
        raise ProducerAuthorizationError(message)


def plain(value):
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


def canonical(value):
    return json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def byte_hash(value):
    require(type(value) is bytes, "actual byte snapshot required")
    return hashlib.sha256(value).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value):
    raise ProducerAuthorizationError("nonfinite JSON number: " + value)


def _finite_float(text):
    result = float(text)
    require(math.isfinite(result), "nonfinite JSON number")
    return result


def decode(raw):
    require(type(raw) is bytes, "JSON bytes required")
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite, parse_float=_finite_float
        )
    except (UnicodeError, ValueError) as exc:
        raise ProducerAuthorizationError("invalid JSON: " + str(exc)) from exc


def closed(value, names, label):
    require(isinstance(value, Mapping) and set(value) == set(names.split()), label + " fields")


def valid_ref(ref, schema=None):
    require(isinstance(ref, str), "content reference type")
    match = ID_PATTERN.fullmatch(ref)
    require(match is not None and match[1] in FIELDS, "malformed/unknown content reference")
    require(schema is None or match[1] == schema, "reference schema mismatch")
    return match[1], match[2]


def reference(body):
    return body["schema"] + ":sha256:" + digest(body)


def safe_path(path):
    require(
        isinstance(path, str)
        and path
        and not path.startswith("/")
        and "\\" not in path
        and ":" not in path
        and all(p not in ("", ".", "..") for p in path.split("/")),
        "unsafe relative path",
    )


def _hash(value):
    require(isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None, "invalid SHA-256")


def _file_hashes(value):
    require(isinstance(value, Mapping) and bool(value), "empty file manifest")
    for path, sha in value.items():
        safe_path(path)
        _hash(sha)


def lifecycle(entry):
    closed(entry, "producer_id lifecycle issue consume", "lifecycle")
    flags = {"active": (True, True), "retired": (False, True), "revoked": (False, False)}
    require(entry["lifecycle"] in flags, "unknown lifecycle")
    require(type(entry["issue"]) is bool and type(entry["consume"]) is bool, "lifecycle booleans")
    require((entry["issue"], entry["consume"]) == flags[entry["lifecycle"]], "contradictory lifecycle")
    require(isinstance(entry["producer_id"], str) and bool(entry["producer_id"]), "producer identity")


def validate_material(body, expected_ref=None):
    require(isinstance(body, Mapping) and body.get("schema") in FIELDS, "unsupported material schema")
    schema = body["schema"]
    closed(body, FIELDS[schema], schema)
    # Validate leaf types, then each nested closed record. Dynamic maps are checked separately.
    boolean_fields = {"fresh_model_retrieval_nli_permitted", "historical_receipt_existed", "fresh_calls_permitted"}
    count_fields = {"scope_context_count", "binding_count", "replay_request_count"}
    for key, value in body.items():
        if key.endswith("_sha256") or key == "combined_hash":
            _hash(value)
        elif key.endswith("_ref"):
            valid_ref(value)
        elif key in boolean_fields:
            require(type(value) is bool and value is False, "forbidden authority flag")
        elif key in count_fields:
            require(type(value) is int and value >= 0, "invalid count")
        elif key not in {
            "profiles",
            "accepted_receipts",
            "runtime_contract",
            "permitted_identities",
            "rulesets",
            "qualification_evidence",
            "files",
            "sufficiency_identity",
            "hierarchy_source_hashes",
        }:
            require(isinstance(value, str) and bool(value), "nonempty string required: " + key)
    if schema == ROOT_SCHEMA:
        require(isinstance(body["profiles"], Mapping) and bool(body["profiles"]), "profiles")
        require(isinstance(body["accepted_receipts"], Mapping) and bool(body["accepted_receipts"]), "accepted receipts")
        for ref, entry in body["profiles"].items():
            valid_ref(ref, "qualified-producer-profile-v1")
            lifecycle(entry)
        for ref, entry in body["accepted_receipts"].items():
            valid_ref(ref, "producer-output-receipt-v1")
            closed(entry, "profile_ref input_manifest_ref purpose", "enrollment")
            valid_ref(entry["profile_ref"], "qualified-producer-profile-v1")
            valid_ref(entry["input_manifest_ref"], "producer-event-input-manifest-v1")
            require(
                entry["profile_ref"] in body["profiles"] and entry["purpose"] == PURPOSE, "enrollment purpose/profile"
            )
    if schema == "qualified-producer-profile-v1":
        closed(body["runtime_contract"], "implementation version semantic_dependencies", "runtime")
        require(all(isinstance(v, str) and v for v in body["runtime_contract"].values()), "runtime strings")
        require(
            isinstance(body["permitted_identities"], (list, tuple)) and len(body["permitted_identities"]) == 1,
            "identity list",
        )
        for ident in body["permitted_identities"]:
            _identity(ident)
        closed(
            body["qualification_evidence"],
            "i4_3c_combined_characterization_sha256 i4_3c_baseline_file_sha256 i4_2b3_context_baseline_file_sha256",
            "qualification",
        )
        for value in body["qualification_evidence"].values():
            _hash(value)
    if "rulesets" in body:
        closed(body["rulesets"], RULE_FIELDS, "rulesets")
        require(all(isinstance(v, str) and v for v in body["rulesets"].values()), "ruleset strings")
    if "sufficiency_identity" in body:
        _identity(body["sufficiency_identity"])
    if "files" in body:
        _file_hashes(body["files"])
    if "hierarchy_source_hashes" in body:
        closed(
            body["hierarchy_source_hashes"],
            "hierarchy-input/approvals hierarchy-input/assembled hierarchy-input/closure hierarchy-input/decisions",
            "hierarchy source",
        )
        _file_hashes(body["hierarchy_source_hashes"])
    if schema == "producer-code-input-manifest-v1":
        require(body["encoding"] == "utf8-universal-newlines-lf-no-other-normalization", "source encoding")
    # Hash serialization also rejects nonfinite/nonstrings in any unanticipated nested value.
    canonical(body)
    if expected_ref is not None:
        valid_ref(expected_ref, schema)
        require(reference(body) == expected_ref, "material content ID mismatch")
    return body


def _identity(value):
    closed(value, "status version", "identity")
    require(value["status"] in ("current", "supported_noncurrent", "historical_versioned"), "identity status")
    require(isinstance(value["version"], str) and bool(value["version"]), "identity version")


@dataclass(frozen=True, init=False)
class TrustedProducerRegistry:
    registry_ref: str
    body: Mapping
    materials: Mapping
    _seal: object


def _trusted_registry(body, materials, token):
    require(token is _LOADER_TOKEN, "fixed loader required")
    validate_material(body)
    for ref, material in materials.items():
        validate_material(material, ref)
    result = object.__new__(TrustedProducerRegistry)
    object.__setattr__(result, "registry_ref", reference(body))
    object.__setattr__(result, "body", freeze(plain(body)))
    object.__setattr__(result, "materials", freeze(plain(materials)))
    object.__setattr__(result, "_seal", _LOADER_TOKEN)
    return result


def require_trusted(registry):
    require(
        type(registry) is TrustedProducerRegistry and registry._seal is _LOADER_TOKEN,
        "trusted loader provenance required",
    )
    validate_material(registry.body, registry.registry_ref)


@dataclass(frozen=True)
class ProducerInputBundle:
    files: Mapping
    nominations: tuple
    replay_requests: tuple
    ownership_context: Mapping
    recovery_targets: Mapping

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, freeze(plain(getattr(self, name))))


@dataclass(frozen=True, init=False)
class VerifiedProducerAuthorization:
    authorization_ref: str
    identities: Mapping


def _verified_authorization(identities):
    result = object.__new__(VerifiedProducerAuthorization)
    object.__setattr__(result, "authorization_ref", reference(identities))
    object.__setattr__(result, "identities", freeze(plain(identities)))
    return result
