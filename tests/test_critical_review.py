"""Critical-review supplement (backlog #12) — the single-paper "scrutiny surface" MVP.

Tier 1 is deterministic/local; Tier 2 is egress-gated LLM candidates through the #13 verbatim-quote bar. Tests
inject fakes for the NLI stance scorer / vector store / generator so they stay hermetic + fast (no model loads).
"""

from __future__ import annotations

from sqlalchemy import create_engine

from app.backend.embeddings.vector_store import VectorHit
from app.backend.methods.critical_review import (
    ChunkInfo,
    ContestedClaim,
    find_contested_claims,
)
from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence import schema
from app.backend.persistence.repository import create_paper
from app.backend.summarization.verification import Stance


def test_candidate_store_roundtrip() -> None:
    eng = create_engine("sqlite://")
    schema.metadata.create_all(eng)
    with eng.begin() as c:
        pid = create_paper(c, title="P", csl_json={"title": "P"})
        ids = repo.insert_candidates(
            c,
            pid,
            [
                {
                    "concern": "overstated",
                    "anchor_quote": "we prove causation",
                    "page": 3,
                    "stance": "contrast",
                    "confidence": 0.8,
                    "signature": "sig1",
                }
            ],
        )
        assert len(ids) == 1
        rows = repo.list_candidates(c, pid, statuses=["pending"])
        assert len(rows) == 1
        assert rows[0]["concern"] == "overstated" and rows[0]["status"] == "pending"
        assert rows[0]["anchor_quote"] == "we prove causation" and rows[0]["confidence"] == 0.8
        assert repo.set_status(c, ids[0], "rejected") is True
        assert repo.set_status(c, 99999, "rejected") is False  # unknown id
        assert repo.rejected_signatures(c, pid) == {"sig1"}
        assert repo.list_candidates(c, pid, statuses=["pending"]) == []  # now rejected, not pending


# --- Task 2: cross-corpus contradiction detector (hermetic — all deps faked, no model loads) ---


class _FakeEmbedModel:
    """Stand-in EmbeddingModel: returns a fixed vector per text (the value is irrelevant to the
    fake vector store, which returns its hit unconditionally)."""

    name = "fake"
    version = "fake"
    dimension = 3
    normalization = "none"

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeVectorStore:
    """Returns exactly one hit (another paper's chunk-embedding) for any query."""

    def __init__(self, hit_embedding_id: int) -> None:
        self._hit_embedding_id = hit_embedding_id

    def search(self, conn, *, vector, top_k, candidate_embedding_ids=None):
        return [VectorHit(embedding_id=self._hit_embedding_id, distance=0.1)]


class _FakeStanceScorer:
    """Returns a CONTRAST stance for the configured contradicting passage, else a MENTION."""

    def __init__(self, contradicting_passage: str, contrast_confidence: float = 0.82) -> None:
        self._passage = contradicting_passage
        self._conf = contrast_confidence

    def classify_stance(self, *, sentence: str, passage: str) -> Stance:
        if passage == self._passage:
            return Stance("contrast", self._conf, {"support": 0.10, "contrast": self._conf, "mention": 0.08})
        return Stance("mention", 0.30, {"support": 0.30, "contrast": 0.10, "mention": 0.60})


def test_find_contested_claims_surfaces_contradiction() -> None:
    passage = "In a large preregistered replication, X had no measurable effect on Y."
    b_chunk_embedding_id = 501
    other_paper_id = 42
    contested = find_contested_claims(
        None,
        7,
        embed_model=_FakeEmbedModel(),
        vector_store=_FakeVectorStore(b_chunk_embedding_id),
        stance_scorer=_FakeStanceScorer(passage),
        resolve_chunk=lambda hit: ChunkInfo(paper_id=other_paper_id, text=passage, page=7),
        claim_sentences=["X reliably causes Y."],
        other_chunk_ids={b_chunk_embedding_id},
    )
    assert len(contested) == 1
    claim = contested[0]
    assert isinstance(claim, ContestedClaim)
    assert claim.other_paper_id == other_paper_id
    assert claim.stance == "contrast"
    assert claim.confidence >= 0.55
    assert claim.passage == passage  # verbatim grounding from the other paper
    assert claim.page == 7
    assert claim.claim == "X reliably causes Y."


def test_find_contested_claims_ignores_mention_only() -> None:
    # The stance scorer's contradicting passage is never the one resolve_chunk returns → only MENTION stances.
    contested = find_contested_claims(
        None,
        7,
        embed_model=_FakeEmbedModel(),
        vector_store=_FakeVectorStore(501),
        stance_scorer=_FakeStanceScorer("a passage the resolver never returns"),
        resolve_chunk=lambda hit: ChunkInfo(paper_id=42, text="A merely related, non-contradicting passage.", page=3),
        claim_sentences=["X reliably causes Y."],
        other_chunk_ids={501},
    )
    assert contested == []


def test_find_contested_claims_respects_threshold() -> None:
    passage = "X had no effect on Y in our sample."
    contested = find_contested_claims(
        None,
        7,
        embed_model=_FakeEmbedModel(),
        vector_store=_FakeVectorStore(501),
        stance_scorer=_FakeStanceScorer(passage, contrast_confidence=0.40),  # below the 0.55 default
        resolve_chunk=lambda hit: ChunkInfo(paper_id=42, text=passage, page=5),
        claim_sentences=["X reliably causes Y."],
        other_chunk_ids={501},
    )
    assert contested == []
