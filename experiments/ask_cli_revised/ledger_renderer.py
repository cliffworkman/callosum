"""Constrained terminal output: verbatim verified claims, no scientific joins.

The renderer does not establish that a verified claim is responsive or true.
It guarantees only that it adds no scientific claim beyond the supplied ledger.
"""
from __future__ import annotations

import re


def _literal(text: str) -> str:
    # Prevent source text from creating Markdown citations, headings or HTML.
    return re.sub(r'([\\`*_{}\[\]()<>#+.!|~-])', r'\\\1', text).replace("\n", "\n> ")


def validate_ledger(ledger: dict) -> list[dict]:
    rows = ledger["verified_propositions"]
    source_spans = {
        (s["paper_id"], s["chunk_id"], s["span_id"], s["text"])
        for s in ledger.get("evidence_spans", [])
    }
    seen = set()
    for row in rows:
        pid = row.get("proposition_id", "")
        if not re.fullmatch(r"p[1-9][0-9]*", pid) or pid in seen:
            raise ValueError("invalid or duplicate proposition ID")
        seen.add(pid)
        if row.get("verification", {}).get("status") != "verified":
            raise ValueError("terminal ledger contains ineligible evidence")
        if not isinstance(row.get("proposition_text"), str) or not row["proposition_text"].strip():
            raise ValueError("missing proposition text")
        for key in ("paper_id", "evidence_anchor_chunk_id", "evidence_span_id", "quote"):
            if not row.get(key):
                raise ValueError(f"missing evidence ancestry: {key}")
        if any(type(row[key]) is not int or row[key] <= 0 for key in ("paper_id", "evidence_anchor_chunk_id")):
            raise ValueError("invalid evidence coordinates")
        if not isinstance(row["quote"], str) or not row["quote"].strip():
            raise ValueError("missing exact source quote")
        if not re.fullmatch(r"e[1-9][0-9]*", row["evidence_span_id"]):
            raise ValueError("invalid packet-local span ID")
        if (row["paper_id"], row["evidence_anchor_chunk_id"], row["evidence_span_id"], row["quote"]) not in source_spans:
            raise ValueError("proposition span does not resolve in the source-span catalog")
    return rows


def render_ledger(ledger: dict) -> tuple[str, dict]:
    rows = validate_ledger(ledger)
    lines = ["# Verified ledger excerpts", "",
             "These are verbatim ledger claims. Their relevance and request completeness are not certified.", ""]
    contract = ledger.get("request_contract")
    if contract:
        lines += ["## Original request (user text)", "", "> " + _literal(contract["original_question"]), ""]
    claims = []
    for row in rows:
        pid = row["proposition_id"]
        lines += ["> " + _literal(row["proposition_text"]), "", f"[{pid}]", "",
                  f"Evidence: paper {row['paper_id']}, chunk {row['evidence_anchor_chunk_id']}, "
                  + _literal(str(row["evidence_span_id"])) + ".", ""]
        claims.append({"proposition_ids": [pid], "text": row["proposition_text"],
                       "aggregation": "none", "paper_id": row["paper_id"],
                       "chunk_id": row["evidence_anchor_chunk_id"], "span_id": row["evidence_span_id"],
                       "obligation_ids": row.get("obligation_ids", [])})
    if not rows:
        lines += ["No verified propositions in this ledger.", ""]
    lines += ["## Request completeness remains unresolved", "",
              "Evidence mappings do not certify all parts of a request. Gaps do not establish library absence.", ""]
    if contract:
        for unit in contract["source_units"]:
            lines += [f"{unit['source_unit_id']} — completeness not certified; literal request:", "",
                      "> " + _literal(unit["text"]), ""]
    else:
        lines += ["Original request referent unavailable in this historical ledger; completeness cannot be audited.", ""]
    return "\n".join(lines).rstrip() + "\n", {"mode": "verbatim-ledger-v1", "claims": claims,
                              "scientific_aggregates": 0, "completeness": "not_certified"}


def audit_final(ledger: dict, markdown: str) -> dict:
    """Citation diagnostics for any answer; strict conformance for safe output.

    Arbitrary prose entailment is NOT decidable by citation presence. Nonmatching
    prose is explicitly unassessed, never blessed by a successful ID check.
    """
    expected, manifest = render_ledger(ledger)
    ids = {r["proposition_id"] for r in ledger["verified_propositions"]}
    cited = re.findall(r"(?<!\\)\[(p\d+(?:\s*,\s*p\d+)*)\]", markdown)
    citations = [pid.strip() for group in cited for pid in group.split(",")]
    exact = markdown == expected
    return {"ledger_ids": sorted(ids), "cited_ids": citations,
            "nonexistent_ids": sorted(set(citations) - ids),
            "constrained_render_match": exact,
            "unsupported_scientific_assertions": 0 if exact else "unassessed_requires_semantic_review",
            "all_proposition_spans_resolve": True,
            "claim_manifest": manifest if exact else None}
