"""Local deterministic citation verification."""

from __future__ import annotations

import math
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import Connection, and_, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.vector_store import VectorStore
from app.backend.model_runtime import PINNED_MODEL_REVISIONS, ManagedModelRuntime
from app.backend.pdf_processing.extraction import canonical_text_contains
from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.persistence.schema import chunks, embeddings
from app.backend.summarization.generators import CandidateCitation, SourceChunk
from app.backend.summarization.stance import (
    CRITICAL_REVIEW_NLI_BATCH_SIZE as CRITICAL_REVIEW_NLI_BATCH_SIZE,
)
from app.backend.summarization.stance import (
    CRITICAL_REVIEW_NLI_BUCKET_LIMITS as CRITICAL_REVIEW_NLI_BUCKET_LIMITS,
)
from app.backend.summarization.stance import (
    CRITICAL_REVIEW_NLI_MAX_LENGTH as CRITICAL_REVIEW_NLI_MAX_LENGTH,
)
from app.backend.summarization.stance import (
    DEFAULT_NLI_MODEL as DEFAULT_NLI_MODEL,
)
from app.backend.summarization.stance import (
    NLIStanceScorer as NLIStanceScorer,
)
from app.backend.summarization.stance import (
    Stance as Stance,
)
from app.backend.summarization.stance import (
    StanceScorer as StanceScorer,
)
from app.backend.summarization.stance import (
    _contradiction_index,
    _entailment_index,
)
from app.backend.summarization.stance import (
    _stance_from_row as _stance_from_row,
)
from app.backend.summarization.stance import (
    _stance_from_scores as _stance_from_scores,
)
from app.backend.summarization.stance import (
    classify_critical_review_stances as classify_critical_review_stances,
)
from app.backend.summarization.stance import (
    classify_stances as classify_stances,
)
from app.backend.summarization.stance import (
    critical_review_nli_bucket as critical_review_nli_bucket,
)
from app.backend.summarization.stance import (
    default_stance_scorer as default_stance_scorer,
)

VERIFICATION_VERSION = "local-verifier-v1"
DEFAULT_SUPPORT_THRESHOLD = 0.55


@dataclass(frozen=True)
class VerificationConfig:
    retrieval_threshold: float = 0.7
    quote_threshold: float = 1.0
    # Calibrated on the real library's NLI support-score valley: rejects <=0.420, keeps >=0.632.
    support_threshold: float = DEFAULT_SUPPORT_THRESHOLD
    # A confident NLI *contradiction* probability (from the same softmax) → the `contradicted` status. Conservative:
    # also requires contradiction to exceed support, so a middling claim isn't flagged as actively disputed.
    contradiction_threshold: float = 0.55


@dataclass(frozen=True)
class VerificationResult:
    chunk_id: int
    quote_text: str
    status: str
    retrieval_confidence: float
    quote_confidence: float
    support_confidence: float
    page_start: int | None
    page_end: int | None
    bbox_json: object | None
    coordinate_precision: str | None
    chunk_version_verified_against: str
    embedding_version_verified_against: str
    verification_version: str = VERIFICATION_VERSION
    # The NLI contradiction probability when available (None for the embedding-only fallback — silence, not a guess).
    contradiction_confidence: float | None = None

    @property
    def verified(self) -> bool:
        return self.status == "verified"


class SupportScorer(Protocol):
    def score(self, *, sentence: str, passage: str) -> float:
        """Return deterministic support confidence in [0, 1]."""


@dataclass(frozen=True)
class EmbeddingSupportScorer:
    model: EmbeddingModel

    def score(self, *, sentence: str, passage: str) -> float:
        sentence_vector, passage_vector = self.model.encode_texts([sentence, passage])
        return _cosine_similarity_confidence(sentence_vector, passage_vector)

    def support_and_contradiction_many(self, pairs: list[tuple[str, str]]) -> list[tuple[float, float | None]]:
        """Score every ``(passage, sentence)`` pair in one embedding-model batch.

        Embeddings do not provide a contradiction probability, so the second tuple item remains ``None`` just as
        it does on the single-item fallback path.
        """
        if not pairs:
            return []
        texts = [text for passage, sentence in pairs for text in (sentence, passage)]
        vectors = self.model.encode_texts(texts)
        return [
            (_cosine_similarity_confidence(vectors[index], vectors[index + 1]), None)
            for index in range(0, len(vectors), 2)
        ]


@dataclass
class NLISupportScorer:
    """Local CrossEncoder NLI support scorer.

    The passage is the premise and the summary sentence is the hypothesis.
    The returned confidence is the model's entailment probability.
    """

    model_name: str = DEFAULT_NLI_MODEL
    local_files_only: bool = False
    revision: str | None = None
    device: str | None = None
    backend: str = "torch"
    fallback_scorer: SupportScorer | None = None
    _model: object | None = field(default=None, init=False, repr=False)
    _loader: Callable[[], object] | None = field(default=None, repr=False)
    _runtime: ManagedModelRuntime | None = field(default=None, repr=False)

    def score(self, *, sentence: str, passage: str) -> float:
        return self.support_and_contradiction(sentence=sentence, passage=passage)[0]

    def support_and_contradiction(self, *, sentence: str, passage: str) -> tuple[float, float | None]:
        """Both probabilities from ONE NLI softmax: (entailment→support, contradiction). On failure → the fallback
        scorer's support + None contradiction (the embedding fallback has no contradiction signal — silence, not a
        guessed verdict). Used by the verifier to surface the `contradicted` status (the source actively disagrees)."""
        return self.support_and_contradiction_many([(passage, sentence)])[0]

    def support_and_contradiction_many(self, pairs: list[tuple[str, str]]) -> list[tuple[float, float | None]]:
        """Batched form of ``support_and_contradiction`` — ONE ``model.predict()`` call for every ``(passage,
        sentence)`` pair, instead of one call per pair. Same model, same math, same thresholds — only the number
        of calls changes. On any failure, falls back to the embedding scorer PER PAIR (preserves the existing
        silent-fallback contract exactly, just applied to each item)."""
        if not pairs:
            return []
        try:

            def predict(model: object):  # type: ignore[no-untyped-def]
                scores = model.predict(list(pairs), apply_softmax=True)  # type: ignore[attr-defined]
                return [_values_from_row(row, model=model) for row in scores]

            return self._runtime.run(predict) if self._runtime is not None else predict(self._load_model())
        except Exception:
            if self.fallback_scorer is None:
                raise
            return [
                (self.fallback_scorer.score(sentence=sentence, passage=passage), None) for passage, sentence in pairs
            ]

    def _load_model(self) -> object:
        if self._model is None:
            if self._loader is not None:
                self._model = self._loader()
            else:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(
                    self.model_name,
                    revision=self.revision,
                    device=self.device,
                    local_files_only=self.local_files_only,
                    backend=self.backend,
                    model_kwargs={"use_safetensors": True},
                )
        return self._model


def default_support_scorer(model: EmbeddingModel) -> SupportScorer:
    return NLISupportScorer(
        revision=PINNED_MODEL_REVISIONS.get(DEFAULT_NLI_MODEL), fallback_scorer=EmbeddingSupportScorer(model)
    )


class LocalCitationVerifier:
    def __init__(
        self,
        *,
        model: EmbeddingModel,
        vector_store: VectorStore,
        config: VerificationConfig | None = None,
        support_scorer: SupportScorer | None = None,
    ) -> None:
        self.model = model
        self.vector_store = vector_store
        self.config = config or VerificationConfig()
        self.support_scorer = support_scorer or default_support_scorer(model)

    def verify(
        self,
        conn: Connection,
        *,
        sentence: str,
        citation: CandidateCitation,
        source_chunks: list[SourceChunk],
    ) -> VerificationResult:
        return self.verify_many(conn, items=[(sentence, citation)], source_chunks=source_chunks)[0]

    def verify_many(
        self,
        conn: Connection,
        *,
        items: list[tuple[str, CandidateCitation]],
        source_chunks: list[SourceChunk],
    ) -> list[VerificationResult]:
        """Batched form of ``verify`` — ONE embedding-encode call and ONE NLI call for the WHOLE batch, instead of
        one each per (sentence, citation) pair. Same per-item logic, same math, same thresholds; only the model
        calls are batched. ``verify()`` is a thin ``verify_many`` wrapper (n=1) — every existing test exercising
        ``verify()`` is therefore a free regression test for this method too."""
        if not items:
            return []
        source_by_id = {chunk.chunk_id: chunk for chunk in source_chunks}
        cited_chunks = [
            source_by_id.get(citation.chunk_id) or _source_chunk_for_id(conn, citation.chunk_id)
            for _, citation in items
        ]

        # `source_chunks` is the SAME candidate pool for every item in a real batch (summarize_scope/reverify both
        # call with one shared list per summary) — hoist the embed/lookup ONCE instead of redoing it per citation
        # (today's `verify()` redundantly re-checks embedding existence for the same chunks on every single
        # citation). Only falls back to a per-item pool when source_chunks is empty, matching verify()'s own
        # existing edge-case behavior exactly.
        shared_candidate_ids = [chunk.chunk_id for chunk in source_chunks]
        shared_embedding_to_chunk = (
            self._embedding_lookup(conn, candidate_chunk_ids=shared_candidate_ids) if shared_candidate_ids else None
        )

        sentence_vectors = self.model.encode_texts([sentence for sentence, _ in items])

        retrieval_confidences: list[float] = []
        for (_, citation), vector in zip(items, sentence_vectors, strict=True):
            embedding_to_chunk = shared_embedding_to_chunk
            if embedding_to_chunk is None:
                embedding_to_chunk = self._embedding_lookup(conn, candidate_chunk_ids=[citation.chunk_id])
            retrieval_confidences.append(
                self._retrieval_confidence_from_vector(
                    conn, vector=vector, cited_chunk_id=citation.chunk_id, embedding_to_chunk=embedding_to_chunk
                )
            )

        quote_results = [
            self._quote_confidence(conn, citation=citation, cited_chunk=cited_chunk)
            for (_, citation), cited_chunk in zip(items, cited_chunks, strict=True)
        ]
        # Support is a property of the evidence the generator actually cited, not every other sentence that
        # happens to share its page-sized source chunk. Quote verification above has already established whether
        # this exact passage occurs in the chunk; using it here both preserves the evidentiary boundary and avoids
        # a long page causing the cross-encoder to truncate the cited passage out of its own input.
        pairs = [(citation.quote, sentence) for sentence, citation in items]
        support_results = self._support_and_contradiction_many(pairs)

        results: list[VerificationResult] = []
        for retrieval_confidence, quote_result, support_result, (_, citation), cited_chunk in zip(
            retrieval_confidences, quote_results, support_results, items, cited_chunks, strict=True
        ):
            quote_confidence, page_start, page_end, bbox_json, coordinate_precision = quote_result
            support_confidence, contradiction_confidence = support_result
            status = self._status(
                retrieval_confidence=retrieval_confidence,
                quote_confidence=quote_confidence,
                support_confidence=support_confidence,
                contradiction_confidence=contradiction_confidence,
            )
            results.append(
                VerificationResult(
                    chunk_id=citation.chunk_id,
                    quote_text=citation.quote,
                    status=status,
                    retrieval_confidence=retrieval_confidence,
                    quote_confidence=quote_confidence,
                    support_confidence=support_confidence,
                    contradiction_confidence=contradiction_confidence,
                    page_start=page_start,
                    page_end=page_end,
                    bbox_json=bbox_json,
                    coordinate_precision=coordinate_precision,
                    chunk_version_verified_against=cited_chunk.chunk_version,
                    embedding_version_verified_against=_embedding_version(self.model),
                )
            )
        return results

    def _support_and_contradiction(self, *, sentence: str, passage: str) -> tuple[float, float | None]:
        """Support + (when the scorer exposes it) contradiction, in one call. A scorer that only implements the
        ``SupportScorer`` Protocol (`.score`) — the embedding fallback, or a test double — yields no contradiction."""
        both = getattr(self.support_scorer, "support_and_contradiction", None)
        if callable(both):
            return both(sentence=sentence, passage=passage)
        return self.support_scorer.score(sentence=sentence, passage=passage), None

    def _support_and_contradiction_many(self, pairs: list[tuple[str, str]]) -> list[tuple[float, float | None]]:
        """Batched dispatch mirroring ``_support_and_contradiction``'s duck-typed fallback: a scorer exposing
        ``support_and_contradiction_many`` batches in one call; one exposing only ``support_and_contradiction``
        (or just ``.score``) is looped through the existing single-item dispatcher — every test-double scorer
        keeps working completely unmodified."""
        if not pairs:
            return []
        many = getattr(self.support_scorer, "support_and_contradiction_many", None)
        if callable(many):
            return many(pairs)
        return [self._support_and_contradiction(sentence=sentence, passage=passage) for passage, sentence in pairs]

    def _embedding_lookup(self, conn: Connection, *, candidate_chunk_ids: list[int]) -> dict[int, int]:
        embed_chunks(conn, model=self.model, vector_store=self.vector_store, chunk_ids=candidate_chunk_ids)
        return _chunk_embedding_ids(conn, model=self.model, chunk_ids=candidate_chunk_ids)

    def _retrieval_confidence_from_vector(
        self,
        conn: Connection,
        *,
        vector: list[float],
        cited_chunk_id: int,
        embedding_to_chunk: dict[int, int],
    ) -> float:
        cited_embedding_ids = {
            embedding_id for embedding_id, chunk_id in embedding_to_chunk.items() if chunk_id == cited_chunk_id
        }
        if not cited_embedding_ids or not embedding_to_chunk:
            return 0.0
        hits = self.vector_store.search(
            conn,
            vector=vector,
            top_k=len(embedding_to_chunk),
            candidate_embedding_ids=set(embedding_to_chunk),
        )
        for hit in hits:
            if hit.embedding_id in cited_embedding_ids:
                return _distance_to_confidence(hit.distance)
        return 0.0

    def _quote_confidence(
        self,
        conn: Connection,
        *,
        citation: CandidateCitation,
        cited_chunk: SourceChunk,
    ) -> tuple[float, int | None, int | None, object | None, str | None]:
        if not canonical_text_contains(needle=citation.quote, haystack=cited_chunk.text):
            return 0.0, None, None, None, None
        match = locate_quote_for_attachment(conn, cited_chunk.attachment_id, citation.quote)
        if not match.found:
            return (
                1.0,
                cited_chunk.page_start,
                cited_chunk.page_end,
                _with_coordinate_precision(cited_chunk.bbox_json, "region"),
                "region",
            )
        return (
            1.0,
            match.page_start,
            match.page_end,
            _with_coordinate_precision(list(match.rectangles), "exact"),
            "exact",
        )

    def _status(
        self,
        *,
        retrieval_confidence: float,
        quote_confidence: float,
        support_confidence: float,
        contradiction_confidence: float | None = None,
    ) -> str:
        # The cited source actively DISAGREES — the most consequential citation error, checked first. Conservative:
        # a confident contradiction that also exceeds support. Signal, not verdict (the user sees the quote + decides).
        if (
            contradiction_confidence is not None
            and contradiction_confidence >= self.config.contradiction_threshold
            and contradiction_confidence > support_confidence
        ):
            return "contradicted"
        if (
            retrieval_confidence >= self.config.retrieval_threshold
            and quote_confidence >= self.config.quote_threshold
            and support_confidence >= self.config.support_threshold
        ):
            return "verified"
        if (
            retrieval_confidence >= self.config.retrieval_threshold
            or support_confidence >= self.config.support_threshold
        ):
            return "weak"
        return "unverified"


def _source_chunk_for_id(conn: Connection, chunk_id: int) -> SourceChunk:
    row = conn.execute(select(chunks).where(chunks.c.id == chunk_id)).mappings().one()
    return SourceChunk(
        chunk_id=int(row["id"]),
        paper_id=int(row["paper_id"]),
        attachment_id=int(row["attachment_id"]),
        text=str(row["text"]),
        page_start=int(row["page_start"]),
        page_end=int(row["page_end"]),
        chunk_version=str(row["chunk_version"]),
        bbox_json=row["bbox_json"],
    )


def _with_coordinate_precision(bbox_json: object | None, precision: str) -> object | None:
    if bbox_json is None:
        return None
    copied = deepcopy(bbox_json)
    if isinstance(copied, list):
        return [{**item, "coordinate_precision": precision} if isinstance(item, dict) else item for item in copied]
    if isinstance(copied, dict):
        copied["coordinate_precision"] = precision
        return copied
    return copied


def _chunk_embedding_ids(
    conn: Connection,
    *,
    model: EmbeddingModel,
    chunk_ids: list[int],
) -> dict[int, int]:
    rows = conn.execute(
        select(embeddings.c.id, embeddings.c.target_id).where(
            and_(
                embeddings.c.target_type == "chunk",
                embeddings.c.target_id.in_(chunk_ids),
                embeddings.c.model_name == model.name,
                embeddings.c.model_version == model.version,
                embeddings.c.dimension == model.dimension,
                embeddings.c.normalization == model.normalization,
            )
        )
    )
    return {int(row.id): int(row.target_id) for row in rows}


def _embedding_version(model: EmbeddingModel) -> str:
    return f"{model.name}:{model.version}"


def _distance_to_confidence(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - distance))


def _cosine_similarity_confidence(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    similarity = sum(a * b for a, b in zip(left, right, strict=False)) / (left_norm * right_norm)
    return max(0.0, min(1.0, similarity))


def _values_from_row(row, *, model: object) -> tuple[float, float | None]:  # type: ignore[no-untyped-def]
    """(entailment, contradiction) from ONE NLI softmax row. A single-value (regression) head has no
    contradiction. Pure per-row extraction, called once per row of a ``model.predict(pairs, ...)`` response — a
    single-item call is just a length-1 batch, so there is only ever this one code path."""
    values = [float(value) for value in row]
    if len(values) <= 1:
        return (max(0.0, min(1.0, values[0])) if values else 0.0), None
    ent = max(0.0, min(1.0, values[_entailment_index(model=model, count=len(values))]))
    con_idx = _contradiction_index(model=model, count=len(values))
    contradiction = max(0.0, min(1.0, values[con_idx])) if 0 <= con_idx < len(values) else None
    return ent, contradiction


def _normalize_space(text: str) -> str:
    return " ".join(text.split())
