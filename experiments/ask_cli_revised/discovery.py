"""Stage 2 (paper-first discovery) + Stage 3 (graph rescue: DISABLED + logged) — deterministic.

Papers are nominated by paper-vector kNN and by auto-axis neighborhood; the reason each paper entered the
set is preserved. Axes NOMINATE papers; they never manufacture scientific synonyms. Stage 3 is specified but
disabled because reference extraction covers too little of the corpus to estimate citation convergence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from sqlalchemy import Connection, func, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import PAPER_TEXT_VERSION
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.persistence.schema import cluster_node_papers, cluster_nodes, embeddings, papers, reference_instances

PAPER_KNN_TOP_K = 15
AXIS_TOP_K = 3
PER_SUBQ_PAPER_CAP = 25


@dataclass
class PaperNomination:
    paper_id: int
    reasons: list[str] = field(default_factory=list)
    direct_score: float = 0.0
    axis_score: float = 0.0
    axis_hits: int = 0

    @property
    def best_score(self) -> float:
        return self.direct_score if self.direct_score > 0 else self.axis_score


def corpus_stats(conn: Connection, *, model: EmbeddingModel) -> dict:
    live_papers = conn.execute(
        select(func.count()).select_from(papers).where(papers.c.deleted_at.is_(None))
    ).scalar_one()
    paper_embs = conn.execute(
        select(func.count()).select_from(embeddings).where(embeddings.c.target_type == "paper")
    ).scalar_one()
    ref_rows = conn.execute(select(func.count()).select_from(reference_instances)).scalar_one()
    papers_with_refs = conn.execute(
        select(func.count(func.distinct(reference_instances.c.citing_paper_id)))
    ).scalar_one()
    axis_nodes = conn.execute(select(func.count()).select_from(cluster_nodes)).scalar_one()
    return {
        "live_papers": int(live_papers),
        "paper_embeddings": int(paper_embs),
        "reference_instances": int(ref_rows),
        "papers_with_references": int(papers_with_refs),
        "axis_nodes": int(axis_nodes),
        "embedding_model": f"{model.name}:{model.version}",
    }


def graph_rescue_stage(conn: Connection) -> dict:
    """Stage 3, DISABLED. Records why + the corpus coverage that makes citation convergence unreliable."""
    total = conn.execute(select(func.count()).select_from(papers).where(papers.c.deleted_at.is_(None))).scalar_one()
    with_refs = conn.execute(select(func.count(func.distinct(reference_instances.c.citing_paper_id)))).scalar_one()
    return {
        "status": "disabled_insufficient_corpus_data",
        "reason": "citation convergence cannot be estimated reliably",
        "papers_with_references": int(with_refs),
        "total_live_papers": int(total),
        "coverage_fraction": (int(with_refs) / int(total)) if total else 0.0,
        "note": (
            "Stage 3 is specified in the scoping report; it is a drop-in once bulk reference extraction "
            "is run (a separate, approved, egress-bearing task). It was NOT silently replaced."
        ),
    }


def _current_paper_embeddings(conn: Connection, *, model: EmbeddingModel) -> dict[int, int]:
    """embedding_id -> paper_id for current paper-level embeddings of this model."""
    rows = conn.execute(
        select(embeddings.c.id, embeddings.c.target_id).where(
            embeddings.c.target_type == "paper",
            embeddings.c.model_name == model.name,
            embeddings.c.model_version == model.version,
            embeddings.c.dimension == model.dimension,
            embeddings.c.normalization == model.normalization,
            embeddings.c.source_text_version == PAPER_TEXT_VERSION,
        )
    )
    return {int(r.id): int(r.target_id) for r in rows}


def _axis_members(conn: Connection) -> list[tuple[int, str, list[int]]]:
    """[(node_id, label, [paper_ids])] for every labelled cluster node with members."""
    node_rows = conn.execute(select(cluster_nodes.c.id, cluster_nodes.c.label)).all()
    out: list[tuple[int, str, list[int]]] = []
    for node_id, label in node_rows:
        if not label:
            continue
        members = [
            int(r.paper_id)
            for r in conn.execute(
                select(cluster_node_papers.c.paper_id).where(cluster_node_papers.c.cluster_node_id == node_id)
            )
        ]
        if members:
            out.append((int(node_id), str(label), members))
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=False)) / (na * nb)


def nominate_papers(
    conn: Connection,
    *,
    subquestion_text: str,
    model: EmbeddingModel,
    vector_store: SQLiteVecVectorStore,
    axis_cache: dict,
) -> tuple[list[PaperNomination], list[dict]]:
    """Union of paper-vec kNN and axis-neighborhood nomination for one subquestion.

    Returns (nominations, log_rows). ``axis_cache`` memoizes axis label vectors within a run.
    """
    subq_vec = model.encode_texts([subquestion_text])[0]
    by_paper: dict[int, PaperNomination] = {}
    log: list[dict] = []

    # (a) paper-vector kNN
    emb_to_paper = _current_paper_embeddings(conn, model=model)
    if emb_to_paper:
        hits = vector_store.search(
            conn, vector=subq_vec, top_k=PAPER_KNN_TOP_K, candidate_embedding_ids=set(emb_to_paper)
        )
        for hit in hits:
            pid = emb_to_paper.get(hit.embedding_id)
            if pid is None:
                continue
            score = max(0.0, 1.0 - float(hit.distance))
            nom = by_paper.setdefault(pid, PaperNomination(paper_id=pid))
            nom.reasons.append("paper_kNN")
            nom.direct_score = max(nom.direct_score, score)
            log.append({"paper_id": pid, "reason": "paper_kNN", "score": score})

    # (b) axis neighborhood
    if "members" not in axis_cache:
        axis_cache["members"] = _axis_members(conn)
        axis_cache["vectors"] = {}
    members = axis_cache["members"]
    if members:
        labels = [label for _, label, _ in members]
        for label in labels:
            if label not in axis_cache["vectors"]:
                axis_cache["vectors"][label] = model.encode_texts([label])[0]
        scored = sorted(
            ((_cosine(subq_vec, axis_cache["vectors"][label]), node_id, label, mem) for node_id, label, mem in members),
            key=lambda t: -t[0],
        )
        for sim, _node_id, label, mem in scored[:AXIS_TOP_K]:
            for pid in mem:
                nom = by_paper.setdefault(pid, PaperNomination(paper_id=pid))
                reason = f"axis:{label}"
                if reason not in nom.reasons:
                    nom.reasons.append(reason)
                    nom.axis_hits += 1
                nom.axis_score = max(nom.axis_score, sim)
                log.append({"paper_id": pid, "reason": reason, "axis_similarity": sim})

    # Preserve direct semantic retrieval as the focal tier. Axis-only papers occupy the remaining budget and
    # are ordered by independent axis convergence before label similarity. The previous implementation gave
    # every axis-only paper score 0, so arbitrary cluster membership order decided which peripheral papers
    # survived the cap.
    nominations = sorted(
        by_paper.values(),
        key=lambda n: (
            n.direct_score > 0,
            n.direct_score,
            n.axis_hits,
            n.axis_score,
            -n.paper_id,
        ),
        reverse=True,
    )[:PER_SUBQ_PAPER_CAP]
    return nominations, log
