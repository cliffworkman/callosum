"""Optional, reversible LLM triage for critical-review items — the reference-noise UX fix's triage half.

Mirrors tests/test_registration_comparisons.py's inc-435 triage test shape: a bounded-advisory unit test on the
evaluator, an endpoint round-trip via a test-seam evaluator, and an egress-gate refusal test. Also covers the
ephemeral (never-persisted) Tier-1 contested-claims triage path, unique to this feature.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api import create_app
from app.backend.methods.critical_review_triage import TRIAGE_PROMPT_VERSION, CriticalReviewTriageEvaluator
from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence.critical_review_triage_repo import attach_candidate_triage, candidate_triage_fingerprint
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import critical_review_candidate_triage


def test_triage_is_bounded_advisory_and_keeps_unlabeled_items_visible() -> None:
    prompts = []

    def complete_fn(config, prompt):
        prompts.append(prompt)
        return SimpleNamespace(
            text='{"items":[{"item_id":1,"label":"likely_noise","show_in_triage":false,'
            '"rationale":"Looks like a citation list.","concerns":["Check the source section."]}]}'
        )

    items = [
        {
            "item_id": 1,
            "claim": "X causes Y",
            "evidence": "1. Smith 2020. 2. Jones 2021.",
            "stance": "contrast",
            "confidence": 0.7,
        },
        {
            "item_id": 2,
            "claim": "Z is robust",
            "evidence": "Z failed to replicate",
            "stance": "contrast",
            "confidence": 0.6,
        },
    ]
    evaluator = CriticalReviewTriageEvaluator(
        config=SimpleNamespace(provider="local", model="fixture-model"), complete_fn=complete_fn
    )
    result = evaluator.evaluate(items=items)
    assert result["status"]["status"] == "success"
    assert result["annotations"][1]["label"] == "likely_noise"
    assert result["annotations"][1]["show_in_triage"] is False
    # item 2 got no model label at all -> fails open as "uncertain", still visible
    assert result["annotations"][2]["label"] == "uncertain"
    assert result["annotations"][2]["show_in_triage"] is True
    assert "Return JSON only" in prompts[0]


def test_triage_bounds_total_input_tighter_for_managed_local() -> None:
    """Real measured worst-case input against the cloud-sized MAX_TOTAL_INPUT_CHARS was 39,879 chars --
    near-certain overflow on the managed Local AI preview's much smaller ~10,240-token window."""

    def complete_fn(config, prompt):
        assert len(prompt) < 15_000
        return SimpleNamespace(text='{"items":[]}')

    items = [
        {"item_id": i, "claim": "x" * 500, "evidence": "y" * 900, "stance": "contrast", "confidence": 0.5}
        for i in range(30)
    ]
    evaluator = CriticalReviewTriageEvaluator(
        config=SimpleNamespace(provider="managed_local", model="fixture-model"), complete_fn=complete_fn
    )
    result = evaluator.evaluate(items=items)
    assert result["status"]["status"] == "success"
    assert result["status"]["evaluated_count"] < 30  # items were dropped to fit the tighter managed_local budget


def test_single_paper_critical_read_triages_contested_claims_ephemerally(temp_db_url: str) -> None:
    from app.backend.embeddings.vector_store import VectorHit

    class FakeEmbed:
        name = version = "fake"
        dimension = 3
        normalization = "none"

        def encode_texts(self, texts):
            return [[0.1, 0.2, 0.3] for _ in texts]

    class OneHitStore:
        def search(self, conn, *, vector, top_k, candidate_embedding_ids=None):
            ids = list(candidate_embedding_ids or [])
            return [VectorHit(embedding_id=ids[0], distance=0.1)] if ids else []

    class ContrastScorer:
        def classify_stance(self, *, sentence, passage):
            from app.backend.summarization.verification import Stance

            return Stance("contrast", 0.9, {"support": 0.05, "contrast": 0.9, "mention": 0.05})

        def classify_stances(self, pairs):
            return [self.classify_stance(sentence=s, passage=p) for s, p in pairs]

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        from sqlalchemy import insert

        from app.backend.persistence import schema
        from app.backend.persistence.repository import create_attachment, create_chunk

        pid = create_paper(conn, title="A", abstract="X reliably causes Y.", csl_json={"title": "A"})
        other_pid = create_paper(conn, title="B", csl_json={"title": "B"})
        aid = create_attachment(
            conn,
            paper_id=other_pid,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="chk-b",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        other_chunk_id = create_chunk(
            conn,
            paper_id=other_pid,
            attachment_id=aid,
            text="X does not cause Y.",
            page_start=2,
            page_end=2,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="v1",
            source_attachment_checksum="chk",
        )
        conn.execute(
            insert(schema.embeddings).values(
                target_type="chunk",
                target_id=other_chunk_id,
                model_name="fake",
                model_version="v1",
                dimension=3,
                normalization="none",
                source_text_version="v1",
            )
        )

    app = create_app(db_url=temp_db_url)
    app.state.critical_review_deps = {
        "embed_model": FakeEmbed(),
        "vector_store": OneHitStore(),
        "stance_scorer": ContrastScorer(),
    }

    def complete_fn(config, prompt):
        return SimpleNamespace(
            text='{"items":[{"item_id":0,"label":"prioritize","show_in_triage":true,'
            '"rationale":"A direct contradiction.","concerns":[]}]}'
        )

    from app.backend.methods.critical_review_triage import CriticalReviewTriageEvaluator

    app.state.critical_review_triage_evaluator = CriticalReviewTriageEvaluator(
        config=SimpleNamespace(provider="local", model="fixture-model"), complete_fn=complete_fn
    )
    client = TestClient(app)
    started = client.post(f"/papers/{pid}/critical-read", json={"triage": True})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    for _ in range(200):
        job = client.get(f"/critical-read/{job_id}").json()
        if job["status"] in ("done", "error"):
            break
    assert job["status"] == "done", job
    claims = job["backbone"]["contested_claims"]
    assert claims, "expected at least one contested claim"
    assert claims[0]["llm_triage"]["label"] == "prioritize"
    assert job["backbone"]["triage_status"]["status"] == "success"
    engine.dispose()


def test_candidate_triage_endpoint_persists_and_is_read_time_attached(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        (cid,) = repo.insert_candidates(
            conn,
            pid,
            [
                {
                    "concern": "overstated causal claim",
                    "anchor_quote": "X reliably causes Y",
                    "page": 1,
                    "stance": "contrast",
                    "confidence": 0.8,
                    "signature": "sig1",
                }
            ],
        )

    def complete_fn(config, prompt):
        return SimpleNamespace(
            text='{"items":[{"item_id":%d,"label":"likely_noise","show_in_triage":false,'
            '"rationale":"Weak retrieval match.","concerns":["Double-check manually."]}]}' % cid
        )

    app = create_app(db_url=temp_db_url)
    app.state.critical_review_triage_evaluator = CriticalReviewTriageEvaluator(
        config=SimpleNamespace(provider="local", model="fixture-model"), complete_fn=complete_fn
    )
    client = TestClient(app)

    r = client.post("/critical-read/candidates/triage", json={"candidate_ids": [cid]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"]["status"] == "success"
    assert body["candidates"][0]["llm_triage"]["label"] == "likely_noise"

    # Read-time attach: GET the candidate list again (a fresh request, no re-triage call) still shows it.
    again = client.get(f"/papers/{pid}/critical-read/candidates").json()
    assert again["candidates"][0]["llm_triage"]["label"] == "likely_noise"
    assert again["candidates"][0]["llm_triage"]["status"] == "current"

    with engine.connect() as conn:
        stored = conn.execute(select(critical_review_candidate_triage)).mappings().one()
    assert stored["provider_id"] == "local" and stored["model_id"] == "fixture-model"
    assert stored["prompt_version"] == TRIAGE_PROMPT_VERSION
    engine.dispose()


def test_candidate_triage_honors_egress_gate(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        (cid,) = repo.insert_candidates(
            conn,
            pid,
            [
                {
                    "concern": "small sample",
                    "anchor_quote": "n = 12",
                    "signature": "sig1",
                    "stance": "contrast",
                    "confidence": 0.7,
                }
            ],
        )
    engine.dispose()

    class MustNotRun:
        def evaluate(self, *, items):
            raise AssertionError("egress gate must run before the evaluator")

    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    app = create_app(db_url=temp_db_url)
    app.state.critical_review_triage_evaluator = MustNotRun()
    client = TestClient(app)
    r = client.post("/critical-read/candidates/triage", json={"candidate_ids": [cid]})
    assert r.status_code == 200
    assert r.json()["status"]["status"] == "unavailable"
    assert "egress consent" in r.json()["status"]["detail"]


def test_candidate_triage_degrades_safely_on_malformed_model_output(temp_db_url: str) -> None:
    """A malformed/non-JSON model response (bare json.loads() inside evaluate(), no try/except at that layer)
    must degrade to a safe "failed" status through this router's own broad catch -- never an unhandled 500.
    Critical Review triage previously lacked this safety net, unlike its funding/registration siblings."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        (cid,) = repo.insert_candidates(
            conn,
            pid,
            [{"concern": "x", "anchor_quote": "y", "signature": "sig1", "stance": "contrast", "confidence": 0.7}],
        )
    engine.dispose()

    def complete_fn(config, prompt):
        return SimpleNamespace(text="not json at all, no braces")

    app = create_app(db_url=temp_db_url)
    app.state.critical_review_triage_evaluator = CriticalReviewTriageEvaluator(
        config=SimpleNamespace(provider="local", model="fixture-model"), complete_fn=complete_fn
    )
    client = TestClient(app)
    r = client.post("/critical-read/candidates/triage", json={"candidate_ids": [cid]})
    assert r.status_code == 200, r.text
    assert r.json()["status"]["status"] == "failed"
    assert "still shown untriaged" in r.json()["status"]["detail"]


def test_candidate_triage_reports_managed_local_not_ready_not_a_raw_crash(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.backend.llm.managed_local import ManagedLocalTargetError

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        (cid,) = repo.insert_candidates(
            conn,
            pid,
            [{"concern": "x", "anchor_quote": "y", "signature": "sig1", "stance": "contrast", "confidence": 0.7}],
        )
    engine.dispose()

    def _raise(app):
        raise ManagedLocalTargetError("descriptor_unreadable")

    monkeypatch.setattr("app.backend.api.routers.critical_review_triage.resolve_llm_config", _raise)
    app = create_app(db_url=temp_db_url)
    client = TestClient(app)
    r = client.post("/critical-read/candidates/triage", json={"candidate_ids": [cid]})
    assert r.status_code == 200, r.text
    assert r.json()["status"]["status"] == "unavailable"
    assert "Local AI is not ready (descriptor_unreadable)" in r.json()["status"]["detail"]


def test_candidate_triage_fingerprint_detects_content_drift() -> None:
    candidate = {
        "id": 1,
        "concern": "overstated",
        "anchor_quote": "we prove causation",
        "stance": "contrast",
        "confidence": 0.8,
        "page": 1,
    }
    fp_before = candidate_triage_fingerprint(candidate)
    stored = {
        1: {
            "label": "prioritize",
            "show_in_triage": True,
            "rationale": None,
            "concerns": [],
            "basis": None,
            "provider_id": "local",
            "model_id": None,
            "prompt_version": TRIAGE_PROMPT_VERSION,
            "evidence_fingerprint": fp_before,
        }
    }

    attached_current = attach_candidate_triage([candidate], stored, current_prompt_version=TRIAGE_PROMPT_VERSION)
    assert attached_current[1]["status"] == "current"

    drifted = {**candidate, "concern": "a materially different concern"}
    attached_stale = attach_candidate_triage([drifted], stored, current_prompt_version=TRIAGE_PROMPT_VERSION)
    assert attached_stale[1]["status"] == "stale"
    assert "candidate-evidence-changed" in attached_stale[1]["stale_reasons"]
