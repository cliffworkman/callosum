# Increment 225 — progress ETA (#4)

## Implemented

Close-out of backlog #4 (progress indication). Long async jobs showed determinate "X / N" + a fill (inc 142) and
a filename in the scan label (inc 214) but no **ETA**. Added a rough "~Ns left" estimate, additive + no
transaction risk:

- `app/backend/api/job_store.py` — `Job` gains `started_at: float | None`, stamped (monotonic) on `mark_running`
  and **preserved across every `mark_progress`** (via a `_started_at` helper) so the ETA measures from when the
  job began, not the last tick. New `Job.eta_seconds()` = `elapsed / current × remaining` (None until there's a
  `started_at` + ≥1 unit of progress; 0 once complete).
- `routers/library.py` — `JobProgressOut` gains `eta_seconds`, computed in the shared `_progress_out(job)` →
  covers **scan / watched-rescan / import / enrich** at once. `routers/citation_counts.py` — the
  `CitationRefreshProgress` mirror gains it too.
- Frontend — a hoisted `_fmtEta(s)` ("45s" / "3m" / "2h") in `10_pdf_layer.jsx`; `ProgressBar` appends
  " · ~Ns left" when `eta_seconds > 0`; the `10b_libmenus.jsx` Citations + Enrich menus capture `eta` into their
  `prog` and render " ~Ns".

**Out of scope — cancel:** correct cooperative cancellation needs the four `_run_*_job` single-`engine.begin()`
blocks split into per-item transactions — the same infra as the open SQLite read-then-write concurrency item.
Deferred to that pass (recorded in the backlog).

## Key technical detail

`mark_progress` rebuilds the frozen `Job` each tick (inc 142), which would drop `started_at`; `_started_at(job_id)`
reads the existing job (under the held lock) and carries it forward, so the elapsed clock is continuous. `eta_seconds`
is computed at status-read time (it depends on "now"), so it lives as a method on `Job`, not a stored field.

## Manual verification script

Three ways (the headed harness needed two pre-existing fixes — see below):
- **Unit** (`tests/test_job_store.py`): `started_at` stamped once + preserved across ticks; `eta_seconds`
  extrapolates (~40s for 2/10 after 10s elapsed), None without progress/started_at, 0 when complete.
- **Live API integration** (probe): a real slowed-import job's `GET /library/import/{id}` payload carries
  `progress.eta_seconds` decreasing 2→2→1→…→0 across the embed phase — proving Job → JobProgressOut → endpoint.
- **Headed** (`.local/visual/drive_inc225_progress.py`, no egress): the import modal's ProgressBar renders
  **`Embedding papers — 3 / 8 · ~2s left`**; 0 console/page/genai.

**Harness fixes (the inc-142 template had drifted, so even `drive_inc142_progress.py` failed):** (1) the driver
now sets an empty `CALLOSUM_LIBRARY_DIR` so the inc-160 on-launch auto-rescan doesn't pull the real 77-PDF
`library/` into the seeded DB; (2) `seed()` cleans the inc-219 `-wal`/`-shm` sidecars (not just the `.sqlite`), so
stale rows don't survive across runs and cause DOI-collision "N failed" imports. (Worth carrying to other
inc-142-derived drivers.)

## Pytest

**791** (+2 `test_job_store.py`). ruff clean; frontend rebuilt (`callosum-app.html` in sync). **QA surface
unchanged** (161/161 API + 719/719 FE, 0 uncovered — `eta_seconds` is an additive optional field on existing
status payloads, no new route/element). No migration / egress / dependency / audit / Principles trigger.
