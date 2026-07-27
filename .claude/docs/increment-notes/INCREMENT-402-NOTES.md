# Increment 402 — surface WIP statcheck in the Methods panel's Statistics section

**Date:** 2026-07-27
**Status:** Implemented and verified live (Playwright); frontend-only, no backend change; full test
suite pending final confirmation (see `changes.md`).

## Context

The first of three "quick win" increments from the larger "wire WIP manuscripts into Methods/
Discover/Synthesize/Work tools" request. Research found a full, working WIP-side statcheck backend
already existed (`app/backend/api/routers/wip_checks.py` + `wip_checks_repo.py`, duck-typing into the
same `run_statcheck()` Library papers use, re-extracting text on demand from disk) — it was simply
never surfaced in the Methods-panel "Statistics" section, only inside `WipDetails`'s own "Checks" tab.
Every WIP manuscript has `ctx.selectedPaper === null` by design (a manuscript has no `papers.id`), so
opening Methods → Statistics while a WIP tab was active showed "Select a paper…" regardless.

## Implemented

- Extracted the presentational `WipChecks` component (props-only, no internal fetching) out of
  `10f_wip.jsx` into a new `10k_wip_checks.jsx`, alongside a new self-fetching wrapper
  `WipStatcheckSection({ manuscript, ctx })` that fetches `/wip/manuscripts/{id}/checks` +
  `/wip/manuscripts/{id}/snapshots` itself (mirroring `StatcheckPaper`'s self-fetch shape) and renders
  `WipChecks` underneath. `10f_wip.jsx`'s own Checks-tab usage is unchanged (629→439 lines, well under
  cap; new file 118 lines) — pure extraction, zero behavior change to the existing WIP tab.
- `06_methods_statcheck.jsx`'s "Statistics" section registration now branches on
  `ctx.researchContext.kind === "manuscript"` — the exact `05_panes.jsx` "Details" precedent — routing
  to `WipStatcheckSection` for a WIP manuscript, else the untouched `StatcheckSection` for a paper.
- **Cross-mount sync**: since the accordion is "mount-but-hide" (every section stays mounted, per
  `05_panes.jsx`'s own comment), a WIP tab open simultaneously shows the checks UI in *three* places —
  the Methods-panel Statistics section (new), the center-pane WIP tab's own Checks sub-tab, and (in
  compact form, no Checks tab) the Methods-panel Details section. Running a check from one of the two
  Checks-capable surfaces needed to be reflected in the other without a manual reload. Exposed the
  `refresh` counter `useWipWorkspace` already maintained internally (`10h_wip_filters.jsx`, previously
  only its setter `reload` was returned) as `wip.refresh`, threaded it into `paneCtx.wipRefresh`
  (`40_app.jsx`) and as a new `externalRefresh` prop on `WipDetails` (both call sites:
  `30c_frame.jsx`'s full workspace tab, `05_panes.jsx`'s compact Details-pane mount) added to its fetch
  effect's dependency array. `WipStatcheckSection`'s own fetch effect depends on `ctx.wipRefresh` too,
  and its `onReload` simply calls `ctx.onReloadWip()` (the existing bump-counter function) — the same
  established `axisRefresh`/`queueRefresh`/`libRefresh` idiom already used throughout `paneCtx`,
  applied to WIP for the first time.

## Key technical detail

No schema/endpoint change was needed at all — this increment is purely a frontend routing/reuse
change. The only non-trivial part was the cross-mount refresh: two independent component instances
(one in the Methods sidebar, one in the WIP tab's own workspace) read/write the *same* manuscript-
scoped data but don't share React state, so a naive implementation would show a run in one place and
not the other until the user switched tabs and back. Threading the existing `wip.refresh` counter
through as a dependency-array value (not just calling its setter) closes that gap the same way every
other cross-panel refresh signal in the app already does.

## Manual verification script

1. Open a WIP manuscript tab (no Library paper equivalent). Expand Methods → **Statistics** — confirm
   it shows "Deterministic checks"/"Content checkpoints" (the WIP Checks UI), not "Select a paper…".
2. Click "Run statcheck" on a manuscript with no primary file set — confirm an inline, honest error
   ("Select a primary manuscript file before creating a checkpoint") appears, no crash, no unhandled
   console error beyond the expected failed-request log line.
3. Switch to the manuscript's own **Checks** tab (center pane) — confirm it shows the identical
   "No checks run yet" state (no divergence between the two mounts).
4. Switch to a Library paper — confirm Methods → Statistics is pixel-identical to before (whole-
   library batch + per-paper cached-result UI, `StatcheckSection`/`StatcheckPaper` untouched).

All verified live via Playwright against the real WIP-watched folders (none had a primary file set, so
the success-path redisplay-after-a-real-run wasn't exercised visually this pass — the error path and
the dual-mount consistency were both directly confirmed; the success path is unchanged code reused
verbatim from the already-tested `WipChecks`/`wip_checks.py`).

## Pytest

`pytest tests/test_frontend_assembly.py tests/test_wip_api.py -q` — 64 passed (one existing assembly
test's literal-string assertion updated for the new `externalRefresh` prop on `WipDetails`'s workspace
call site — `test_wip_is_a_distinct_library_level_context_and_never_leaks_stale_paper_selection`).
Full suite before merge: see `changes.md`.

## Files changed

- `app/frontend/js/10f_wip.jsx` (WipChecks extracted out; `externalRefresh` prop + dependency)
- `app/frontend/js/10k_wip_checks.jsx` (new — `WipChecks` + `WipStatcheckSection`)
- `app/frontend/js/06_methods_statcheck.jsx` (Statistics section branches on `researchContext.kind`)
- `app/frontend/js/10h_wip_filters.jsx` (expose `refresh` counter value, not just its setter)
- `app/frontend/js/40_app.jsx` (`paneCtx.wipRefresh`)
- `app/frontend/js/30c_frame.jsx`, `app/frontend/js/05_panes.jsx` (`externalRefresh` at both
  `WipDetails` call sites)
- `tests/test_frontend_assembly.py` (updated literal-string assertion)
- `.claude/qa-routes/route_75_wip_workspace.md` (extended: step 18, `fe:` file list)
- `callosum-app.html` (rebuilt)
