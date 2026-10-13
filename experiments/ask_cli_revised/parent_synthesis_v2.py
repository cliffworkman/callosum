"""Deterministic typed realization. V2 never enters legacy flat-support/model screens."""

from experiments.ask_cli_revised._layerc_common import canonical, digest, plain, require

VERSION = "parent-synthesis-v2"


def authorized_claim_text(claim, projection):
    require(claim["schema"] == "parent-claim-v2", "v2 claim required")
    return canonical(
        {
            "semantic_identity": claim["semantic_identity"],
            "members": {v: plain(projection.records["semantic_values"][v]) for v in claim["member_value_refs"]},
        }
    )


def build_prompt(claims, projection):
    """Typed inspection/prompt transport only; no model executor is exposed."""
    return {c["claim_id"]: authorized_claim_text(c, projection) for c in claims}


def _authorized_items(claim, receipts, finalized, units):
    for ref, receipt in sorted(receipts.items()):
        if receipt["claim_ref"] != claim["claim_id"]:
            continue
        for source in finalized[receipt["coverage_ref"]]["accepted"]:
            if claim["semantic_identity"]["family"] == "relational" and not any(
                claim["claim_id"] in unit["claim_refs"]
                and path["proof_ref"] in receipt["relation_proof"]
                and receipt["coverage_ref"] in path["coverage_refs"]
                and source["sentence"] in path["joint_sentences"]
                and source["proposition_id"] == path["join"].get("proposition_id")
                for unit in units.values()
                for path in unit["paths"]
            ):
                continue
            require(source["source_ref"] in receipt["citation"], "v2 source has no member citation receipt")
            item = {
                "value_ref": receipt["value_ref"],
                "receipt_ref": ref,
                "source_ref": source["source_ref"],
                "display_envelope_ref": source["display_envelope_ref"],
                "text": source.get("statement", source["sentence"]),
                "proposition_id": source["proposition_id"],
                "reported_finding": receipt["reported_finding"],
                "scientific_goal_state": receipt["scientific_goal_state"],
            }
            # The verified claim is the statement; the authorized source sentence stays beside it as its evidence.
            if "statement" in source:
                item["evidence_sentence"] = source["sentence"]
            if "qualification" in source:
                item["qualification"] = source["qualification"]
            yield item


def claim_value_reasons(claim, item, receipts, finalized, units):
    return [] if item in list(_authorized_items(claim, receipts, finalized, units)) else ["unauthorized_value_path"]


def source_passage_reasons(claim, item, receipts, finalized, units):
    # Exact typed item equality includes member, receipt, source, text and polarity.
    return claim_value_reasons(claim, item, receipts, finalized, units)


def realize(claims, projection, receipts, finalized, units):
    segments = [
        {
            "claim_ref": c["claim_id"],
            "authorized_claim_text": authorized_claim_text(c, projection),
            "items": list(_authorized_items(c, receipts, finalized, units)),
            "mode": "deterministic_authorized_paths",
        }
        for c in claims
    ]
    body = {
        "version": VERSION,
        "projection_ref": projection.projection_id,
        "segments": segments,
        "claim_ledger_sha256": digest(claims),
        "claim_evidence_sha256": digest(receipts),
        "relation_units_sha256": digest(units),
    }
    return {**body, "record_sha256": digest(body)}


def audit(record, claims, projection, receipts, finalized, units):
    require(record == realize(claims, projection, receipts, finalized, units), "v2 synthesis rebuild mismatch")
    return {"valid": True, "version": VERSION, "record_sha256": record["record_sha256"]}
