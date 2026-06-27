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
from app.backend.pdf_processing.extraction import canonical_text_contains
from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.persistence.schema import chunks, embeddings
from app.backend.summarization.generators import CandidateCitation, SourceChunk

VERIFICATION_VERSION = "local-verifier-v1"
DEFAULT_SUPPORT_THRESHOLD = 0.55


@dataclass(frozen=True)
class VerificationConfig:
    retrieval_threshold: float = 0.7
    quote_threshold: float = 1.0
    # Calibrated on the real library's NLI support-score valley: rejects <=0.420, keeps >=0.632.
    support_threshold: float = DEFAULT_SUPPORT_THRESHOLD


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


@dataclass
class NLISupportScorer:
    """Local CrossEncoder NLI support scorer.

    The passage is the premise and the summary sentence is the hypothesis.
    The returned confidence is the model's entailment probability.
    """

    model_name: str = "cross-encoder/nli-MiniLM2-L6-H768"
    local_files_only: bool = False
    fallback_scorer: SupportScorer | None = None
    _model: object | None = field(default=None, init=False, repr=False)
    _loader: Callable[[], object] | None = field(default=None, repr=False)

    def score(self, *, sentence: str, passage: str) -> float:
        try:
            model = self._load_model()
            scores = model.predict([(passage, sentence)], apply_softmax=True)  # type: ignore[attr-defined]
            return _entailment_confidence(scores, model=model)
        except Exception:
            if self.fallback_scorer is None:
                raise
            return self.fallback_scorer.score(sentence=sentence, passage=passage)

    def _load_model(self) -> object:
        if self._model is None:
            if self._loader is not None:
                self._model = self._loader()
            else:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name, local_files_only=self.local_files_only)
        return self._model


def default_support_scorer(model: EmbeddingModel) -> SupportScorer:
    return NLISupportScorer(fallback_scorer=EmbeddingSupportScorer(model))


@dataclass(frozen=True)
class Stance:
    """A 3-way NLI stance of a passage toward a claim (inc 156, highlight-to-evaluate)."""

    label: str  # "support" | "contrast" | "mention"
    confidence: float
    probs: dict[str, float]  # {"support": .., "contrast": .., "mention": ..}


class StanceScorer(Protocol):
    def classify_stance(self, *, sentence: str, passage: str) -> Stance | None:
        """Local NLI stance of `passage` toward `sentence`, or None if unavailable (never a guessed verdict)."""


@dataclass
class NLIStanceScorer:
    """Local CrossEncoder NLI stance scorer (shares the model family with NLISupportScorer).

    The passage is the premise and the claim sentence is the hypothesis; the 3-way softmax maps
    entailment→support, contradiction→contrast, neutral→mention. On ANY failure → None, so the evaluate path
    shows no stance rather than a guessed verdict ("silence is not a certificate").
    """

    model_name: str = "cross-encoder/nli-MiniLM2-L6-H768"
    local_files_only: bool = False
    _model: object | None = field(default=None, init=False, repr=False)
    _loader: Callable[[], object] | None = field(default=None, repr=False)

    def classify_stance(self, *, sentence: str, passage: str) -> Stance | None:
        try:
            model = self._load_model()
            scores = model.predict([(passage, sentence)], apply_softmax=True)  # type: ignore[attr-defined]
            return _stance_from_scores(scores, model=model)
        except Exception:
            return None

    def _load_model(self) -> object:
        if self._model is None:
            if self._loader is not None:
                self._model = self._loader()
            else:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name, local_files_only=self.local_files_only)
        return self._model


def default_stance_scorer() -> StanceScorer:
    return NLIStanceScorer()


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
        source_by_id = {chunk.chunk_id: chunk for chunk in source_chunks}
        cited_chunk = source_by_id.get(citation.chunk_id) or _source_chunk_for_id(conn, citation.chunk_id)
        candidate_chunk_ids = [chunk.chunk_id for chunk in source_chunks] or [citation.chunk_id]
        retrieval_confidence = self._retrieval_confidence(
            conn,
            sentence=sentence,
            cited_chunk_id=citation.chunk_id,
            candidate_chunk_ids=candidate_chunk_ids,
        )
        quote_confidence, page_start, page_end, bbox_json, coordinate_precision = self._quote_confidence(
            conn,
            citation=citation,
            cited_chunk=cited_chunk,
        )
        support_confidence = self.support_scorer.score(sentence=sentence, passage=cited_chunk.text)
        status = self._status(
            retrieval_confidence=retrieval_confidence,
            quote_confidence=quote_confidence,
            support_confidence=support_confidence,
        )
        return VerificationResult(
            chunk_id=citation.chunk_id,
            quote_text=citation.quote,
            status=status,
            retrieval_confidence=retrieval_confidence,
            quote_confidence=quote_confidence,
            support_confidence=support_confidence,
            page_start=page_start,
            page_end=page_end,
            bbox_json=bbox_json,
            coordinate_precision=coordinate_precision,
            chunk_version_verified_against=cited_chunk.chunk_version,
            embedding_version_verified_against=_embedding_version(self.model),
        )

    def _retrieval_confidence(
        self,
        conn: Connection,
        *,
        sentence: str,
        cited_chunk_id: int,
        candidate_chunk_ids: list[int],
    ) -> float:
        embed_chunks(conn, model=self.model, vector_store=self.vector_store, chunk_ids=candidate_chunk_ids)
        embedding_to_chunk = _chunk_embedding_ids(conn, model=self.model, chunk_ids=candidate_chunk_ids)
        cited_embedding_ids = {
            embedding_id for embedding_id, chunk_id in embedding_to_chunk.items() if chunk_id == cited_chunk_id
        }
        if not cited_embedding_ids or not embedding_to_chunk:
            return 0.0
        hits = self.vector_store.search(
            conn,
            vector=self.model.encode_texts([sentence])[0],
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
    ) -> str:
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


def _entailment_confidence(scores, *, model: object) -> float:  # type: ignore[no-untyped-def]
    row = scores[0] if hasattr(scores, "__len__") and len(scores) else scores
    values = [float(value) for value in row]
    if len(values) == 1:
        return max(0.0, min(1.0, values[0]))
    index = _entailment_index(model=model, count=len(values))
    return max(0.0, min(1.0, values[index]))


# NLI label → stance label (inc 156). Standard 3-class NLI cross-encoders order [contradiction, entailment, neutral].
_STANCE_BY_NLI = {"entailment": "support", "contradiction": "contrast", "neutral": "mention"}
_DEFAULT_STANCE_INDEX = {"support": 1, "contrast": 0, "mention": 2}


def _label_index(*, model: object, count: int, label: str, default: int) -> int:
    config = getattr(getattr(model, "model", None), "config", None)
    id2label = getattr(config, "id2label", None)
    if isinstance(id2label, dict):
        for key, lab in id2label.items():
            if str(lab).lower() == label:
                return int(key)
    return default


def _entailment_index(*, model: object, count: int) -> int:
    return _label_index(model=model, count=count, label="entailment", default=1 if count > 1 else 0)


def _stance_from_scores(scores, *, model: object) -> Stance:  # type: ignore[no-untyped-def]
    row = scores[0] if hasattr(scores, "__len__") and len(scores) else scores
    values = [float(value) for value in row]
    count = len(values)
    probs: dict[str, float] = {}
    for nli_label, stance_label in _STANCE_BY_NLI.items():
        idx = _label_index(model=model, count=count, label=nli_label, default=_DEFAULT_STANCE_INDEX[stance_label])
        probs[stance_label] = max(0.0, min(1.0, values[idx])) if 0 <= idx < count else 0.0
    label = max(probs, key=lambda key: probs[key])
    return Stance(label=label, confidence=probs[label], probs=probs)


def _normalize_space(text: str) -> str:
    return " ".join(text.split())
