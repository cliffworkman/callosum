"""Axis-relevance highlight for discovery results (backlog #28, SP1b, inc 185).

For each search result, score its title+abstract against the user's AXIS embeddings and return the **best-matching
axis + similarity** for items that clear that axis's cutoff. This is a **hint, never a filter** — the caller
HIGHLIGHTS likely matches WITHIN the complete list (the `/discovery/search` endpoint still returns everything;
nothing is hidden or reordered). A below-cutoff item simply carries no badge — that is "no strong axis match,"
NOT "irrelevant" (silence is not a certificate). The match is one labeled cosine similarity (no opaque composite).

Fully local: embeddings over the user's own axes; **no egress**. No DB write (a pure read — axis vectors are
embedded fresh with the SAME text prep the axis scorer uses, so the numbers agree with the axis cards).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy import Connection, select

from app.backend.clustering.my_publications import MY_PUBLICATIONS_KIND
from app.backend.embeddings.models import EmbeddingModel, strip_punctuation
from app.backend.persistence.schema import axes

DEFAULT_AXIS_CUTOFF = 0.35  # mirrors routers/axes.py; a NULL scoring_gain means "use this default"


def _axis_text(label: Any, description: Any) -> str:
    # Mirror axis_scoring._axis_text: the description (its curated "Related:" terms) is the search vocabulary;
    # the label is a cosmetic display name, used only when the description is blank.
    d = (description or "").strip()
    return d if d else (str(label) if label else "")


def _unit_rows(vectors: list[list[float]]) -> np.ndarray:
    arr = np.asarray(vectors, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / (norms + 1e-12)


def score_axis_relevance(
    conn: Connection,
    items: list[dict[str, Any]],
    *,
    embedding_model: EmbeddingModel,
    cutoff_default: float = DEFAULT_AXIS_CUTOFF,
) -> dict[str, dict[str, Any]]:
    """``items``: ``[{dedup_key, text}]`` (text = title + abstract). Returns ``{dedup_key: {axis_id, axis_label,
    similarity}}`` for each item whose best axis match clears that axis's cutoff. My-Publications (an authorship
    axis, not a topical lens) is excluded; an empty/axis-less library returns ``{}`` (no badges)."""
    if not items:
        return {}
    rows = conn.execute(select(axes).where(axes.c.kind != MY_PUBLICATIONS_KIND)).mappings().all()
    prepared: list[tuple[int, str, float, str]] = []
    for ax in rows:
        text = strip_punctuation(_axis_text(ax["label"], ax["description"]))
        if not text.strip():
            continue
        cutoff = float(ax["scoring_gain"]) if ax["scoring_gain"] is not None else cutoff_default
        prepared.append((int(ax["id"]), str(ax["label"]), cutoff, text))
    if not prepared:
        return {}

    axis_units = _unit_rows(embedding_model.encode_texts([p[3] for p in prepared]))
    item_units = _unit_rows(embedding_model.encode_texts([it["text"] for it in items]))
    sims = item_units @ axis_units.T  # (n_items, n_axes) cosine similarities

    out: dict[str, dict[str, Any]] = {}
    for it, row in zip(items, sims, strict=False):
        best_idx = int(np.argmax(row))
        # Round to the 2 decimals the axis cards show, so the match number is the SAME as a paper's confidence.
        conf = round(float(max(0.0, min(1.0, row[best_idx]))), 2)
        axis_id, label, cutoff, _ = prepared[best_idx]
        if conf >= cutoff:
            out[it["dedup_key"]] = {"axis_id": axis_id, "axis_label": label, "similarity": conf}
    return out
