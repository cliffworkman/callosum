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
RECORD_FILE = "15a_parent_synthesis.json"
ANSWER_FILE = "15_parent_answer.md"
INSPECTION_FILE = "15b_parent_synthesis_inspection.md"

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


def distinct_surface(values) -> list[str]:
    """Surface-level dedup for DISPLAY only (Phase 27a). Strings identical after whitespace normalization are shown
    once, first occurrence kept. Exact, never fuzzy: a near-but-not-identical value is a different value and stays.
    The ledger, every value, every proposition id and every citation are untouched; this only decides what is printed.
    Two independent corroborating sources for one value are still two sources in the ledger and in the citations."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = " ".join(str(value).split())
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _render_category_list(claim: dict) -> str:
    items = "; ".join(distinct_surface(v["exact_text"] for v in claim["values"]))
    return f"{claim['category_description']}: {items}."


def _render_relational(claim: dict) -> str:
    parts = "; ".join(f"{v['role']}: {v['exact_text']}" for v in claim["values"])
    return f"A reported relationship ({parts})."


def _render_direction_or_effectiveness(claim: dict) -> str:
    summary = claim["direction_or_effectiveness"]
    field = summary["field"]
    if summary["consensus_value"] is not None:
        return f"A {field} finding ({summary['consensus_value']}) was reported."
    observed = ", ".join(distinct_surface(summary["observed_values"])) or "none resolved"
    lines = [f"Reported {field} values across instances: {observed}."]
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


def literal_statement(claim: dict) -> str:
    """The Phase-26 deterministic literal for one claim: the fallback text Phase 27 uses whenever a model
    segment is not grounded. Public so the realization layer never re-implements a template."""
    return _render_claim(claim)


def _render_gap(gap: dict) -> str:
    label = _REASON_LABELS.get(gap["reason"], gap["reason"])
    categories = "; ".join(gap["category_descriptions"]) or "(no category description recorded)"
    return f"- {categories} ({label})."


def format_citations(claim: dict) -> str:
    """The deterministic citation for one claim: exactly its admissible proposition ids, sorted. The only citation a
    rendered statement can carry, so a model can never choose one (Phase 27 Section 5)."""
    ids = claim["admissible_proposition_ids"]
    return f"[{', '.join(ids)}]" if ids else ""


def _statement(claim: dict, realized_text: dict | None, cite: bool) -> str:
    text = (realized_text or {}).get(claim["claim_id"]) or _render_claim(claim)
    citation = format_citations(claim) if cite else ""
    return f"{text} {citation}".rstrip() if citation else text


def _render_resolved_empty(outcome: dict) -> str:
    """A statement about the completed search's outcome. Never a statement that the effect or the literature is absent."""
    categories = "; ".join(outcome["category_descriptions"])
    return f"- The scoped search completed without establishing a supported result for {categories}."


def render_answer(
    claim_ledger: list[dict],
    gap_report: list[dict],
    *,
    sealed: dict | None = None,
    realized_text: dict | None = None,
    cite: bool = False,
    resolved_empty_outcomes: list | None = None,
) -> str:
    """The researcher-facing answer. Pure: a function of its own arguments only.

    Phase 26 behaviour is the default and is unchanged when ``realized_text`` and ``cite`` are omitted.
    ``realized_text`` (Phase 27) maps claim_id to the statement shown for that claim; a claim absent from it, or mapped
    to an empty string, shows its deterministic literal. ``cite`` appends each claim's own admissible proposition ids
    to its Overview/Qualified line. ``sealed``, when supplied, additively enriches Supporting findings with the full
    cited passage (mirroring ``overview_render._finding_block``'s own style). ``resolved_empty_outcomes`` (Phase 27b)
    adds a deterministic "searched, no supported result" section only when there are outcomes, so a run without one
    renders byte-identically to before. It is never routed through the realization stage."""
    overview_claims = [c for c in claim_ledger if not _is_qualified(c)]
    qualified_claims = [c for c in claim_ledger if _is_qualified(c)]

    lines = ["# Overview", ""]
    if overview_claims:
        for claim in overview_claims:
            lines.append(_statement(claim, realized_text, cite))
    else:
        lines.append("No claim is established by the retrieved evidence in this run.")
    lines += ["", "## Qualified / heterogeneous findings", ""]
    if qualified_claims:
        for claim in qualified_claims:
            lines.append(_statement(claim, realized_text, cite))
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
    if resolved_empty_outcomes:
        lines += ["", "## Searched, no supported result established", ""]
        lines.extend(_render_resolved_empty(o) for o in resolved_empty_outcomes)
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


def record_hash(record: dict) -> str:
    """Canonical hash of a construction record minus its own ``parent_synthesis_hash`` key -- the same "hash the whole
    record minus its own hash" discipline ``overview.canonical_hash`` established."""
    body = {k: v for k, v in record.items() if k != "parent_synthesis_hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def construction_record(
    claim_ledger: list[dict],
    gap_report: list[dict],
    *,
    sealed_hash: str,
    sufficiency_map_hash: str,
    realization: dict | None = None,
    resolved_empty_outcomes: list | None = None,
    scoped_search_status: dict | None = None,
) -> dict:
    """The construction record. Without ``realization`` this is exactly the Phase-26 deterministic-only object (no model
    metadata, ``realization_state`` "deterministic_only"). With a Phase-27 ``realization`` it adds the realization fields;
    model metadata appears only when a call was actually attempted. Phase 27b adds two orthogonal fields, never inside
    ``claim_ledger`` or ``gap_report``: ``resolved_empty_outcomes`` (the deterministic searched-no-support projection)
    and ``scoped_search_status`` (the canonical per-requirement search status it was derived from). Both are always
    present, so a record's shape never depends on whether recovery ran. ``parent_synthesis_hash`` is computed last."""
    record = {
        "version": CONSTRUCTION_RECORD_VERSION,
        "sealed_ledger_hash": sealed_hash,
        "sufficiency_map_final_hash": sufficiency_map_hash,
        "claim_ledger": claim_ledger,
        "gap_report": gap_report,
        "resolved_empty_outcomes": list(resolved_empty_outcomes or []),
        "scoped_search_status": dict(scoped_search_status or {}),
    }
    if realization is None:
        record["realization_state"] = "deterministic_only"
        record["fallback_used"] = True
    else:
        record.update(
            {
                "realization_state": realization["state"],
                "call_attempted": realization["call_attempted"],
                "skip_reason": realization["skip_reason"],
                "whole_call_status": realization["whole_call_status"],
                "call_outcome": realization["call_outcome"],
                "prompt_sha256": realization["prompt_sha256"],
                "schema_sha256": realization["schema_sha256"],
                "contract_sha256": realization["contract_sha256"],
                "realized_segments": realization["segments"],
                "unknown_claim_ids": realization["unknown_claim_ids"],
                "item_diagnostics": realization.get("item_diagnostics"),
                "grounded_count": realization["grounded_count"],
                "fallback_count": realization["fallback_count"],
                "fallback_used": realization["fallback_count"] > 0,
            }
        )
        if realization["call_attempted"]:
            record["model"] = realization["model"]
    record["parent_synthesis_hash"] = record_hash(record)
    return record


def declined_record(*, reason: str, sealed_hash: str) -> dict:
    """The explicit decline: parent synthesis was requested but there is no final sufficiency map to consume. No ledger,
    no gaps, no model call, and no fallback to a raw-ledger rendering (Phase 27 Section 27)."""
    record = {
        "version": CONSTRUCTION_RECORD_VERSION,
        "sealed_ledger_hash": sealed_hash,
        "sufficiency_map_final_hash": None,
        "claim_ledger": [],
        "gap_report": [],
        "resolved_empty_outcomes": [],
        "scoped_search_status": {},
        "realization_state": "declined",
        "skip_reason": reason,
        "call_attempted": False,
        "fallback_used": False,
    }
    record["parent_synthesis_hash"] = record_hash(record)
    return record


def render_inspection(claim_ledger: list[dict], gap_report: list[dict], realization: dict | None) -> str:
    """The inspection artifact: every claim's segment status, screen reasons and citations, plus the full gap report with
    identifiers. Lives beside the researcher answer, never inside it."""
    lines = ["# Parent synthesis inspection", ""]
    if realization is None:
        lines += ["Deterministic-only rendering: no realization was supplied.", ""]
    else:
        header = f"Realization state: {realization['state']}"
        if realization["skip_reason"]:
            header += f" (skip: {realization['skip_reason']})"
        if realization["whole_call_status"]:
            header += f"; whole-call status: {realization['whole_call_status']}"
        lines += [
            header,
            "",
            "| claim | kind | segment | cited | claim-value reasons | evidence reasons | heterogeneity reasons | NLI reasons |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for seg in realization["segments"]:
            lines.append(
                f"| {seg['claim_id']} | {seg['claim_kind']} | {seg['status']} | "
                f"{', '.join(seg['cited_proposition_ids']) or '-'} | {', '.join(seg['claim_screen_reasons']) or '-'} | "
                f"{', '.join(seg['evidence_screen_reasons']) or '-'} | {', '.join(seg['heterogeneity_reasons']) or '-'} | "
                f"{', '.join(seg['nli_reasons']) or '-'} |"
            )
        lines.append("")
    lines += ["## Unresolved parts (identifiers)", ""]
    gap_lines = [
        f"- {g['target_id']} ({g['search_child_id']} / {g['requirement_id']}): {g['reason']}" for g in gap_report
    ]
    lines += gap_lines or ["None recorded."]
    return "\n".join(lines).rstrip() + "\n"
