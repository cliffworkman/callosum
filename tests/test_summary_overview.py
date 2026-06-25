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
