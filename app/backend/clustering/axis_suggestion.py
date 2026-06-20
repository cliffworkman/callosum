"""Suggest optimal axes — unsupervised discovery over the library with coverage-with-diversity.

Clusters the library's paper embeddings, drops clusters already covered by the user's existing axes
(novelty), greedily picks a diverse subset (MMR-lite), and labels each from its OWN papers (local
c-TF-IDF). `apply_labels` can polish the labels with an egress-gated Gemini labeler; it degrades to
the local labels whenever Gemini is unavailable (egress off, or any failure), so suggestion always
works offline. Nothing is persisted — suggestions are ephemeral; the user creates the ones they like.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace

import numpy as np
from sqlalchemy import Connection, select

from app.backend.clustering.abstract_clustering import AgglomerativeAbstractClusterer
from app.backend.embeddings.models import EmbeddingModel, normalize_text, strip_punctuation
from app.backend.embeddings.pipeline import paper_embedding_text
from app.backend.metadata.abstract_display import abstract_plain_text
from app.backend.persistence.schema import axes, papers

MIN_PAPERS = 6  # below this, clustering isn't meaningful → suggest nothing
TARGET_CLUSTER_SIZE = 5  # aim for ~this many papers per cluster
MAX_CLUSTERS = 12
NOVELTY_SIM = 0.6  # a cluster centroid this close to an existing axis is "already covered" → skip
DIVERSITY_SIM = 0.5  # skip a cluster centroid this close to one already selected (MMR-lite)
DEFAULT_MAX_SUGGESTIONS = 6
LABEL_TERMS = 6
REP_PAPERS = 5

# A small stopword set so local labels surface distinctive content words, not scaffolding.
_STOPWORDS = frozenset(
    """a an the of and or to in for on with without via using from into over under between within across
    is are was were be been being has have had do does did this that these those it its their our your his
    her them they we you not no als study studies paper papers article articles analysis approach approaches
    method methods model models result results effect effects role based toward towards new novel review
    reviews use used using data evidence findings finding via per among about against during through""".split()
)


@dataclass(frozen=True)
class SuggestedAxis:
    label: str
    terms: list[str]
    paper_ids: list[int]
    paper_titles: list[str]
    size: int


def suggest_axes(
    conn: Connection, *, model: EmbeddingModel, max_suggestions: int = DEFAULT_MAX_SUGGESTIONS
) -> list[SuggestedAxis]:
    rows = list(conn.execute(select(papers).where(papers.c.deleted_at.is_(None)).order_by(papers.c.id)).mappings())
    if len(rows) < MIN_PAPERS:
        return []
    vectors = _l2_normalize(np.array(model.encode_texts([paper_embedding_text(row) for row in rows]), dtype=float))
    n = len(rows)
    k = max(2, min(round(n / TARGET_CLUSTER_SIZE), MAX_CLUSTERS, n))
    labels = AgglomerativeAbstractClusterer().fit_predict(vectors.tolist(), cluster_count=k)

    candidates = []
    grouped: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        grouped.setdefault(int(label), []).append(index)
    for members in grouped.values():
        if len(members) < 2:  # a singleton isn't a useful axis
            continue
        block = vectors[members]
        centroid = _l2_normalize(block.mean(axis=0, keepdims=True))[0]
        order = list(np.argsort(-(block @ centroid)))  # papers nearest the centroid = representatives
        candidates.append(
            {
                "members": members,
                "centroid": centroid,
                "rep": [members[i] for i in order[:REP_PAPERS]],
                "size": len(members),
            }
        )
    if not candidates:
        return []

    # Novelty — drop clusters a current axis already covers (coverage-with-diversity, vs existing axes).
    existing = _existing_axis_vectors(conn, model)
    if existing is not None and len(existing):
        candidates = [c for c in candidates if float(np.max(existing @ c["centroid"])) < NOVELTY_SIM]

    # Diversity — greedily take the biggest clusters, skipping near-duplicates of those already chosen.
    candidates.sort(key=lambda c: -c["size"])
    selected: list[dict] = []
    for candidate in candidates:
        if any(float(candidate["centroid"] @ s["centroid"]) >= DIVERSITY_SIM for s in selected):
            continue
        selected.append(candidate)
        if len(selected) >= max_suggestions:
            break
    if not selected:
        return []

    # Local labels — c-TF-IDF over each selected cluster's papers (distinctive content words).
    token_lists = [[_paper_tokens(rows[i]) for i in c["members"]] for c in selected]
    term_lists = _top_terms_per_cluster(token_lists)
    return [
        SuggestedAxis(
            label=_label_from_terms(terms),
            terms=terms,
            paper_ids=[int(rows[i]["id"]) for i in c["members"]],
            paper_titles=[str(rows[i]["title"]) for i in c["rep"]],
            size=c["size"],
        )
        for c, terms in zip(selected, term_lists, strict=False)
    ]


def apply_labels(suggestions: list[SuggestedAxis], *, labeler) -> list[SuggestedAxis]:
    """Optionally polish labels/terms with an injected Gemini labeler. Per cluster: on ANY failure —
    including egress-off (`DataEgressDisabledError`, raised before any genai call) — keep the local
    label. Never raises, so suggestion always returns (offline → all local)."""
    if not suggestions or labeler is None:
        return suggestions
    out: list[SuggestedAxis] = []
    for suggestion in suggestions:
        try:
            result = labeler.label(titles=suggestion.paper_titles, terms=suggestion.terms)
            label = str((result or {}).get("label") or "").strip()
            terms = (result or {}).get("terms")
            cleaned = [str(t).strip() for t in terms if str(t).strip()] if isinstance(terms, list) else None
            out.append(replace(suggestion, label=label or suggestion.label, terms=cleaned or suggestion.terms))
        except Exception:
            out.append(suggestion)
    return out


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _existing_axis_vectors(conn: Connection, model: EmbeddingModel) -> np.ndarray | None:
    texts = []
    for axis in conn.execute(select(axes)).mappings():
        text = (axis["description"] or "").strip() or str(axis["label"] or "")
        if text:
            texts.append(text)
    if not texts:
        return None
    return _l2_normalize(np.array(model.encode_texts(texts), dtype=float))


def _paper_tokens(row) -> list[str]:
    # Strip JATS/HTML from the abstract first, so tag names ("jats", "italic", …) never become terms.
    abstract = abstract_plain_text(row["abstract"]) or ""
    text = normalize_text(strip_punctuation(f"{row['title'] or ''} {abstract}"))
    return [t for t in text.split() if len(t) >= 3 and t not in _STOPWORDS and not t.isdigit()]


def _top_terms_per_cluster(token_lists: list[list[list[str]]], *, top: int = LABEL_TERMS) -> list[list[str]]:
    counters = [Counter(token for paper in cluster for token in paper) for cluster in token_lists]
    cluster_count = len(counters)
    doc_freq: Counter = Counter()
    for counter in counters:
        doc_freq.update(counter.keys())
    results = []
    for counter in counters:
        scored = sorted(
            counter.items(),
            key=lambda kv: (-(kv[1] * (math.log((cluster_count + 1) / (doc_freq[kv[0]] + 1)) + 1.0)), kv[0]),
        )
        results.append([term for term, _ in scored[:top]])
    return results


def _label_from_terms(terms: list[str]) -> str:
    return " ".join(terms[:2]).title() if terms else "Untitled cluster"
