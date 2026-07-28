# Increment 408 — Status Phase 2, Wave 2: real progress for Synthesize > Ask

## Implemented

Backlog #50's Wave 2: Ask (`api.state.summary_jobs`) previously only went pending→running→done —
`summaries.py`'s `_run_summarize_job` never called `mark_progress`, so it always showed the
Status popover's honest indeterminate spinner. This wave instruments the one genuinely
instrumentable stage without pretending to know the unknowable:

- **Retrieval + generation stay fully indeterminate — deliberately, not as a shortcut.** The LLM
  call (`generator.generate(...)`, `pipeline.py`) is a single opaque blocking HTTP request with no
  sub-progress signal available, and a cache hit (`llm_cache`) can make elapsed-so-far wildly
  unrepresentative of a real ETA. A fabricated percentage here would be a worse signal than an
  honest spinner, not a better one — so `on_progress` is never called before verification starts.
- **The per-candidate verification loop is now instrumented.** `app/backend/summarization/
  pipeline.py`'s `summarize_scope` gained an `on_progress: Callable[[int, int, str], None] | None`
  parameter. The verification stage — previously a nested list comprehension — is now an explicit
  `for index, candidate in enumerate(candidates, start=1):` loop, calling
  `on_progress(index, total_candidates, "Verifying claim")` once per candidate, after that
  candidate's citations are all verified.
- `app/backend/api/routers/summaries.py`'s `_run_summarize_job` passes
  `on_progress=lambda i, n, label: jobs.mark_progress(job_id, i, n, label)` into
  `summarize_scope(...)` — the exact `on_progress=lambda i,n,name: jobs.mark_progress(...)` pattern
  already used in `library.py` and `ocr.py`, no new plumbing invented. `on_progress` is a
  keyword-only parameter with a `None` default, so every other existing call site
  (`test_summarization.py`, `test_summary_overview.py`, `test_nli_support.py`,
  `tools/validation_harness.py`) is unaffected.

## Tests

- `tests/test_summarization.py`: two new tests at the `summarize_scope` level —
  `test_on_progress_reports_one_call_per_candidate_only_during_verification` (2 candidates → calls
  `== [(1, 2, "Verifying claim"), (2, 2, "Verifying claim")]`) and
  `test_on_progress_is_optional_and_never_called_with_zero_candidates` (0 candidates → `on_progress`
  never called, no crash).
- `tests/test_summaries.py`: `test_summarize_job_reports_real_progress_during_verification` —
  end-to-end through the real `/summarize` endpoint + `JobStore`, confirming the finished job's
  `Job.progress` shows `(2, 2, "Verifying claim")` (carrying forward per inc 406's `mark_done`
  behavior).

## Manual / live verification (real Gemini call, not a fake generator)

Started a disposable second callosum instance (port 8899, `.local/validation-summarize/
validation.sqlite`, real egress enabled via one of the permitted `.env` Gemini keys — never
touching Cliff's own running dev server on 8888, the inc-406/407 pattern), and ran a real 3-paper
"papers" scope Ask job (`top_k=10`) end to end:

- During retrieval + the real Gemini call: `progress: null` the whole time (~30+ seconds) — an
  honest indeterminate spinner, exactly as designed, not a bug.
- The moment verification began: `1/7 (ETA 458s) → 2/7 (197s) → 3/7 (110s) → 4/7 (83s) → 6/7 (19s)
  → 7/7 (0s)` — a real, live-shrinking bar and ETA.
- Finished: `status: "done", progress: {current: 7, total: 7, eta_seconds: null}` — the final
  count preserved, no ETA shown for a completed job (matching the retraction job's behavior from
  inc 407).

Frontend was not touched this wave either (no UI changes needed — `04c_status.jsx` already
renders whatever `GET /status/jobs` returns), so no rebuild/Playwright check was required.

## Pytest

`pytest tests/test_summarization.py tests/test_summaries.py -q` → **27 passed**.
`pytest -n 4 -q` (full suite) → **1679 passed, 1 skipped** (+3 from inc 407's 1676).
`python tools/check_line_budget.py` → all files within the 600-line cap.
`ruff format --check .` + `ruff check .` → clean.

## Backlog #50 status

Both waves of Phase 2 are now closed. `dedup_jobs` remains the one deliberately-indeterminate job
in the app (no per-item loop exposed to the router without restructuring the duplicate-detection
algorithm itself) — an honest gap, not an oversight, revisit only if that algorithm is restructured
for other reasons.
