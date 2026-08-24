"""Stable length-aware execution-shape tests for Critical Read NLI inference."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.backend.embeddings.vector_store import VectorHit
from app.backend.methods.critical_review import ChunkInfo, ContestedSearchScope, search_contested_claim_scopes
from app.backend.summarization.verification import (
    CRITICAL_REVIEW_NLI_BATCH_SIZE,
    NLIStanceScorer,
    Stance,
    classify_critical_review_stances,
    critical_review_nli_bucket,
)


class _Config:
    id2label = {0: "contradiction", 1: "entailment", 2: "neutral"}


class _InnerModel:
    config = _Config()


class _LengthTokenizer:
    model_max_length = 512

    def __init__(self, length_for_pair: Callable[[str, str], int]) -> None:
        self._length_for_pair = length_for_pair
        self.calls: list[list[tuple[str, str]]] = []

    def __call__(self, premises, hypotheses, **kwargs):  # noqa: ANN001
        pairs = list(zip(premises, hypotheses, strict=True))
        self.calls.append(pairs)
        assert kwargs == {
            "add_special_tokens": True,
            "truncation": "longest_first",
            "max_length": 512,
            "padding": False,
            "verbose": False,
        }
        return {"input_ids": [[0] * self._length_for_pair(premise, hypothesis) for premise, hypothesis in pairs]}


class _LengthAwareModel:
    model = _InnerModel()
    max_length = 512

    def __init__(
        self,
        lengths: dict[tuple[str, str], int],
        rows: dict[tuple[str, str], list[float]],
    ) -> None:
        self.tokenizer = _LengthTokenizer(lambda premise, hypothesis: lengths[(premise, hypothesis)])
        self.rows = rows
        self.calls: list[list[tuple[str, str]]] = []
        self.batch_sizes: list[int | None] = []

    def predict(self, pairs, *, apply_softmax=True, batch_size=None):  # noqa: ANN001
        assert apply_softmax is True
        ordered = [tuple(pair) for pair in pairs]
        self.calls.append(ordered)
        self.batch_sizes.append(batch_size)
        return [self.rows[pair] for pair in ordered]


def _pairs(count: int) -> list[tuple[str, str]]:
    return [(f"claim-{index}", f"passage-{index}") for index in range(count)]


def _model_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(passage, sentence) for sentence, passage in pairs]


def _rows(pairs: list[tuple[str, str]], *, equal: bool = False) -> dict[tuple[str, str], list[float]]:
    rows: dict[tuple[str, str], list[float]] = {}
    for index, pair in enumerate(_model_pairs(pairs)):
        contrast = 0.7 if equal else 0.6 + index / 10_000
        rows[pair] = [contrast, 0.2, 0.8 - contrast]
    return rows


@pytest.mark.parametrize(
    ("effective_tokens", "expected_bucket"),
    [
        (1, 0),
        (64, 0),
        (65, 1),
        (128, 1),
        (129, 2),
        (256, 2),
        (257, 3),
        (384, 3),
        (385, 4),
        (511, 4),
        (512, 5),
    ],
)
def test_critical_review_nli_bucket_boundaries(effective_tokens: int, expected_bucket: int) -> None:
    assert critical_review_nli_bucket(effective_tokens) == expected_bucket


@pytest.mark.parametrize("pair_count", [1, 15, 30, 32])
def test_one_batch_bypasses_length_planning_and_preserves_inference_order(pair_count: int) -> None:
    pairs = _pairs(pair_count)
    model = _LengthAwareModel(
        {pair: 512 for pair in _model_pairs(pairs)},
        _rows(pairs),
    )
    scorer = NLIStanceScorer(_loader=lambda: model)

    result = classify_critical_review_stances(scorer, pairs)

    assert model.tokenizer.calls == []
    assert model.calls == [_model_pairs(pairs)]
    assert model.batch_sizes == [None]
    assert [stance.confidence for stance in result if stance is not None] == pytest.approx(
        [0.6 + index / 10_000 for index in range(pair_count)]
    )


@pytest.mark.parametrize("pair_count", [33, 35])
def test_first_multi_batch_cases_bucket_stably_and_reconstruct_original_positions(pair_count: int) -> None:
    pairs = _pairs(pair_count)
    boundary_cycle = [512, 64, 65, 128, 129, 256, 257, 384, 385, 511]
    lengths = {pair: boundary_cycle[index % len(boundary_cycle)] for index, pair in enumerate(_model_pairs(pairs))}
    model = _LengthAwareModel(lengths, _rows(pairs))
    scorer = NLIStanceScorer(_loader=lambda: model)

    result = classify_critical_review_stances(scorer, pairs)

    expected_order = sorted(
        range(pair_count),
        key=lambda index: (critical_review_nli_bucket(lengths[_model_pairs(pairs)[index]]), index),
    )
    assert model.calls == [[_model_pairs(pairs)[index] for index in expected_order]]
    assert model.batch_sizes == [CRITICAL_REVIEW_NLI_BATCH_SIZE]
    assert [stance.confidence for stance in result if stance is not None] == pytest.approx(
        [0.6 + index / 10_000 for index in range(pair_count)]
    )


def test_duplicate_pairs_and_equal_confidence_ties_remain_in_original_positions() -> None:
    unique = _pairs(31)
    duplicate = ("claim-duplicate", "passage-duplicate")
    pairs = [duplicate, *unique, duplicate, duplicate]
    model_pairs = _model_pairs(pairs)
    lengths = {pair: 512 if index % 4 == 0 else 65 + index for index, pair in enumerate(model_pairs)}
    lengths[(duplicate[1], duplicate[0])] = 129
    model = _LengthAwareModel(lengths, _rows(pairs, equal=True))
    scorer = NLIStanceScorer(_loader=lambda: model)

    result = classify_critical_review_stances(scorer, pairs)

    assert len(result) == len(pairs)
    assert model.calls[0].count((duplicate[1], duplicate[0])) == 3
    assert [stance.confidence for stance in result if stance is not None] == pytest.approx([0.7] * len(pairs))
    assert [stance.label for stance in result if stance is not None] == ["contrast"] * len(pairs)


def test_threshold_positions_and_probabilities_match_original_order_reference() -> None:
    pairs = _pairs(35)
    rows = _rows(pairs)
    threshold_values = [0.549999, 0.55, 0.550001]
    for index, value in enumerate(threshold_values):
        rows[_model_pairs(pairs)[index]] = [value, 0.2, 0.8 - value]
    lengths = {pair: [512, 64, 256, 128, 385][index % 5] for index, pair in enumerate(_model_pairs(pairs))}
    reference_model = _LengthAwareModel(lengths, rows)
    candidate_model = _LengthAwareModel(lengths, rows)
    reference = NLIStanceScorer(_loader=lambda: reference_model).classify_stances(pairs)
    candidate = classify_critical_review_stances(NLIStanceScorer(_loader=lambda: candidate_model), pairs)

    assert reference == candidate
    assert [stance.confidence for stance in candidate[:3] if stance is not None] == pytest.approx(threshold_values)
    assert [stance.confidence >= 0.55 for stance in candidate[:3] if stance is not None] == [False, True, True]
    assert candidate_model.calls[0] != _model_pairs(pairs)


def test_custom_injected_batch_scorer_keeps_original_order_without_tokenizer_contract() -> None:
    pairs = _pairs(35)

    class _CustomScorer:
        def __init__(self) -> None:
            self.calls: list[list[tuple[str, str]]] = []

        def classify_stances(self, batch):  # noqa: ANN001
            self.calls.append(list(batch))
            return [Stance("mention", 0.7, {"support": 0.1, "contrast": 0.2, "mention": 0.7})] * len(batch)

    scorer = _CustomScorer()
    result = classify_critical_review_stances(scorer, pairs)  # type: ignore[arg-type]

    assert scorer.calls == [pairs]
    assert len(result) == len(pairs)


def test_planner_exception_outside_narrow_tuple_still_falls_back_to_original_batch_path() -> None:
    """A tokenizer failure that is NOT a KeyError/TypeError/ValueError (e.g. RuntimeError, as the real
    HuggingFace Rust fast-tokenizer can raise) must still fall through to the existing unbucketed batch path,
    not escape the inner planning guard and hit the outer handler, which would silently return
    `[None] * len(pairs)` for the WHOLE batch even though every pair is otherwise perfectly classifiable."""
    pairs = _pairs(35)
    rows = _rows(pairs)

    class _RaisingTokenizer:
        model_max_length = 512

        def __call__(self, *_args, **_kwargs):  # noqa: ANN001
            raise RuntimeError("tokenizer backend failure (e.g. the Rust fast-tokenizer)")

    class _ModelWithRaisingTokenizer:
        model = _InnerModel()
        max_length = 512
        tokenizer = _RaisingTokenizer()

        def __init__(self) -> None:
            self.calls: list[list[tuple[str, str]]] = []
            self.batch_sizes: list[int | None] = []

        def predict(self, model_pairs, *, apply_softmax=True, batch_size=None):  # noqa: ANN001
            ordered = [tuple(pair) for pair in model_pairs]
            self.calls.append(ordered)
            self.batch_sizes.append(batch_size)
            return [rows[pair] for pair in ordered]

    model = _ModelWithRaisingTokenizer()
    result = classify_critical_review_stances(NLIStanceScorer(_loader=lambda: model), pairs)

    # The fallback path ran (one ordered, unbucketed call) rather than the whole batch being lost.
    assert model.calls == [_model_pairs(pairs)]
    assert model.batch_sizes == [None]
    assert len(result) == len(pairs)
    assert all(stance is not None for stance in result)


def test_nli_scorer_without_compatible_tokenizer_retains_original_batch_path() -> None:
    pairs = _pairs(35)

    class _ModelWithoutTokenizer:
        model = _InnerModel()

        def __init__(self) -> None:
            self.calls: list[list[tuple[str, str]]] = []

        def predict(self, model_pairs, *, apply_softmax=True):  # noqa: ANN001
            self.calls.append(list(model_pairs))
            return [_rows(pairs)[tuple(pair)] for pair in model_pairs]

    model = _ModelWithoutTokenizer()
    result = classify_critical_review_stances(NLIStanceScorer(_loader=lambda: model), pairs)

    assert model.calls == [_model_pairs(pairs)]
    assert len(result) == len(pairs)


def test_shared_single_set_wip_search_seam_uses_one_length_aware_phase_and_preserves_ties() -> None:
    claims = [f"claim-{index}" for index in range(8)]
    hit_ids = {index: list(range(index * 5, index * 5 + 5)) for index in range(8)}
    chunks = {
        hit_id: ChunkInfo(
            paper_id=100 + hit_id,
            text=f"passage-{hit_id}",
            page=hit_id + 1,
        )
        for ids in hit_ids.values()
        for hit_id in ids
    }

    class _Embed:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def encode_texts(self, texts):  # noqa: ANN001
            self.calls.append(list(texts))
            return [[index] for index, _ in enumerate(texts)]

    class _Store:
        def search(self, _conn, *, vector, top_k, candidate_embedding_ids=None):  # noqa: ANN001
            return [
                VectorHit(embedding_id=hit_id, distance=0.1)
                for hit_id in hit_ids[int(vector[0])]
                if hit_id in set(candidate_embedding_ids or set())
            ][:top_k]

    model_pairs = [
        (chunks[hit_id].text, claim) for claim_index, claim in enumerate(claims) for hit_id in hit_ids[claim_index]
    ]
    lengths = {pair: [512, 64, 129, 257, 385][index % 5] for index, pair in enumerate(model_pairs)}
    rows: dict[tuple[str, str], list[float]] = {}
    for index, pair in enumerate(model_pairs):
        hit_index = index % 5
        contrast = 0.7 if hit_index in {0, 1} else 0.549999 if hit_index == 2 else 0.2
        rows[pair] = [contrast, 0.8 - contrast, 0.2]

    reference_model = _LengthAwareModel(lengths, rows)
    candidate_model = _LengthAwareModel(lengths, rows)

    class _ReferenceScorer:
        def __init__(self) -> None:
            self.inner = NLIStanceScorer(_loader=lambda: reference_model)

        def classify_stances(self, batch):  # noqa: ANN001
            return self.inner.classify_stances(batch)

    def run(scorer):  # noqa: ANN001
        embed = _Embed()
        [report] = search_contested_claim_scopes(
            None,
            scopes=[ContestedSearchScope(1, claims, set(chunks))],
            embed_model=embed,
            vector_store=_Store(),
            stance_scorer=scorer,
            resolve_chunk=lambda hit: chunks.get(hit.embedding_id),
        )
        assert embed.calls == [claims]
        return report

    reference = run(_ReferenceScorer())
    candidate = run(NLIStanceScorer(_loader=lambda: candidate_model))

    assert candidate == reference
    assert len(reference_model.calls) == len(candidate_model.calls) == 1
    assert reference_model.calls[0] == model_pairs
    assert candidate_model.calls[0] != model_pairs
    assert candidate_model.batch_sizes == [CRITICAL_REVIEW_NLI_BATCH_SIZE]
    assert [item.passage for item in candidate.contested_claims] == [
        chunks[hit_ids[index][0]].text for index in range(len(claims))
    ]
