# Increment 318 — automatic cadence refresh for the Retraction Watch DB mirror (backlog #31)

## Context
The Retraction Watch mirror only ever refreshed on a manual click (Settings' "Refresh database," or the
Library-header "Retractions ↻" full batch). Settings already showed a 30-day staleness nudge (v1, inc 134) but
nothing acted on it — a long-running instance could go stale indefinitely unless a human happened to notice.
This closes backlog #31's remaining slice: an opt-in, staleness-gated automatic refresh.

## Design (confirmed with the user before implementing)
callosum has no backend scheduler (no APScheduler/cron — confirmed by absence in `requirements.txt`); every
"keep this fresh automatically" feature is a **client-driven, staleness-gated pull**, not a server-side timer —
the Literature Feed's own opt-in auto-refresh (`30e_feed.jsx`, default off, 6h staleness gate) is the direct
precedent, and its code comment states the deliberate constraint plainly: "pull-first... never a background
daemon." The original Retraction Watch security audit
(`.claude/security-audits/2026-06-26_retraction-watch.md`) also characterizes today's design as *"manual-
triggered... no covert/standing data movement"* — an automatic cadence is exactly the kind of change the
Principles gate (rule #9) asks you to reflect on before building, since it turns "manual" into "standing." The
aligned choice, matching Feed's own precedent, is an opt-in toggle (default off) with the snapshot age always
visible — not a silent timer with no user-facing control.

**Refresh scope** (a real decision, put to the user before implementing): the cadence refresh calls the
**full batch** (`POST /methods/retraction/run` — mirror refresh + re-check every paper's DOI), the same endpoint
the existing "Retractions ↻" library-header button already uses — not the mirror-only endpoint. A mirror-only
refresh would be invisible: nothing re-reads the fresher table until the next manual check or import, so
"automatic" wouldn't actually deliver its point (catching a newly-retracted paper the user already has).

## Implemented
1. **`app/frontend/js/03_library.jsx`** (`useLibrary` hook): a new `triggerRetractionAutoRefresh`, fired from the
   same mount+window-focus effect that already runs `triggerWatchedRescan` (inc 98/136) — both are "library-wide
   background reconcile on launch/focus" concerns, so one effect handles both, not two. Gated on
   `healthLoaded && !readOnly` (same read-only-companion guard as the watched-folder rescan, so a launch attempt
   never 403s before `readOnly` is known) `&&` opted-in (`localStorage["callosum.retractionAutoRefresh"] ===
   "1"`). When gated open: `GET /methods/retraction/database` first (cheap, read-only) to read `retrieved_at`,
   computing `ageDays` the same way Settings already does; only when `ageDays > 30` or never-downloaded does it
   proceed to `POST /methods/retraction/run` and poll to completion, then call the already-in-scope
   `refreshRetractionChip()` so the header "⚠ Retracted · N" chip updates without a reload.
2. **`app/frontend/js/35_settings.jsx`** (`LocalMaintenanceSettings`): an opt-in checkbox ("Auto-refresh when
   stale (checked on launch)") right below the existing staleness nudge, default off, reading/writing the same
   `localStorage` key the trigger in `03_library.jsx` checks. No prop/ctx threading between the two files —
   localStorage is the shared, decoupled channel (the two components are otherwise unrelated).
3. **A one-line consolidation while touching this recipe:** `30e_feed.jsx`'s existing `.feed-autorefresh`
   checkbox class was renamed to the generic `.auto-refresh-toggle` (styles.css) now that a second feature
   shares its exact recipe — a feature-named class for a checkbox two different features now use was a legibility
   smell not worth leaving behind.

## Key technical detail — a real gap found during live verification, not assumed
Live-testing against a QA fixture with no contact email set (so every refresh attempt fails, per the existing
fail-closed design — `_run_retraction_all_job` logs `database_refresh_error` and continues rather than aborting)
surfaced that `retrieved_at` then **never** resolves to "fresh." Without an additional guard, every single window
focus would re-run the full per-paper check batch — real Crossref/OpenAlex calls per paper — indefinitely, not
just once. Fixed with a same-session, ref-based **1-hour attempt throttle** (`lastRetractionAttempt`, checked
before even the cheap staleness `GET`) as a safety net alongside the 30-day staleness gate: the 30-day gate
handles the success path (a completed refresh naturally quiets things for a month); the 1-hour throttle bounds
the failure/never-resolves path. Confirmed live: dispatching 3 rapid `focus` events after one real attempt
produced zero additional requests.

## Manual verification (Playwright, this session, against fresh `tools/qa/_qa_serve.py` fixtures)
1. Confirmed the checkbox renders unchecked by default in Settings → Local Maintenance, and that with it off, a
   full page load makes **zero** `/methods/retraction/database` or `/methods/retraction/run` requests (only the
   pre-existing, unrelated `/methods/retraction/summary` chip fetch).
2. Checked the box, confirmed `localStorage["callosum.retractionAutoRefresh"] === "1"`, reloaded, and confirmed
   it stayed checked.
3. With the mirror never-downloaded (a fresh fixture) and the box checked, reloaded and confirmed via the
   network log the exact expected sequence: `GET /methods/retraction/database` → `POST /methods/retraction/run`
   (202) → polling `GET .../run/{job_id}` → a final `GET /methods/retraction/summary` (the chip refresh). The job
   completed with `status: "done"` and an honest `database_refresh_error` detail (no mailto configured in the
   fixture) — the existing fail-closed design held throughout, 0 console errors.
4. Dispatched 3 rapid synthetic `focus` events immediately after — confirmed **zero** additional requests (the
   1-hour throttle found in step 3's fixture behavior, added and reverified in the same session).

## Pytest
Full suite run in progress at time of writing this file (prior runs this session: 1303→1304 after the QA
re-triage batch); `tests/test_frontend_assembly.py` gained
`test_retraction_watch_cadence_auto_refresh_is_opt_in_and_staleness_gated`, asserting: the trigger reads the
shared localStorage key, the 1-hour throttle check, the staleness-gate early-return, the full-batch POST call,
that it's fired alongside the existing watched-folder trigger (not a second effect), the chip-refresh
completion callback, and the Settings checkbox's default-off state + shared key. `ruff check .` /
`ruff format --check .` clean; `python tools/check_line_budget.py` clean (348 files);
`python tools/qa/build_surface_map.py check`: API 250/250 (no new endpoints — pure reuse of existing ones), FE
the same pre-existing 15-surface `35a_mypubs.jsx` gap (unrelated, unchanged).

## Gates
- **QA (#10):** `route_74_retraction_watch.md` extended — `api:` header gained
  `/methods/retraction/run`+`/run/{job_id}` (now exercised by this route too, not just route 39), `fe:` gained
  `03_library.jsx`, a new standing assertion (opt-in + visible, never a silent standing timer) and a new step
  (checkbox renders/persists, fires only when checked+stale, doesn't fire when off or fresh).
- **Principles/A-A (rule #9):** named explicitly above, not treated as incidental — the opt-in/default-off/
  visible-toggle design is the direct aligned response to the "manual → standing" tension this change introduces,
  following Feed's own established precedent rather than inventing an easier, less visible mechanism.
- **DESIGN.md:** no entry added — the checkbox reuses an existing, now-generalized recipe (`.auto-refresh-toggle`)
  rather than introducing a new one; the project doesn't document individual checkbox recipes at that granularity
  elsewhere either.

## Next
None outstanding from this slice. The other backlog #31 sub-item (folding the statcheck signal chip into the
unified findings facet) remains a deliberate v1 non-goal, unchanged by this increment.
