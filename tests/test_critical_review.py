"""Critical-review supplement (backlog #12) — the single-paper "scrutiny surface" MVP.

Tier 1 is deterministic/local; Tier 2 is egress-gated LLM candidates through the #13 verbatim-quote bar. Tests
inject fakes for the NLI stance scorer / vector store / generator so they stay hermetic + fast (no model loads).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, insert, update

from app.backend.api import create_app
from app.backend.embeddings.vector_store import VectorHit
from app.backend.methods.critical_review import (
    ChunkInfo,
    ContestedClaim,
    ScrutinyBackbone,
    build_scrutiny_backbone,
    extract_claim_sentences,
    find_contested_claims,
    make_chunk_resolver,
    other_paper_chunk_embedding_ids,
    search_contested_claims,
)
from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence import findings_repo, schema, signals_repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
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


class _RecordingBatchEmbed:
    name = version = "fake-batch"
    dimension = 1
    normalization = "none"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(index)] for index in range(1, len(texts) + 1)]


class _VectorMappedStore:
    def __init__(self, hits_by_vector: dict[int, list[int]]) -> None:
        self.hits_by_vector = hits_by_vector
        self.vectors: list[int] = []

    def search(self, conn, *, vector, top_k, candidate_embedding_ids=None):
        key = int(vector[0])
        self.vectors.append(key)
        return [VectorHit(embedding_id=item, distance=0.1) for item in self.hits_by_vector.get(key, [])][:top_k]


class _RecordingBatchStance:
    def __init__(self, confidence_by_passage: dict[str, tuple[str, float]]) -> None:
        self.confidence_by_passage = confidence_by_passage
        self.calls: list[list[tuple[str, str]]] = []

    def classify_stances(self, pairs: list[tuple[str, str]]) -> list[Stance]:
        self.calls.append(list(pairs))
        out: list[Stance] = []
        for _, passage in pairs:
            label, confidence = self.confidence_by_passage[passage]
            probs = {"support": 0.1, "contrast": 0.1, "mention": 0.1, label: confidence}
            out.append(Stance(label, confidence, probs))
        return out


def test_search_contested_claims_batches_and_preserves_claim_hit_mapping() -> None:
    claims = ["Repeated claim.", "Second claim.", "Repeated claim."]
    passages = {
        101: ChunkInfo(41, "related mention", 1),
        102: ChunkInfo(42, "repeated passage", 2),
        104: ChunkInfo(43, "stronger contrast", 3),
        105: ChunkInfo(44, "repeated passage", 4),
    }
    embed = _RecordingBatchEmbed()
    store = _VectorMappedStore({1: [101, 102, 999], 2: [103, 104], 3: [105]})
    scorer = _RecordingBatchStance(
        {
            "related mention": ("mention", 0.9),
            "repeated passage": ("contrast", 0.61),
            "stronger contrast": ("contrast", 0.81),
        }
    )
    report = search_contested_claims(
        None,
        7,
        embed_model=embed,
        vector_store=store,
        stance_scorer=scorer,
        resolve_chunk=lambda hit: passages.get(hit.embedding_id),
        claim_sentences=claims,
        other_chunk_ids={101, 102, 103, 104, 105},
    )

    assert embed.calls == [claims]
    assert store.vectors == [1, 2, 3]
    assert scorer.calls == [
        [
            ("Repeated claim.", "related mention"),
            ("Repeated claim.", "repeated passage"),
            ("Second claim.", "stronger contrast"),
            ("Repeated claim.", "repeated passage"),
        ]
    ]
    assert [(item.claim, item.passage, item.other_paper_id, item.confidence) for item in report.contested_claims] == [
        ("Repeated claim.", "repeated passage", 42, 0.61),
        ("Second claim.", "stronger contrast", 43, 0.81),
        ("Repeated claim.", "repeated passage", 44, 0.61),
    ]
    assert report.retrieved_passages == report.classified_passages == 4


def test_search_contested_claims_batches_maximum_normal_claim_count() -> None:
    claims = ["Same bounded claim."] * 12
    embed = _RecordingBatchEmbed()
    store = _VectorMappedStore({index: [501] for index in range(1, 13)})
    scorer = _RecordingBatchStance({"Same passage.": ("contrast", 0.75)})

    report = search_contested_claims(
        None,
        7,
        embed_model=embed,
        vector_store=store,
        stance_scorer=scorer,
        resolve_chunk=lambda hit: ChunkInfo(42, "Same passage.", 3),
        claim_sentences=claims + ["Beyond the cap."],
        other_chunk_ids={501},
    )

    assert len(embed.calls) == 1 and len(embed.calls[0]) == 12
    assert len(scorer.calls) == 1 and len(scorer.calls[0]) == 12
    assert report.claims_considered == 12 and len(report.contested_claims) == 12


def test_search_contested_claims_zero_claims_skips_both_models() -> None:
    embed = _RecordingBatchEmbed()
    scorer = _RecordingBatchStance({})
    report = search_contested_claims(
        None,
        7,
        embed_model=embed,
        vector_store=_VectorMappedStore({}),
        stance_scorer=scorer,
        resolve_chunk=lambda hit: None,
        claim_sentences=[],
        other_chunk_ids={501},
    )

    assert report.retrieval_status == "no-claims"
    assert embed.calls == [] and scorer.calls == []


# --- Task 3: tier-1 scrutiny backbone + real DB-backed retrieval helpers (real temp SQLite, no model loads) ---


def _fresh_db():
    eng = create_engine("sqlite://")
    schema.metadata.create_all(eng)
    return eng


def _paper_with_attachment(conn, title: str) -> tuple[int, int]:
    pid = create_paper(conn, title=title, csl_json={"title": title})
    aid = create_attachment(
        conn,
        paper_id=pid,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum=f"chk-{title}",
        import_source="test",
        attachment_type="pdf",
        role="primary",
    )
    return pid, aid


def _chunk_with_embedding(conn, paper_id: int, attachment_id: int, *, text: str, page: int) -> tuple[int, int]:
    chunk_id = create_chunk(
        conn,
        paper_id=paper_id,
        attachment_id=attachment_id,
        text=text,
        page_start=page,
        page_end=page,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="test",
        extraction_version="1",
        chunking_strategy="paragraph",
        chunk_version="v1",
        source_attachment_checksum="chk",
    )
    embedding_id = int(
        conn.execute(
            insert(schema.embeddings).values(
                target_type="chunk",
                target_id=chunk_id,
                model_name="fake",
                model_version="v1",
                dimension=3,
                normalization="none",
                source_text_version="v1",
            )
        ).inserted_primary_key[0]
    )
    return chunk_id, embedding_id


def test_build_scrutiny_backbone_gathers_stored_signals() -> None:
    eng = _fresh_db()
    with eng.begin() as c:
        pid = create_paper(c, title="P", csl_json={"title": "P"})
        # a stored deterministic CHECK-STATUS signal (statcheck flagged) → open_science_signals
        signals_repo.store_statcheck(c, pid, checked=12, inconsistent=3, decision_errors=0)
        # a stored FACT → paper_findings
        findings_repo.upsert_findings(
            c,
            pid,
            "retraction",
            [
                {
                    "kind": "fact",
                    "payload": {
                        "status": "retracted",
                        "reason": "data issue",
                        "notice_url": "https://doi.org/10.1/notice",
                    },
                }
            ],
        )
        fake_contested = [
            ContestedClaim(
                claim="X causes Y.", passage="not so", other_paper_id=9, page=2, stance="contrast", confidence=0.7
            )
        ]
        backbone = build_scrutiny_backbone(c, pid, contested_claims=fake_contested)

    assert isinstance(backbone, ScrutinyBackbone)
    kinds = {s["kind"] for s in backbone.method_signals}
    assert "statcheck" in kinds  # from open_science_signals
    assert "retraction" in kinds  # from the paper_findings FACT
    for s in backbone.method_signals:  # the fixed {kind, label, detail, notice_url} shape
        assert set(s.keys()) == {"kind", "label", "detail", "notice_url"}
    statcheck = next(s for s in backbone.method_signals if s["kind"] == "statcheck")
    assert "3 inconsistent" in statcheck["detail"]  # grounded in the stored counts, no re-run
    assert statcheck["notice_url"] is None  # only a retraction FACT ever carries a registry notice link
    retraction = next(s for s in backbone.method_signals if s["kind"] == "retraction")
    assert retraction["notice_url"] == "https://doi.org/10.1/notice"  # passed through verbatim, never re-derived
    assert backbone.contested_claims == fake_contested  # the passed-in claims, not recomputed
    assert backbone.citation_signal is None  # concentration/overlooked is network-based → no local Tier-1 read


def test_build_scrutiny_backbone_empty_is_honest_not_clean() -> None:
    eng = _fresh_db()
    with eng.begin() as c:
        pid = create_paper(c, title="Bare", csl_json={"title": "Bare"})
        backbone = build_scrutiny_backbone(c, pid, contested_claims=[])
    # Empty is the honest "these checks surfaced nothing", NOT a clean bill of health (silence != certificate).
    assert backbone.method_signals == []
    assert backbone.contested_claims == []
    assert backbone.citation_signal is None


def test_build_scrutiny_backbone_excludes_not_applicable() -> None:
    eng = _fresh_db()
    with eng.begin() as c:
        pid = create_paper(c, title="P", csl_json={"title": "P"})
        # precondition-not-met → contributes nothing to the scrutiny surface
        c.execute(
            insert(schema.open_science_signals).values(
                paper_id=pid, signal_type="transparency", source="registration", status="not-applicable"
            )
        )
        # applicable, auditor ran + did not surface it → a review prompt, kept
        c.execute(
            insert(schema.open_science_signals).values(
                paper_id=pid, signal_type="transparency", source="data_availability", status="not-detected"
            )
        )
        backbone = build_scrutiny_backbone(c, pid, contested_claims=[])
    transparency = [s for s in backbone.method_signals if s["kind"] == "transparency"]
    assert len(transparency) == 1
    assert transparency[0]["detail"] == "not-detected"


def test_extract_claim_sentences_from_abstract() -> None:
    eng = _fresh_db()
    with eng.begin() as c:
        pid = create_paper(
            c,
            title="P",
            csl_json={"title": "P"},
            abstract="X causes Y. We tested Z in a trial. Results were significant.",
        )
        sents = extract_claim_sentences(c, pid, max_claims=12)
    assert len(sents) == 3
    assert sents[0] == "X causes Y."
    assert sents[-1] == "Results were significant."


def test_extract_claim_sentences_respects_max() -> None:
    abstract = " ".join(f"Sentence number {i} makes a claim." for i in range(20))
    eng = _fresh_db()
    with eng.begin() as c:
        pid = create_paper(c, title="P", csl_json={"title": "P"}, abstract=abstract)
        sents = extract_claim_sentences(c, pid, max_claims=5)
    assert len(sents) == 5


def test_extract_claim_sentences_falls_back_to_chunk_then_empty() -> None:
    eng = _fresh_db()
    with eng.begin() as c:
        # no abstract, but a first stored chunk → falls back to it
        pid, aid = _paper_with_attachment(c, "NoAbs")
        _chunk_with_embedding(c, pid, aid, text="A first chunk sentence. And a second one.", page=1)
        sents = extract_claim_sentences(c, pid)
        assert sents and sents[0] == "A first chunk sentence."
        # neither abstract nor chunks → honest empty
        bare = create_paper(c, title="Bare", csl_json={"title": "Bare"})
        assert extract_claim_sentences(c, bare) == []


def test_other_paper_chunk_embedding_ids() -> None:
    eng = _fresh_db()
    with eng.begin() as c:
        pid_a, aid_a = _paper_with_attachment(c, "A")
        pid_b, aid_b = _paper_with_attachment(c, "B")
        _, emb_a = _chunk_with_embedding(c, pid_a, aid_a, text="a", page=1)
        _, emb_b = _chunk_with_embedding(c, pid_b, aid_b, text="b", page=1)

        ids = other_paper_chunk_embedding_ids(c, pid_a)
        assert emb_b in ids  # the OTHER paper's chunk-embedding
        assert emb_a not in ids  # never this paper's own

        # soft-deleting B removes its chunk-embeddings from the corpus
        c.execute(update(schema.papers).where(schema.papers.c.id == pid_b).values(deleted_at=func.current_timestamp()))
        assert other_paper_chunk_embedding_ids(c, pid_a) == set()


def test_make_chunk_resolver_resolves_and_misses() -> None:
    eng = _fresh_db()
    with eng.begin() as c:
        pid, aid = _paper_with_attachment(c, "A")
        _, emb = _chunk_with_embedding(c, pid, aid, text="the contradicting passage", page=4)
        resolve = make_chunk_resolver(c)

        info = resolve(VectorHit(embedding_id=emb, distance=0.1))
        assert isinstance(info, ChunkInfo)
        assert info.paper_id == pid
        assert info.text == "the contradicting passage"
        assert info.page == 4

        assert resolve(VectorHit(embedding_id=999999, distance=0.1)) is None  # unknown embedding id


# --- Task 4: the critical-read router (async job + candidate accept/reject) — hermetic (fake deps, no model loads) ---


class _EmptyVectorStore:
    """A vector store that finds nothing — the job completes with no contested claims (deterministic test)."""

    def search(self, conn, *, vector, top_k, candidate_embedding_ids=None):
        return []


def test_critical_read_endpoints(temp_db_url) -> None:
    app = create_app(db_url=temp_db_url)
    app.state.critical_review_deps = {  # the router's test seam → no NLI/embedding model loads
        "embed_model": _FakeEmbedModel(),
        "vector_store": _EmptyVectorStore(),
        "stance_scorer": _FakeStanceScorer("unused"),
    }
    client = TestClient(app)
    with make_engine(temp_db_url).begin() as conn:
        pid = create_paper(
            conn, title="P", abstract="X reliably causes Y. A second claim sentence.", csl_json={"title": "P"}
        )
        (cid,) = repo.insert_candidates(
            conn,
            pid,
            [
                {
                    "concern": "overstated causal claim",
                    "anchor_quote": "X reliably causes Y",
                    "page": 1,
                    "stance": "contrast",
                    "confidence": 0.7,
                    "signature": "sig-t4",
                }
            ],
        )

    start = client.post(f"/papers/{pid}/critical-read")
    assert start.status_code == 202
    job_id = start.json()["job_id"]
    done = client.get(f"/critical-read/{job_id}").json()
    assert done["status"] == "done" and done["backbone"] is not None
    assert done["backbone"]["contested_claims"] == []  # empty vector store → nothing contested
    timing_job = app.state.critical_review_jobs.get(job_id)
    assert [stage.key for stage in timing_job.completed_stages] == [
        "preparing_evidence",
        "embedding_claims",
        "evaluating_evidence",
        "finalizing_result",
    ]

    cands = client.get(f"/papers/{pid}/critical-read/candidates").json()["candidates"]
    assert len(cands) == 1 and cands[0]["concern"] == "overstated causal claim" and cands[0]["status"] == "pending"

    assert client.post(f"/critical-read/candidates/{cid}/reject").json()["status"] == "rejected"
    after = client.get(f"/papers/{pid}/critical-read/candidates").json()["candidates"]
    assert after[0]["status"] == "rejected"

    assert client.post("/papers/999999/critical-read").status_code == 404
    assert client.get("/critical-read/does-not-exist").status_code == 404
    assert client.post("/critical-read/candidates/999999/accept").status_code == 404


# --- Task 5: Tier-2 verified candidates (egress-gated) ----------------------------------------------------------


def test_verify_candidates_keeps_only_grounded_and_skips_rejected():
    from types import SimpleNamespace

    from integrations.gemini.critical_review import CandidateDraft, candidate_signature, verify_candidates

    class _Stance:
        def classify_stance(self, *, sentence, passage):
            return SimpleNamespace(label="contrast", confidence=0.7)

    text = "We prove causation between X and Y in every condition tested."
    drafts = [
        CandidateDraft(concern="causal overreach", anchor_quote="We prove causation between X and Y"),  # verbatim
        CandidateDraft(concern="not grounded", anchor_quote="a sentence that is absent from the paper"),  # dropped
    ]
    verified = verify_candidates(drafts, paper_id=1, paper_text=text, stance_scorer=_Stance())
    assert [v["concern"] for v in verified] == ["causal overreach"]  # ungrounded draft dropped (#13 honest shortfall)
    assert verified[0]["stance"] == "contrast" and verified[0]["confidence"] == 0.7 and verified[0]["signature"]
    # a previously-rejected signature is never re-created
    sig = candidate_signature(1, "causal overreach", "We prove causation between X and Y")
    assert (
        verify_candidates(drafts, paper_id=1, paper_text=text, stance_scorer=_Stance(), rejected_signatures={sig}) == []
    )


def test_verify_candidates_batches_only_grounded_unique_pairs_in_order() -> None:
    from types import SimpleNamespace

    from integrations.gemini.critical_review import CandidateDraft, verify_candidates

    class _BatchStance:
        def __init__(self) -> None:
            self.calls: list[list[tuple[str, str]]] = []

        def classify_stances(self, pairs):
            self.calls.append(list(pairs))
            return [
                SimpleNamespace(label="contrast", confidence=0.71),
                SimpleNamespace(label="mention", confidence=0.62),
            ]

    scorer = _BatchStance()
    drafts = [
        CandidateDraft("Concern A", "Grounded quote A."),
        CandidateDraft("Ungrounded", "Absent quote."),
        CandidateDraft("Concern B", "Grounded quote B."),
        CandidateDraft("Concern A", "Grounded quote A."),
    ]
    out = verify_candidates(
        drafts,
        paper_id=1,
        paper_text="Grounded quote A. Grounded quote B.",
        stance_scorer=scorer,
    )

    assert scorer.calls == [[("Concern A", "Grounded quote A."), ("Concern B", "Grounded quote B.")]]
    assert [(item["concern"], item["stance"], item["confidence"]) for item in out] == [
        ("Concern A", "contrast", 0.71),
        ("Concern B", "mention", 0.62),
    ]


def test_generate_candidates_endpoint_verifies_and_egress_gates(temp_db_url, monkeypatch):
    from types import SimpleNamespace

    from integrations.gemini.critical_review import CandidateDraft

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(
            conn, title="P", abstract="We prove causation between X and Y in all cases.", csl_json={"title": "P"}
        )
    engine.dispose()

    class _FakeGen:
        def propose(self, *, paper_text):
            return [
                CandidateDraft(concern="causal overreach", anchor_quote="We prove causation between X and Y"),
                CandidateDraft(concern="ungrounded", anchor_quote="text not present anywhere in the paper"),
            ]

    class _FakeStance:
        def classify_stance(self, *, sentence, passage):
            return SimpleNamespace(label="contrast", confidence=0.6)

    app = create_app(db_url=temp_db_url)
    app.state.critical_review_generator = _FakeGen()
    app.state.critical_review_deps = {"embed_model": None, "vector_store": None, "stance_scorer": _FakeStance()}
    client = TestClient(app)

    # egress ON (conftest default): only the grounded candidate persists, as pending
    r = client.post(f"/papers/{pid}/critical-read/candidates/generate")
    assert r.status_code == 200, r.text
    cands = r.json()["candidates"]
    assert len(cands) == 1 and cands[0]["concern"] == "causal overreach" and cands[0]["status"] == "pending"

    # egress OFF: honest refusal, no crash, no new candidates
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    r2 = client.post(f"/papers/{pid}/critical-read/candidates/generate")
    assert r2.status_code == 422


# --- Task 7: Principles guard (signal not verdict; no composite score; no author-directed judgment) -------------


def test_no_composite_score_field_and_no_author_directed_copy():
    import pathlib

    # (1) The API responses expose per-item confidence ONLY — no composite quality/score/verdict field (Principle #7).
    from app.backend.api.routers.critical_review import CandidateResponse, ScrutinyBackboneResponse

    banned_fields = {"quality", "score", "overall", "grade", "rating", "verdict"}
    for model in (CandidateResponse, ScrutinyBackboneResponse):
        assert not (set(model.model_fields) & banned_fields), f"{model.__name__} exposes a composite-score field"

    # (2) Our static UI + prompt copy carries no author-directed judgment (A-A no-accusation veto).
    banned_phrases = ["the authors are", "the author is", "sloppy", "dishonest", "incompetent", "fraud", "bad science"]
    for rel in ("app/frontend/js/08x_methods_critical.jsx", "integrations/gemini/critical_review.py"):
        text = pathlib.Path(rel).read_text(encoding="utf-8").lower()
        for phrase in banned_phrases:
            assert phrase not in text, f"{rel}: banned author-directed phrase {phrase!r}"
