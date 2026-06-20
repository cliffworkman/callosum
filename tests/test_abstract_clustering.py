from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import insert, select

from alembic import command
from alembic.config import Config
from app.backend.clustering.abstract_clustering import (
    get_auto_cluster_memberships,
    run_abstract_first_clustering,
)
from app.backend.embeddings.models import DEFAULT_NORMALIZATION, normalize_text
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import cluster_nodes


@dataclass(frozen=True)
class ClusterFakeEmbeddingModel:
    name: str = "fake-cluster-model"
    version: str = "v1"
    dimension: int = 2
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [_cluster_vector(normalize_text(text, self.normalization)) for text in texts]


def test_abstract_first_clustering_groups_similar_papers_and_separates_dissimilar(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = ClusterFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        paper_ids = _create_cluster_fixture_papers(conn)
        result = run_abstract_first_clustering(
            conn,
            model=model,
            vector_store=vector_store,
            cluster_count=2,
        )
        memberships = get_auto_cluster_memberships(conn)

    grouped_sets = {frozenset(cluster.paper_ids) for cluster in result.clusters}
    assert result.algorithm == "agglomerative-average-cosine"
    assert result.cluster_count == 2
    assert grouped_sets == {
        frozenset({paper_ids["neural_a"], paper_ids["neural_b"]}),
        frozenset({paper_ids["orchard_a"], paper_ids["orchard_b"]}),
    }
    assert {frozenset(ids) for ids in memberships.values()} == grouped_sets


def test_abstract_cluster_rerun_replaces_only_prior_auto_clusters(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = ClusterFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        _create_cluster_fixture_papers(conn)
        user_node_id = conn.execute(
            insert(cluster_nodes).values(label="User axis node", description="manual", confidence=None)
        ).inserted_primary_key[0]
        first = run_abstract_first_clustering(
            conn,
            model=model,
            vector_store=vector_store,
            cluster_count=2,
        )
        second = run_abstract_first_clustering(
            conn,
            model=model,
            vector_store=vector_store,
            cluster_count=2,
        )
        user_node_exists = conn.execute(
            select(cluster_nodes.c.id).where(cluster_nodes.c.id == int(user_node_id))
        ).scalar_one_or_none()
        auto_node_count = conn.execute(
            select(cluster_nodes.c.id).where(cluster_nodes.c.label.like("[auto] Abstract cluster %"))
        ).all()

    assert user_node_exists == int(user_node_id)
    assert [cluster.paper_ids for cluster in second.clusters] == [cluster.paper_ids for cluster in first.clusters]
    assert len(auto_node_count) == 2


def _migrated_engine(tmp_path: Path):
    db_path = tmp_path / "callosum-abstract-clustering.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return make_engine(url)


def _create_cluster_fixture_papers(conn) -> dict[str, int]:
    return {
        "neural_a": create_paper(
            conn,
            title="Neural Cortex A",
            abstract="Brain cortex neural representation.",
            csl_json={"id": "neural-a", "type": "article-journal", "title": "Neural Cortex A"},
            processing_tier="abstract-embedded",
        ),
        "neural_b": create_paper(
            conn,
            title="Neural Cortex B",
            abstract="Cortex brain neural signal.",
            csl_json={"id": "neural-b", "type": "article-journal", "title": "Neural Cortex B"},
            processing_tier="abstract-embedded",
        ),
        "orchard_a": create_paper(
            conn,
            title="Fruit Orchard A",
            abstract="Fruit orchard banana ripening.",
            csl_json={"id": "orchard-a", "type": "article-journal", "title": "Fruit Orchard A"},
            processing_tier="abstract-embedded",
        ),
        "orchard_b": create_paper(
            conn,
            title="Fruit Orchard B",
            abstract="Banana fruit orchard management.",
            csl_json={"id": "orchard-b", "type": "article-journal", "title": "Fruit Orchard B"},
            processing_tier="abstract-embedded",
        ),
    }


def _cluster_vector(text: str) -> list[float]:
    if "neural cortex a" in text:
        return [1.0, 0.0]
    if "neural cortex b" in text:
        return [0.95, 0.05]
    if "fruit orchard a" in text:
        return [0.0, 1.0]
    if "fruit orchard b" in text:
        return [0.05, 0.95]
    return [0.1, 0.1]
