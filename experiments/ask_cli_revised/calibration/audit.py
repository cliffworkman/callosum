"""Design-C deterministic semantic audit over a decomposition (§7a of the pivot addendum).

All four measures are DIAGNOSTIC. Nothing here deletes a canonical source unit or a decomposition item;
provenance stays deterministic (`datasets.segment_source_units`). Similarity is measurement, anomaly
detection, and repair guidance only — a plausible hallucinated item can still be highly similar to the
question, so similarity can never establish provenance or correctness.

Uses the already-loaded embedding model (all-MiniLM-L6-v2) on a handful of short strings — this is NOT
corpus re-embedding. all-MiniLM truncates beyond ~256 tokens; the aggregate of a few short questions is
well under that, but the caveat is noted in the report.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AuditThresholds:
    """Empirical Run 0.5 calibration parameters (picked from the dev-set distribution, not invented)."""

    global_gate: float
    coverage_gate: float
    redundancy_gate: float = 0.88


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _embed_map(embed_model, texts: list[str]) -> dict[str, np.ndarray]:
    """One batched encode over the distinct non-empty strings needed by the audit."""
    distinct = [t for t in dict.fromkeys(texts) if t.strip()]
    if not distinct:
        return {}
    vectors = np.asarray(embed_model.encode_texts(distinct))
    return {text: np.asarray(vectors[i]) for i, text in enumerate(distinct)}


def _aggregate_text(items: list[dict], *, exclude_item_id: str | None = None) -> str:
    parts = [item["text"] for item in items if item.get("item_id") != exclude_item_id and item["text"].strip()]
    return "\n".join(parts)


def audit_decomposition(
    question: str, units: list[dict], items: list[dict], embed_model, *, thresholds: AuditThresholds
) -> dict:
    item_texts = [item["text"] for item in items]
    unit_texts = [unit["text"] for unit in units]
    aggregate = _aggregate_text(items)
    loo_aggregates = [_aggregate_text(items, exclude_item_id=item["item_id"]) for item in items]

    to_embed = [question, aggregate, *item_texts, *unit_texts, *loo_aggregates]
    vectors = _embed_map(embed_model, to_embed)
    q_vec = vectors.get(question)

    def sim(text: str) -> float:
        vec = vectors.get(text)
        if q_vec is None or vec is None:
            return 0.0
        return _cosine(q_vec, vec)

    global_reconstruction = sim(aggregate) if aggregate.strip() else 0.0

    coverage = []
    for unit in units:
        unit_vec = vectors.get(unit["text"])
        best_match, best_item = 0.0, None
        for item in items:
            item_vec = vectors.get(item["text"])
            if unit_vec is None or item_vec is None:
                continue
            score = _cosine(unit_vec, item_vec)
            if score > best_match:
                best_match, best_item = score, item["item_id"]
        coverage.append(
            {
                "source_unit_id": unit["source_unit_id"],
                "source_text": unit["text"],
                "best_match": round(best_match, 4),
                "best_item_id": best_item,
                "weak": best_match < thresholds.coverage_gate,
            }
        )
    weakest = min((c["best_match"] for c in coverage), default=0.0)

    leave_one_out = []
    for item, loo_text in zip(items, loo_aggregates, strict=False):
        without = sim(loo_text) if loo_text.strip() else 0.0
        delta = global_reconstruction - without
        leave_one_out.append(
            {
                "item_id": item["item_id"],
                "full": round(global_reconstruction, 4),
                "without": round(without, 4),
                "delta": round(delta, 4),
                "suspicious": delta < 0,
            }
        )

    redundancy = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            vi, vj = vectors.get(items[i]["text"]), vectors.get(items[j]["text"])
            if vi is None or vj is None:
                continue
            score = _cosine(vi, vj)
            if score >= thresholds.redundancy_gate:
                redundancy.append(
                    {"item_a": items[i]["item_id"], "item_b": items[j]["item_id"], "similarity": round(score, 4)}
                )

    return {
        "global_reconstruction": round(global_reconstruction, 4),
        "passes_global": global_reconstruction >= thresholds.global_gate,
        "aggregate_text": aggregate[:1000],
        "source_unit_coverage": coverage,
        "weakest_coverage": round(weakest, 4),
        "leave_one_out": leave_one_out,
        "redundancy": redundancy,
        "thresholds": {
            "global_gate": thresholds.global_gate,
            "coverage_gate": thresholds.coverage_gate,
            "redundancy_gate": thresholds.redundancy_gate,
        },
    }
