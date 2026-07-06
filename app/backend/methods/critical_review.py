"""Cross-corpus contradiction detector — the deterministic heart of the critical-review
"weak claim" signal (backlog #12, Tier 1).

Given a paper's candidate claim sentences, retrieve semantically-related passages from the
*rest of the corpus* via the local vector store and run the existing local NLI stance
classifier with each claim as the hypothesis. A claim is "contested" when another paper's
passage takes a confident CONTRAST stance toward it — surfacing disagreement the corpus
already contains, never resolving it (the THEORY contract: "surface disagreement, do not
smooth it"). The result is a signal, not a verdict: each contested claim carries its
contradicting passage (verbatim, with the other paper's id + page), the stance, and a
visible confidence, so the human appraises.

Fully local, no network, no LLM: this module imports NOTHING from any gemini/LLM module.
Every heavy dependency (embedding model, vector store, stance scorer, chunk resolver) is
INJECTED so the detector is pure and hermetically testable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import VectorHit, VectorStore
from app.backend.summarization.verification import StanceScorer


@dataclass(frozen=True)
class ContestedClaim:
    claim: str  # a sentence from THIS paper
    passage: str  # the contradicting passage (verbatim, from another paper)
    other_paper_id: int
    page: int | None
    stance: str  # always "contrast" here
    confidence: float


@dataclass(frozen=True)
class ChunkInfo:
    paper_id: int
    text: str
    page: int | None


def find_contested_claims(
    conn,
    paper_id,
    *,
    embed_model: EmbeddingModel,
    vector_store: VectorStore,
    stance_scorer: StanceScorer,
    resolve_chunk: Callable[[VectorHit], ChunkInfo | None],
    claim_sentences: list[str],
    other_chunk_ids: set[int],
    contradiction_threshold: float = 0.55,
    top_k: int = 5,
    max_claims: int = 12,
) -> list[ContestedClaim]:
    """Return the claims from this paper that another paper in the corpus contradicts.

    For each of up to ``max_claims`` ``claim_sentences``: embed it, retrieve the ``top_k``
    nearest passages from ``other_chunk_ids`` (the *other* papers' chunk-embeddings), resolve
    each hit to a :class:`ChunkInfo`, and classify the passage's stance toward the claim. A
    claim is kept when some passage takes a CONTRAST stance at or above
    ``contradiction_threshold``; only the single highest-confidence contradicter is recorded
    (claims with none are skipped). Support/mention/None stances never surface a claim.
    """
    if not claim_sentences or not other_chunk_ids:
        return []

    contested: list[ContestedClaim] = []
    for claim in claim_sentences[:max_claims]:
        vector = embed_model.encode_texts([claim])[0]
        hits = vector_store.search(
            conn,
            vector=vector,
            top_k=top_k,
            candidate_embedding_ids=other_chunk_ids,
        )
        best: ContestedClaim | None = None
        for hit in hits:
            chunk = resolve_chunk(hit)
            if chunk is None:
                continue
            stance = stance_scorer.classify_stance(sentence=claim, passage=chunk.text)
            if stance is None or stance.label != "contrast":
                continue
            if stance.confidence < contradiction_threshold:
                continue
            if best is None or stance.confidence > best.confidence:
                best = ContestedClaim(
                    claim=claim,
                    passage=chunk.text,
                    other_paper_id=chunk.paper_id,
                    page=chunk.page,
                    stance="contrast",
                    confidence=stance.confidence,
                )
        if best is not None:
            contested.append(best)
    return contested
