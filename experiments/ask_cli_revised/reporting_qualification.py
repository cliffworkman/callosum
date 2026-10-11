"""Replay-only reporting view; original authenticated overlay/outputs remain unchanged."""

import json

from experiments.ask_cli_revised import producer_authorization as pa
from experiments.ask_cli_revised import reporting_contract as rc
from experiments.ask_cli_revised._layerc_common import body_reference, plain, require
from experiments.ask_cli_revised.producer_authorization_store import load_trusted_producer_registry


def reporting_view(smap, sealed_bytes, authored, receipt, *, input_bundle):
    verified = pa.verify_producer_authorization(
        smap,
        sealed_bytes,
        authored,
        receipt,
        input_bundle=input_bundle,
        trusted_registry=load_trusted_producer_registry(),
    )
    request = json.loads(input_bundle.files["preserved-run/01_request_contract.json"])
    scientific = {cid: {"child_id": cid, "requirements": rows} for cid, rows in authored["requirements"].items()}
    overlay = authored["overlay"]
    require(
        overlay["status"] == "REPLAY_ONLY_OFFLINE_OVERLAY" and overlay["postdates_phase28_attempt2_live_run"] is True,
        "confirmed replay overlay required",
    )
    owned = {c for node in overlay["nodes"] for c in node["owning_child_ids"]}
    folded = {c for children in overlay.get("folded_child_ids", {}).values() for c in children}
    missing = set(scientific) - owned
    require(missing <= folded, "unaccounted replay scientific child")
    result = {
        "schema": rc.SCHEMA,
        "request_ref": rc.request_ref(request),
        "nodes": [
            {
                "node_id": n["label"],
                "literal_text": n["literal_text"],
                "parent_id": n.get("parent"),
                "owning_child_ids": list(n["owning_child_ids"]),
            }
            for n in overlay["nodes"]
        ],
        "scientific_only_child_ids": sorted(missing),
        "requested_construct_terms": plain(overlay["requested_construct_terms"]),
    }
    rc.validate(result, request, scientific)
    return {
        "reporting": result,
        "reporting_ref": rc.reporting_ref(result),
        "provenance": {
            "kind": "derived_confirmed_replay_view",
            "claims_live_run_possession": False,
            "source_overlay_ref": body_reference("replay-overlay", overlay),
            "verified_producer_authorization_ref": verified.authorization_ref,
        },
    }
