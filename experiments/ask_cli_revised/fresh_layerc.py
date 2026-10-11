"""Fresh invocation consumer: same projection and downstream science as qualification."""

from experiments.ask_cli_revised import fresh_invocation as fi
from experiments.ask_cli_revised import layerc_pipeline, layerc_projection
from experiments.ask_cli_revised._layerc_common import body_reference, canonical, digest, plain, require


def consume(invocation, smap, sealed_bytes, authored, *, recovery, search):
    require(type(invocation) is fi.TrustedFreshInvocation, "actual trusted invocation required")
    invocation.validate()
    require(
        digest(recovery) == invocation.body["recovery_sha256"] and digest(search) == invocation.body["search_sha256"],
        "fresh recovery/search mismatch",
    )
    before = canonical([smap, authored, recovery, search])
    profile = invocation.projection_profile()
    projection = layerc_projection.validate_layerc_inputs(
        smap, sealed_bytes, authored, profile=profile, fresh_authority=invocation
    )
    import json

    result = layerc_pipeline.build_components(
        projection, authored, json.loads(sealed_bytes), fresh_authority=invocation
    )
    manifest = {
        "schema": "fresh-layerc-output-manifest-v1",
        "profile": fi.PROFILE,
        "upstream_authority": {"kind": "trusted_fresh_invocation", "ref": invocation.provenance_ref},
        "reporting_contract_ref": invocation.body["reporting_ref"],
        "projection_ref": projection.projection_id,
        "projection_sha256": result["plan"]["projection_sha256"],
        "components": {key: digest(value) for key, value in result.items()},
        "sufficiency_identity": plain(invocation.body["sufficiency_identity"]),
    }
    result["output_manifest"] = manifest
    result["output_manifest_ref"] = body_reference("fresh-layerc-output-manifest-v1", manifest)
    result["invocation_provenance"] = plain(invocation.body)
    result["combined_sha256"] = digest(result)
    require(before == canonical([smap, authored, recovery, search]), "Layer C mutated scientific state")
    validate_output(result)
    return result


def validate_output(result):
    manifest, plan = result["output_manifest"], result["plan"]
    require(
        manifest["schema"] == "fresh-layerc-output-manifest-v1" and manifest["profile"] == fi.PROFILE,
        "fresh output schema",
    )
    require(
        result["combined_sha256"] == digest({k: v for k, v in result.items() if k != "combined_sha256"}),
        "fresh combined hash",
    )
    require(
        result["output_manifest_ref"] == body_reference("fresh-layerc-output-manifest-v1", manifest),
        "fresh manifest ref",
    )
    require(
        manifest["upstream_authority"]
        == plan["upstream_authority"]
        == {
            "kind": "trusted_fresh_invocation",
            "ref": body_reference("trusted-fresh-invocation-v1", result["invocation_provenance"]),
        },
        "fresh upstream identity",
    )
    require(
        manifest["reporting_contract_ref"]
        == plan["reporting_contract_ref"]
        == result["invocation_provenance"]["reporting_ref"],
        "fresh reporting ref",
    )
    require(
        set(manifest["components"])
        == {"claims", "claim_evidence", "relation_units", "value_coverage", "parent_synthesis", "plan", "render"},
        "fresh component inventory",
    )
    require(all(digest(result[k]) == h for k, h in manifest["components"].items()), "fresh component binding")
    require(plan["plan_sha256"] == digest({k: v for k, v in plan.items() if k != "plan_sha256"}), "fresh plan hash")
    require(
        plan["plan_version"] == "answer-plan-step2-v5" and plan["layerc_profile"] == fi.PROFILE, "fresh plan profile"
    )
    for key in ("projection_ref", "projection_sha256", "sufficiency_identity"):
        require(manifest[key] == plan[key], "fresh plan/manifest binding: " + key)
    require(
        manifest["sufficiency_identity"] == result["invocation_provenance"]["sufficiency_identity"],
        "fresh disposition binding",
    )
    synthesis = result["parent_synthesis"]
    require(synthesis["projection_ref"] == plan["projection_ref"], "fresh synthesis projection")
    for key, component in (
        ("claim_ledger_sha256", "claims"),
        ("claim_evidence_sha256", "claim_evidence"),
        ("relation_units_sha256", "relation_units"),
    ):
        require(plan[key] == synthesis[key] == digest(result[component]), "fresh downstream component: " + key)
    require(
        plan["parent_synthesis_sha256"]
        == synthesis["record_sha256"]
        == digest({k: v for k, v in synthesis.items() if k != "record_sha256"}),
        "fresh synthesis body",
    )
    return True
