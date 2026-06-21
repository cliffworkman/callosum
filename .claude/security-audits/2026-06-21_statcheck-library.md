# Security audit — statcheck library-wide lens (inc 97)

**Date:** 2026-06-21
**Feature:** persist per-paper statcheck summaries + a batch "check all" job + a library filter for reporting
inconsistencies. Builds on the inc-95 recomputation engine (unchanged).
**Trigger(s):** new API endpoints (`POST/GET /methods/statcheck/run`) + a new DB-**write** path
(`open_science_signals`) + a new `GET /papers?signal=…` filter. No new dependency, no migration, no auth.

## Surface
- `app/backend/persistence/signals_repo.py` (NEW) — `store_statcheck` (OR-REPLACE upsert) + `get_statcheck_summary`.
- `app/backend/persistence/repository.py` — `list_papers(signal=…)` + `SIGNAL_FILTERS` allowlist + `list_live_paper_ids`.
- `app/backend/api/routers/methods.py` — the async batch endpoints + `_run_statcheck_all_job`.
- `app/backend/api/routers/papers.py` — the `signal` query param. `app.py` — `statcheck_jobs` JobStore.
- Frontend `35_settings.jsx` (Statistics-check section) + `40_app.jsx`/`10_pdf_layer.jsx` (the filter view + banner).

## Threat review
- **EGRESS / external calls / LLM.** **None.** Pure local recomputation over already-stored chunk text + a local
  DB write. Nothing leaves the machine; no model.
- **SQL injection (rule #3).** The write is a bound-param `insert(...).prefix_with("OR REPLACE")`; `signal_type` /
  `source` / `status` are **server-side constants** (never client input). The library filter takes a `signal`
  query param whose value **indexes the `SIGNAL_FILTERS` allowlist** → a fixed `(signal_type, status)` subquery;
  an unknown value is ignored (no filter), never interpolated. Reads use bound params.
- **Write-path safety.** One summary row per `(paper_id, signal_type='statcheck', source='statcheck')`; the UNIQUE
  constraint + OR REPLACE make re-runs **idempotent** (overwrite, never duplicate, never unbounded growth). The
  `paper_id` FK has `ON DELETE CASCADE`, so purging a paper cleans its signal. No other table is touched.
- **Resource exhaustion.** The batch is an **async job** (doesn't block the event loop), bounded by the live-paper
  count × the inc-95 per-paper `MAX_RESULTS` cap; each paper's scan is linear (anchored regexes). A re-run is safe.
- **Input validation.** Reuses the inc-95 defensive parser (malformed/degenerate stats dropped, never fatal). A
  paper with no chunks → `checked: 0`, stored as `consistent` (the snippet records `checked:0`, so "no stats" is
  distinguishable on inspection from "stats all consistent").
- **Output encoding.** The library list + banner render as React text (escaped). The persisted `evidence_snippet`
  is app-authored JSON (counts), not shown raw.
- **Principle/values posture (the load-bearing design constraint, not a vuln).** The aggregate is a **filter, not
  a rank/score** (no sorting by inconsistency count; no composite number); framed **non-accusatorily** ("a list to
  review, usually innocent — not a verdict"); coverage stated; the per-test evidence stays in the inc-95 Details
  view. See the inc-97 notes' gate write-up.

## Negative-path checks (run)
- `store_statcheck` re-run → OR-REPLACE keeps exactly one row, status flips (test). ✓
- `list_papers(signal="statcheck-inconsistent")` returns only inconsistent papers; **unknown value ignored**
  (no filter) (test). ✓
- Batch run over a mixed library → summary `{total, checked, flagged}`; the filter then returns only the flagged
  paper — **not a ranking** (test). ✓ `GET /methods/statcheck/run/{bad}` → 404. ✓
- Empty library → batch completes with zero counts; filter view empty (not an error).

## Result
**Security Audit: PASS.** Local-only (no egress/LLM), bound-param SQL with a constant-only write + an allowlisted
filter, idempotent bounded async batch, defensive (reuses inc-95). The principle risk (aggregate → rank/accusation)
is structurally declined: a filter + honest counts + non-accusatory framing, no score.
