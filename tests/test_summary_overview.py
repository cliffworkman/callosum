from __future__ import annotations

import sqlalchemy as sa

from app.backend.persistence.database import make_engine


def test_summaries_has_overview_json_column(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)  # create_all + alembic upgrade head
    cols = {c["name"] for c in sa.inspect(engine).get_columns("summaries")}
    engine.dispose()
    assert "overview_json" in cols


from app.backend.llm.egress import DataEgressDisabledError, EgressGatedOverviewGenerator
from app.backend.summarization.overview import FakeOverviewGenerator, OverviewSentence
from integrations.gemini.overview import _parse_overview_response


def test_fake_overview_generator_returns_sentences() -> None:
    gen = FakeOverviewGenerator(sentences=[OverviewSentence(text="In sum, X.", claim_indices=[0, 1])])
    out = gen.generate(verified_claims=["claim a", "claim b"], scope_ref={})
    assert out == [OverviewSentence(text="In sum, X.", claim_indices=[0, 1])]


def test_egress_gate_blocks_overview_when_disabled() -> None:
    gated = EgressGatedOverviewGenerator(inner=FakeOverviewGenerator(sentences=[]), data_egress_enabled=False)
    try:
        gated.generate(verified_claims=["a"], scope_ref={})
        raised = False
    except DataEgressDisabledError:
        raised = True
    assert raised


def test_egress_gate_delegates_when_enabled() -> None:
    inner = FakeOverviewGenerator(sentences=[OverviewSentence(text="Y.", claim_indices=[0])])
    gated = EgressGatedOverviewGenerator(inner=inner, data_egress_enabled=True)
    assert gated.generate(verified_claims=["a"], scope_ref={}) == inner.sentences


def test_parse_overview_response_drops_malformed_items() -> None:
    raw = (
        '[{"text":"A.","claim_indices":[0,1]},{"text":"","claim_indices":[0]},{"claim_indices":[2]},'
        '{"text":"B.","claim_indices":"nope"},{"text":"C.","claim_indices":[1,"x",2]}]'
    )
    out = _parse_overview_response(raw)
    # kept: "A." (valid) and "C." (non-int refs dropped, leaving [1,2]); dropped: empty text, missing text,
    # non-list claim_indices.
    assert [s.text for s in out] == ["A.", "C."]
    assert out[1].claim_indices == [1, 2]


from sqlalchemy import select as _select

from app.backend.persistence.database import make_engine as _make_engine
from app.backend.persistence.schema import summaries as _summaries
from app.backend.summarization.generators import (
    CandidateCitation,
    CandidateSummarySentence,
    FakeSummaryGenerator,
)
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from tests.api_helpers import ApiFakeEmbeddingModel, ConstantSupportScorer, InMemoryVectorStore
from tests.test_summarize_selected import _seed_two_papers_two_chunks  # reuse the multi-paper fixture


def _overview_for(db_url: str, *, overview_gen):
    seed = _seed_two_papers_two_chunks(db_url)
    sgen = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Cortex is discussed.",
                citations=[CandidateCitation(chunk_id=seed["a1"], quote="Paper A chunk 1 discusses cortex.")],
            )
        ]
    )
    engine = _make_engine(db_url)
    with engine.begin() as conn:
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[seed["pa"], seed["pb"]]),
            generator=sgen,
            model=ApiFakeEmbeddingModel(),
            vector_store=InMemoryVectorStore(),
            support_scorer=ConstantSupportScorer(),
            top_k=4,
            overview_generator=overview_gen,
        )
        row = conn.execute(
            _select(_summaries.c.overview_json).where(_summaries.c.id == result.summary_id)
        ).scalar_one()
    engine.dispose()
    return row


def test_overview_stored_with_mapped_ordinals(temp_db_url: str) -> None:
    gen = FakeOverviewGenerator(sentences=[OverviewSentence(text="In sum, cortex matters.", claim_indices=[0])])
    overview = _overview_for(temp_db_url, overview_gen=gen)
    assert overview == [{"text": "In sum, cortex matters.", "claim_ordinals": [0]}]


def test_overview_drops_out_of_range_claim_indices(temp_db_url: str) -> None:
    # index 5 doesn't exist (only 1 verified claim, ordinal 0) → dropped; a sentence left with no valid refs is
    # dropped entirely.
    gen = FakeOverviewGenerator(
        sentences=[
            OverviewSentence(text="Valid.", claim_indices=[0, 5]),
            OverviewSentence(text="All bad refs.", claim_indices=[9]),
        ]
    )
    overview = _overview_for(temp_db_url, overview_gen=gen)
    assert overview == [{"text": "Valid.", "claim_ordinals": [0]}]


def test_no_overview_generator_leaves_overview_null(temp_db_url: str) -> None:
    assert _overview_for(temp_db_url, overview_gen=None) is None
