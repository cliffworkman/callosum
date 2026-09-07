"""Unit tests for the faceted broad-Ask pure logic (inc 581): the H1a hygiene/budget selection and
the verified-first assembly + coverage. No DB, no models, no provider."""

from __future__ import annotations

from types import SimpleNamespace

from app.backend.summarization.faceted_pipeline import (
    GLOBAL_CHUNK_CAP,
    MAX_FLAGGED_PER_FACET,
    MAX_VERIFIED_PER_FACET,
    PER_PAPER_CAP,
    _assemble,
    _select_with_hygiene,
)
from app.backend.summarization.generators import CandidateSummarySentence, SourceChunk
from app.backend.summarization.query_planner import Facet, QueryPlan


def _chunk(cid: int, pid: int = 1) -> SourceChunk:
    return SourceChunk(
        chunk_id=cid, paper_id=pid, attachment_id=pid, text=f"text {cid}", page_start=1, page_end=1, chunk_version="v1"
    )


def _facets(n: int) -> tuple:
    return tuple(Facet(label=f"F{i}", query=f"q{i}") for i in range(n))


# ---- hygiene + budget ----------------------------------------------------------------------------


def test_deprioritizes_bibliographic_and_structural_never_deletes():
    ranked = [_chunk(1, pid=1), _chunk(2, pid=2), _chunk(3, pid=3), _chunk(4, pid=4)]  # distinct papers
    roles = {
        1: ("reference_entry", "bibliographic"),
        2: ("body_prose", "scientific"),
        3: ("running_head", "structural"),
        4: ("unknown", "unknown"),
    }
    selected, counts = _select_with_hygiene(per_facet={0: ranked}, facets=_facets(1), roles=roles)
    ids = [fe.chunk.chunk_id for fe in selected[0]]
    # scientific(2) + unknown(4) lead in relevance order; bibliographic(1) + structural(3) demoted to the end.
    assert ids == [2, 4, 1, 3]
    assert counts[0] == 4  # nothing deleted -- demotion only
    # roles are attached for coverage/inspection
    assert {fe.chunk.chunk_id: fe.evidence_role for fe in selected[0]}[1] == "bibliographic"


def test_absent_roles_is_a_noop_preserving_relevance_order():
    ranked = [_chunk(3), _chunk(1), _chunk(2)]
    selected, _ = _select_with_hygiene(per_facet={0: ranked}, facets=_facets(1), roles={})
    assert [fe.chunk.chunk_id for fe in selected[0]] == [3, 1, 2]
    assert all(fe.evidence_role is None for fe in selected[0])


def test_unknown_is_never_penalized_peer_of_scientific():
    # unknown must NOT be demoted below scientific; both are full priority, relevance order preserved.
    ranked = [_chunk(1), _chunk(2)]
    roles = {1: ("unknown", "unknown"), 2: ("body_prose", "scientific")}
    selected, _ = _select_with_hygiene(per_facet={0: ranked}, facets=_facets(1), roles=roles)
    assert [fe.chunk.chunk_id for fe in selected[0]] == [1, 2]  # unchanged -- unknown kept ahead


def test_per_paper_cap_enforced():
    ranked = [_chunk(i, pid=7) for i in range(1, 6)]  # 5 chunks, same paper
    selected, counts = _select_with_hygiene(per_facet={0: ranked}, facets=_facets(1), roles={})
    assert counts[0] == PER_PAPER_CAP == 3


def test_dedup_across_facets_attributes_to_first():
    shared = _chunk(99, pid=2)
    selected, _ = _select_with_hygiene(
        per_facet={0: [shared, _chunk(1)], 1: [shared, _chunk(2)]}, facets=_facets(2), roles={}
    )
    ids0 = [fe.chunk.chunk_id for fe in selected[0]]
    ids1 = [fe.chunk.chunk_id for fe in selected[1]]
    assert 99 in ids0 and 99 not in ids1  # deduped, kept in facet 0


def test_global_cap_enforced():
    per_facet = {i: [_chunk(i * 100 + j, pid=i * 100 + j) for j in range(20)] for i in range(6)}
    selected, _ = _select_with_hygiene(per_facet=per_facet, facets=_facets(6), roles={})
    total = sum(len(v) for v in selected.values())
    assert total == GLOBAL_CHUNK_CAP == 36


# ---- assembly + coverage -------------------------------------------------------------------------


def _row(verified: bool, support: float = 0.9):
    return [SimpleNamespace(verified=verified, support_confidence=support)]


def _cand(text: str) -> CandidateSummarySentence:
    return CandidateSummarySentence(text=text, citations=[])


def test_verified_first_and_coverage_partial():
    plan = QueryPlan(scope="broad", facets=_facets(1), planner_used=True)
    facet_candidates = [
        (0, _cand("v-lo")),
        (0, _cand("v-hi")),
        (0, _cand("flagged-a")),
        (0, _cand("flagged-b")),
    ]
    rows = [_row(True, 0.7), _row(True, 0.95), _row(False), _row(False)]
    ordered, ordered_rows, coverage, responsiveness = _assemble(
        plan=plan, facet_candidates=facet_candidates, verification_rows=rows, retrieved_counts={0: 6}
    )
    assert len(responsiveness) == len(ordered)  # inc 582: ordinal-aligned, one label per claim
    texts = [c.text for c in ordered]
    assert texts[:2] == ["v-hi", "v-lo"]  # verified first, strongest support first
    assert set(texts[2:]) == {"flagged-a", "flagged-b"}  # flagged after
    assert len(ordered_rows) == len(ordered)
    cov = coverage[0]
    assert cov.status == "partial" and cov.verified_claim_count == 2 and cov.flagged_claim_count == 2


def test_coverage_supported_when_no_flagged():
    plan = QueryPlan(scope="broad", facets=_facets(1))
    _, _, coverage, _ = _assemble(
        plan=plan, facet_candidates=[(0, _cand("v"))], verification_rows=[_row(True)], retrieved_counts={0: 3}
    )
    assert coverage[0].status == "supported"


def test_coverage_retrieved_unverified():
    plan = QueryPlan(scope="broad", facets=_facets(1))
    _, _, coverage, _ = _assemble(
        plan=plan, facet_candidates=[(0, _cand("x"))], verification_rows=[_row(False)], retrieved_counts={0: 4}
    )
    assert coverage[0].status == "retrieved_unverified"  # evidence retrieved, none verified -- NOT absence


def test_coverage_no_evidence_retrieved_is_not_absence():
    plan = QueryPlan(scope="broad", facets=_facets(1))
    ordered, _, coverage, responsiveness = _assemble(
        plan=plan, facet_candidates=[], verification_rows=[], retrieved_counts={0: 0}
    )
    assert ordered == []
    assert responsiveness == []
    assert coverage[0].status == "no_evidence_retrieved"


def test_per_facet_verified_cap():
    plan = QueryPlan(scope="broad", facets=_facets(1))
    facet_candidates = [(0, _cand(f"v{i}")) for i in range(5)]
    rows = [_row(True, 0.5 + i * 0.1) for i in range(5)]
    ordered, _, coverage, _ = _assemble(
        plan=plan, facet_candidates=facet_candidates, verification_rows=rows, retrieved_counts={0: 6}
    )
    assert len(ordered) == MAX_VERIFIED_PER_FACET == 3
    assert coverage[0].verified_claim_count == 3


def test_per_facet_flagged_cap():
    plan = QueryPlan(scope="broad", facets=_facets(1))
    facet_candidates = [(0, _cand(f"f{i}")) for i in range(5)]
    rows = [_row(False) for _ in range(5)]
    ordered, _, coverage, _ = _assemble(
        plan=plan, facet_candidates=facet_candidates, verification_rows=rows, retrieved_counts={0: 6}
    )
    assert len(ordered) == MAX_FLAGGED_PER_FACET == 2
    assert coverage[0].status == "retrieved_unverified"


def test_verified_first_across_facets():
    plan = QueryPlan(scope="broad", facets=_facets(2))
    facet_candidates = [(0, _cand("f0-verified")), (0, _cand("f0-flagged")), (1, _cand("f1-verified"))]
    rows = [_row(True), _row(False), _row(True)]
    ordered, _, _, _ = _assemble(
        plan=plan, facet_candidates=facet_candidates, verification_rows=rows, retrieved_counts={0: 3, 1: 3}
    )
    texts = [c.text for c in ordered]
    # both facets' verified claims precede any flagged claim
    assert texts.index("f0-verified") < texts.index("f0-flagged")
    assert texts.index("f1-verified") < texts.index("f0-flagged")


# ---- inc 582 responsiveness (presentation label; never changes status/order) --------------------


def test_responsiveness_is_ordinal_aligned_and_labels_findings_vs_descriptive():
    plan = QueryPlan(scope="broad", facets=_facets(1))
    facet_candidates = [
        (0, _cand("Higher amyloid burden was observed in late-life depressed patients.")),  # verified finding
        (0, _cand("This study investigates structural imaging in late-life depression.")),  # verified descriptive
        (0, _cand("Research has investigated glucose metabolism.")),  # FLAGGED descriptive
    ]
    rows = [_row(True, 0.9), _row(True, 0.8), _row(False)]
    ordered, ordered_rows, _, responsiveness = _assemble(
        plan=plan, facet_candidates=facet_candidates, verification_rows=rows, retrieved_counts={0: 6}
    )
    # one label per claim, aligned to final order (== persisted ordinal)
    assert len(responsiveness) == len(ordered) == 3
    by_text = {c.text: responsiveness[i] for i, c in enumerate(ordered)}
    assert by_text["Higher amyloid burden was observed in late-life depressed patients."] == "finding"
    assert by_text["This study investigates structural imaging in late-life depression."] == "descriptive"
    # #8: the flagged claim keeps its flagged status (verified flag comes from its row, unchanged) and is
    # never promoted -- responsiveness is orthogonal metadata, it does not verify anything.
    assert ordered_rows[-1][0].verified is False
    assert ordered[-1].text == "Research has investigated glucose metabolism."


def test_responsiveness_from_ref_reader():
    from app.backend.api.routers.summaries_response import _responsiveness_from_ref

    # narrow / non-faceted summary -> None (unchanged response)
    assert _responsiveness_from_ref({"source_chunk_count": 8}) is None
    assert _responsiveness_from_ref(None) is None
    # faceted -> the ordinal-aligned list, with an unrecognized value failing open to "unknown"
    assert _responsiveness_from_ref({"responsiveness": ["finding", "descriptive", "bogus"]}) == [
        "finding",
        "descriptive",
        "unknown",
    ]
