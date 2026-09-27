"""Embedding search over the read-only library copy, scoped by chunk id (whole library, one paper, or a section pool).

The embedding model and vector store are the production ones (all-MiniLM-L6-v2, sqlite-vec); nothing is written, no chunk
is embedded at query time (a chunk without a current embedding is simply not searchable and is counted, never hidden).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, DEFAULT_NORMALIZATION
from app.backend.embeddings.pipeline import current_chunk_embedding_ids
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.model_runtime import PINNED_MODEL_REVISIONS, ModelRuntimeRegistry
from app.backend.persistence.chunk_structure_repo import current_structure_roles
from experiments.ask_cli_revised.contract_directed.store import Library

DEPRIORITIZED_ROLES = frozenset({"bibliographic", "structural"})  # demoted below scientific/unknown, never deleted


@dataclass(frozen=True)
class Hit:
    chunk_id: int
    paper_id: int
    score: float  # 1 - cosine distance, floored at 0 (the baseline's convention)
    evidence_role: str | None = None
    chunk_type: str | None = None


class Retriever:
    def __init__(self, library: Library, *, model=None, registry: ModelRuntimeRegistry | None = None):
        self.library = library
        self.registry = registry or ModelRuntimeRegistry()
        self.model = model or self.registry.get_embedding_model(
            name=DEFAULT_EMBEDDING_MODEL,
            normalization=DEFAULT_NORMALIZATION,
            revision=PINNED_MODEL_REVISIONS.get(DEFAULT_EMBEDDING_MODEL),
        )
        self.store = SQLiteVecVectorStore()
        self.index = library.article_chunk_index()
        self.by_chunk = {r["chunk_id"]: r for r in self.index}
        with library.engine.connect() as conn:
            self.chunk_to_emb = current_chunk_embedding_ids(
                conn, ((r["chunk_id"], r["chunk_version"]) for r in self.index), model=self.model
            )
        self.emb_to_chunk = {emb: cid for cid, emb in self.chunk_to_emb.items()}
        self.unsearchable = [r["chunk_id"] for r in self.index if r["chunk_id"] not in self.chunk_to_emb]

    def encode(self, text: str) -> list[float]:
        return self.model.encode_texts([text])[0]

    def search(
        self, query: str | list[float], *, chunk_ids: set[int] | None = None, top_k: int = 20, demote: bool = True
    ) -> list[Hit]:
        """Top-k chunks by cosine to `query`, restricted to `chunk_ids` (None = every searchable article chunk).

        With `demote`, chunks the H1a structure table marks bibliographic/structural (running heads, references, table debris)
        sort below every other hit, exactly as the baseline retrieval does: demoted, never deleted, and recorded on the Hit.
        """
        vector = query if isinstance(query, list) else self.encode(query)
        scope = (
            self.chunk_to_emb
            if chunk_ids is None
            else {c: self.chunk_to_emb[c] for c in chunk_ids if c in self.chunk_to_emb}
        )
        if not scope:
            return []
        fetch = min(top_k * 3, 4096) if demote else top_k
        with self.library.engine.connect() as conn:
            raw = self.store.search(conn, vector=vector, top_k=fetch, candidate_embedding_ids=set(scope.values()))
            ids = [self.emb_to_chunk[h.embedding_id] for h in raw if h.embedding_id in self.emb_to_chunk]
            roles = current_structure_roles(conn, ids) if demote else {}
        hits = []
        for hit in raw:
            chunk_id = self.emb_to_chunk.get(hit.embedding_id)
            if chunk_id is None:
                continue
            chunk_type, role = roles.get(chunk_id, (None, None))
            hits.append(
                Hit(
                    chunk_id, self.by_chunk[chunk_id]["paper_id"], max(0.0, 1.0 - float(hit.distance)), role, chunk_type
                )
            )
        if demote:
            hits = [h for h in hits if h.evidence_role not in DEPRIORITIZED_ROLES] + [
                h for h in hits if h.evidence_role in DEPRIORITIZED_ROLES
            ]
        return hits[:top_k]
