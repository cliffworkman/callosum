# Increment 601 — Persist single-paper critiques + a reaccessible critique modal

The reader "acquire OA → Critique" flow (inc 598) worked in the packaged app, but the critique result was
**trapped**: it lived only in the in-memory job store (recomputed each view, never saved), and clicking its
Status entry routed to `synthesis/critique`, whose panel is bound to the **globally-selected** paper — so it
showed an empty critique for the wrong paper. This increment persists the critique per paper and gives it a
reaccessible modal, fixing both halves. **The critique computation and renderer are unchanged and reused.**

## Backend
- **`critical_read_snapshots` (migration 0083, `schema_critical_review.py`):** ONE current-only Tier-1 backbone
  snapshot per paper (`UNIQUE(paper_id)`; Refresh replaces — no history). Columns: `backbone_json`,
  `snapshot_schema_version`, `critical_review_version`, `content_fingerprint`, `requested_at`, `computed_at`.
- **`critical_review_repo.py`:** `read_backbone_snapshot` + `save_backbone_snapshot` (race-safe upsert:
  delete-then-insert, **writes only if `requested_at >= stored`** so an out-of-order Refresh can't regress).
- **`_run_critical_read_job` (`routers/critical_review.py`):** persists the backbone on completion via
  `run_write` (best-effort — a write failure never fails the in-hand critique). `critical_read_start` now dedups
  to **one in-flight run per paper** (`create_or_get_active_matching`, the acquire-oa/inc-587 pattern) + carries
  a monotonic `requested_at`.
- **`GET /papers/{id}/critical-read/snapshot` (`routers/critical_review_snapshot.py`, sibling for the 600 cap):**
  returns the persisted backbone (validated through `ScrutinyBackboneResponse`) + `computed_at`, a narrow
  `stale` hint, `refresh_required`, and `running_job_id`. Runs nothing.

## Frontend
- **`08x2_critical_modal.jsx` (new):** `CriticalReadModal` reuses the hoisted `ScrutinyBackboneView` (the same
  renderer as the Synthesize → Critique tab) + `CriticalReadModalHost`, a self-hosted controller (the
  FeedbackLauncher pattern) listening for `callosum:open-critical-read`.
- **`30h_reference_finder.jsx`:** the reader critique states gained **View critique** (dispatches the event) so
  closing the reference finder no longer loses the result.
- **`08x_methods_critical.jsx`:** the Critique tab loads the persisted snapshot on mount (shows the last result
  instead of idle; a running Refresh stays running).
- **`status.py` `JOB_NAV_DEFAULTS`:** `critical_review_jobs` → `{modal: "critical-read"}` (carries the job's own
  `paper_id`) instead of the selected-paper-bound tab — the fix for the "empty critique on the wrong paper" bug
  (symmetric with the set-flow fix documented right beside it). `40_app.jsx` dispatches the event on that nav.

## Approved-constraint compliance (c1–c7)
- **c1 fulltext gate everywhere:** the modal offers Run/Refresh only when `chunk_count > 0`; `backbone == null` +
  metadata-only → honest "Critique needs the full paper." No path critiques metadata/abstract. (The tab already
  gated on `hasText`.)
- **c2 race-safety:** one in-flight run per paper + the `requested_at` monotonic write guard; frontend, a job's
  `onDone` wins and a late snapshot GET never clobbers it.
- **c3 narrow staleness:** the canonical `compute_content_fingerprint` (chunk ids + attachment checksums) →
  "the paper's full text has changed since this was computed" ONLY — not evidence-source/retraction detection
  (that's the backlog issue). Not an invented version.
- **c4 durable payload versioning:** `snapshot_schema_version` + `critical_review_version`; read validates
  through `ScrutinyBackboneResponse`; incompatible/unparseable → `refresh_required`, never a crash/misrender.
- **c5 Status = paper + job state:** explicit `paper_id`; a running Refresh over a stale snapshot stays visibly
  running (`running_job_id`).
- **c6 no cap-gaming:** the snapshot READ was split into a sibling router (`critical_review_snapshot.py`) to keep
  `critical_review.py` ≤600; in `40_app.jsx` the modal host is one line, offset by two *genuine* consolidations
  reflecting inc-600's "one destination, two facets" model (the gaps/overlooked nav + render) — not compression.
- **c7 current-only:** exactly one snapshot per paper; Refresh replaces. No history/versioning/monitoring.

## Gates
- **Security audit:** `2026-09-13_critical-read-snapshot.md` — **PASS** (local-only, no egress, no client-writable
  payload, race-guarded, fail-closed on corrupt/old rows).
- **Principles (#9):** reuses the aligned critical-read machinery; a persisted signal stays honest (always dated,
  refreshable, narrow stale hint). No new score/verdict; snapshotting doesn't change epistemics.
- **Latency (#12):** persistence REMOVES recompute-on-reopen (a win); no new per-item inference.
- **Tests:** `tests/test_critical_read_snapshot.py` (7 — write/guard/version/parse/staleness/cascade); a real
  Playwright test (`test_smoke.py::test_reaccessible_critique_modal_opens_from_event_and_honors_fulltext_gate`,
  passes headless — event→modal, reused renderer, stale hint, and the fulltext gate); assembly 87;
  `test_critical_review.py` green; QA 441/441 (route_67 covers the wildcard endpoint); tach + ruff + line budget.
- **Not built (backlog):** auto-refresh a stale critique when its evidence sources change (a cited paper is
  retracted/corrected) — see the GitHub issue to open.

## Manual verification (owed — packaged app)
Reader: acquire OA → critique → **close the reference finder** → reopen via **View critique** and via the
**Status** row → same result for the *right* paper (not the selected one); **Refresh**; both inc-598 epistemic
branches; a metadata-only reference shows the honest "needs the full paper" state.

Not part of a shipped release yet — rides a future 0.5.x cut. 0.5.14 is immutable.
