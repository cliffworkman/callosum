"""Set (multi-paper) critical review — backlog #12. Engine + Tier-2 + endpoint tests, hermetic (injected fakes)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, update

from app.backend.api import create_app
from app.backend.embeddings.vector_store import VectorHit
from app.backend.methods.critical_review_set import set_aggregate, set_chunk_embedding_ids, set_contested_claims
from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence import schema, signals_repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.summarization.verification import Stance
from integrations.gemini.critical_review import candidate_signature
from integrations.gemini.critical_review_set import (
    SetCandidateDraft,
    parse_set_drafts,
    verify_set_candidates,
)


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


def _chunk_with_embedding(
    conn, paper_id: int, attachment_id: int, *, text: str, page: int, section: str | None = None
) -> tuple[int, int]:
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
        section=section,
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


class _FakeEmbed:
    name = version = "fake"
    dimension = 3
    normalization = "none"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode_texts(self, texts):
        self.calls.append(list(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]


class _CandidateRespectingVectorStore:
    """Returns a hit for each seeded embedding_id that IS in candidate_embedding_ids — so set-scoping is honored."""

    def __init__(self, known_ids):
        self._known = set(known_ids)

    def search(self, conn, *, vector, top_k, candidate_embedding_ids=None):
        cand = set(candidate_embedding_ids or set())
        return [VectorHit(embedding_id=eid, distance=0.1) for eid in sorted(self._known & cand)][:top_k]


class _ContrastStance:
    def __init__(self) -> None:
        self.batch_calls: list[list[tuple[str, str]]] = []

    def classify_stance(self, *, sentence, passage):
        return Stance("contrast", 0.8, {"support": 0.1, "contrast": 0.8, "mention": 0.1})

    def classify_stances(self, pairs):
        self.batch_calls.append(list(pairs))
        return [self.classify_stance(sentence=sentence, passage=passage) for sentence, passage in pairs]


def test_related_paper_ids_roundtrips(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="A", csl_json={"title": "A"})
        [cid] = repo.insert_candidates(
            conn,
            pid,
            [
                {
                    "concern": "small sample",
                    "anchor_quote": "n = 12",
                    "signature": "sig1",
                    "stance": "contrast",
                    "confidence": 0.7,
                    "related_paper_ids": [pid + 1, pid + 2],
                }
            ],
        )
        rows = repo.list_candidates(conn, pid)
    engine.dispose()
    assert cid > 0
    assert rows[0]["related_paper_ids_json"] == [pid + 1, pid + 2]


def test_set_chunk_embedding_ids_scopes_to_set():
    eng = _fresh_db()
    with eng.begin() as c:
        a, aa = _paper_with_attachment(c, "A")
        b, ab = _paper_with_attachment(c, "B")
        cc, ac = _paper_with_attachment(c, "C")
        _, _a_emb = _chunk_with_embedding(c, a, aa, text="alpha", page=1)
        _, b_emb = _chunk_with_embedding(c, b, ab, text="beta", page=1)
        _, _c_emb = _chunk_with_embedding(c, cc, ac, text="gamma", page=1)
        got = set_chunk_embedding_ids(c, [a, b], a)
    eng.dispose()
    assert got == {b_emb}  # only B (in-set, other); excludes A (self) and C (not in set)


def test_set_chunk_embedding_ids_excludes_references_section():
    # A bibliography is not substantive contrasting prose -- must never enter the set's own corpus.
    eng = _fresh_db()
    with eng.begin() as c:
        a, aa = _paper_with_attachment(c, "A")
        b, ab = _paper_with_attachment(c, "B")
        _, b_body = _chunk_with_embedding(c, b, ab, text="a body passage", page=1)
        _, b_refs = _chunk_with_embedding(c, b, ab, text="1. Smith et al. 2020.", page=9, section="references")
        got = set_chunk_embedding_ids(c, [a, b], a)
    eng.dispose()
    assert got == {b_body}
    assert b_refs not in got


def test_set_contested_only_surfaces_intra_set():
    eng = _fresh_db()
    with eng.begin() as c:
        a, _aa = _paper_with_attachment(c, "A")
        b, ab = _paper_with_attachment(c, "B")
        cc, ac = _paper_with_attachment(c, "C")
        c.execute(update(schema.papers).where(schema.papers.c.id == a).values(abstract="X strongly causes Y."))
        _, b_emb = _chunk_with_embedding(c, b, ab, text="X does not cause Y.", page=3)
        _, c_emb = _chunk_with_embedding(c, cc, ac, text="X does not cause Y either.", page=4)
        store = _CandidateRespectingVectorStore({b_emb, c_emb})
        rows = set_contested_claims(
            c, [a, b], embed_model=_FakeEmbed(), vector_store=store, stance_scorer=_ContrastStance()
        )
    eng.dispose()
    assert len(rows) == 1  # C is not in the set → excluded by set-scoping
    assert rows[0]["claim_paper_id"] == a
    assert rows[0]["other_paper_id"] == b
    assert rows[0]["stance"] == "contrast"


def test_set_contested_claims_batches_across_all_papers() -> None:
    eng = _fresh_db()
    embed, stance = _FakeEmbed(), _ContrastStance()
    with eng.begin() as c:
        a, aa = _paper_with_attachment(c, "A")
        b, ab = _paper_with_attachment(c, "B")
        c.execute(update(schema.papers).where(schema.papers.c.id == a).values(abstract="A one. A two."))
        c.execute(update(schema.papers).where(schema.papers.c.id == b).values(abstract="B one. B two."))
        _, a_emb = _chunk_with_embedding(c, a, aa, text="Passage A", page=1)
        _, b_emb = _chunk_with_embedding(c, b, ab, text="Passage B", page=2)

        rows = set_contested_claims(
            c,
            [a, b],
            embed_model=embed,
            vector_store=_CandidateRespectingVectorStore({a_emb, b_emb}),
            stance_scorer=stance,
        )
    eng.dispose()

    assert embed.calls == [["A one.", "A two.", "B one.", "B two."]]
    assert stance.batch_calls == [
        [
            ("A one.", "Passage B"),
            ("A two.", "Passage B"),
            ("B one.", "Passage A"),
            ("B two.", "Passage A"),
        ]
    ]
    assert [(row["claim_paper_id"], row["claim"], row["other_paper_id"]) for row in rows] == [
        (a, "A one.", b),
        (a, "A two.", b),
        (b, "B one.", a),
        (b, "B two.", a),
    ]


def test_set_aggregate_is_a_fact_matrix_not_a_score():
    eng = _fresh_db()
    with eng.begin() as c:
        a, _ = _paper_with_attachment(c, "A")
        b, _ = _paper_with_attachment(c, "B")
        signals_repo.store_statcheck(c, a, checked=10, inconsistent=2, decision_errors=0)
        contested = [
            {
                "claim_paper_id": a,
                "other_paper_id": b,
                "claim": "x",
                "passage": "y",
                "page": 1,
                "stance": "contrast",
                "confidence": 0.7,
            }
        ]
        rows = set_aggregate(c, [a, b], contested)
    eng.dispose()
    by_id = {r["paper_id"]: r for r in rows}
    assert {r["title"] for r in rows} == {"A", "B"}
    assert any(s["kind"] == "statcheck" for s in by_id[a]["method_signals"])
    assert by_id[a]["contested_count"] == 1
    assert by_id[b]["method_signals"] == []  # honest empty, never "clean"
    assert by_id[b]["contested_count"] == 0
    for r in rows:  # honesty: no composite score / ranking field
        assert not ({"score", "quality", "grade", "rank", "rating"} & set(r.keys()))


def _set_papers():
    return [
        {"index": 1, "paper_id": 101, "text": "Alpha alpha. The sample was n = 12 participants. Beta."},
        {"index": 2, "paper_id": 102, "text": "Gamma. We used a within-subjects design. Delta."},
    ]


def test_verify_set_candidates_grounds_anchor_and_relates():
    drafts = [SetCandidateDraft("Small sample.", "The sample was n = 12 participants.", [1, 2, 99])]
    out = verify_set_candidates(drafts, set_papers=_set_papers(), stance_scorer=_ContrastStance())
    assert len(out) == 1
    assert out[0]["paper_id"] == 101  # anchored where the quote lives
    assert out[0]["related_paper_ids"] == [102]  # index 2 -> 102; index 1 is the anchor; 99 invalid -> dropped
    assert out[0]["stance"] == "contrast"
    assert out[0]["anchor_quote"] == "The sample was n = 12 participants."


def test_verify_set_candidates_batches_grounded_pairs_without_reordering() -> None:
    scorer = _ContrastStance()
    drafts = [
        SetCandidateDraft("Small sample.", "The sample was n = 12 participants.", [1, 2]),
        SetCandidateDraft("Repeated design.", "We used a within-subjects design.", [2, 1]),
    ]
    out = verify_set_candidates(drafts, set_papers=_set_papers(), stance_scorer=scorer)

    assert scorer.batch_calls == [
        [
            ("Small sample.", "The sample was n = 12 participants."),
            ("Repeated design.", "We used a within-subjects design."),
        ]
    ]
    assert [(item["paper_id"], item["concern"]) for item in out] == [
        (101, "Small sample."),
        (102, "Repeated design."),
    ]


def test_verify_set_candidates_drops_ungrounded_and_rejected():
    good = SetCandidateDraft("c", "We used a within-subjects design.", [])
    bad = SetCandidateDraft("c2", "a quote appearing in no paper at all", [])
    sig = candidate_signature(102, "c", "We used a within-subjects design.")
    out = verify_set_candidates(
        [good, bad], set_papers=_set_papers(), stance_scorer=_ContrastStance(), rejected_signatures={sig}
    )
    assert out == []  # good is rejected-by-signature; bad is ungrounded


def test_verify_set_output_has_no_author_or_score_fields():
    drafts = [SetCandidateDraft("Small sample.", "The sample was n = 12 participants.", [])]
    out = verify_set_candidates(drafts, set_papers=_set_papers(), stance_scorer=_ContrastStance())
    blob = json.dumps(out).lower()
    for banned in ("the authors are", "sloppy", "dishonest", "fraud", "incompetent"):
        assert banned not in blob
    assert not ({"score", "quality", "grade", "rating", "verdict"} & set(out[0].keys()))


def test_set_prompt_bounds_paper_text_tighter_for_managed_local_than_cloud():
    """The managed Local AI preview's ~10,240-token input budget is a fraction of the cloud-sized
    _MAX_SET_PROMPT_CHARS above (measured real worst-case input: 20,565 chars -- already at/past the cloud
    cap). Every set paper still gets representation (truncated, never dropped)."""
    from integrations.gemini.critical_review_set import (
        _MAX_SET_PROMPT_CHARS,
        _MAX_SET_PROMPT_CHARS_MANAGED_LOCAL,
        _set_prompt,
    )

    set_papers = [{"index": i + 1, "paper_id": i, "text": "x" * 5000} for i in range(5)]

    cloud_prompt = _set_prompt(set_papers, provider="gemini")
    managed_prompt = _set_prompt(set_papers, provider="managed_local")

    assert _MAX_SET_PROMPT_CHARS_MANAGED_LOCAL < _MAX_SET_PROMPT_CHARS
    assert len(managed_prompt) < len(cloud_prompt)
    assert managed_prompt.count("[1]") == 1 and managed_prompt.count("[5]") == 1  # every paper still represented


def test_parse_set_drafts_defensive():
    assert parse_set_drafts("not json") == []
    drafts = parse_set_drafts('[{"concern":"c","anchor_quote":"q","related":[1,2]}]')
    assert drafts[0].concern == "c" and drafts[0].related_indices == [1, 2]


class _EmptyVectorStore:
    def search(self, conn, *, vector, top_k, candidate_embedding_ids=None):
        return []


def _cr_set_app(temp_db_url):
    app = create_app(db_url=temp_db_url)
    app.state.critical_review_deps = {
        "embed_model": _FakeEmbed(),
        "vector_store": _EmptyVectorStore(),
        "stance_scorer": _ContrastStance(),
    }
    return app


def _poll_set(client, job_id):
    for _ in range(30):
        d = client.get(f"/critical-read/set/{job_id}").json()
        if d["status"] in {"done", "error"}:
            return d
    raise AssertionError("job did not finish")


def test_set_validation(temp_db_url):
    client = TestClient(_cr_set_app(temp_db_url))
    with make_engine(temp_db_url).begin() as conn:
        a = create_paper(conn, title="A", csl_json={"title": "A"})
    assert client.post("/critical-read/set", json={"paper_ids": [a]}).status_code == 422  # < 2
    assert client.post("/critical-read/set", json={"paper_ids": list(range(1, 20))}).status_code == 422  # > 12
    assert client.post("/critical-read/set", json={"paper_ids": [a, 999999]}).status_code == 404


def test_set_tier1_report(temp_db_url):
    app = _cr_set_app(temp_db_url)
    client = TestClient(app)
    with make_engine(temp_db_url).begin() as conn:
        a = create_paper(conn, title="A", csl_json={"title": "A"})
        b = create_paper(conn, title="B", csl_json={"title": "B"})
    job_id = client.post("/critical-read/set", json={"paper_ids": [a, b]}).json()["job_id"]
    done = _poll_set(client, job_id)
    assert done["status"] == "done"
    assert len(done["report"]["aggregate"]) == 2
    assert done["report"]["contested_claims"] == []
    assert done["report"]["llm_status"]["status"] == "not_searched"
    timing_job = app.state.critical_review_set_jobs.get(job_id)
    assert [stage.key for stage in timing_job.completed_stages] == [
        "preparing_evidence",
        "embedding_claims",
        "evaluating_evidence",
        "finalizing_result",
    ]


class _FakeSetGenerator:
    def __init__(self, drafts):
        self._drafts = drafts

    def propose(self, set_papers):
        return list(self._drafts)


def test_set_tier2_fake_generator_and_egress_off(temp_db_url, monkeypatch):
    app = _cr_set_app(temp_db_url)
    with make_engine(temp_db_url).begin() as conn:
        a = create_paper(conn, title="A", abstract="The sample was n = 12 participants.", csl_json={"title": "A"})
        b = create_paper(conn, title="B", abstract="We used a within-subjects design.", csl_json={"title": "B"})
    app.state.critical_review_set_generator = _FakeSetGenerator(
        [SetCandidateDraft("Small sample size.", "The sample was n = 12 participants.", [2])]
    )
    client = TestClient(app)
    # egress ON (conftest default): the fake runs; one grounded candidate persists, anchored to A, related=[B]
    done = _poll_set(
        client, client.post("/critical-read/set", json={"paper_ids": [a, b], "llm": True}).json()["job_id"]
    )
    assert done["status"] == "done"
    cands = done["report"]["candidates"]
    assert len(cands) == 1
    assert cands[0]["paper_id"] == a and cands[0]["concern"] == "Small sample size."
    assert cands[0]["related_paper_ids_json"] == [b]
    # egress OFF: honest unavailable, no LLM call, no new candidates
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    done2 = _poll_set(
        client, client.post("/critical-read/set", json={"paper_ids": [a, b], "llm": True}).json()["job_id"]
    )
    assert done2["report"]["llm_status"]["status"] == "unavailable"
    assert done2["report"]["candidates"] == []


def test_set_tier2_reports_managed_local_not_ready_without_failing_the_whole_job(
    temp_db_url, tmp_path, monkeypatch
) -> None:
    """A ManagedLocalTargetError raised resolving config for the set path must degrade to the same honest
    llm_status.unavailable shape the egress-off case already uses -- not fail the whole job (mirrors the
    single-paper Tier-2 fix; this path is job-based so a raw exception would otherwise surface only as an
    opaque bare-code job error, per the known follow-up noted when the single-paper fix shipped)."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"provider": "managed_local", "data_egress_enabled": True}), encoding="utf-8")
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(settings))
    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", str(tmp_path))  # no managed-local-ai/target.json written here
    app = _cr_set_app(temp_db_url)
    with make_engine(temp_db_url).begin() as conn:
        a = create_paper(conn, title="A", abstract="The sample was n = 12 participants.", csl_json={"title": "A"})
        b = create_paper(conn, title="B", abstract="We used a within-subjects design.", csl_json={"title": "B"})
    client = TestClient(app)
    done = _poll_set(
        client, client.post("/critical-read/set", json={"paper_ids": [a, b], "llm": True}).json()["job_id"]
    )
    assert done["status"] == "done"  # the job itself completes -- only the LLM sub-step degrades
    assert done["report"]["llm_status"]["status"] == "unavailable"
    assert "Local AI is not ready (descriptor_unreadable)" in done["report"]["llm_status"]["detail"]
    assert done["report"]["candidates"] == []
    app.state.provider_client_runtime.close()
    app.state.model_runtime_registry.close()
    app.state.engine.dispose()


class _FakeCandidateTriage:
    """Introspects the actual item_ids sent (a candidate's DB id, not knowable ahead of time) and labels each."""

    def evaluate(self, *, items):
        return {
            "status": {"status": "success", "provider_id": "local", "model_id": "fixture-model"},
            "annotations": {
                item["item_id"]: {
                    "label": "prioritize",
                    "show_in_triage": True,
                    "rationale": "Matches a substantive concern.",
                    "concerns": [],
                    "basis": "test",
                }
                for item in items
            },
        }


def test_set_triage_toggle_annotates_candidates_in_one_run(temp_db_url):
    app = _cr_set_app(temp_db_url)
    with make_engine(temp_db_url).begin() as conn:
        a = create_paper(conn, title="A", abstract="The sample was n = 12 participants.", csl_json={"title": "A"})
        b = create_paper(conn, title="B", abstract="We used a within-subjects design.", csl_json={"title": "B"})
    app.state.critical_review_set_generator = _FakeSetGenerator(
        [SetCandidateDraft("Small sample size.", "The sample was n = 12 participants.", [2])]
    )
    app.state.critical_review_triage_evaluator = _FakeCandidateTriage()
    client = TestClient(app)
    done = _poll_set(
        client,
        client.post("/critical-read/set", json={"paper_ids": [a, b], "llm": True, "triage": True}).json()["job_id"],
    )
    assert done["status"] == "done"
    cands = done["report"]["candidates"]
    assert len(cands) == 1
    assert cands[0]["llm_triage"]["label"] == "prioritize"
    # no contested claims surfaced (empty vector store) -> the ephemeral Tier-1 triage stage is honestly "not_searched"
    assert done["report"]["triage_status"]["status"] == "not_searched"
