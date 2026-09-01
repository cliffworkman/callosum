# Increment 551 — resume duplicate scans without duplicate jobs

## Implemented

Closed backlog #62 at both lifecycle boundaries.

- `JobStore.create_or_get_active()` performs the active-job lookup and insertion under the store lock, returning
  whether the caller owns worker scheduling. Concurrent duplicate-scan POSTs therefore cannot create multiple
  pending/running jobs or Status rows.
- `POST /papers/duplicates` reuses a pending/running scan and schedules work only for a newly created job.
- Status navigation passes the clicked duplicate scan's exact `job_id` into `DuplicatesModal`. The modal polls that
  running, completed, or failed record directly instead of mounting into a fresh POST.
- An ordinary Library → Duplicates open still asks the idempotent start endpoint for the active scan, while
  **un-dismiss** remains an explicit fresh rescan after the persisted dismissal changes.

The result preserves the existing local-only duplicate detector, result schema, polling cadence, dismiss/undismiss,
merge flow, and Status destination. No provider/model call, egress, persistence migration, or destructive behavior
was added.

## Verification

- Focused job-store/API/frontend regression slice: **16 passed** (rerun after final formatting).
- Cross-feature Status regressions: **19 passed**.
- Duplicate detector/value regressions: **20 passed**.
- Generated `callosum-app.html` byte-sync regression: **1 passed**.
- Ruff format/check over all touched Python files: clean.
- `callosum-app.html` rebuilt with the pinned esbuild arguments through file-backed stdin/stdout, the already-
  documented Windows workaround for the active Dropbox/Python-pipe hang from inc 550.
- Bandit (touched backend files), Tach, line-budget gate, and `git diff --check`: clean.
- Targeted pre-commit gate (whitespace/EOF/conflicts/large files, Ruff format/check, line budget, Bandit, Tach):
  all passed.

## Revert

Revert the increment commit. There is no migration or durable-data transformation to undo; an in-flight scan remains
ephemeral in the existing process-local `JobStore`.
