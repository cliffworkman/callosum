"""Exact pre-slice stance evaluation for beyond-library citation suggestions."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from sqlalchemy import Connection

from app.backend.citations import beyond_library as beyond
from app.backend.discovery.providers import Item, SourceRegistry
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.summarization.stance import Stance


@dataclass
class RecordingScorer:
    calls: list[str] = field(default_factory=list)
    raise_on: str | None = None

    def classify_stance(self, *, sentence: str, passage: str) -> Stance:
        del sentence
        self.calls.append(passage)
        if passage == self.raise_on:
            raise RuntimeError("selected scorer failure")
        confidence = 0.7 + (len(passage) % 10) / 100
        return Stance(
            label="support",
            confidence=confidence,
            probs={"support": confidence, "contrast": (1 - confidence) / 2, "mention": (1 - confidence) / 2},
        )


@dataclass
class BatchCountingScorer:
    """Proves suggest_beyond_library batches its NLI calls (LATENCY.md) instead of one call per candidate."""

    batch_calls: int = 0
    single_calls: int = 0
    last_pairs: list = field(default_factory=list)

    def classify_stance(self, *, sentence: str, passage: str) -> Stance:
        del sentence, passage
        self.single_calls += 1
        raise AssertionError("suggest_beyond_library must not call classify_stance per-item when a batch API exists")

    def classify_stances(self, pairs: list[tuple[str, str]]) -> list[Stance]:
        self.batch_calls += 1
        self.last_pairs = list(pairs)
        return [
            Stance(label="support", confidence=0.9, probs={"support": 0.9, "contrast": 0.05, "mention": 0.05})
            for _ in pairs
        ]


@dataclass
class StaticProvider:
    name: str
    items: list[Item]
    label: str = "Static provider"
    calls: list[tuple[str, int]] = field(default_factory=list)

    def search(self, query: str, limit: int) -> list[Item]:
        self.calls.append((query, limit))
        return list(self.items)


class EmptyProvider:
    name = "empty"
    label = "Empty"

    def search(self, query: str, limit: int) -> list[Item]:
        del query, limit
        return []


def _item(index: int, *, title: str | None = None, abstract: str | None = None) -> Item:
    return Item(
        title=title or f"Candidate {index:03d}",
        sources=("fixture",),
        doi=f"10.9999/candidate-{index}",
        abstract=abstract if abstract is not None else f"evidence-{index}",
        year=2020 + index % 5,
    )


def _run(
    conn: Connection,
    providers: list[StaticProvider],
    *,
    top_k: int = 20,
    evaluate: bool = True,
    scorer: RecordingScorer | None = None,
) -> tuple[list[beyond.BeyondLibrarySuggestion], list[beyond.ProviderStatus]]:
    registry = SourceRegistry()
    for provider in providers:
        registry.register(provider)
    return beyond.suggest_beyond_library(
        conn,
        text="query terms",
        registry=registry,
        top_k=top_k,
        evaluate=evaluate,
        stance_scorer=scorer,
        openalex_provider=EmptyProvider(),
        anchors=[],
    )


def test_openalex_neighborhood_outage_is_reported_as_partial(temp_db_url: str) -> None:
    class UnavailableOpenAlex:
        def fetch_work_id(self, conn, ref):
            del conn, ref
            raise RuntimeError("OpenAlex unavailable")

        fetch_work_id_strict = fetch_work_id

        def fetch_work_meta_for(self, conn, ref):
            del conn, ref
            return None

        def fetch_referenced_works(self, conn, ref):
            del conn, ref
            return []

        def fetch_citing_works(self, conn, work_id):
            del conn, work_id
            return []

        def fetch_works_by_ids(self, conn, work_ids):
            del conn, work_ids
            return []

    anchor = beyond.CitationNeighborhoodAnchor(1, "Anchor", "10.1/anchor", 0.9)
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        items, status = beyond._neighborhood_items(conn, anchors=[anchor], openalex_client=UnavailableOpenAlex())
    engine.dispose()

    assert items == []
    assert status.status == "partial"
    assert "unavailable" in (status.warning or "").lower()


def _old_reference(
    conn: Connection,
    raw_items: list[Item],
    *,
    limit: int,
    scorer: RecordingScorer,
) -> list[beyond.BeyondLibrarySuggestion]:
    """The former evaluate-all-then-sort behavior, retained only as a test oracle."""
    query = "query terms"
    query_terms = beyond._terms(query)
    suggestions: list[beyond.BeyondLibrarySuggestion] = []
    for item in beyond._dedupe_mark_library(conn, raw_items):
        if item.in_library:
            continue
        overlap = beyond._overlap(query_terms, beyond._terms(f"{item.title} {item.abstract or ''}"))
        stance = scorer.classify_stance(sentence=query, passage=item.abstract[:1200]) if item.abstract else None
        suggestions.append(
            beyond.BeyondLibrarySuggestion(
                dedup_key=item.dedup_key,
                title=item.title,
                sources=list(item.sources),
                doi=item.doi,
                abstract=item.abstract,
                authors=list(item.authors),
                journal=item.journal,
                year=item.year,
                url=item.url,
                in_library=item.in_library,
                reason=beyond._reason(item, overlap),
                reason_kind="public_metadata_search",
                evidence_text=beyond._evidence_text(item),
                evidence_kind="abstract" if item.abstract else "metadata",
                metadata_overlap=round(overlap, 4),
                stance=stance,
            )
        )
    suggestions.sort(key=beyond._suggestion_rank_key)
    return suggestions[:limit]


def test_exact_response_matches_evaluate_all_reference_and_skips_tail(temp_db_url: str) -> None:
    items = [_item(index) for index in range(40)]
    items[2] = _item(2, abstract="")
    items[7] = _item(7, abstract="")
    items[24] = _item(24, abstract="")
    reference_scorer = RecordingScorer()
    optimized_scorer = RecordingScorer()
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        reference = _old_reference(conn, items, limit=20, scorer=reference_scorer)
        optimized, _ = _run(conn, [StaticProvider("one", items)], scorer=optimized_scorer)
    engine.dispose()

    assert [item.to_dict() for item in optimized] == [item.to_dict() for item in reference]
    assert len(reference_scorer.calls) == 37
    assert len(optimized_scorer.calls) == 18
    assert optimized_scorer.calls == [f"evidence-{index}" for index in range(20) if index not in {2, 7}]


def test_suggest_beyond_library_batches_stance_scorer_calls(temp_db_url: str) -> None:
    items = [_item(index) for index in range(5)]
    scorer = BatchCountingScorer()
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        result, _ = _run(conn, [StaticProvider("one", items)], top_k=5, scorer=scorer)
    engine.dispose()

    assert len(result) == 5
    assert scorer.single_calls == 0
    assert scorer.batch_calls == 1  # one NLI call for every scoreable candidate, not one per candidate (LATENCY.md)
    assert len(scorer.last_pairs) == 5


@pytest.mark.parametrize(("top_k", "expected_calls"), [(1, 0), (5, 4), (20, 19)])
def test_requested_limit_scores_only_returned_eligible(temp_db_url: str, top_k: int, expected_calls: int) -> None:
    items = [_item(index) for index in range(30)]
    items[0] = _item(0, abstract="")
    scorer = RecordingScorer()
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        result, _ = _run(conn, [StaticProvider("one", items)], top_k=top_k, scorer=scorer)
    engine.dispose()

    assert len(result) == top_k
    assert len(scorer.calls) == expected_calls
    assert result[0].stance is None


def test_multi_provider_complete_ties_preserve_first_seen_order_and_boundary(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = [replace_item(_item(index), title="Same Title") for index in range(13)]
    second = [replace_item(_item(index), title="Same Title") for index in range(13, 25)]
    raw_overlaps = iter([0.50001, 0.50004] * 13)
    monkeypatch.setattr(beyond, "_overlap", lambda _query, _item_terms: next(raw_overlaps))
    scorer = RecordingScorer()
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        result, _ = _run(
            conn,
            [StaticProvider("first", first), StaticProvider("second", second)],
            scorer=scorer,
        )
    engine.dispose()

    assert [item.dedup_key for item in result] == [item.dedup_key for item in [*first, *second][:20]]
    assert all(item.metadata_overlap == 0.5 for item in result)
    assert len(scorer.calls) == 20


def replace_item(item: Item, **changes: object) -> Item:
    values = {**item.__dict__, **changes}
    return Item(**values)


def test_doi_pmid_and_title_duplicates_merge_and_fill_metadata(temp_db_url: str) -> None:
    first = [
        Item(title="DOI Candidate", sources=("a",), doi="10.1/shared", abstract=None),
        Item(title="PMID Candidate", sources=("a",), pmid="12345", abstract=None),
        Item(title="Normalized Title", sources=("a",), abstract=None),
    ]
    second = [
        Item(title="DOI Candidate Later", sources=("b",), doi="10.1/shared", abstract="doi evidence"),
        Item(title="PMID Candidate Later", sources=("b",), pmid="12345", abstract="pmid evidence"),
        Item(title="normalized-title", sources=("b",), abstract="title evidence"),
    ]
    scorer = RecordingScorer()
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        result, _ = _run(conn, [StaticProvider("a", first), StaticProvider("b", second)], scorer=scorer)
    engine.dispose()

    assert len(result) == 3
    assert all(item.sources == ["a", "b"] for item in result)
    assert {item.abstract for item in result} == {"doi evidence", "pmid evidence", "title evidence"}
    assert len(scorer.calls) == 3


def test_library_exclusion_and_missing_abstract_do_not_backfill(temp_db_url: str) -> None:
    library = Item(title="Candidate 000", sources=("fixture",), doi="10.1/in-library", abstract="library evidence")
    missing = Item(title="Candidate 001", sources=("fixture",), doi="10.1/missing", abstract=None)
    eligible = Item(title="Candidate 002", sources=("fixture",), doi="10.1/eligible", abstract="eligible evidence")
    tail = Item(title="Candidate 003", sources=("fixture",), doi="10.1/tail", abstract="tail evidence")
    scorer = RecordingScorer()
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(
            conn,
            title=library.title,
            doi=library.doi,
            csl_json={"type": "article-journal", "title": library.title},
        )
    with engine.connect() as conn:
        result, _ = _run(
            conn,
            [StaticProvider("one", [library, missing, eligible, tail])],
            top_k=2,
            scorer=scorer,
        )
    engine.dispose()

    assert [item.dedup_key for item in result] == [missing.dedup_key, eligible.dedup_key]
    assert result[0].stance is None
    assert result[1].stance is not None
    assert scorer.calls == ["eligible evidence"]


def test_selected_call_order_follows_original_construction_before_ranked_emission(temp_db_url: str) -> None:
    constructed = [
        _item(1, title="Beta", abstract="beta evidence"),
        _item(2, title="Alpha", abstract="alpha evidence"),
        _item(3, title="Zulu", abstract="zulu evidence"),
    ]
    scorer = RecordingScorer()
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        result, _ = _run(conn, [StaticProvider("one", constructed)], top_k=2, scorer=scorer)
    engine.dispose()

    assert scorer.calls == ["beta evidence", "alpha evidence"]
    assert [item.title for item in result] == ["Alpha", "Beta"]


def test_discarded_tail_scorer_failure_is_not_called_but_selected_failure_propagates(temp_db_url: str) -> None:
    selected = _item(1, title="Alpha", abstract="selected evidence")
    tail = _item(2, title="Zulu", abstract="tail failure")
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        tail_scorer = RecordingScorer(raise_on="tail failure")
        result, _ = _run(
            conn,
            [StaticProvider("one", [selected, tail])],
            top_k=1,
            scorer=tail_scorer,
        )
        assert [item.dedup_key for item in result] == [selected.dedup_key]
        assert tail_scorer.calls == ["selected evidence"]

        with pytest.raises(RuntimeError, match="selected scorer failure"):
            _run(
                conn,
                [StaticProvider("one", [selected, tail])],
                top_k=1,
                scorer=RecordingScorer(raise_on="selected evidence"),
            )
    engine.dispose()


def test_evaluate_false_missing_scorer_and_provider_status_are_unchanged(temp_db_url: str) -> None:
    first = StaticProvider("first", [_item(1)])
    second = StaticProvider("second", [_item(2)])
    scorer = RecordingScorer()
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        plain, plain_status = _run(conn, [first, second], evaluate=False, scorer=scorer)
        unavailable, unavailable_status = _run(conn, [first, second], scorer=None)
    engine.dispose()

    assert scorer.calls == []
    assert [item.to_dict() for item in plain] == [item.to_dict() for item in unavailable]
    assert [(row.provider_id, row.status, row.result_count) for row in plain_status] == [
        (row.provider_id, row.status, row.result_count) for row in unavailable_status
    ]
    assert first.calls == [("query terms", 60), ("query terms", 60)]
    assert second.calls == [("query terms", 60), ("query terms", 60)]
