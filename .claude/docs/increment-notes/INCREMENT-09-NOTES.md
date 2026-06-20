# Increment 09 Notes

## Implemented

- Added `SummaryGenerator` protocol, `FakeSummaryGenerator`, and summary candidate data types.
- Added `GeminiSummaryGenerator` under `integrations/gemini/` with explicit data-egress gating.
- Added local deterministic citation verification in `app/backend/summarization/verification.py`.
- Added summarization orchestration and trust-spine persistence in `app/backend/summarization/pipeline.py`.
- Added hermetic tests for verified, quote-failing, support-failing, full round-trip, and Gemini-egress-disabled paths.
- Added `google-genai>=1,<2` to `pyproject.toml`.

## Verification Thresholds

- `retrieval_threshold = 0.7`
- `quote_threshold = 1.0`
- `support_threshold = 0.7`

Rationale: a citation is `verified` only when the cited chunk is semantically retrieved, the claimed quote is verbatim located in PDF coordinates, and local support similarity clears the same conservative relatedness bar. Failing any component prevents `verified`.

## Support Confidence

- Current support measure: local embedding cosine similarity between the summary sentence and the cited chunk text.
- This is deterministic and local.
- NLI/stance classification is deferred behind the support-scorer interface.

## Gemini Data Egress

- `GeminiSummaryGenerator` refuses to call Gemini unless `GeminiConfig.data_egress_enabled=True`.
- `GeminiConfig.from_environment()` reads `CALLOSUM_ALLOW_DATA_EGRESS`.
- API keys are not hardcoded; the default key env var is `GOOGLE_API_KEY`.
- Tests use `FakeSummaryGenerator`; the real Gemini call is not exercised.

## Deferred / Out Of Scope

- UI rendering, streaming, FastAPI routes, OpenAlex/Semantic Scholar, full-text acquisition, NLI models, and prompt polish.
- Gemini caching, token accounting, and retry/backoff are noted in the integration spec but deferred.

## Ambiguities / Questions

- No schema gap surfaced.
- `.claude/docs/build-log.md` still records Increment 8 as pending, but the current user prompt and repository state indicate Increment 8 is accepted; this did not affect the Stage 4 summarization work.

## Raw Pytest Output

Targeted summarization suite:

```text
.....                                                                    [100%]
5 passed in 4.85s
```

Full suite:

```text
........................................                                 [100%]
40 passed in 25.52s
```
