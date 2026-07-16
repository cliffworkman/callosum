"""User-defined axis scoring over local paper embeddings."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy import Connection, Engine, RowMapping, and_, delete, insert, select, update

from app.backend.embeddings.models import EmbeddingModel, normalize_text, strip_punctuation
from app.backend.embeddings.pipeline import PAPER_TEXT_VERSION, embed_papers
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.repository import list_live_paper_ids
from app.backend.persistence.schema import axes, cluster_node_papers, cluster_nodes, embeddings
from app.backend.persistence.sqlite_retry import commit_each

_log = logging.getLogger("callosum.axis_scoring")

AXIS_TEXT_VERSION_PREFIX = "axis-text-sha256-v1:"
AssignmentStatus = Literal["assigned", "uncertain", "below-threshold"]
AssignmentMode = Literal["absolute", "top_n", "largest_gap", "natural_break"]


@dataclass(frozen=True)
class AxisScoringConfig:
    assignment_threshold: float = 0.7
    uncertainty_threshold: float = 0.5
    assignment_mode: AssignmentMode = "largest_gap"
    top_n: int | None = None
    minimum_gap: float = 0.15

    def __post_init__(self) -> None:
        if not 0 <= self.uncertainty_threshold <= self.assignment_threshold <= 1:
            raise ValueError("Expected 0 <= uncertainty_threshold <= assignment_threshold <= 1")
        if self.assignment_mode not in {"absolute", "top_n", "largest_gap", "natural_break"}:
            raise ValueError("Unknown assignment mode")
        if self.top_n is not None and self.top_n < 1:
            raise ValueError("top_n must be positive when set")
        if self.minimum_gap < 0:
            raise ValueError("minimum_gap must be nonnegative")


@dataclass(frozen=True)
class PaperAxisScore:
    paper_id: int
    embedding_id: int
    confidence: float
    status: AssignmentStatus


@dataclass(frozen=True)
class AxisScoringResult:
    axis_id: int
    cluster_node_id: int
    parent_cluster_node_id: int | None
    scores: list[PaperAxisScore]

    @property
    def recorded_assignments(self) -> list[PaperAxisScore]:
        return [score for score in self.scores if score.status != "below-threshold"]


class PaperRepresentationStrategy(Protocol):
    def ensure_embeddings(
        self,
        conn: Connection,
        *,
        model: EmbeddingModel,
        vector_store: VectorStore,
        paper_ids: set[int] | None,
    ) -> None:
        """Ensure candidate paper representations exist in metadata and vector store."""

    def candidate_embeddings(
        self,
        conn: Connection,
        *,
        model: EmbeddingModel,
        paper_ids: set[int] | None,
    ) -> dict[int, int]:
        """Return embedding_id -> paper_id for candidate paper representations."""


class PaperEmbeddingRepresentation:
    """Represent each paper by its paper-level title/abstract metadata embedding."""

    def ensure_embeddings(
        self,
        conn: Connection,
        *,
        model: EmbeddingModel,
        vector_store: VectorStore,
        paper_ids: set[int] | None,
    ) -> None:
        embed_papers(
            conn,
            model=model,
            vector_store=vector_store,
            paper_ids=sorted(paper_ids) if paper_ids is not None else None,
        )

    def candidate_embeddings(
        self,
        conn: Connection,
        *,
        model: EmbeddingModel,
        paper_ids: set[int] | None,
    ) -> dict[int, int]:
        stmt = (
            select(embeddings.c.id, embeddings.c.target_id)
            .where(
                and_(
                    embeddings.c.target_type == "paper",
                    embeddings.c.model_name == model.name,
                    embeddings.c.model_version == model.version,
                    embeddings.c.dimension == model.dimension,
                    embeddings.c.normalization == model.normalization,
                    embeddings.c.source_text_version == PAPER_TEXT_VERSION,
                    embeddings.c.source_chunk_version.is_(None),
                )
            )
            .order_by(embeddings.c.id)
        )
        if paper_ids is not None:
            if not paper_ids:
                return {}
            stmt = stmt.where(embeddings.c.target_id.in_(paper_ids))
        return {int(row.id): int(row.target_id) for row in conn.execute(stmt)}


def create_axis(conn: Connection, *, label: str, description: str | None = None, kind: str = "standard") -> int:
    result = conn.execute(insert(axes).values(label=label, description=description, kind=kind))
    return int(result.inserted_primary_key[0])


def update_axis(
    conn: Connection,
    axis_id: int,
    *,
    label: str | None = None,
    description: str | None = None,
) -> None:
    values = {}
    if label is not None:
        values["label"] = label
    if description is not None:
        values["description"] = description
    if values:
        conn.execute(update(axes).where(axes.c.id == axis_id).values(**values))


def ensure_candidate_embeddings_committing(
    engine: Engine,
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
    parent_cluster_node_id: int | None = None,
    representation: PaperRepresentationStrategy | None = None,
) -> None:
    """Pre-embed an axis-scoring run's candidate papers, ONE committed transaction per paper (inc A3), so the slow
    embedding phase releases the SQLite write lock between papers instead of holding it for the whole run. The
    subsequent ``score_axis`` call's own ``ensure_embeddings`` then finds them present (``embed_papers`` is
    idempotent) and is a fast no-op. Only papers lacking a current embedding are embedded (no wasted transactions);
    one paper's embed failure is skipped + logged, never aborting the pre-embed (that paper is simply unscored)."""
    representation = representation or PaperEmbeddingRepresentation()
    with engine.connect() as conn:
        candidate = _candidate_paper_ids(conn, parent_cluster_node_id)
        all_ids = candidate if candidate is not None else set(list_live_paper_ids(conn))
        embedded = set(representation.candidate_embeddings(conn, model=model, paper_ids=candidate).values())
    pending = sorted(all_ids - embedded)
    commit_each(
        engine,
        pending,
        lambda conn, pid: embed_papers(conn, model=model, vector_store=vector_store, paper_ids=[pid]),
        on_item_error="skip",
        logger=_log,
    )


def score_axis(
    conn: Connection,
    *,
    axis_id: int,
    model: EmbeddingModel,
    vector_store: VectorStore,
    config: AxisScoringConfig | None = None,
    parent_cluster_node_id: int | None = None,
    representation: PaperRepresentationStrategy | None = None,
) -> AxisScoringResult:
    config = config or AxisScoringConfig()
    representation = representation or PaperEmbeddingRepresentation()

    axis = conn.execute(select(axes).where(axes.c.id == axis_id)).mappings().one()
    axis_vector = _embed_axis(conn, axis=axis, model=model, vector_store=vector_store)
    cluster_node_id = _ensure_cluster_node(conn, axis=axis, parent_cluster_node_id=parent_cluster_node_id)

    candidate_paper_ids = _candidate_paper_ids(conn, parent_cluster_node_id)
    representation.ensure_embeddings(
        conn,
        model=model,
        vector_store=vector_store,
        paper_ids=candidate_paper_ids,
    )
    embedding_to_paper = representation.candidate_embeddings(
        conn,
        model=model,
        paper_ids=candidate_paper_ids,
    )
    scores = _score_candidate_embeddings(
        conn,
        vector_store=vector_store,
        axis_vector=axis_vector,
        embedding_to_paper=embedding_to_paper,
        config=config,
    )
    _replace_axis_assignments(conn, cluster_node_id=cluster_node_id, scores=scores)
    return AxisScoringResult(
        axis_id=axis_id,
        cluster_node_id=cluster_node_id,
        parent_cluster_node_id=parent_cluster_node_id,
        scores=scores,
    )


def _embed_axis(
    conn: Connection,
    *,
    axis: RowMapping,
    model: EmbeddingModel,
    vector_store: VectorStore,
) -> list[float]:
    # Punctuation-normalize so phrasings differing only in punctuation/spacing embed identically
    # ("anomalous-is-bad" == "anomalous is bad"); same cleaned form drives the vector AND the version.
    text = strip_punctuation(_axis_text(axis))
    vector = model.encode_texts([text])[0]
    source_text_version = _axis_source_text_version(text, model=model)
    existing = (
        conn.execute(
            select(embeddings.c.id).where(
                and_(
                    embeddings.c.target_type == "axis",
                    embeddings.c.target_id == int(axis["id"]),
                    embeddings.c.model_name == model.name,
                    embeddings.c.model_version == model.version,
                    embeddings.c.dimension == len(vector),
                    embeddings.c.normalization == model.normalization,
                    embeddings.c.source_text_version == source_text_version,
                    embeddings.c.source_chunk_version.is_(None),
                )
            )
        )
        .mappings()
        .first()
    )
    if existing is None:
        result = conn.execute(
            insert(embeddings).values(
                target_type="axis",
                target_id=int(axis["id"]),
                model_name=model.name,
                model_version=model.version,
                dimension=len(vector),
                normalization=model.normalization,
                source_text_version=source_text_version,
                source_chunk_version=None,
                vector_store_kind=vector_store.kind,
                vector_store_ref="pending",
            )
        )
        embedding_id = int(result.inserted_primary_key[0])
        vector_ref = vector_store.add(conn, embedding_id=embedding_id, vector=vector)
        conn.execute(
            update(embeddings)
            .where(embeddings.c.id == embedding_id)
            .values(vector_store_kind=vector_store.kind, vector_store_ref=vector_ref)
        )
    return vector


def _ensure_cluster_node(conn: Connection, *, axis: RowMapping, parent_cluster_node_id: int | None) -> int:
    predicate = and_(
        cluster_nodes.c.axis_id == int(axis["id"]),
        cluster_nodes.c.parent_id.is_(None)
        if parent_cluster_node_id is None
        else cluster_nodes.c.parent_id == parent_cluster_node_id,
    )
    existing = conn.execute(select(cluster_nodes.c.id).where(predicate).limit(1)).scalar_one_or_none()
    values = {
        "label": axis["label"],
        "description": axis["description"],
        "confidence": None,
    }
    if existing is not None:
        conn.execute(update(cluster_nodes).where(cluster_nodes.c.id == int(existing)).values(**values))
        return int(existing)

    result = conn.execute(
        insert(cluster_nodes).values(
            axis_id=int(axis["id"]),
            parent_id=parent_cluster_node_id,
            **values,
        )
    )
    return int(result.inserted_primary_key[0])


def _candidate_paper_ids(conn: Connection, parent_cluster_node_id: int | None) -> set[int] | None:
    if parent_cluster_node_id is None:
        return None
    rows = conn.execute(
        select(cluster_node_papers.c.paper_id).where(cluster_node_papers.c.cluster_node_id == parent_cluster_node_id)
    )
    return {int(row[0]) for row in rows}


def _score_candidate_embeddings(
    conn: Connection,
    *,
    vector_store: VectorStore,
    axis_vector: list[float],
    embedding_to_paper: dict[int, int],
    config: AxisScoringConfig,
) -> list[PaperAxisScore]:
    raw_scores: list[tuple[int, int, float]] = []
    for candidate_ids in _candidate_batches(set(embedding_to_paper), vector_store=vector_store):
        hits = vector_store.search(
            conn,
            vector=axis_vector,
            top_k=len(candidate_ids),
            candidate_embedding_ids=candidate_ids,
        )
        for hit in hits:
            confidence = _confidence_from_cosine_distance(hit.distance)
            raw_scores.append((embedding_to_paper[hit.embedding_id], hit.embedding_id, confidence))
    raw_scores.sort(key=lambda score: (-score[2], score[0]))
    if config.assignment_mode == "natural_break":
        statuses = _natural_break_statuses(raw_scores, config=config)
    else:
        selected = _selected_paper_ids(raw_scores, config=config)
        statuses = {
            paper_id: _assignment_status(paper_id, confidence, selected_paper_ids=selected, config=config)
            for paper_id, _embedding_id, confidence in raw_scores
        }
        # never-empty is a supervised-axis (absolute) affordance; other modes record nothing when nothing qualifies
        if config.assignment_mode == "absolute" and not any(
            status != "below-threshold" for status in statuses.values()
        ):
            statuses = _never_empty_uncertain(raw_scores)  # nothing cleared the floor — show the closest few
    return [
        PaperAxisScore(paper_id=pid, embedding_id=eid, confidence=conf, status=statuses.get(pid, "below-threshold"))
        for pid, eid, conf in raw_scores
    ]


def _replace_axis_assignments(conn: Connection, *, cluster_node_id: int, scores: list[PaperAxisScore]) -> None:
    conn.execute(delete(cluster_node_papers).where(cluster_node_papers.c.cluster_node_id == cluster_node_id))
    for score in _scores_to_record(scores):
        if score.status == "below-threshold":
            continue
        conn.execute(
            insert(cluster_node_papers).values(
                cluster_node_id=cluster_node_id,
                paper_id=score.paper_id,
                confidence=score.confidence,
            )
        )


def _scores_to_record(scores: list[PaperAxisScore]) -> list[PaperAxisScore]:
    return [score for score in scores if score.status != "below-threshold"]


def _candidate_batches(candidate_ids: set[int], *, vector_store: VectorStore) -> list[set[int]]:
    if not candidate_ids:
        return []
    batch_size = int(getattr(vector_store, "max_knn_k", len(candidate_ids)))
    batch_size = max(1, batch_size)
    sorted_ids = sorted(candidate_ids)
    return [set(sorted_ids[index : index + batch_size]) for index in range(0, len(sorted_ids), batch_size)]


def _selected_paper_ids(
    raw_scores: list[tuple[int, int, float]],
    *,
    config: AxisScoringConfig,
) -> set[int]:
    eligible = [score for score in raw_scores if score[2] >= config.uncertainty_threshold]
    if config.assignment_mode == "absolute":
        return {paper_id for paper_id, _, _ in eligible}
    if config.assignment_mode == "top_n":
        limit = config.top_n if config.top_n is not None else len(eligible)
        return {paper_id for paper_id, _, _ in eligible[:limit]}
    if config.assignment_mode == "largest_gap":
        if not eligible:
            return set()
        cutoff_count = _largest_gap_cutoff_count([confidence for _, _, confidence in eligible], config=config)
        return {paper_id for paper_id, _, _ in eligible[:cutoff_count]}
    return set()


def _largest_gap_cutoff_count(confidences: list[float], *, config: AxisScoringConfig) -> int:
    if len(confidences) <= 1:
        return len(confidences) if confidences and confidences[0] >= config.assignment_threshold else 0
    gaps = [confidences[index] - confidences[index + 1] for index in range(len(confidences) - 1)]
    largest_index, largest_gap = max(enumerate(gaps), key=lambda item: (item[1], -item[0]))
    if largest_gap >= config.minimum_gap:
        return largest_index + 1
    return len(confidences) if confidences[0] >= config.assignment_threshold else 0


def _assignment_status(
    paper_id: int,
    confidence: float,
    *,
    selected_paper_ids: set[int],
    config: AxisScoringConfig,
) -> AssignmentStatus:
    selected = paper_id in selected_paper_ids
    if selected and confidence >= config.assignment_threshold:
        return "assigned"
    if selected and confidence >= config.uncertainty_threshold:
        return "uncertain"
    return "below-threshold"


def natural_break_assigned_ids(
    scored: list[tuple[int, float]],
    *,
    config: AxisScoringConfig,
) -> set[int]:
    """The "assigned" cluster under natural-break tiering: papers at/above the noise floor
    (`uncertainty_threshold`) sitting above the largest gap in this axis's descending ranking — a
    relative, model-agnostic break, not an absolute cosine threshold. Sub-floor papers are never
    assigned. Shared by score-time + the read endpoint so tiers match without persisting them."""
    ranked = sorted(((int(pid), float(conf)) for pid, conf in scored), key=lambda s: (-s[1], s[0]))
    eligible = [(pid, conf) for pid, conf in ranked if conf >= config.uncertainty_threshold]
    if not eligible:
        return set()
    cutoff = _largest_gap_cutoff_count([conf for _, conf in eligible], config=config)
    return {pid for pid, _ in eligible[:cutoff]}


def _never_empty_uncertain(raw_scores: list[tuple[int, int, float]]) -> dict[int, AssignmentStatus]:
    """Never-empty fallback: when nothing clears the floor, surface the closest few positive matches as
    `uncertain` candidates so an axis is never blank. Shared by every assignment mode."""
    return {paper_id: "uncertain" for paper_id, _embedding_id, confidence in raw_scores[:3] if confidence > 0}


def _natural_break_statuses(
    raw_scores: list[tuple[int, int, float]],
    *,
    config: AxisScoringConfig,
) -> dict[int, AssignmentStatus]:
    """Natural-break tiers: eligible (>= floor) split into `assigned` (above the largest gap) /
    `uncertain` (rest); nothing clears the floor → the closest few become `uncertain` (never-empty)."""
    eligible = [(pid, conf) for pid, _eid, conf in raw_scores if conf >= config.uncertainty_threshold]
    if not eligible:
        return _never_empty_uncertain(raw_scores)
    assigned = natural_break_assigned_ids(eligible, config=config)
    return {pid: ("assigned" if pid in assigned else "uncertain") for pid, _conf in eligible}


def _confidence_from_cosine_distance(distance: float) -> float:
    # Round to the 2 decimals the UI shows (toFixed(2)) so the SAME number drives display, storage, and
    # the cutoff/tier comparison — a paper shown as "0.35" is never tagged uncertain because its raw
    # score was 0.349 (inc 48; per the user).
    return round(max(0.0, min(1.0, 1.0 - distance)), 2)


def _axis_text(axis: RowMapping) -> str:
    # The title (`label`) is a cosmetic display name, NOT embedded — the search vocabulary lives in the
    # description (its "Related:" terms). Fall back to the label only when the description is blank.
    description = (axis["description"] or "").strip()
    return description if description else (str(axis["label"]) if axis["label"] else "")


def _axis_source_text_version(text: str, *, model: EmbeddingModel) -> str:
    return _axis_text_version(text, normalization=model.normalization)


def _axis_text_version(text: str, *, normalization: str) -> str:
    normalized = normalize_text(text, normalization)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{AXIS_TEXT_VERSION_PREFIX}{digest}"


# --- Write + read helpers exposed by the supervised-axis API (increment 1) -----------------
# These reuse the scoring engine above; they do NOT reimplement scoring. score_axis remains the
# only path that embeds + compares the library and (re)writes scored assignments.


def delete_axis(conn: Connection, axis_id: int) -> None:
    """Delete an axis. Its cluster_nodes + cluster_node_papers cascade via FK ondelete=CASCADE."""
    conn.execute(delete(axes).where(axes.c.id == axis_id))
