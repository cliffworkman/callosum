"""Run 0.6 audit = Run 0.5's four diagnostics + source-local drift (2E). All DIAGNOSTIC.

Reuses `audit.audit_decomposition` (2A global reconstruction, 2B per-source-unit coverage, 2C leave-one-out,
2D redundancy) verbatim and adds 2E source-local drift (per-item cosine of the rewrite to its OWN source
unit). None of these is epistemic authority: a plausible hallucinated item can be highly similar, and a
short/anaphoric unit's faithful reference-resolving rewrite can be less literally similar — so drift and
coverage are anomaly/repair signals, never delete rules or a standalone fidelity oracle.
"""

from __future__ import annotations

from experiments.ask_cli_revised.calibration.audit import (
    AuditThresholds,
    _cosine,
    _embed_map,
    audit_decomposition,
)


def source_local_drift(items: list[dict], embed_model) -> list[dict]:
    """Per-item cosine(rewrite, own source unit). Diagnostic only."""
    texts = [i["text"] for i in items] + [i["source_text"] for i in items]
    vectors = _embed_map(embed_model, texts)
    out = []
    for item in items:
        vt = vectors.get(item["text"])
        vs = vectors.get(item["source_text"])
        sim = _cosine(vt, vs) if vt is not None and vs is not None else 0.0
        out.append(
            {
                "item_id": item["item_id"],
                "source_unit_id": item["source_unit_id"],
                "source_local_similarity": round(sim, 4),
            }
        )
    return out


def audit_candidate(question: str, units: list[dict], items: list[dict], embed_model, *, thresholds: AuditThresholds) -> dict:
    """Full Run 0.6 audit dict for a candidate: the four Run 0.5 measures + source-local drift."""
    base = audit_decomposition(question, units, items, embed_model, thresholds=thresholds)
    base["source_local_drift"] = source_local_drift(items, embed_model)
    return base
