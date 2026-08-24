# Increment 496 — calibrated stage-aware job timing

## Implemented

- Every running Status row now shows a monotonic elapsed duration. Client-tracked synchronous AI operations use
  their existing local start/finish timestamps; backend jobs expose monotonic elapsed time through the Status API.
- Synthesis and single-paper, Set, and WIP Critical Read publish a small user-facing stage taxonomy. Stage transitions
  carry only controlled timing identity plus numeric workload size and do not wake result-completion long polls.
- The browser stores schema-v1 timing receipts locally, capped at 24 per comparable shape and 200 total. Comparable
  means the same workflow/model/execution identity, stage, and coarse workload bucket. Three receipts permit a broad
  recent range; eight narrow, non-provider-variable receipts permit a remaining-time estimate. Overruns switch to
  “Taking longer than recent runs”; missing/sparse local history remains stage + elapsed, and opaque provider calls
  say timing varies.
- The synthesis primary job remains complete before supplementary Overview generation. The Overview lifecycle keeps
  its existing pending/running/complete/failed UI and never extends the primary elapsed/ETA boundary.

## Key technical detail

The estimator uses a rolling median and a guarded empirical range: min/max for the first 3–4 comparable receipts,
then p10/p90, widened by 10% for scheduler/host variation. “High” requires at least eight samples, relative spread
at most 35%, and a non-variable stage; all other estimable histories are “moderate.” History version mismatch or
malformed storage safely returns to first-run behavior. Receipts never include paper/prompt/citation text, titles,
authors, paths, raw endpoints, or secrets.

Controlled leave-forward calibration (12 privacy-safe numeric durations per shape; 9 predictions after warm-up) was:

| Stage shape | Median actual | Median absolute error | Median signed error | Guarded-range coverage |
|---|---:|---:|---:|---:|
| Provider-variable generation | 2.25 s | 0.30 s | -0.20 s | 77.8% |
| Stable local inference | 10.05 s | 0.15 s | -0.10 s | 100% |
| Workload-scaled local inference | 41.10 s | 1.40 s | -0.20 s | 100% |

These are estimator mechanics checks, not real-provider claims. Production confidence begins empty and learns only
from the current browser/device. A 10,000-update microbenchmark measured `JobStore.mark_stage()` at about 6.4 µs per
same-stage update on the development host; normal jobs emit only a handful of transitions.

## Manual verification script

1. Start a synthesis, switch to Library, open **Status**, and confirm the row shows a stage plus elapsed seconds.
2. Repeat comparable jobs at least three times and confirm a broad “Usually … total” range appears; use a fresh
   browser profile to confirm first-run stage + elapsed fallback.
3. Delay a provider fixture beyond its learned upper range and confirm “Taking longer than recent runs,” never 0 or
   a negative countdown.
4. Start single, Set, and WIP Critical Read jobs and confirm Preparing evidence → Embedding claims → Evaluating
   evidence → Finalizing result, with indeterminate rather than fabricated percent progress.
5. Block supplementary Overview generation: the synthesis row must be done while verified claims render and the
   Overview component independently says it is generating.
6. Run two jobs concurrently, reload, and confirm each row keeps independent authoritative status/elapsed state.
7. Inspect `localStorage["callosum.status-timing.v1"]`: only receipt id, timing/stage keys, coarse bucket, duration,
   and variability flag may appear; no scholarly content or credential may appear.

## Pytest and quality gates

- The final affected run passed 165 tests in 2m10s. The focused headless-Chromium Status flow passed in 29.34s with
  zero console/page errors and its existing mobile-width overflow assertion. The full root suite passed **2445 with
  3 skipped** in 21m55s using `pytest -n auto -q`.
- A final monotonic-display clamp then passed 91 status/frontend tests plus the same headless-Chromium flow (26.62s).
  The browser-grounded Multi-tasker experience pass found the compact stage/elapsed/provider-variance line readable,
  the click-back path intact, and no new dead end; no follow-up was required.
- Ruff format/check, Tach, the 562-file line budget, QA surface coverage (429/429 API surfaces), website coverage,
  frontend source/artifact equality, and `git diff --check` passed. Bandit was not installed in the environment.
  The dedicated review `.claude/security-audits/2026-08-23_calibrated-status-timing.md` ends PASS.
