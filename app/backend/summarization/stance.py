"""Local NLI stance scoring and Critical Read execution planning.

The stance scorer owns probability-label interpretation. Critical Read may alter only the independent pair
execution order: exact inputs are grouped into stable tokenizer-length buckets, inferred once, and reconstructed
before callers apply scientific thresholds or evidence-selection logic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from app.backend.model_runtime import PINNED_MODEL_REVISIONS, ManagedModelRuntime

T = TypeVar("T")

DEFAULT_NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
CRITICAL_REVIEW_NLI_BATCH_SIZE = 32
CRITICAL_REVIEW_NLI_MAX_LENGTH = 512
CRITICAL_REVIEW_NLI_BUCKET_LIMITS = (64, 128, 256, 384, 511, 512)


@dataclass(frozen=True)
class Stance:
    """A 3-way NLI stance of a passage toward a claim (inc 156, highlight-to-evaluate)."""

    label: str  # "support" | "contrast" | "mention"
    confidence: float
    probs: dict[str, float]  # {"support": .., "contrast": .., "mention": ..}


@dataclass(frozen=True)
class _IndexedCriticalReviewNLIPair:
    """One planned NLI pair's immutable original position and effective tokenizer length."""

    original_index: int
    effective_tokens: int


class StanceScorer(Protocol):
    def classify_stance(self, *, sentence: str, passage: str) -> Stance | None:
        """Local NLI stance of `passage` toward `sentence`, or None if unavailable (never a guessed verdict)."""

    def classify_stances(self, pairs: list[tuple[str, str]]) -> list[Stance | None]:
        """Batch ``(sentence, passage)`` pairs while preserving their positional order."""


@dataclass
class NLIStanceScorer:
    """Local CrossEncoder NLI stance scorer (shares the model family with NLISupportScorer).

    The passage is the premise and the claim sentence is the hypothesis; the 3-way softmax maps
    entailment→support, contradiction→contrast, neutral→mention. A failed batch is retried per pair so one
    pathological input cannot silence independent results; any pair that still fails returns None rather than a
    guessed verdict ("silence is not a certificate").
    """

    model_name: str = DEFAULT_NLI_MODEL
    local_files_only: bool = False
    revision: str | None = None
    device: str | None = None
    backend: str = "torch"
    _model: object | None = field(default=None, init=False, repr=False)
    _loader: Callable[[], object] | None = field(default=None, repr=False)
    _runtime: ManagedModelRuntime | None = field(default=None, repr=False)

    def classify_stance(self, *, sentence: str, passage: str) -> Stance | None:
        return self.classify_stances([(sentence, passage)])[0]

    def classify_stances(self, pairs: list[tuple[str, str]]) -> list[Stance | None]:
        """Classify every pair in one CrossEncoder call, isolating individual failures only on batch failure."""
        if not pairs:
            return []

        def predict(model: object):  # type: ignore[no-untyped-def]
            return self._predict_stances(model, pairs)

        return self._predict_with_pair_fallback(pairs, predict)

    def classify_critical_review_stances(self, pairs: list[tuple[str, str]]) -> list[Stance | None]:
        """Classify Critical Read pairs with stable, length-aware batching when more than one batch is present.

        Every premise/hypothesis pair remains byte-for-byte unchanged. Only inference order changes, and every
        stance is explicitly reconstructed into its original position before Critical Read applies thresholds,
        chooses evidence, or persists anything. A one-batch workload bypasses token-length planning because its
        padded width cannot improve. A custom model without the production tokenizer contract retains the current
        ordered batch path.
        """
        if len(pairs) <= CRITICAL_REVIEW_NLI_BATCH_SIZE:
            return self.classify_stances(pairs)

        def predict(model: object):  # type: ignore[no-untyped-def]
            try:
                order = _critical_review_nli_order(model, pairs)
            except Exception:
                # A custom CrossEncoder-like model may expose a tokenizer without the production Hugging Face
                # call/result contract, and the real tokenizer call can also raise types outside a narrow
                # tuple (e.g. RuntimeError from the Rust fast-tokenizer, AttributeError, IndexError, OSError).
                # Planning is optional, side-effect-free execution shaping that only returns an ordering, so
                # catching broadly here is safe: any failure should fall through to the existing, already-
                # working unbucketed path below rather than escape to the outer failure-isolation handler.
                order = None
            if order is None:
                return self._predict_stances(model, pairs)
            bucketed_pairs = [pairs[original_index] for original_index in order]
            bucketed_stances = self._predict_stances(
                model,
                bucketed_pairs,
                batch_size=CRITICAL_REVIEW_NLI_BATCH_SIZE,
            )
            reconstructed: list[Stance | None] = [None] * len(pairs)
            for bucketed_index, original_index in enumerate(order):
                reconstructed[original_index] = bucketed_stances[bucketed_index]
            return reconstructed

        return self._predict_with_pair_fallback(pairs, predict)

    def _predict_with_pair_fallback(
        self,
        pairs: list[tuple[str, str]],
        predict_batch: Callable[[object], list[Stance | None]],
    ) -> list[Stance | None]:
        """Keep one batched fast path, but restore independent fail-closed behavior after an exception."""
        try:
            return self._run_model(predict_batch)
        except Exception:
            results: list[Stance | None] = []
            for pair in pairs:
                try:
                    results.extend(self._run_model(lambda model, pair=pair: self._predict_stances(model, [pair])))
                except Exception:
                    results.append(None)
            return results

    def _run_model(self, operation: Callable[[object], T]) -> T:
        return self._runtime.run(operation) if self._runtime is not None else operation(self._load_model())

    @staticmethod
    def _predict_stances(
        model: object,
        pairs: list[tuple[str, str]],
        *,
        batch_size: int | None = None,
    ) -> list[Stance]:
        kwargs: dict[str, object] = {"apply_softmax": True}
        if batch_size is not None:
            kwargs["batch_size"] = batch_size
        scores = model.predict(  # type: ignore[attr-defined]
            [(passage, sentence) for sentence, passage in pairs],
            **kwargs,
        )
        return [_stance_from_row(row, model=model) for row in scores]

    def _load_model(self) -> object:
        if self._model is None:
            if self._loader is not None:
                self._model = self._loader()
            else:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(
                    self.model_name,
                    revision=self.revision,
                    device=self.device,
                    local_files_only=self.local_files_only,
                    backend=self.backend,
                    model_kwargs={"use_safetensors": True},
                )
        return self._model


def default_stance_scorer() -> StanceScorer:
    return NLIStanceScorer(revision=PINNED_MODEL_REVISIONS.get(DEFAULT_NLI_MODEL))


def classify_stances(scorer: StanceScorer, pairs: list[tuple[str, str]]) -> list[Stance | None]:
    """Use a scorer's batch seam when available, retaining compatibility with single-pair test/custom scorers."""
    if not pairs:
        return []
    many = getattr(scorer, "classify_stances", None)
    if callable(many):
        return many(pairs)
    return [scorer.classify_stance(sentence=sentence, passage=passage) for sentence, passage in pairs]


def classify_critical_review_stances(scorer: StanceScorer, pairs: list[tuple[str, str]]) -> list[Stance | None]:
    """Use length-aware inference only for compatible Critical Read scorers.

    Custom/injected scorers keep their existing batch or single-item seam and are never required to expose a
    tokenizer. Other NLI consumers continue to call :func:`classify_stances`, so this production change remains
    explicitly scoped to the benchmarked Critical Read workflow.
    """
    if not pairs:
        return []
    critical_many = getattr(scorer, "classify_critical_review_stances", None)
    if callable(critical_many):
        return critical_many(pairs)
    return classify_stances(scorer, pairs)


def critical_review_nli_bucket(effective_tokens: int) -> int:
    """Return the stable fine-grained Critical Read bucket for an effective token length."""
    if not 0 < effective_tokens <= CRITICAL_REVIEW_NLI_MAX_LENGTH:
        raise ValueError(f"effective token length must be within 1..{CRITICAL_REVIEW_NLI_MAX_LENGTH}")
    for bucket, upper_bound in enumerate(CRITICAL_REVIEW_NLI_BUCKET_LIMITS):
        if effective_tokens <= upper_bound:
            return bucket
    raise AssertionError("the final Critical Read NLI bucket must cover the model maximum")


def _critical_review_nli_order(model: object, pairs: list[tuple[str, str]]) -> list[int] | None:
    """Plan stable fine buckets with the exact tokenizer/truncation contract used by the production model.

    ``None`` means the model does not expose the expected 512-token CrossEncoder tokenizer contract; callers then
    retain the existing original-order batch behavior. No text or token data is cached or logged.
    """
    tokenizer = getattr(model, "tokenizer", None)
    if not callable(tokenizer):
        return None
    model_max_length = getattr(model, "max_length", None) or getattr(tokenizer, "model_max_length", None)
    if model_max_length != CRITICAL_REVIEW_NLI_MAX_LENGTH:
        return None
    encoded = tokenizer(
        [passage for _, passage in pairs],
        [sentence for sentence, _ in pairs],
        add_special_tokens=True,
        truncation="longest_first",
        max_length=CRITICAL_REVIEW_NLI_MAX_LENGTH,
        padding=False,
        verbose=False,
    )
    input_ids = encoded["input_ids"]
    if len(input_ids) != len(pairs):
        raise ValueError("tokenizer returned a different number of Critical Read NLI pairs")
    buckets: list[list[_IndexedCriticalReviewNLIPair]] = [[] for _ in CRITICAL_REVIEW_NLI_BUCKET_LIMITS]
    for original_index, token_ids in enumerate(input_ids):
        indexed_pair = _IndexedCriticalReviewNLIPair(original_index, len(token_ids))
        buckets[critical_review_nli_bucket(indexed_pair.effective_tokens)].append(indexed_pair)
    return [indexed_pair.original_index for bucket in buckets for indexed_pair in bucket]


def _label_index(*, model: object, count: int, label: str, default: int) -> int:
    config = getattr(getattr(model, "model", None), "config", None)
    id2label = getattr(config, "id2label", None)
    if isinstance(id2label, dict):
        for key, lab in id2label.items():
            if str(lab).lower() == label:
                return int(key)
    return default


def _entailment_index(*, model: object, count: int) -> int:
    return _label_index(model=model, count=count, label="entailment", default=1 if count > 1 else 0)


def _contradiction_index(*, model: object, count: int) -> int:
    return _label_index(model=model, count=count, label="contradiction", default=0)


def _stance_from_scores(scores, *, model: object) -> Stance:  # type: ignore[no-untyped-def]
    row = scores[0] if hasattr(scores, "__len__") and len(scores) else scores
    return _stance_from_row(row, model=model)


def _stance_from_row(row, *, model: object) -> Stance:  # type: ignore[no-untyped-def]
    values = [float(value) for value in row]
    count = len(values)
    stance_by_nli = {"entailment": "support", "contradiction": "contrast", "neutral": "mention"}
    default_index = {"support": 1, "contrast": 0, "mention": 2}
    probs: dict[str, float] = {}
    for nli_label, stance_label in stance_by_nli.items():
        idx = _label_index(model=model, count=count, label=nli_label, default=default_index[stance_label])
        probs[stance_label] = max(0.0, min(1.0, values[idx])) if 0 <= idx < count else 0.0
    label = max(probs, key=lambda key: probs[key])
    return Stance(label=label, confidence=probs[label], probs=probs)
