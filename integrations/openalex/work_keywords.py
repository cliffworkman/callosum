"""Browsable keyword tags from an OpenAlex work (inc 306).

A pure function over an already-fetched work dict — **no egress**. Prefers OpenAlex's curated ``topics`` taxonomy
(current, ~1-3 per work, score-ranked); falls back to the legacy ``concepts`` list (score- **and** level-filtered
to drop the broadest disciplines) for works cached before OpenAlex added ``topics``. Feeds the ``keyword:openalex``
tag source in the metadata enricher (``enrichment.apply_openalex_keyword_tags``). Lives in its own leaf so the
extraction is unit-testable and ``adapter.py`` stays under the 600-line cap.
"""

from __future__ import annotations

from typing import Any

DEFAULT_MAX_TERMS = 5
DEFAULT_MIN_SCORE = 0.3
# Concepts at level 0 are the broadest disciplines ("Biology", "Psychology") — too generic to be a useful keyword
# facet, so the concepts fallback keeps only level >= 1 (topics carry no level and are curated, so they're kept).
_MIN_CONCEPT_LEVEL = 1


def keywords_from_work(
    work: Any, *, max_terms: int = DEFAULT_MAX_TERMS, min_score: float = DEFAULT_MIN_SCORE
) -> list[str]:
    """Curated keyword display-names for a work: score-filtered ``topics``, else score+level-filtered ``concepts``.
    Deduped case-insensitively (first spelling wins), capped at ``max_terms``, order preserved (OpenAlex returns
    both lists score-ranked). Returns ``[]`` for a missing / empty / malformed work — never raises."""
    if not isinstance(work, dict):
        return []
    names = _filtered_names(work.get("topics"), min_score, require_level=False)
    if not names:  # older cached works predate `topics` — fall back to the legacy concepts list
        names = _filtered_names(work.get("concepts"), min_score, require_level=True)
    return _dedupe_cap(names, max_terms)


def _filtered_names(items: Any, min_score: float, *, require_level: bool) -> list[str]:
    """Display-names from a topics/concepts list, dropping blanks, below-threshold scores, and (for concepts)
    level-0 terms. A missing/non-numeric score is kept (curated topics may omit it); order is preserved."""
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("display_name") or "").strip()
        if not name:
            continue
        score = item.get("score")
        if isinstance(score, (int, float)) and float(score) < min_score:
            continue
        if require_level:
            level = item.get("level")
            if isinstance(level, int) and level < _MIN_CONCEPT_LEVEL:
                continue
        out.append(name)
    return out


def _dedupe_cap(names: list[str], max_terms: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
        if len(out) >= max_terms:
            break
    return out
