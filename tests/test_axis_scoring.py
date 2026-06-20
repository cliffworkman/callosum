from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from alembic import command
from alembic.config import Config
from app.backend.clustering.axis_scoring import (
    AxisScoringConfig,
    create_axis,
    score_axis,
    update_axis,
)
from app.backend.embeddings.models import DEFAULT_NORMALIZATION, normalize_text
from app.backend.embeddings.vector_store import InMemoryVectorStore, SQLiteVecVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import cluster_node_papers, embeddings


@dataclass(frozen=True)
class AxisFakeEmbeddingModel:
    name: str = "fake-axis-model"
    version: str = "v1"
    dimension: int = 3
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [_fake_vector(normalize_text(text, self.normalization)) for text in texts]


class RecordingVectorStore(InMemoryVectorStore):
    def __init__(self) -> None:
        super().__init__()
        self.candidate_calls: list[set[int]] = []

    def search(
        self,
        conn,
        *,
        vector: list[float],
        top_k: int,
        candidate_embedding_ids: set[int] | None = None,
    ):
        if candidate_embedding_ids is not None:
            self.candidate_calls.append(set(candidate_embedding_ids))
        return super().search(
            conn,
            vector=vector,
            top_k=top_k,
            candidate_embedding_ids=candidate_embedding_ids,
        )


def test_sqlite_vec_and_in_memory_rank_unnormalized_vectors_identically() -> None:
    engine = make_engine("sqlite:///:memory:")
    sqlite_store = SQLiteVecVectorStore()
    memory_store = InMemoryVectorStore()
    vectors = {
        1: [100.0, 0.2],
        2: [2.0, 1.0],
        3: [0.0, 10.0],
        4: [-5.0, 0.0],
    }

    with engine.begin() as conn:
        for embedding_id, vector in vectors.items():
            sqlite_store.add(conn, embedding_id=embedding_id, vector=vector)
            memory_store.add(conn, embedding_id=embedding_id, vector=vector)
        sqlite_hits = sqlite_store.search(conn, vector=[1.0, 0.0], top_k=4)
        memory_hits = memory_store.search(conn, vector=[1.0, 0.0], top_k=4)

    assert [hit.embedding_id for hit in sqlite_hits] == [hit.embedding_id for hit in memory_hits]
    assert [hit.embedding_id for hit in sqlite_hits] == [1, 2, 3, 4]


def test_axis_scoring_records_clear_and_borderline_assignments(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = AxisFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    config = AxisScoringConfig(
        assignment_mode="absolute",
        assignment_threshold=0.8,
        uncertainty_threshold=0.65,
    )

    with engine.begin() as conn:
        paper_ids = _create_axis_fixture_papers(conn)
        axis_id = create_axis(conn, label="Facial Anomalies")
        result = score_axis(conn, axis_id=axis_id, model=model, vector_store=vector_store, config=config)
        assignments = _assignments(conn, result.cluster_node_id)

    by_paper = {score.paper_id: score for score in result.scores}
    assert by_paper[paper_ids["clear_facial"]].confidence > by_paper[paper_ids["borderline"]].confidence
    assert by_paper[paper_ids["clear_facial"]].status == "assigned"
    assert by_paper[paper_ids["borderline"]].status == "uncertain"
    assert by_paper[paper_ids["unrelated"]].status == "below-threshold"
    assert assignments[paper_ids["clear_facial"]] > assignments[paper_ids["borderline"]]
    assert paper_ids["borderline"] in assignments
    assert paper_ids["unrelated"] not in assignments


def test_nested_axis_scores_only_parent_assigned_subset(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = AxisFakeEmbeddingModel()
    vector_store = RecordingVectorStore()
    config = AxisScoringConfig(
        assignment_mode="absolute",
        assignment_threshold=0.8,
        uncertainty_threshold=0.65,
    )

    with engine.begin() as conn:
        paper_ids = _create_axis_fixture_papers(conn)
        parent_axis_id = create_axis(conn, label="Facial Anomalies")
        parent = score_axis(
            conn,
            axis_id=parent_axis_id,
            model=model,
            vector_store=vector_store,
            config=config,
        )
        child_axis_id = create_axis(conn, label="Signal Detection Theory")
        child = score_axis(
            conn,
            axis_id=child_axis_id,
            model=model,
            vector_store=vector_store,
            config=config,
            parent_cluster_node_id=parent.cluster_node_id,
        )
        parent_embedding_ids = _paper_embedding_ids(
            conn,
            model=model,
            paper_ids=set(_assignments(conn, parent.cluster_node_id)),
        )
        child_assignments = _assignments(conn, child.cluster_node_id)

    assert child.parent_cluster_node_id == parent.cluster_node_id
    assert vector_store.candidate_calls[-1] == parent_embedding_ids
    assert paper_ids["borderline"] in child_assignments
    assert paper_ids["pure_signal"] not in {score.paper_id for score in child.scores}
    assert paper_ids["pure_signal"] not in child_assignments


def test_rescoring_one_axis_leaves_other_axis_assignments_intact(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = AxisFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    config = AxisScoringConfig(
        assignment_mode="absolute",
        assignment_threshold=0.8,
        uncertainty_threshold=0.65,
    )

    with engine.begin() as conn:
        _create_axis_fixture_papers(conn)
        facial_axis_id = create_axis(conn, label="Facial Anomalies")
        signal_axis_id = create_axis(conn, label="Signal Detection Theory")
        facial = score_axis(
            conn,
            axis_id=facial_axis_id,
            model=model,
            vector_store=vector_store,
            config=config,
        )
        signal = score_axis(
            conn,
            axis_id=signal_axis_id,
            model=model,
            vector_store=vector_store,
            config=config,
        )
        signal_before = _assignments(conn, signal.cluster_node_id)

        update_axis(conn, facial_axis_id, description="edited user wording")
        rescored_facial = score_axis(
            conn,
            axis_id=facial_axis_id,
            model=model,
            vector_store=vector_store,
            config=config,
        )
        signal_after = _assignments(conn, signal.cluster_node_id)

    assert rescored_facial.cluster_node_id == facial.cluster_node_id
    assert signal_after == signal_before


def test_top_n_assignment_caps_recorded_papers_even_above_threshold(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = AxisFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    config = AxisScoringConfig(
        assignment_mode="top_n",
        top_n=2,
        assignment_threshold=0.7,
        uncertainty_threshold=0.5,
    )

    with engine.begin() as conn:
        paper_ids = _create_calibration_fixture_papers(conn)
        axis_id = create_axis(conn, label="Calibration Axis")
        result = score_axis(conn, axis_id=axis_id, model=model, vector_store=vector_store, config=config)
        assignments = _assignments(conn, result.cluster_node_id)

    assert set(assignments) == {paper_ids["strong_a"], paper_ids["strong_b"]}
    assert paper_ids["strong_c"] not in assignments
    assert result.scores[2].confidence > config.assignment_threshold


def test_largest_gap_assignment_excludes_weak_tail_at_realistic_mid_score(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = AxisFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    config = AxisScoringConfig(
        assignment_mode="largest_gap",
        assignment_threshold=0.7,
        uncertainty_threshold=0.5,
        minimum_gap=0.15,
    )

    with engine.begin() as conn:
        paper_ids = _create_calibration_fixture_papers(conn)
        axis_id = create_axis(conn, label="Calibration Axis")
        result = score_axis(conn, axis_id=axis_id, model=model, vector_store=vector_store, config=config)
        assignments = _assignments(conn, result.cluster_node_id)

    by_paper = {score.paper_id: score for score in result.scores}
    assert round(by_paper[paper_ids["weak_tail"]].confidence, 2) == 0.63
    assert paper_ids["weak_tail"] not in assignments
    assert set(assignments) == {paper_ids["strong_a"], paper_ids["strong_b"], paper_ids["strong_c"]}


def test_largest_gap_assignment_records_nothing_for_flat_noisy_tail(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = AxisFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    config = AxisScoringConfig(
        assignment_mode="largest_gap",
        assignment_threshold=0.7,
        uncertainty_threshold=0.5,
        minimum_gap=0.15,
    )

    with engine.begin() as conn:
        weak_tail_id = create_paper(
            conn,
            title="Calibration Weak Tail",
            abstract="Weakly related tail paper.",
            csl_json={"id": "cal-only-tail", "type": "article-journal", "title": "Calibration Weak Tail"},
            processing_tier="abstract-embedded",
        )
        axis_id = create_axis(conn, label="Calibration Axis")
        result = score_axis(conn, axis_id=axis_id, model=model, vector_store=vector_store, config=config)
        assignments = _assignments(conn, result.cluster_node_id)

    by_paper = {score.paper_id: score for score in result.scores}
    assert round(by_paper[weak_tail_id].confidence, 2) == 0.63
    assert assignments == {}


def _migrated_engine(tmp_path: Path):
    db_path = tmp_path / "callosum-axis-scoring.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return make_engine(url)


def _create_axis_fixture_papers(conn) -> dict[str, int]:
    return {
        "clear_facial": create_paper(
            conn,
            title="Clear Facial Morphology",
            abstract="Facial anomaly morphology paper.",
            csl_json={"id": "clear-facial", "type": "article-journal", "title": "Clear Facial Morphology"},
            processing_tier="abstract-embedded",
        ),
        "borderline": create_paper(
            conn,
            title="Borderline Face Signal",
            abstract="A paper mixing facial anomaly features with signal detection ideas.",
            csl_json={"id": "borderline", "type": "article-journal", "title": "Borderline Face Signal"},
            processing_tier="abstract-embedded",
        ),
        "pure_signal": create_paper(
            conn,
            title="Pure Signal Detection",
            abstract="Signal detection theory without facial anomalies.",
            csl_json={"id": "pure-signal", "type": "article-journal", "title": "Pure Signal Detection"},
            processing_tier="abstract-embedded",
        ),
        "unrelated": create_paper(
            conn,
            title="Unrelated Orchard",
            abstract="Fruit orchard control article.",
            csl_json={"id": "unrelated", "type": "article-journal", "title": "Unrelated Orchard"},
            processing_tier="abstract-embedded",
        ),
    }


def _create_calibration_fixture_papers(conn) -> dict[str, int]:
    return {
        "strong_a": create_paper(
            conn,
            title="Calibration Strong A",
            abstract="High relevance calibration paper.",
            csl_json={"id": "cal-strong-a", "type": "article-journal", "title": "Calibration Strong A"},
            processing_tier="abstract-embedded",
        ),
        "strong_b": create_paper(
            conn,
            title="Calibration Strong B",
            abstract="High relevance calibration paper.",
            csl_json={"id": "cal-strong-b", "type": "article-journal", "title": "Calibration Strong B"},
            processing_tier="abstract-embedded",
        ),
        "strong_c": create_paper(
            conn,
            title="Calibration Strong C",
            abstract="High relevance calibration paper.",
            csl_json={"id": "cal-strong-c", "type": "article-journal", "title": "Calibration Strong C"},
            processing_tier="abstract-embedded",
        ),
        "weak_tail": create_paper(
            conn,
            title="Calibration Weak Tail",
            abstract="Weakly related tail paper.",
            csl_json={"id": "cal-weak-tail", "type": "article-journal", "title": "Calibration Weak Tail"},
            processing_tier="abstract-embedded",
        ),
    }


def _assignments(conn, cluster_node_id: int) -> dict[int, float]:
    rows = conn.execute(
        select(cluster_node_papers.c.paper_id, cluster_node_papers.c.confidence).where(
            cluster_node_papers.c.cluster_node_id == cluster_node_id
        )
    )
    return {int(row.paper_id): float(row.confidence) for row in rows}


def _paper_embedding_ids(conn, *, model: AxisFakeEmbeddingModel, paper_ids: set[int]) -> set[int]:
    rows = conn.execute(
        select(embeddings.c.id).where(
            embeddings.c.target_type == "paper",
            embeddings.c.target_id.in_(paper_ids),
            embeddings.c.model_name == model.name,
            embeddings.c.model_version == model.version,
            embeddings.c.dimension == model.dimension,
            embeddings.c.normalization == model.normalization,
        )
    )
    return {int(row[0]) for row in rows}


def _fake_vector(text: str) -> list[float]:
    if "calibration strong a" in text:
        return [1.0, 0.0, 0.0]
    if "calibration strong b" in text:
        return [0.95, 0.3122498999, 0.0]
    if "calibration strong c" in text:
        return [0.9, 0.4358898944, 0.0]
    if "calibration weak tail" in text:
        return [0.63, 0.7765951326, 0.0]
    if "calibration axis" in text:
        return [1.0, 0.0, 0.0]
    if "clear facial morphology" in text:
        return [10.0, 1.0, 0.0]
    if "borderline face signal" in text:
        return [5.0, 5.0, 0.0]
    if "pure signal detection" in text:
        return [0.0, 10.0, 0.0]
    if "unrelated orchard" in text:
        return [0.0, 0.0, 10.0]
    if "facial anomalies" in text:
        return [10.0, 0.0, 0.0]
    if "signal detection theory" in text:
        return [0.0, 10.0, 0.0]
    return [0.0, 0.0, 1.0]
