"""Local embedding generation and vector search."""

from app.backend.embeddings.models import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_NORMALIZATION,
    EmbeddingModel,
    SentenceTransformerEmbeddingModel,
    normalize_text,
)
from app.backend.embeddings.pipeline import (
    StaleEmbedding,
    embed_chunks,
    embed_papers,
    find_stale_embeddings,
)
from app.backend.embeddings.retrieval import RetrievalHit, search_similar
from app.backend.embeddings.vector_store import (
    InMemoryVectorStore,
    SQLiteVecVectorStore,
    VectorHit,
    VectorStore,
)

__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_NORMALIZATION",
    "EmbeddingModel",
    "SentenceTransformerEmbeddingModel",
    "normalize_text",
    "StaleEmbedding",
    "embed_chunks",
    "embed_papers",
    "find_stale_embeddings",
    "RetrievalHit",
    "search_similar",
    "InMemoryVectorStore",
    "SQLiteVecVectorStore",
    "VectorHit",
    "VectorStore",
]
