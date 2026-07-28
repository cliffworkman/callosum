# Increment 407 — Status Phase 2, Wave 1: library-refresh progress coverage

## Implemented

Backlog #50's Phase 2 was scoped and split into two waves at Cliff's request (his call on the
split, deferred to the assistant), with an explicit ask to fold "library refreshes (citations &
metadata)" into the first wave. Two research agents audited the actual current state before any
design work:

- **Citation-count refresh, metadata enrichment, library scan, library import, and bundle
  import already report real progress.** All five already call `JobStore.mark_progress` with
  real current/total (papers processed / total papers, etc.) — they already rendered a real bar
  + ETA in the Status popover with zero code change. This wave's actual "library refresh" ask was
  already satisfied by what shipped in inc 406; nothing needed building there.
- **The one genuine gap found: `retraction_jobs` (the library-wide retraction batch).** It has a
  plain `for paper_id in ids:` loop (`app/backend/api/routers/methods_retraction.py`,
  `_run_retraction_all_job`) but never called `mark_progress`. Fixed with the same pattern every
  other batch job already uses: `jobs.mark_progress(job_id, total, len(ids), "Checking
  retractions")`, called after each paper's processing (success or failure), matching
  `citation_counts.py`'s exact placement.
- `tests/test_retraction.py`'s existing `test_retraction_endpoints_and_filter` extended with an
  assertion that the finished job's `Job.progress` shows `(3, 3, "Checking retractions")` — proving
  `mark_done`'s inc-406 carry-forward behavior works end-to-end for this job too.
- **Ruled out for this wave:** `dedup_jobs` has no per-item loop exposed to the router
  (`find_duplicate_groups` does one in-memory bulk compare) — instrumenting it means restructuring
  the duplicate-detection algorithm, not a trivial add. Left indeterminate, matching Phase 1's
  honest-spinner posture. `text_health_jobs` was re-checked and already had progress too — no
  action needed there either.

## Key technical detail

The retraction batch's own response model (`RetractionRunResponse`) has no `progress` field and
doesn't need one — the Status popover reads progress directly off the underlying `JobStore`
(`request.app.state.retraction_jobs`) via its own aggregator, not through this router's polling
endpoint. So the fix is purely the `mark_progress` call itself; no response-model or endpoint
change was needed.

## Manual / live verification

Started a disposable second callosum instance (port 8899, `.local/validation-summarize/
validation.sqlite`, never touching Cliff's own running dev server on 8888 — the inc-406 pattern),
kicked off all three jobs for real, and polled `GET /status/jobs`:
- Citation-count refresh: finished at `178/178`, real progress the whole way (already working).
- Metadata enrichment: real per-paper progress with the paper's title in the label and a live
  ETA (already working) — e.g. `current: 9, total: 210, eta_seconds: 419`.
- Retraction check: **confirmed the new instrumentation** — caught mid-run at `177/210` (ETA 6s,
  after the pre-loop Retraction Watch DB refresh phase, which has no per-item signal and
  correctly stays `progress: null` during it — an honest gap, not a bug), then `done` at
  `210/210`.

Frontend was not touched this wave (no UI changes needed — the existing `04c_status.jsx` already
renders whatever `GET /status/jobs` returns), so no rebuild/Playwright check was required.

## Pytest

`pytest tests/test_retraction.py -q` → **27 passed**.
`pytest -n 4 -q` (full suite) → **1676 passed, 1 skipped**.
`python tools/check_line_budget.py` → all files within the 600-line cap.
`ruff format --check .` + `ruff check .` → clean.

## Wave 2 (not built this pass)

Ask's real-progress instrumentation was traced and designed but deliberately deferred to its own
build pass — see the plan backup at `.claude/backups/plans/2026-07-28_status-phase2-waves.md`
for the full design (leave retrieval+generation indeterminate — the LLM call is a single opaque
blocking request with no sub-progress signal, and a cache hit would make a naive ETA misleading;
instrument only the per-candidate/per-citation verification loop, which is typically the
majority of a multi-citation Ask's wall-clock time).
