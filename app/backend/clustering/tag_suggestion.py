"""Suggest tags for a single paper via local c-TF-IDF (inc 72) — the per-paper analogue of axis suggestion.

Ranks the terms most **distinctive of this paper vs the library** (TF-IDF) using the same content
tokenization the axis suggester uses, drops the paper's existing tags, and returns candidate names the user
curates (the human opts in, like axis-term curation). Entirely local — no embeddings, no clustering, no
egress; purely token statistics over the user's own stored metadata.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable

from sqlalchemy import Connection, select

# Intentional shared tokenizer: tags and axis terms should come from the same vocabulary (title + JATS-
# stripped abstract, stopwords/short/digits removed). Reusing keeps them consistent.
from app.backend.clustering.axis_suggestion import _paper_tokens
from app.backend.persistence.schema import papers

MAX_LIBRARY_PAPERS = 5000  # safety cap on the IDF corpus scan (single-user local tool)
DEFAULT_MAX_SUGGESTIONS = 8


def suggest_tags_for_paper(
    conn: Connection,
    paper_id: int,
    *,
    existing_tag_names: Iterable[str] = (),
    limit: int = DEFAULT_MAX_SUGGESTIONS,
) -> list[str]:
    """Top distinctive terms for the paper, excluding its current tags. Empty if the paper is trashed/absent
    or has no usable text. Ranking = tf(term, paper) · idf(term, library)."""
    rows = list(
        conn.execute(
            select(papers.c.id, papers.c.title, papers.c.abstract)
            .where(papers.c.deleted_at.is_(None))
            .order_by(papers.c.id)
        ).mappings()
    )[:MAX_LIBRARY_PAPERS]
    target = next((r for r in rows if int(r["id"]) == paper_id), None)
    if target is None:
        return []
    target_tf = Counter(_paper_tokens(target))
    if not target_tf:
        return []

    n = len(rows)
    doc_freq: Counter = Counter()
    for row in rows:
        doc_freq.update(set(_paper_tokens(row)))  # one increment per paper that contains the term

    excluded = {name.strip().lower() for name in existing_tag_names}
    scored = []
    for term, tf in target_tf.items():
        if term in excluded:
            continue
        idf = math.log((n + 1) / (doc_freq[term] + 1)) + 1.0
        scored.append((term, tf * idf))
    scored.sort(key=lambda kv: (-kv[1], kv[0]))  # score desc, then term asc for stable output
    return [term for term, _ in scored[:limit]]
