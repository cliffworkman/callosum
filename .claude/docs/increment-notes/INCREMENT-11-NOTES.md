# Increment 11 Notes

## Implemented

- Added a summarization probe to `tools/validation_harness.py`.
- New CLI scope flags:
  - `--summarize-query "..."`
  - `--summarize-papers 1,2,3`
  - `--summarize-cluster <node-id>`
- New support calibration flags:
  - `--support-scorer embedding|nli`
  - `--support-threshold <float>`
- The probe builds a `SummaryScope`, calls the existing `summarize_scope`, and renders the persisted trust chain into `validation-report.md`.
- The report shows each sentence, each citation, cited paper/page/chunk, located quote status, retrieval/quote/support scores, citation status, flagged sentences, and a sorted support-score distribution.

## Egress And Credentials

- Real Gemini generation is skipped unless `CALLOSUM_ALLOW_DATA_EGRESS` is enabled and `GOOGLE_API_KEY` is present.
- If egress is disabled or the key is missing, the harness reports `Generation skipped` and still writes the report.
- `--support-scorer nli` constructs the real local `NLISupportScorer`; first use may download model weights through the existing scorer behavior.
- Tests inject fake generators/scorers and never call Gemini or load the real NLI model.

## Support-Score Distribution

- The distribution is reported as a descending table of support confidence by citation.
- It is diagnostic only; the harness does not choose or mutate thresholds automatically.

## Deferred

- No UI, FastAPI route, streaming, discovery, full-text acquisition, or prompt-polish changes.
- No verifier, scorer, schema, or `summarize_scope` changes.

## Real-Data Run

- Not run in this increment. The tests use synthetic PDFs and deterministic fake generation/scoring only.

## Raw Pytest Output

```text
pytest -q
..............................................                           [100%]
46 passed in 34.65s
```
