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


_HEADER = (
    "Every claim below is source-verified: it was checked against its source passage. Whether a claim answers a part "
    "of your request is a separate judgment, shown separately, and it is not certified. This is a report on the "
    "evidence retrieved in this run; it makes no statement about what the library or the literature holds."
)
_ITEM_NONE = (
    "No claim has been judged responsive to this item from the evidence retrieved. This describes what was retrieved "
    "and assessed in this run, not the library or the literature."
)
_ITEM_NOT_ASSESSED = (
    "Responsiveness could not be assessed for this item in this run (a mechanical failure), so no judgment is shown."
)
_ITEM_GAPS = (
    "{n} source-verified claim(s) retrieved for this item could not be assessed for responsiveness in this run "
    "(a mechanical failure), so this is not settled."
)
_TAIL = (
    "Judged-responsive claims do not certify that every part of your request is answered, and an item without one "
    "reflects the limits of this run's retrieval and assessment."
)


def _claim_block(row: dict) -> list[str]:
    return [
        "> " + _literal(row["proposition_text"]),
        "",
        f"[{row['proposition_id']}]",
        "",
        f"Source-verified evidence: paper {row['paper_id']}, chunk {row['evidence_anchor_chunk_id']}, "
        + _literal(str(row["evidence_span_id"]))
        + ".",
        "",
    ]


def _roll_child(field_id: str, roll: dict) -> dict:
    return next(c for c in roll["children"] if c["child_id"] == field_id)


def _item_heading(state: dict, roll) -> str:
    """The item heading; a hierarchical child also names its parent. Flat ledgers (no roll-up) are headed exactly as before."""
    nested = ""
    if roll:
        parent = _roll_child(state["field_id"], roll)["parent"]
        nested = f" (nested under {parent})" if parent != "R" else ""
    return f"### {state['source_unit_id']}{nested}: {_literal(state['note'])}"


def _contract_block(state: dict, roll: dict) -> list[str]:
    """What was asked and approved for this item: a record for the researcher, never evidence and never a finding."""
    child = _roll_child(state["field_id"], roll)
    owned = [o for o in roll["obligations"] if o["owner_child"] == child["child_id"]]
    approval = f" ({child['approval_ref']})" if child["approval_ref"] else ""
    lines = ["Contract for this item (a record of what was asked and approved; it is not evidence):", ""]
    lines.append("- Owned obligations (representation only): " + "; ".join(f"{o['obligation']} {_literal(o['text'])}" for o in owned))
    lines.append(
        f"- Wording provenance: {child['wording_provenance'] or 'none recorded'}; execution: {child['execution_state']}{approval}"
    )
    shown = [q["text"] for q in child["qualifications"] if q["model_facing"]] + [
        r["text"] for r in child["active_constraints"] if r["model_facing"]
    ]
    if shown:
        lines.append("- Constraints shown to the models: " + " ".join(f"({i}) {_literal(t)}" for i, t in enumerate(shown, 1)))
    for q in child["qualifications"]:
        if not q["model_facing"]:
            lines.append(f"- Recorded, not shown to the models: {q['id']}: {_literal(q['text'])} ({q['excluded_reason']})")
    scope = child["scope_carrier"]
    if scope:
        lines.append(f"- Scope carried into retrieval and assessment (from {scope['from']}): \"{_literal(scope['wording'])}\"")
    for m in child["human_review_meanings"]:
        lines.append(f"- Recorded human-review meaning ({m['id']}): {_literal(m['text'])}. {m['note']}")
    for s in child["superseded"]:
        lines.append(f"- Superseded ({s['id']}, {s['decision']}): {s['note']}")
    lines += ["- " + roll["item_disclaimer"], ""]
    return lines


def _reconciliation_section(roll: dict) -> list[str]:
    """Structural only: obligation -> owner item -> that item's state, copied. No obligation or parent is judged from it."""
    labels = roll["labels"]
    counts = roll["representation_accounted"]
    lines = [
        "## Parent reconciliation (structural; no verdict)",
        "",
        roll["note"],
        "",
        f"- Representation: {labels['representation']}: {counts['accounted']} of {counts['of']} obligations are owned by a child item ({counts['basis']}).",
        "- Child-level responsiveness: assessed per item above (" + ", ".join(labels["child_item_states"]) + " for each item).",
        "- Individual obligation fulfilment: NOT assessed by this run.",
        "- Parent answer completeness: NOT certified.",
        *([f"- {roll['human_review_statement']}"] if roll.get("human_review_statement") else []),
        "",
        "| obligation | owner item | owner item state | obligation fulfilment |",
        "|---|---|---|---|",
    ]
    for o in roll["obligations"]:
        lines.append(
            f"| {o['obligation']} {_literal(o['text'])} ({o['kind']}) | {o['owner_child']} | {o['owner_item_state']} | {o['obligation_fulfilment']} |"
        )
    lines += ["", "Parent items (each keeps its own state; a subordinate item never changes its parent's state):", ""]
    for p in roll["parents"]:
        subs = ", ".join(f"{k} {v}" for k, v in p["subordinate_item_states"].items())
        lines.append(f"- {p['node']}: own item {p['own_item_state']}; subordinate items {subs}; parent completeness {p['parent_completeness']}")
    lines += [""]
    if roll["background"]:
        lines += ["Background (never asked): " + "; ".join(f"{b['id']} {_literal(b['text'])}" for b in roll["background"]), ""]
    lines += ["Closure rule: " + _literal(roll["closure_rule"]), ""]
    return lines


def render_responsive_ledger(ledger: dict) -> tuple[str, dict]:
    """Source-verified claims arranged by the responsiveness judgments the run made, verbatim and unaggregated.

    Source verification and responsiveness stay separate: a claim is listed under an item only if the coverage
    authority judged it responsive to that item; every other source-verified claim is still shown, either as not
    judged responsive or, where no judgment could be made, as not assessed. Model and role names live in the manifest
    (a trace/debug surface), not in the prose. Nothing here certifies completeness or speaks to the literature.
    """
    rows = validate_ledger(ledger)
    assessed = bool(ledger.get("coverage_assessed", True))
    lines = ["# What the retrieved evidence shows for your request", "", _HEADER, ""]
    contract = ledger.get("request_contract")
    if contract:
        lines += ["## Your request (verbatim)", "", "> " + _literal(contract["original_question"]), ""]
    by_id = {r["proposition_id"]: r for r in rows}
    roll = ledger.get("hierarchy")  # present only for a hierarchical run
    lines += ["## By request item", ""]
    for state in ledger["obligation_states"]:
        lines += [_item_heading(state, roll), ""]
        if state["state"] == "not_assessed":
            lines += [_ITEM_NOT_ASSESSED, ""]
        elif state["proposition_ids"]:
            lines += ["Judged responsive to this item:", ""]
            for pid in state["proposition_ids"]:
                lines += _claim_block(by_id[pid])
        else:
            lines += [_ITEM_NONE, ""]
        if state.get("mechanical_gaps"):
            lines += [_ITEM_GAPS.format(n=state["mechanical_gaps"]), ""]
        if roll:
            lines += _contract_block(state, roll)

    def responsiveness(row: dict) -> str:
        if row.get("responsive_obligation_ids"):
            return "judged_responsive"
        if not assessed or row.get("mapping_state") == "no_answer":
            return "not_assessed"
        return "not_judged_responsive"

    not_judged = [r for r in rows if responsiveness(r) == "not_judged_responsive"]
    not_assessed = [r for r in rows if responsiveness(r) == "not_assessed"]
    lines += ["## Source-verified but not judged responsive", ""]
    if not_judged:
        for row in not_judged:
            lines += _claim_block(row)
    else:
        lines += ["None.", ""]
    if not_assessed:
        lines += ["## Source-verified claims whose responsiveness was not assessed", ""]
        for row in not_assessed:
            lines += _claim_block(row)
    if roll:
        lines += _reconciliation_section(roll)
    lines += ["## Completeness remains unresolved", "", _TAIL, ""]
    claims = [
        {
            "proposition_ids": [row["proposition_id"]],
            "text": row["proposition_text"],
            "aggregation": "none",
            "paper_id": row["paper_id"],
            "chunk_id": row["evidence_anchor_chunk_id"],
            "span_id": row["evidence_span_id"],
            "responsive_obligation_ids": list(row.get("responsive_obligation_ids", [])),
            "responsiveness_state": responsiveness(row),
        }
        for row in rows
    ]
    manifest = {
        "mode": "responsive-ledger-v1",
        "claims": claims,
        "obligation_states": ledger["obligation_states"],
        "coverage_authority": ledger.get("coverage_authority"),
        "coverage_assessed": assessed,
        "scientific_aggregates": 0,
        "completeness": "not_certified",
    }
    return "\n".join(lines).rstrip() + "\n", manifest


def render_answer(ledger: dict) -> tuple[str, dict]:
    """The authoritative deterministic answer: responsiveness-aware when the ledger carries per-item judgments."""
    return render_responsive_ledger(ledger) if "obligation_states" in ledger else render_ledger(ledger)


def audit_final(ledger: dict, markdown: str) -> dict:
    """Citation diagnostics for any answer; strict conformance for safe output.

    Arbitrary prose entailment is NOT decidable by citation presence. Nonmatching
    prose is explicitly unassessed, never blessed by a successful ID check.
    """
    expected, manifest = render_answer(ledger)
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
