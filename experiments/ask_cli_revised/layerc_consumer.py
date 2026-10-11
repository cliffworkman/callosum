"""Profile-B caller bridge: verify upstream authority before the unchanged projection."""

import json
from dataclasses import dataclass

from experiments.ask_cli_revised import layerc_projection as lp
from experiments.ask_cli_revised import producer_authorization as pa
from experiments.ask_cli_revised._layerc_common import PROFILE, V8, digest, freeze, plain, require, text_hash
from experiments.ask_cli_revised.producer_authorization_store import load_trusted_producer_registry


@dataclass(frozen=True)
class AuthorizedLayerCInput:
    projection: lp.LayerCProjectionV1
    authored: object
    sealed: object
    producer_authorization: pa.VerifiedProducerAuthorization


def project_authorized(
    smap, sealed_bytes, authored_contract, producer_receipt, *, input_bundle, verified_authorization
):
    """Only the fixed current installation registry can authenticate supplied snapshots.

    The existing projection envelope is compatibility binding material, not a trust root.
    Authored reporting obligations travel separately so its frozen identity stays unchanged.
    """
    require(type(verified_authorization) is pa.VerifiedProducerAuthorization, "verified producer authority required")
    current = pa.verify_producer_authorization(
        smap,
        sealed_bytes,
        authored_contract,
        producer_receipt,
        input_bundle=input_bundle,
        trusted_registry=load_trusted_producer_registry(),
    )
    require(current == verified_authorization, "producer authority does not bind these inputs")
    identity = plain(current.identities)
    require(identity["sufficiency_identity"] == {"status": "supported_noncurrent", "version": V8}, "profile identity")
    ledger = json.loads(sealed_bytes)
    props = {p["proposition_id"]: p for p in ledger["verified_propositions"]}
    require(identity["map_canonical_sha256"] == digest(smap), "map bridge")
    require(identity["sealed_artifact_bytes_sha256"] == text_hash(sealed_bytes.decode()), "sealed bridge")
    require(identity["sealed_proposition_index_sha256"] == digest(props), "proposition bridge")
    # D1 verification above independently binds authored/overlay/nomination/context/output shape
    # and all rulesets to the actual snapshots. Do not infer authoring from the output map.
    producer = {"identity": "offline-qualified-v8-producer", "output_map_sha256": digest(smap)}
    producer["receipt_sha256"] = digest(producer)
    profile = {
        "name": PROFILE,
        "sufficiency_identity": identity["sufficiency_identity"],
        "map_sha256": digest(smap),
        "sealed_artifact_sha256": identity["sealed_artifact_bytes_sha256"],
        "sealed_proposition_index_sha256": digest(props),
        "authored_contract_sha256": digest(authored_contract["requirements"]),
        "overlay_sha256": digest(authored_contract["overlay"]),
        "context_manifest_sha256": digest(()),
        "containment_semantics": identity["rulesets"]["containment_semantics"],
        "direction_semantics": identity["rulesets"]["direction_semantics"],
        "producer": producer,
    }
    profile["authorization_sha256"] = digest(profile)
    projection = lp.validate_layerc_inputs(smap, sealed_bytes, authored_contract, profile=profile)
    return AuthorizedLayerCInput(projection, freeze(plain(authored_contract)), freeze(ledger), current)


def verify_and_project(smap, sealed_bytes, authored_contract, producer_receipt, *, input_bundle):
    verified = pa.verify_producer_authorization(
        smap,
        sealed_bytes,
        authored_contract,
        producer_receipt,
        input_bundle=input_bundle,
        trusted_registry=load_trusted_producer_registry(),
    )
    return project_authorized(
        smap,
        sealed_bytes,
        authored_contract,
        producer_receipt,
        input_bundle=input_bundle,
        verified_authorization=verified,
    )
