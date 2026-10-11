"""Explicit v8 Layer C integration. Upstream authority is verified, never issued here."""

from experiments.ask_cli_revised import layerc_consumer
from experiments.ask_cli_revised._layerc_common import PROFILE, body_reference, canonical, digest, plain, require
from experiments.ask_cli_revised.answer_plan import plan_v5

PROFILE_A = "v8-legacy-layerc-plan-v4-characterization"


def _build_components(projection, authored, sealed, verified):
    """Detached consumers; also the synthetic qualification seam, never an authority issuer."""
    from experiments.ask_cli_revised.layerc_pipeline import build_components

    return build_components(projection, authored, sealed, verified)


def _manifest(result, projection, verified):
    return {
        "schema": "profile-b-output-manifest-v1",
        "profile": PROFILE,
        "profile_version": "1",
        "verified_producer_authorization_ref": verified.authorization_ref,
        "projection_ref": projection.projection_id,
        "projection_sha256": result["plan"]["projection_sha256"],
        "schemas": result["plan"]["schemas"],
        "value_coverage_sha256": digest(result["value_coverage"]),
        "claim_ledger_sha256": digest(result["claims"]),
        "claim_evidence_sha256": digest(result["claim_evidence"]),
        "relation_units_sha256": digest(result["relation_units"]),
        "parent_synthesis_sha256": result["parent_synthesis"]["record_sha256"],
        "plan_sha256": result["plan"]["plan_sha256"],
        "render_sha256": digest(result["render"]),
        "sufficiency_identity": plain(verified.identities["sufficiency_identity"]),
    }


def build_profile_b(smap, sealed_bytes, authored_contract, producer_receipt, *, input_bundle, profile):
    require(profile == PROFILE, "explicit supported Layer C profile required")
    before = canonical(
        [smap, authored_contract, plain(input_bundle.recovery_targets), plain(input_bundle.replay_requests)]
    )
    bound = layerc_consumer.verify_and_project(
        smap,
        sealed_bytes,
        authored_contract,
        producer_receipt,
        input_bundle=input_bundle,
    )
    result = _build_components(bound.projection, bound.authored, bound.sealed, bound.producer_authorization)
    manifest = _manifest(result, bound.projection, bound.producer_authorization)
    result["output_manifest"] = manifest
    ref = body_reference("profile-b-output-manifest-v1", manifest)
    # A transport back-reference is outside the hashed plan body. The directed hashes are
    # upstream -> projection -> plan core -> render -> manifest; no fixed-point hash cycle.
    result["plan"]["output_manifest_ref"] = ref
    result["output_manifest_ref"] = ref
    result["combined_sha256"] = digest(result)
    require(
        before
        == canonical(
            [smap, authored_contract, plain(input_bundle.recovery_targets), plain(input_bundle.replay_requests)]
        ),
        "consumer mutated scientific input",
    )
    validate_output(result)
    return result


def validate_output(result):
    require(
        set(result)
        == {
            "claims",
            "claim_evidence",
            "relation_units",
            "value_coverage",
            "parent_synthesis",
            "plan",
            "render",
            "output_manifest",
            "output_manifest_ref",
            "combined_sha256",
        },
        "profile-B output fields",
    )
    body = {k: v for k, v in result.items() if k != "combined_sha256"}
    require(digest(body) == result["combined_sha256"], "combined output hash")
    plan, manifest = result["plan"], result["output_manifest"]
    require(
        set(manifest)
        == {
            "schema",
            "profile",
            "profile_version",
            "verified_producer_authorization_ref",
            "projection_ref",
            "projection_sha256",
            "schemas",
            "value_coverage_sha256",
            "claim_ledger_sha256",
            "claim_evidence_sha256",
            "relation_units_sha256",
            "parent_synthesis_sha256",
            "plan_sha256",
            "render_sha256",
            "sufficiency_identity",
        },
        "closed output manifest fields",
    )
    require(
        manifest["schemas"]
        == {
            "projection": "layerc-validated-projection-v1",
            "semantic_value": "semantic-value-v1",
            "value_coverage": "value-coverage-v1",
            "parent_claim": "parent-claim-v2",
            "claim_evidence": "claim-evidence-v1",
            "relation_unit": "relation-unit-v2",
            "parent_synthesis": "parent-synthesis-v2",
        }
        == plan["schemas"],
        "schema profile tuple",
    )
    require(plan["plan_version"] == plan_v5.PLAN_VERSION and plan["layerc_profile"] == PROFILE, "plan profile tuple")
    require(
        digest({k: v for k, v in plan.items() if k not in ("plan_sha256", "output_manifest_ref")})
        == plan["plan_sha256"],
        "plan core hash",
    )
    require(
        body_reference("profile-b-output-manifest-v1", manifest)
        == result["output_manifest_ref"]
        == plan["output_manifest_ref"],
        "output manifest reference",
    )
    require(
        manifest["profile"] == PROFILE and manifest["schema"] == "profile-b-output-manifest-v1",
        "output manifest profile",
    )
    for field, target in (
        ("claim_ledger_sha256", "claims"),
        ("claim_evidence_sha256", "claim_evidence"),
        ("relation_units_sha256", "relation_units"),
        ("value_coverage_sha256", "value_coverage"),
        ("render_sha256", "render"),
    ):
        require(manifest[field] == digest(result[target]), "output binding: " + field)
        if field in plan:
            require(plan[field] == manifest[field], "plan component binding: " + field)
    require(manifest["plan_sha256"] == plan["plan_sha256"], "output plan binding")
    require(
        manifest["parent_synthesis_sha256"] == result["parent_synthesis"]["record_sha256"], "output synthesis binding"
    )
    synthesis = result["parent_synthesis"]
    require(synthesis["version"] == "parent-synthesis-v2", "synthesis profile tuple")
    require(result["render"]["schema"] == "profile-b-render-v1", "render profile tuple")
    for key in ("claim_ledger_sha256", "claim_evidence_sha256", "relation_units_sha256", "projection_ref"):
        require(synthesis[key] == manifest[key], "synthesis binding: " + key)
    require(plan["parent_synthesis_sha256"] == synthesis["record_sha256"], "plan synthesis binding")
    require(
        plan["sufficiency_identity"] == {"status": "supported_noncurrent", "version": "sufficiency-semantics-v8"},
        "output sufficiency tuple",
    )
    require(
        digest({k: v for k, v in synthesis.items() if k != "record_sha256"}) == synthesis["record_sha256"],
        "synthesis body hash",
    )
    for key in ("verified_producer_authorization_ref", "projection_ref", "projection_sha256", "sufficiency_identity"):
        require(manifest[key] == plan[key], "manifest plan identity: " + key)
    require(manifest["profile_version"] == "1", "unsupported output profile version")
    return True
