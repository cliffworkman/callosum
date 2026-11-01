"""Embedding profiles: explicit, revision-pinned retrieval encoders that can be selected per library.

A profile is a complete encoding contract, not just a model name: the checkpoint revision, pooling, sequence
length, text normalization and the query/document prefixes all change the vectors, so all of them are part of the
stored identity (``model_version`` + ``normalization``). Two rules follow:

* **Vector spaces never mix.** Profiles of the same dimension share one sqlite-vec table, so every search scopes
  its candidates to embedding rows matching the querying model's full identity (``retrieval._candidate_embedding_ids``
  and the other candidate builders). ``tests/test_embedding_profiles.py`` pins that invariant.
* **Baseline rows keep their legacy identity.** MiniLM's stored rows read ``all-MiniLM-L6-v2`` with normalization
  ``whitespace-lower-v1``; the baseline profile reproduces exactly that identity, so nothing is relabelled.

Only retrieval (Ask's evidence ranking) uses the active profile. Citation verification keeps the baseline MiniLM
model and its MiniLM-calibrated 0.70 similarity gate: Arctic cosines live on a different, uncalibrated scale.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, and_, exists, func, select

from app.backend.embeddings.models import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_NORMALIZATION,
    WHITESPACE_NORMALIZATION,
)
from app.backend.model_runtime import PINNED_MODEL_REVISIONS
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.schema import attachments, chunks, embeddings, papers

ARCTIC_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@dataclass(frozen=True)
class EmbeddingProfile:
    key: str
    label: str
    model_name: str
    revision: str
    model_version: str  # the stored identity; includes everything that changes the vectors
    normalization: str
    dimension: int
    query_prefix: str = ""
    document_prefix: str = ""
    pooling: str | None = None  # enforced at load when set
    max_seq_length: int | None = None  # enforced at load when set
    lazy_indexing: bool = True  # False: never embed missing chunks inside retrieval
    qualification: str = ""


BASELINE_PROFILE_KEY = "minilm"
ARCTIC_S_PROFILE_KEY = "arctic-s"
_ARCTIC_S_MODEL = "Snowflake/snowflake-arctic-embed-s"
_ARCTIC_S_REVISION = PINNED_MODEL_REVISIONS[_ARCTIC_S_MODEL]

PROFILES: dict[str, EmbeddingProfile] = {
    BASELINE_PROFILE_KEY: EmbeddingProfile(
        key=BASELINE_PROFILE_KEY,
        label="MiniLM (baseline)",
        model_name=DEFAULT_EMBEDDING_MODEL,
        revision=PINNED_MODEL_REVISIONS[DEFAULT_EMBEDDING_MODEL],
        model_version=DEFAULT_EMBEDDING_MODEL,  # legacy stored identity, deliberately unchanged
        normalization=DEFAULT_NORMALIZATION,
        dimension=384,
        qualification="Production default; also the citation-verification similarity model.",
    ),
    ARCTIC_S_PROFILE_KEY: EmbeddingProfile(
        key=ARCTIC_S_PROFILE_KEY,
        label="Arctic S",
        model_name=_ARCTIC_S_MODEL,
        revision=_ARCTIC_S_REVISION,
        model_version=f"{_ARCTIC_S_MODEL}@{_ARCTIC_S_REVISION};pooling=cls;max_seq=512;query_prefix=v1;doc_prefix=none",
        normalization=WHITESPACE_NORMALIZATION,
        dimension=384,
        query_prefix=ARCTIC_QUERY_PREFIX,
        pooling="cls",
        max_seq_length=512,
        lazy_indexing=False,
        qualification="Experimental: selected on development questions only; not yet preregistered-evaluated.",
    ),
}

ACTIVE_RETRIEVAL_PROFILE_SETTING = "retrieval_embedding_profile"


class UnknownEmbeddingProfileError(ValueError):
    pass


class IncompleteEmbeddingIndexError(RuntimeError):
    """Retrieval with a profile whose index does not cover every eligible chunk would silently bias toward the
    indexed papers, so it is refused instead."""


def get_profile(key: str) -> EmbeddingProfile:
    try:
        return PROFILES[key]
    except KeyError:
        raise UnknownEmbeddingProfileError(f"Unknown embedding profile: {key}") from None


def eligible_chunks_query():
    """Article-fulltext chunks of live papers: exactly the pool Ask's evidence retrieval ranks."""
    return (
        select(chunks.c.id, chunks.c.chunk_version)
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .join(papers, papers.c.id == chunks.c.paper_id)
        .where(papers.c.deleted_at.is_(None), attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES))
    )


def profile_coverage(conn: Connection, profile: EmbeddingProfile) -> dict:
    """Index completeness over the sources the retrieval contract actually uses.

    Ask retrieves article-fulltext chunks only, so completeness is measured over those. Papers with no chunks
    (metadata-only or abstract-only records) have no scientific passage text to index and are reported, not
    counted as gaps. Abstracts are not part of the chunk retrieval contract for either profile.
    """
    eligible = eligible_chunks_query().subquery()
    current = exists().where(
        and_(
            embeddings.c.target_type == "chunk",
            embeddings.c.target_id == eligible.c.id,
            embeddings.c.model_name == profile.model_name,
            embeddings.c.model_version == profile.model_version,
            embeddings.c.normalization == profile.normalization,
            embeddings.c.dimension == profile.dimension,
            embeddings.c.source_chunk_version == eligible.c.chunk_version,
            embeddings.c.source_text_version == eligible.c.chunk_version,
        )
    )
    total = int(conn.execute(select(func.count()).select_from(eligible)).scalar_one())
    indexed = int(conn.execute(select(func.count()).select_from(eligible).where(current)).scalar_one())
    live_papers = int(conn.execute(select(func.count()).where(papers.c.deleted_at.is_(None))).scalar_one())
    papers_with_chunks = int(
        conn.execute(
            select(func.count(func.distinct(chunks.c.paper_id))).where(chunks.c.id.in_(select(eligible.c.id)))
        ).scalar_one()
    )
    return {
        "eligible_chunks": total,
        "indexed_chunks": indexed,
        "missing_chunks": total - indexed,
        "complete": indexed == total,
        "live_papers": live_papers,
        "papers_with_eligible_chunks": papers_with_chunks,
        "papers_without_passage_text": live_papers - papers_with_chunks,
    }


def baseline_retrieval_provenance(model: object) -> dict[str, object]:
    """What a synthesis records when the baseline ranked its evidence: the encoder that actually ran (which is also
    the verification-similarity model), read from the model itself rather than from Settings."""
    version = getattr(model, "version", None)
    return {
        "profile": BASELINE_PROFILE_KEY,
        "model_name": getattr(model, "name", None),
        "model_version": version,
        "normalization": getattr(model, "normalization", None),
        "verification_embedding": version,
    }


def require_complete_index(conn: Connection, profile: EmbeddingProfile) -> dict:
    coverage = profile_coverage(conn, profile)
    if not profile.lazy_indexing and not coverage["complete"]:
        raise IncompleteEmbeddingIndexError(
            f"The {profile.label} index covers {coverage['indexed_chunks']} of {coverage['eligible_chunks']} "
            "passages in this library. Callosum does not search a partial index. Build the index in Settings → "
            f"Retrieval model, or switch to {PROFILES[BASELINE_PROFILE_KEY].label} or to automatic selection."
        )
    return coverage
