"""Phase 26: the deterministic parent-synthesis renderer and its construction record.

No model client (Phase 27 owns the bounded editorial realization pass). Every sentence here is a
deliberately literal template over an already-built ``ParentClaim``/``UnresolvedGap`` -- "favor
slightly awkward fidelity over fluent overstatement" (Phase-26 brief Section 18). This renderer
never joins two independently-built claims into one sentence and never infers a relationship the
claim ledger did not already decide; it only reorders, labels and lists what the ledger gives it.
"""

from __future__ import annotations

import hashlib
import json

CONSTRUCTION_RECORD_VERSION = "parent-synthesis-v1"

_REASON_LABELS = {
    "missing": "not established in the retrieved evidence",
    "partial": "some required evidence established; the remainder is not",
    "relationship_unverified": "the ingredients may be present, but the required relationship is not established",
    "provisional_corroboration": "a usable finding exists; further corroboration remains an open search obligation",
    "open_list_breadth": "current findings exist; the declared breadth obligation remains incomplete",
    "cardinality_deficit": "current findings exist; the declared cardinality obligation remains incomplete",
}


def _is_qualified(claim: dict) -> bool:
    heterogeneity = claim.get("conflict_or_heterogeneity")
    if not heterogeneity:
        return False
    return bool(
        heterogeneity.get("has_within_instance_conflict") or heterogeneity.get("has_across_instance_heterogeneity")
    )


def _locator(sealed: dict | None, proposition_id: str) -> str | None:
    if sealed is None:
        return None
    row = next((r for r in sealed["verified_propositions"] if r["proposition_id"] == proposition_id), None)
    if row is None:
        return None
    return f"Paper {row['paper_id']}, chunk {row['evidence_anchor_chunk_id']}: “{row['quote']}”"


def _render_role_value(claim: dict) -> str:
    value = claim["values"][0]
    return f"{claim['category_description']}: {value['exact_text']}."


def _render_category_list(claim: dict) -> str:
    items = "; ".join(v["exact_text"] for v in claim["values"])
    return f"{claim['category_description']}: {items}."


def _render_relational(claim: dict) -> str:
    parts = "; ".join(f"{v['role']}: {v['exact_text']}" for v in claim["values"])
    return f"A reported relationship ({parts})."


def _render_direction_or_effectiveness(claim: dict) -> str:
    summary = claim["direction_or_effectiveness"]
    field = summary["field"]
    if summary["consensus_value"] is not None:
        return f"A {field} finding ({summary['consensus_value']}) was reported."
    lines = [f"Reported {field} values across instances: {', '.join(summary['observed_values']) or 'none resolved'}."]
    if summary["has_across_instance_heterogeneity"]:
        lines.append("These instances disagree (heterogeneous across instances), and are not collapsed to one value.")
    if summary["has_within_instance_conflict"]:
        conflicted = ", ".join(str(k) for k in summary["conflicted_instance_keys"])
        lines.append(f"At least one instance ({conflicted}) carries internally conflicting observations.")
    return " ".join(lines)


_RENDERERS = {
    "role_value": _render_role_value,
    "category_list": _render_category_list,
    "relational": _render_relational,
    "direction_or_effectiveness": _render_direction_or_effectiveness,
}


def _render_claim(claim: dict) -> str:
    return _RENDERERS[claim["claim_kind"]](claim)


def _render_gap(gap: dict) -> str:
    label = _REASON_LABELS.get(gap["reason"], gap["reason"])
    categories = "; ".join(gap["category_descriptions"]) or "(no category description recorded)"
    return f"- {categories} ({label})."


def render_answer(claim_ledger: list[dict], gap_report: list[dict], *, sealed: dict | None = None) -> str:
    """The researcher-facing deterministic fallback answer. Pure: a function of its own arguments
    only. ``sealed``, when supplied, additively enriches Supporting findings with the full cited
    passage (mirroring ``overview_render._finding_block``'s own style); omitting it falls back to
    each claim's own short ``exact_text`` spans, still fully provenance-complete."""
    overview_claims = [c for c in claim_ledger if not _is_qualified(c)]
    qualified_claims = [c for c in claim_ledger if _is_qualified(c)]

    lines = ["# Overview", ""]
    if overview_claims:
        for claim in overview_claims:
            lines.append(_render_claim(claim))
    else:
        lines.append("No claim is established by the retrieved evidence in this run.")
    lines += ["", "## Qualified / heterogeneous findings", ""]
    if qualified_claims:
        for claim in qualified_claims:
            lines.append(_render_claim(claim))
    else:
        lines.append("None.")
    lines += ["", "## Supporting findings", ""]
    if claim_ledger:
        for claim in claim_ledger:
            cited = ", ".join(claim["admissible_proposition_ids"]) or "(none)"
            lines.append(f"- [{claim['claim_kind']}] cited: {cited}")
            if sealed is not None:
                for pid in claim["admissible_proposition_ids"]:
                    locator = _locator(sealed, pid)
                    if locator:
                        lines.append(f"  - {locator}")
    else:
        lines.append("No source-verified claims were established in this run.")
    lines += ["", "## Unresolved parts", ""]
    if gap_report:
        by_reason: dict[str, list[dict]] = {}
        for gap in gap_report:
            by_reason.setdefault(gap["reason"], []).append(gap)
        for reason in sorted(by_reason):
            lines.append(f"**{reason}**")
            lines.extend(_render_gap(g) for g in by_reason[reason])
            lines.append("")
    else:
        lines.append("None recorded.")
    lines.append("")
    lines.append(
        "This answer restates the structured sufficiency state of this run. It makes no statement "
        "about what the library or the literature holds, and completeness is not certified."
    )
    return "\n".join(lines).rstrip() + "\n"


def construction_record(
    claim_ledger: list[dict], gap_report: list[dict], *, sealed_hash: str, sufficiency_map_hash: str
) -> dict:
    """The Phase-26 construction-record object -- deterministic-only, no fake model metadata.
    ``parent_synthesis_hash`` is computed last, over everything else (the same "hash the whole
    record minus its own hash key" discipline ``overview.canonical_hash`` already established)."""
    record = {
        "version": CONSTRUCTION_RECORD_VERSION,
        "sealed_ledger_hash": sealed_hash,
        "sufficiency_map_final_hash": sufficiency_map_hash,
        "claim_ledger": claim_ledger,
        "gap_report": gap_report,
        "realization_state": "deterministic_only",
        "fallback_used": True,
    }
    canonical = json.dumps(record, sort_keys=True, ensure_ascii=False)
    record["parent_synthesis_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return record
