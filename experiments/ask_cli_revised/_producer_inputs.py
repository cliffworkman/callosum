"""Pure identity checks over supplied byte snapshots; no scientific producer execution."""

import json

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_model_scope as scope
from experiments.ask_cli_revised._producer_schema import (
    PREFIX,
    byte_hash,
    canonical,
    closed,
    decode,
    digest,
    plain,
    require,
)

FROZEN = PREFIX + "sufficiency_contract.aib_hier_v9.frozen.json"
REVIEW = PREFIX + "sufficiency_contract.aib_hier_v9.review.json"
HIERARCHY = PREFIX + "hierarchy_contract.frozen.json"
HIERARCHY_REVIEW = PREFIX + "hierarchy_contract.review.json"
OVERLAY = PREFIX + "answer_plan/overlays/phase30_replay_decomposition_overlay.json"
RUN = "preserved-run/"


def reviewed_contracts(files):
    frozen, review = decode(files[FROZEN]), decode(files[REVIEW])
    entries = frozen["per_child"]
    require(bool(entries), "empty authored contract")
    for entry in entries.values():
        require(se.contract_hash(entry["frozen_view"]) == entry["hash"], "authored child hash")
    combined = byte_hash(json.dumps(entries, sort_keys=True, ensure_ascii=False).encode())
    require(combined == frozen["combined_hash"] == review["combined_hash"], "authored review hash")
    require(frozen["question_key"] == review["question_key"], "authored question identity")
    require(
        all(isinstance(review.get(k), str) and review[k] for k in ("reviewed_by", "reviewed_at")), "authored review"
    )
    return {cid: entry["frozen_view"] for cid, entry in entries.items()}


def requirements(contracts):
    return {cid: se.frozen_view(c)["requirements"] for cid, c in contracts.items()}


def parent_map(files):
    pins, review = decode(files[HIERARCHY]), decode(files[HIERARCHY_REVIEW])
    require(review["pins_sha256"] == byte_hash(files[HIERARCHY]), "hierarchy review pin")
    require(review["inputs_sha256"] == pins["inputs"], "hierarchy review inputs")
    require(
        all(isinstance(review.get(k), str) and review[k] for k in ("reviewed_by", "reviewed_at")), "hierarchy review"
    )
    for name in ("assembled", "approvals", "decisions", "closure"):
        require(byte_hash(files["hierarchy-input/" + name]) == pins["inputs"][name + "_sha256"], "hierarchy source")
    return {c["child_id"]: c["parent"] for c in pins["children"]}


def held_nominations(preserved):
    """Exact accepted replay extraction; empty slots and binding order are preserved."""
    held = {}
    for cid, contract in preserved.items():
        for req in contract["requirements"]:
            for inst in req["instances"]:
                for role, spec in req["role_specs"].items():
                    if spec["mapping_strategy"] != "model_nomination_only":
                        continue
                    key = (cid, req["id"], role, inst.get("request_context"))
                    choices = held.setdefault(key, [])
                    binding = inst["role_bindings"].get(role, {})
                    if (
                        binding.get("state") == "filled"
                        and binding.get("provenance", {}).get("candidate_source") != "parent_context"
                        and binding not in choices
                    ):
                        choices.append(plain(binding))
    return [
        {"scope": list(key[:3]), "request_context": key[3], "bindings": bindings}
        for key, bindings in sorted(held.items(), key=lambda item: canonical(item[0]))
    ]


def nomination_traces(value):
    if isinstance(value, dict):
        if {"request_fingerprint", "scope", "candidates_offered"} <= set(value):
            yield value
        for child in value.values():
            yield from nomination_traces(child)
    elif isinstance(value, list):
        for child in value:
            yield from nomination_traces(child)


def validate_preserved_nominations(files, contracts, nominations, manifest):
    held = held_nominations(decode(files[RUN + "17_sufficiency_map.json"]))
    require(plain(nominations) == held, "held nomination slot/binding mismatch")
    require(len(held) == manifest["scope_context_count"] == 32, "nomination slots")
    require(sum(len(r["bindings"]) for r in held) == manifest["binding_count"] == 21, "nomination bindings")
    require(digest(held) == manifest["held_bindings_sha256"], "held nomination manifest")
    traces = list(nomination_traces(decode(files[RUN + "18_sufficiency_model_assist.json"])))
    require(len(traces) == 49, "stored nomination trace count")
    specs = {
        (cid, q["id"], role): spec
        for cid, c in contracts.items()
        for q in c["requirements"]
        for role, spec in q["role_specs"].items()
    }
    for trace in traces:
        key = tuple(trace["scope"])
        require(key in specs, "unknown stored nomination scope")
        expected = scope.request_fingerprint(specs[key]["category_description"], trace["candidates_offered"])
        require(expected == trace["request_fingerprint"], "stored request fingerprint")
    return held, specs, traces


def validate_request_record(request, held, specs, traces):
    slots = {(tuple(r["scope"]), r["request_context"]) for r in held}
    closed(request, "scope request_context category_description candidate_rows request_fingerprint", "replay request")
    key = tuple(request["scope"])
    require(key in specs and (key, request["request_context"]) in slots, "unknown replay request slot")
    require(request["category_description"] == specs[key]["category_description"], "category description")
    fingerprint = scope.request_fingerprint(request["category_description"], request["candidate_rows"])
    require(request["request_fingerprint"] == fingerprint, "replay request fingerprint")
    candidates = sorted(plain(request["candidate_rows"]), key=canonical)
    matches = [
        t
        for t in traces
        if tuple(t["scope"]) == key
        and t.get("request_context") == request["request_context"]
        and t["request_fingerprint"] == fingerprint
        and sorted(t["candidates_offered"], key=canonical) == candidates
    ]
    require(bool(matches), "replay request has no preserved source")


def validate_nomination_requests(files, contracts, nominations, requests, manifest):
    held, specs, traces = validate_preserved_nominations(files, contracts, nominations, manifest)
    require(len(requests) == manifest["replay_request_count"] == 33, "replay request count")
    for request in requests:
        validate_request_record(request, held, specs, traces)
    require(
        digest(sorted(plain(requests), key=canonical)) == manifest["replay_request_manifest_sha256"],
        "replay request manifest",
    )
    for field, name in (
        ("final_map_bytes_sha256", "17_sufficiency_map.json"),
        ("initial_map_bytes_sha256", "17_sufficiency_map.initial.json"),
        ("model_assist_bytes_sha256", "18_sufficiency_model_assist.json"),
        ("qwen_calls_bytes_sha256", "qwen_calls.jsonl"),
    ):
        require(manifest[field] == byte_hash(files[RUN + name]), "nomination source bytes")


def validate_input_bundle(bundle, sealed_bytes, authored_contract, event, authored, nominations):
    require(set(bundle.files) == set(event["files"]), "input file set")
    for name, expected in event["files"].items():
        require(byte_hash(bundle.files[name]) == expected, "input bytes mismatch: " + name)
    files = bundle.files
    require(sealed_bytes == files[RUN + "11_verified_ledger.json"], "sealed snapshot mismatch")
    contracts = reviewed_contracts(files)
    closed(authored_contract, "requirements overlay", "authored input")
    require(plain(authored_contract["requirements"]) == requirements(contracts), "independent authoring mismatch")
    require(digest(authored_contract["requirements"]) == authored["requirements_sha256"], "authored requirements")
    for field, path in (
        ("frozen_file_sha256", FROZEN),
        ("review_file_sha256", REVIEW),
        ("hierarchy_frozen_sha256", HIERARCHY),
        ("hierarchy_review_sha256", HIERARCHY_REVIEW),
    ):
        require(authored[field] == byte_hash(files[path]), "authored source identity")
    frozen = decode(files[FROZEN])
    require(
        (authored["contract_version"], authored["question_key"], authored["combined_hash"])
        == (frozen["version"], frozen["question_key"], frozen["combined_hash"]),
        "authored identity",
    )
    require(digest(parent_map(files)) == authored["parent_map_sha256"], "parent map")
    for name, expected in authored["hierarchy_source_hashes"].items():
        require(byte_hash(files[name]) == expected, "hierarchy manifest source")
    overlay = decode(files[OVERLAY])
    require(plain(authored_contract["overlay"]) == overlay, "overlay substitution")
    require(
        overlay["status"] == "REPLAY_ONLY_OFFLINE_OVERLAY" and overlay["postdates_phase28_attempt2_live_run"] is True,
        "overlay authority",
    )
    require(digest(overlay) == event["overlay_canonical_sha256"], "overlay identity")
    require(event["overlay_authority_kind"] == "phase30-confirmed-offline-decomposition-only", "overlay scope")
    ledger = decode(sealed_bytes)
    props = {p["proposition_id"]: p for p in ledger["verified_propositions"]}
    require(len(props) == len(ledger["verified_propositions"]), "duplicate proposition")
    require(digest(props) == event["sealed_proposition_index_sha256"], "sealed proposition index")
    context = bundle.ownership_context
    closed(context, "schema_version sources entries bindings manifest_sha256", "ownership context")
    require(context["schema_version"] == "ownership-context-v1", "ownership schema")
    require(
        digest({k: v for k, v in context.items() if k != "manifest_sha256"}) == context["manifest_sha256"],
        "ownership context integrity",
    )
    require(context["manifest_sha256"] == event["ownership_context_manifest_sha256"], "ownership manifest")
    require(digest(context) == event["ownership_context_full_sha256"], "ownership index")
    validate_nomination_requests(files, contracts, bundle.nominations, bundle.replay_requests, nominations)
    return contracts
