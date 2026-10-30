"""Embedding model interfaces and local sentence-transformers backend."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Protocol

from app.backend.model_runtime import ManagedModelRuntime

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_NORMALIZATION = "whitespace-lower-v1"
# Collapse whitespace but keep case: a case-aware model must see the text as written (uncased tokenizers still
# lower-case internally). Part of the qualified Arctic S profile, so it is a distinct stored identity.
WHITESPACE_NORMALIZATION = "whitespace-v1"


class EmbeddingModel(Protocol):
    name: str
    version: str
    dimension: int
    normalization: str

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per normalized text (document side for an asymmetric model)."""


class EmbeddingModelConfigurationError(RuntimeError):
    """A loaded checkpoint does not match the profile it is supposed to implement."""


def normalize_text(text: str, setting: str = DEFAULT_NORMALIZATION) -> str:
    if setting == "none":
        return text
    if setting == DEFAULT_NORMALIZATION:
        return " ".join(text.split()).lower()
    if setting == WHITESPACE_NORMALIZATION:
        return " ".join(text.split())
    raise ValueError(f"Unknown text normalization setting: {setting}")


def encode_query_texts(model: EmbeddingModel, texts: list[str]) -> list[list[float]]:
    """Encode retrieval queries in one batch. An asymmetric model applies its query prefix; a symmetric one
    (MiniLM, test fakes) has no ``encode_queries`` and encodes exactly as before."""
    encode_queries = getattr(model, "encode_queries", None)
    if callable(encode_queries):
        return encode_queries(texts)
    return model.encode_texts(texts)


def encode_query(model: EmbeddingModel, text: str) -> list[float]:
    return encode_query_texts(model, [text])[0]


_PUNCT_RE = re.compile(r"[\W_]+", re.UNICODE)


def strip_punctuation(text: str) -> str:
    """Collapse runs of punctuation/symbols/underscores to a single space (keeping unicode
    letters + digits) so phrasings that differ only in punctuation/spacing become equivalent —
    e.g. 'anomalous-is-bad' and 'anomalous is bad' both become 'anomalous is bad'. Case +
    whitespace are handled downstream by `normalize_text`."""
    return _PUNCT_RE.sub(" ", text).strip()


@dataclass
class SentenceTransformerEmbeddingModel:
    """Lazy sentence-transformers wrapper.

    Instantiating this class may download model weights if they are not already
    cached locally. Tests use a fake model to stay network-free.
    """

    name: str = DEFAULT_EMBEDDING_MODEL
    version: str | None = None
    normalization: str = DEFAULT_NORMALIZATION
    batch_size: int = 32
    local_files_only: bool = False
    revision: str | None = None
    device: str | None = None
    backend: str = "torch"
    # Asymmetric retrieval (embedding profiles): queries and documents may take different prefixes. Both empty
    # (the MiniLM default) encodes byte-identically to the symmetric path.
    query_prefix: str = ""
    document_prefix: str = ""
    # Load-time contract checks for a qualified profile; None skips the check (legacy MiniLM behavior).
    expected_pooling: str | None = None
    expected_max_seq_length: int | None = None
    # False: retrieval must never embed missing chunks on the fly with this model (a profile index is built by
    # an explicit, Status-tracked job); a missing vector is an incomplete index, not work to do inside Ask.
    lazy_indexing: bool = True
    profile_key: str | None = None
    _runtime: ManagedModelRuntime | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._model = None
        self._contract_checked = False
        if self.version is None:
            self.version = self.name

    @property
    def dimension(self) -> int:
        def get_dimension(model: object) -> int:
            if hasattr(model, "get_embedding_dimension"):
                return int(model.get_embedding_dimension())  # type: ignore[attr-defined]
            return int(model.get_sentence_embedding_dimension())  # type: ignore[attr-defined]

        if self._runtime is not None:
            return self._runtime.run(get_dimension)
        return get_dimension(self._load_model())

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, self.document_prefix)

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, self.document_prefix)

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, self.query_prefix)

    def _encode(self, texts: list[str], prefix: str) -> list[list[float]]:
        normalized = [prefix + normalize_text(text, self.normalization) for text in texts]

        def encode(model: object):  # type: ignore[no-untyped-def]
            self._check_contract(model)
            return model.encode(  # type: ignore[attr-defined]
                normalized,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )

        embeddings = self._runtime.run(encode) if self._runtime is not None else encode(self._load_model())
        return [_to_float_list(vector) for vector in embeddings]

    def _check_contract(self, model: object) -> None:
        """Refuse to encode with a checkpoint whose pooling or sequence length differs from the profile."""
        if self._contract_checked or (self.expected_pooling is None and self.expected_max_seq_length is None):
            return
        if self.expected_pooling is not None:
            modes = [
                module.get_pooling_mode_str()
                for module in getattr(model, "_modules", {}).values()
                if hasattr(module, "get_pooling_mode_str")
            ]
            if modes != [self.expected_pooling]:
                raise EmbeddingModelConfigurationError(
                    f"{self.name}: expected {self.expected_pooling} pooling, checkpoint has {modes or 'none'}"
                )
        if self.expected_max_seq_length is not None:
            actual = getattr(model, "max_seq_length", None)
            if actual != self.expected_max_seq_length:
                raise EmbeddingModelConfigurationError(
                    f"{self.name}: expected max_seq_length {self.expected_max_seq_length}, checkpoint has {actual}"
                )
        self._contract_checked = True

    def _load_model(self):  # type: ignore[no-untyped-def]
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.name,
                revision=self.revision,
                device=self.device,
                local_files_only=self.local_files_only,
                backend=self.backend,
                model_kwargs={"use_safetensors": True},
            )
        return self._model


def l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _to_float_list(vector) -> list[float]:  # type: ignore[no-untyped-def]
    return [float(value) for value in vector.tolist() if isinstance(value, (int, float))] or [
        float(value) for value in vector
    ]
