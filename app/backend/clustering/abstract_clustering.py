"""Lightweight abstract-first paper clustering."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import Connection, RowMapping, and_, delete, insert, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import embed_papers, paper_embedding_text
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.schema import cluster_node_papers, cluster_nodes, papers

AUTO_CLUSTER_LABEL_PREFIX = "[auto] Abstract cluster"


@dataclass(frozen=True)
class AbstractCluster:
    label: str
    paper_ids: list[int]


@dataclass(frozen=True)
class AbstractClusteringResult:
    algorithm: str
    cluster_count: int
    clusters: list[AbstractCluster]
    cluster_node_ids: list[int]


class AbstractClusterer(Protocol):
    name: str

    def fit_predict(self, vectors: list[list[float]], *, cluster_count: int) -> list[int]:
        """Return one cluster label per vector."""


class AgglomerativeAbstractClusterer:
    name = "agglomerative-average-cosine"

    def fit_predict(self, vectors: list[list[float]], *, cluster_count: int) -> list[int]:
        if cluster_count <= 1:
            return [0 for _ in vectors]

        from sklearn.cluster import AgglomerativeClustering

        model = AgglomerativeClustering(
            n_clusters=cluster_count,
            metric="cosine",
            linkage="average",
        )
        return [int(label) for label in model.fit_predict(vectors)]


def run_abstract_first_clustering(
    conn: Connection,
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
    clusterer: AbstractClusterer | None = None,
    cluster_count: int | None = None,
) -> AbstractClusteringResult:
    clusterer = clusterer or AgglomerativeAbstractClusterer()
    rows_and_vectors = _paper_rows_and_vectors(conn, model=model, vector_store=vector_store)
    if not rows_and_vectors:
        _delete_previous_auto_clusters(conn)
        return AbstractClusteringResult(
            algorithm=clusterer.name,
            cluster_count=0,
            clusters=[],
            cluster_node_ids=[],
        )

    resolved_cluster_count = cluster_count or choose_cluster_count(len(rows_and_vectors))
    resolved_cluster_count = max(1, min(resolved_cluster_count, len(rows_and_vectors)))
    labels = clusterer.fit_predict(
        [vector for _, vector in rows_and_vectors],
        cluster_count=resolved_cluster_count,
    )
    clusters = _clusters_from_labels(rows_and_vectors, labels)
    cluster_node_ids = _persist_auto_clusters(
        conn,
        clusters=clusters,
        algorithm=clusterer.name,
        cluster_count=resolved_cluster_count,
    )
    return AbstractClusteringResult(
        algorithm=clusterer.name,
        cluster_count=resolved_cluster_count,
        clusters=clusters,
        cluster_node_ids=cluster_node_ids,
    )


def choose_cluster_count(paper_count: int) -> int:
    if paper_count <= 0:
        return 0
    if paper_count == 1:
        return 1
    return max(1, min(round(math.sqrt(paper_count)), paper_count, 12))


def get_auto_cluster_memberships(conn: Connection) -> dict[str, list[int]]:
    rows = conn.execute(
        select(cluster_nodes.c.label, cluster_node_papers.c.paper_id)
        .select_from(cluster_nodes.join(cluster_node_papers))
        .where(_auto_cluster_predicate())
        .order_by(cluster_nodes.c.label, cluster_node_papers.c.paper_id)
    )
    memberships: dict[str, list[int]] = {}
    for label, paper_id in rows:
        memberships.setdefault(str(label), []).append(int(paper_id))
    return memberships


def _paper_rows_and_vectors(
    conn: Connection,
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
) -> list[tuple[RowMapping, list[float]]]:
    embed_papers(conn, model=model, vector_store=vector_store)
    rows = list(conn.execute(select(papers).order_by(papers.c.id)).mappings())
    return [(row, model.encode_texts([paper_embedding_text(row)])[0]) for row in rows]


def _clusters_from_labels(
    rows_and_vectors: list[tuple[RowMapping, list[float]]],
    labels: list[int],
) -> list[AbstractCluster]:
    grouped: dict[int, list[int]] = {}
    for (row, _), label in zip(rows_and_vectors, labels, strict=False):
        grouped.setdefault(label, []).append(int(row["id"]))

    ordered_groups = sorted((sorted(paper_ids) for paper_ids in grouped.values()), key=lambda ids: ids[0])
    return [
        AbstractCluster(label=f"{AUTO_CLUSTER_LABEL_PREFIX} {index}", paper_ids=paper_ids)
        for index, paper_ids in enumerate(ordered_groups, start=1)
    ]


def _persist_auto_clusters(
    conn: Connection,
    *,
    clusters: list[AbstractCluster],
    algorithm: str,
    cluster_count: int,
) -> list[int]:
    _delete_previous_auto_clusters(conn)
    cluster_node_ids = []
    for cluster in clusters:
        result = conn.execute(
            insert(cluster_nodes).values(
                axis_id=None,
                parent_id=None,
                label=cluster.label,
                description=f"Auto-generated provisional abstract cluster; algorithm={algorithm}; cluster_count={cluster_count}",
                confidence=None,
            )
        )
        cluster_node_id = int(result.inserted_primary_key[0])
        cluster_node_ids.append(cluster_node_id)
        for paper_id in cluster.paper_ids:
            conn.execute(
                insert(cluster_node_papers).values(
                    cluster_node_id=cluster_node_id,
                    paper_id=paper_id,
                    confidence=None,
                )
            )
    return cluster_node_ids


def _delete_previous_auto_clusters(conn: Connection) -> None:
    conn.execute(delete(cluster_nodes).where(_auto_cluster_predicate()))


def _auto_cluster_predicate():
    return and_(
        cluster_nodes.c.axis_id.is_(None),
        cluster_nodes.c.parent_id.is_(None),
        cluster_nodes.c.label.like(f"{AUTO_CLUSTER_LABEL_PREFIX} %"),
    )
