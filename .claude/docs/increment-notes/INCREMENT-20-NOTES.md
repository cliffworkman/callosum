# Increment 20 Notes

## Implemented

- Changed the default verifier support scorer to `NLISupportScorer`.
- Configured the default NLI scorer with `EmbeddingSupportScorer` as its fallback, so an unavailable CrossEncoder model does not hard-crash the summarization path.
- Changed the default `VerificationConfig.support_threshold` from `0.7` to `0.55`.
- Aligned validation-harness defaults:
  - `--support-scorer` now defaults to `nli`.
  - `--support-threshold` now defaults to `0.55`.
- Preserved explicit embedding opt-in through `--support-scorer embedding` and programmatic `support_scorer=EmbeddingSupportScorer(...)`.

## Calibration Rationale

- Real-library calibration showed NLI support scores were discriminative and bimodal, spanning roughly `0.006` to `0.991`.
- Embedding support scores were not useful for entailment calibration, returning approximately `1.000` for every citation.
- The default threshold `0.55` sits in the observed empty valley between the reject cluster ceiling around `0.420` and the keep cluster floor around `0.632`.

## Test Handling

- Hermetic tests do not load or download the real NLI model.
- Default-NLI fallback is tested by monkeypatching the NLI model load to raise `OSError`; the verifier then uses the embedding fallback.
- Existing summarization tests that intentionally depend on fake embedding-vector behavior now explicitly pass `EmbeddingSupportScorer(model)`.
- Added tests for:
  - default verifier scorer type (`NLISupportScorer`) and embedding fallback;
  - default threshold `0.55`;
  - explicit embedding scorer behavior;
  - default path fallback when NLI is unavailable;
  - inclusive boundary behavior where `0.55` passes and `0.54` fails;
  - validation-harness default reporting of `nli` and `0.55`.

## Raw Pytest Output

```text
........................................................................ [100%]
72 passed in 33.78s
```
