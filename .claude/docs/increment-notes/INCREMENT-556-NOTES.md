# Increment 556 Notes — missing PDF resilience for Synthesize → Ask

## Outcome

Synthesize → Ask no longer aborts when an attachment PDF was moved or removed after Callosum extracted
its evidence chunks. Exact rectangle lookup is optional enrichment: when neither stored path is currently
readable, the existing citation verifier continues from the immutable chunk text, page, and bounding region
and labels the result with `coordinate_precision="region"` rather than claiming an exact highlight.

The user-reported `Workman et al. - 2021 - Unknown.pdf` and
`Gonzalez et al. - 2023 - Unknown.pdf` paths were not phantom papers. Read-only inspection of the packaged
desktop database found that both were extra legacy OpenAlex attachments associated with real, titled papers;
each paper also had a primary attachment. The legacy OA files were absent while their extracted chunks remained.

## Root causes

1. `locate_quote_for_attachment()` unconditionally passed the preferred stored path to the PDF locator. A
   stale path therefore raised `FileNotFoundError` before the citation verifier could use its existing honest
   stored-chunk fallback.
2. Managed acquisition filenames used the publication venue as their third component and emitted `Unknown`
   whenever venue metadata had not yet arrived. Acquisition can precede metadata enrichment, so a paper with a
   known title could acquire a filename that misleadingly looked like an unknown/phantom paper.

## Implementation

- `app/backend/pdf_processing/location.py`
  - tries the resolved path and then the original path;
  - avoids duplicate path work;
  - treats missing, inaccessible, or concurrently removed files as an exact-location miss;
  - returns `QuoteMatch(found=False)` so the existing verifier preserves stored page/region provenance.
- `app/backend/acquisition/fetch.py`
  - falls back to the known paper/CSL title whenever venue metadata is absent;
  - retains `Unknown` only when both venue and title are absent;
  - does not rename existing user files or mutate legacy attachment rows.
- `app/backend/help/help_content.md`
  - documents the missing-file degradation path and its exact-coordinate limitation;
  - updates the old key-only synthesis setup copy to include managed Local AI.

## Scientific and latency contract

- Exact coordinates remain preferred whenever an attachment is readable.
- The quote, support, and sentence-verification thresholds are unchanged.
- Retrieval order, model input, batching, model reuse, and inference work are unchanged.
- Missing files do not trigger a cloud call or broaden privacy scope.
- The only added work on the synthesis path is at most two bounded local `Path.is_file()` checks during
  exact-coordinate enrichment. This is correctness behavior, not model-path work, so no latency benchmark is
  required under `.claude/LATENCY.md`.

## Verification

- Focused regression suite:
  `uv run pytest -q tests/test_summarization.py tests/test_pdf_processing.py tests/test_acquisition.py`
  — 60 passed.
- Broader affected suite:
  `uv run pytest -q tests/test_summarization.py tests/test_summaries.py tests/test_summarize_selected.py
  tests/test_pdf_processing.py tests/test_acquisition.py tests/test_acquisition_sources.py` — 115 passed.
- `uv run ruff format --check` and `uv run ruff check` on the four touched Python files — passed.
- `uv run python tools/check_line_budget.py` — passed (576 application-source files).
- `uv run python -m tach check` — passed.
- `uv run python tools/run_bandit.py` — passed.
- Website coverage drift was reviewed and refreshed for increment 556; no public showcase claim or visual
  change is required for this narrow recovery fix.
- Targeted pre-commit, final `git diff --check`, package version checks, and release CI are recorded in the
  final commit/report.

## Manual acceptance after the patch update

1. Open **Synthesize → Ask** against the same library state that contains the stale legacy OA attachments.
2. Run the question that previously named either missing `Unknown.pdf` path.
3. Confirm the synthesis completes instead of returning `FileNotFoundError`.
4. Confirm citations backed by an unavailable PDF show honest region precision and do not claim an exact
   highlight; citations backed by available PDFs still behave normally.
5. Confirm no cloud request occurs when Local AI is selected.

## Revert

Revert this increment commit. No database migration, attachment deletion, file rename, or user-data mutation
is involved.
