"""Stored observation/basis/reference validation; no observation classification."""

from experiments.ask_cli_revised._layerc_common import (
    V8,
    check_span,
    put,
    reference,
    require,
    source_identity,
    text_hash,
)


def validate_observations(requirement, instance, props, output):
    b = instance["witness_bundle"]
    views, records, proofs = b["support_views"], b["support_records"], b["proofs"]
    for bid, basis in b["observation_bases"].items():
        body = {k: v for k, v in basis.items() if k != "basis_id"}
        require(bid == basis["basis_id"] == reference("observation-basis-v1", body), "basis identity")
        require(basis["placement"] == b["placement"] and basis["semantic_version"] == V8, "basis placement")
        pid = basis["common_proposition_id"]
        require(pid in props, "basis source missing")
        for role, vid in basis["selected_views"].items():
            require(
                vid in views
                and views[vid]["placement"]["role"] == role
                and views[vid]["immediate_operand_source"] == "own"
                and pid in views[vid]["supporting_proposition_ids"],
                "basis own view",
            )
        require(basis["participating_own_roles"] == sorted(basis["selected_views"]), "basis own roles")
        for field, purpose in (("completion_proof_refs", "completion_joint"), ("i1_proof_refs", "i1_relation_witness")):
            for ref in basis[field]:
                require(
                    ref in proofs
                    and proofs[ref]["purpose"] == purpose
                    and proofs[ref]["join"].get("proposition_id") == pid,
                    "basis proof reference",
                )
                for role, vid in basis["selected_views"].items():
                    if role in proofs[ref]["assignment"]:
                        require(proofs[ref]["assignment"][role]["support_view_id"] == vid, "basis wrong tuple")
        for path in basis["direction_paths"]:
            for role, vid in path["selected_views"].items():
                require(vid in views and views[vid]["placement"]["role"] == role, "basis path view")
            require(
                all(path["selected_views"].get(r) == vid for r, vid in basis["selected_views"].items()),
                "basis changed own assignment",
            )
            require(
                path["operand_text_refs"]
                == {
                    role: views[vid]["operand_text_ref"]
                    for role, vid in path["selected_views"].items()
                    if role in requirement["role_completion"]["required_roles"]
                },
                "basis operand text refs",
            )
            for ref in path["i1_proof_refs"]:
                require(ref in basis["i1_proof_refs"], "basis path proof")
                require(
                    all(
                        path["selected_views"].get(role) == a["support_view_id"]
                        for role, a in proofs[ref]["assignment"].items()
                    ),
                    "basis path proof tuple",
                )
        put(output["observation_bases"], bid, basis)
    for kind in ("direction", "effectiveness"):
        for obs in instance.get(kind + "_observations", []):
            a = obs["evidence_alignment"]
            require(
                a["schema_version"] == "observation-alignment-v1" and a["semantic_version"] == V8, "alignment schema"
            )
            body = {
                "placement": b["placement"],
                "kind": kind,
                "scope_kind": a["scope_kind"],
                "physical_scope": a["physical_scope"],
                "semantic_result": {k: v for k, v in obs.items() if k not in ("proposition_id", "evidence_alignment")},
                "classifier_version": V8,
            }
            oid = reference("observation-v1", body)
            require(oid == a["observation_id"], "observation identity")
            require(bool(a["paths"]), "orphaned observation")
            pids = set()
            for path in a["paths"]:
                bid = path["basis_ref"]
                require(bid in b["observation_bases"], "orphaned observation basis")
                basis = b["observation_bases"][bid]
                pid = basis["common_proposition_id"]
                pids.add(pid)
                selected = path["selected_support_view_refs"]
                for role, vid in selected.items():
                    require(vid in views and views[vid]["placement"]["role"] == role, "observation selected view")
                require(
                    all(selected.get(r) == vid for r, vid in basis["selected_views"].items()),
                    "observation own assignment mismatch",
                )
                if kind == "direction":
                    matches = [
                        p
                        for p in basis["direction_paths"]
                        if p["selected_views"] == selected and p["operand_text_refs"] == path["operand_text_refs"]
                    ]
                    require(bool(matches), "observation path not stored in basis")
                    allowed = {tuple(sorted(set(basis["completion_proof_refs"] + p["i1_proof_refs"]))) for p in matches}
                    require(tuple(path["witness_proof_refs"]) in allowed, "observation proof alignment")
                else:
                    require(
                        selected == basis["selected_views"]
                        and path["operand_text_refs"] == {}
                        and path["witness_proof_refs"] == basis["completion_proof_refs"],
                        "effectiveness path",
                    )
                _physical(a, path, basis, views, records, props[pid])
                if a["scope_kind"] == "candidate_assertion":
                    raw = props[pid]["quote"][slice(*a["physical_scope"]["observation_span"])]
                    expected_text = " ".join(raw.split()) if kind == "direction" else raw
                    require(obs["exact_text"] == expected_text, "observation text outside stored physical scope")
            require(
                a["evidence_proposition_ids"] == sorted(pids) and obs["proposition_id"] == min(pids),
                "observation source membership",
            )
            put(output["observations"], oid, {"kind": kind, "placement": b["placement"], "record": obs})


def _physical(alignment, path, basis, views, records, prop):
    p = alignment["physical_scope"]
    quote = prop["quote"]
    if alignment["scope_kind"] == "candidate_assertion":
        ref = path["evidence_locator_ref"]
        require(
            ref in records and any(views[v]["support_ref"] == ref for v in basis["selected_views"].values()),
            "observation evidence locator",
        )
        rec = records[ref]
        require(
            p["assertion_span"] == rec["assertion_span"]
            and p["source_identity"] == source_identity(prop)
            and p["sealed_quote_sha256"] == text_hash(quote),
            "observation physical identity",
        )
        span = p["observation_span"]
        check_span(span, quote)
        require(rec["assertion_span"][0] <= span[0] < span[1] <= rec["assertion_span"][1], "observation span overrun")
        require(p["raw_text_sha256"] == text_hash(quote[slice(*span)]), "observation raw hash")
    else:
        require(
            alignment["scope_kind"] == "legacy_unit" and path["evidence_locator_ref"] is None,
            "unknown observation scope",
        )
        require(
            p["legacy_passage_sha256"] == text_hash(quote) and p["raw_text_sha256"] == text_hash(quote),
            "legacy observation hash",
        )
        expected = (
            [{"chunk_id": a["chunk_id"], "span_id": a["span_id"]} for a in prop["anchors"]]
            if prop.get("anchors")
            else [{"chunk_id": prop["evidence_anchor_chunk_id"], "span_id": prop["evidence_span_id"]}]
        )
        require(all(loc in p["locators"] for loc in expected), "legacy observation locator")


def validate_summary_refs(child_id, requirement, output):
    """Check stored summary memberships, not recompute conclusions or classifier results."""
    instances = {i["instance_key"]: i for i in requirement["instances"]}
    for kind in ("direction", "effectiveness"):
        summary = requirement.get(kind + "_summary")
        if not summary:
            continue
        complete = {k for k, i in instances.items() if i["complete"]}
        require(set(summary["complete_instance_keys"]) == complete, "summary complete membership")
        observed = set(summary["instance_keys_with_observations"])
        missing = set(summary["instance_keys_missing_observations"])
        require(not observed.intersection(missing) and observed | missing == complete, "summary membership partition")
        require(set(summary["conflicted_instance_keys"]) <= observed, "summary conflict references")
        for key in observed:
            require(bool(instances[key].get(kind + "_observations")), "summary orphaned observation")
        require(
            summary["consensus_value"] is None or summary["consensus_value"] in summary["observed_values"],
            "summary consensus outside recorded values",
        )
        require(
            not summary["has_within_instance_conflict"] or summary["consensus_value"] is None,
            "conflicted summary has consensus",
        )
        refs = sorted(
            o["evidence_alignment"]["observation_id"]
            for key in observed
            for o in instances[key].get(kind + "_observations", [])
        )
        require(all(ref in output["observations"] for ref in refs), "summary unknown observation reference")
        body = {
            "child_id": child_id,
            "requirement_id": requirement["id"],
            "kind": kind,
            "stored_summary": summary,
            "observation_refs": refs,
        }
        put(output["summaries"], reference("layerc-summary-v1", body), body)
