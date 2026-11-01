# Increment 620 — Visible background modernization and Status integration

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on `4e2edc60`.
Local only: not pushed, not merged.

Authorized by the "Callosum 0.6.0 - Increment 620: Visible Background Modernization and Status Integration"
instruction. It implements release blocker **B9**. Status: **implemented and focused-tested (backend on disposable
libraries with scripted model/coordinator state; frontend logic under node). Not verified in a real browser and not in
a packaged first run.** No version bump, no release gate armed, no scientific behaviour changed.

## Implemented
- **`app/backend/modernization/presentation.py`** (new, pure): `summarize(status, run_message=)` maps the inc-617
  coordinator status to one summary: `state` (working / waiting / paused / action_required / complete / disabled), a
  plain `headline`, `attention` (terminal problems), one note per stage (model, classification, indexing), a grounded
  `progress` block for the current activity only, `eta_seconds` always null.
- **`routers/modernization.py`:** `GET /modernization` (and the Pause/Resume responses) add `summary`, `index_run`
  (message, byte-only disk check, auto-retry flag), `effective_retrieval` (the inc-618 resolution; incomplete forced
  Arctic → `ask_blocked`; cached ≤ 60 s keyed on its inputs), `verifier` (no-load preview, incl.
  `automatic_deberta_enabled`) and `library_empty`. `modernization_status_job(app)` builds the one Status row.
- **`routers/status.py`:** `/status/jobs` puts the derived "Library modernization" row first, hides
  `embedding_index_jobs` while modernization is enabled (`MODERNIZATION_COVERED_STORES`), and drops the row rather than
  failing if it cannot be derived. `StatusJob` gains `notes` and `persistent`.
- **`modernization/coordinator.py`:** `status()` try-acquires the lock for 0.2 s; during a classification pass it uses
  the cached counts instead of blocking for the whole pass.
- **`api/dependencies.py::preview_verifier`** + **`verifier_resolution.explanation`:** the no-load verifier preview,
  now shared by the NLI settings panel (`embedding_profiles._nli_state`, unchanged output) and the modernization panel.
- **Frontend.**
  - `04f_modernization_logic.jsx` (new, JSX-free): `INDEX_RUN_ACTIVE_STATES` (incl. `waiting_disk`),
    `modernizationPollDelay`, `whatsNewHeadline`, `MODERNIZATION_SETTINGS_NAV`, `_focusSettingsSection`.
  - `35j_modernization.jsx` (new): `LibraryModelsSection` owns one refresh loop for the modernization and retrieval
    panels; `ModernizationPanel` shows summary, stage notes, effective Ask retrieval and verifier, and Pause/Resume.
  - `35i_retrieval_profiles.jsx`: its private 2 s loop (which omitted `waiting_disk`) is removed; it receives state
    from the parent. `IndexRunStatus` uses the shared active list. The NLI selector is unchanged.
  - `04c_status.jsx`: `PersistentStatusRow` (no dismiss, no elapsed/ETA, stage notes); Clear finished keeps it.
  - `04e_whatsnew.jsx` / `whatsnew.json`: a 0.6.0 entry with `freshHeadline` and `actionKind: "modernization"`
    ("See progress and controls"); a library with no papers gets the fresh wording (one `/modernization` read).
  - `40_app.jsx` / `30c_frame.jsx`: Status `nav.section` and the notice action scroll Settings to the panel.
- **Help:** new "Library modernization" section; the Retrieval and Verification settings bullets rewritten
  (Automatic, temporary MiniLM, catch-up, complete index vs downloaded model, forced-incomplete fail-closed, verifier
  provenance, "possible disagreement").

## Key technical detail
- **No second truth.** The row and the summary are recomputed from stored rows (run row, intent, classification
  coverage, provisioner state) on every read, so they are identical after a restart and in every window.
- **Precedence:** paused intent → indexing actively running → classification running / owned elsewhere → model
  downloading → indexing starting → any wait → attention only → complete. Terminal problems ride alongside working
  stages in `attention`. With the model `invalid` or not installable, "waiting for the model" is reported as blocked.
- **Polling contract:** 2 s while a build is busy, 5 s during build waits (`retrying`, `waiting_resources`,
  `waiting_disk`), 3 s / 10 s for other working / waiting summaries, stop otherwise. One timer, cleared on every
  reschedule and on unmount.
- **No percentages:** grounded counts only; the provisioner has no reliable downloaded-byte count, so the download
  is a state label plus total size. No time estimate anywhere; the 4,000-paper estimate is not used in the UI.
- **§12 timing caveat (bounded, no code change):** v0.5.16 contains no `nli_profiles.py`, and inc 608 is not an
  ancestor of v0.5.16, so no released build could select DeBERTa. Mixed MiniLM2/DeBERTa verification receipts can
  exist only in browser-local timing history from dev builds of incs 608–618, before inc 619 keyed the stage by
  verifier. Those unkeyed receipts were all recorded on MiniLM2 unless a developer selected DeBERTa by hand; they age
  out of the bounded local history. Nothing is guessed retroactively.

## Manual verification script (owed; not run)
1. Copy a 0.5.16-shaped library to a disposable path; start with `CALLOSUM_MODERNIZATION=1` and that DB.
2. Open Status: exactly one "Library modernization" row, Local AI, with a headline, counts and three notes; no dismiss
   button, no time remaining. Click it: Settings opens scrolled to **Library modernization**.
3. Pause → the row shows paused; restart → still paused; both selectors unchanged. Resume → work continues.
4. Simulate low disk (or set the run row to `waiting_disk`): the retrieval panel keeps refreshing, shows required/free
   space, and returns to the running display when the row changes back.
5. After the 0.6.0 version bump (not in this increment): the notice shows once, its action opens the panel, dismissing
   it records 0.6.0 as seen; an empty library shows the short wording.

## Pytest
- New `tests/test_modernization_status.py`: **30 passed** (backend + node frontend logic; covers the 26 §13 items).
- Neighbouring suites at `-n 4` (modernization, status, status_timing, embedding_profiles, verifier_resolution,
  nli_profiles, arctic_activation, frontend_assembly, index_recovery, model_provisioning, summaries, help,
  whatsnew_gate, plus the new file): **340 passed**.
- Known gate failures unchanged (identical with and without this change, not refreshed or declined):
  `test_demo_experience_coverage::test_every_public_capability_claim_has_an_explicit_demo_disposition`,
  `test_demo_snapshot::test_static_build_is_self_contained_and_base_path_safe`,
  `test_website_how_it_works::test_primary_local_destinations_exist[demo/-target2]`.
- The full suite was **not** run (memory constrained). Recommended next: one bounded full run, e.g. `pytest -n 2 -q`
  on an idle machine.

## Files for the later demo/website reviews
User-facing changes since those gates' last reviews that this increment adds: `app/frontend/js/04c_status.jsx`,
`04e_whatsnew.jsx`, `04f_modernization_logic.jsx` (new), `30c_frame.jsx`, `35_settings.jsx`,
`35i_retrieval_profiles.jsx`, `35j_modernization.jsx` (new), `40_app.jsx`, `app/frontend/whatsnew.json`,
`app/backend/help/help_content.md`, `callosum-app.html`.

## Security
Self-review: `.claude/security-audits/2026-11-01_modernization-status-ui.md` (PASS, self-review; no independent review).
