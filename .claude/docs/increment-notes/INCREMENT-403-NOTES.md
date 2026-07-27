# Increment 403 — wire Discover > Funding to WIP manuscripts

**Date:** 2026-07-27
**Status:** Implemented and verified live (Playwright, a real end-to-end funding search against a WIP
manuscript with real provider results); 5 new backend tests; security audit PASS.

## Context

Second of three "quick win" increments from the larger WIP-integration request. Research found
Discover > Funding already had a paper-free "Describe research" mode end to end
(`08k_funding_discovery.jsx`'s `mode==="manual"` → `funding.py`'s `description`+`field` path, which
never touches `papers`) — since a WIP manuscript already has `ctx.selectedPaper === null`, the tool
technically already *ran* in that context. What was missing was **attribution** (a run made while a
manuscript was active looked identical to any other anonymous "manual" search — `source_kind:
"manual"`, no way to tell it apart later) and **visibility from the manuscript's own workspace tab**.

## Implemented

**Backend** — no new table. `research_funding_profiles.source_kind`/`source_id` were already generic,
unconstrained strings (already used for `"paper"`/`"manual"`/`"saved_<kind>"`) — this increment adds
one more value, `"wip-manuscript"`, rather than retrofitting the statcheck-specific `wip_tool_runs`/
`wip_snapshots` content-checkpoint machinery (which assumes a NOT NULL file+snapshot per run — wrong
fit for a manually-typed description that doesn't need the manuscript to have any files at all yet, an
important case for an early "idea"-stage manuscript):
- `FundingRunRequest` gains an optional `manuscript_id`. `funding_run` validates it's mutually
  exclusive with `paper_id` (422) and 404s if the manuscript doesn't exist (`get_manuscript`, the same
  check every other WIP route uses).
- `_run_funding_job`: when `manuscript_id` is set, `profile_from_text(..., source_kind="wip-manuscript",
  source_id=str(manuscript_id), title=manuscript.display_title)` instead of `source_kind="manual"`.
- `funding_run_summaries` (`app/backend/funding/run_report.py`) gains optional `source_kind`/`source_id`
  filter kwargs (backward compatible — existing callers pass neither).
- New `GET /wip/manuscripts/{manuscript_id}/funding-runs` (`wip_checks.py`) — 404s if the manuscript is
  missing, else returns `funding_run_summaries(..., source_kind="wip-manuscript", source_id=str(id))`.

**Frontend**:
- `08k_funding_discovery.jsx`: mode already defaulted to "manual" whenever `ctx.selectedPaper == null`
  (true for any WIP manuscript by construction) — no change needed there. Added a seed-once effect that
  pre-fills `description`/`field` from the manuscript's title/notes/target_journal *without clobbering
  user edits* (only seeds when the field is still empty), a "Pre-filled from `<title>`" note, and passes
  `manuscript_id` in the run request when a manuscript is active. On a completed run, also calls
  `ctx.onReloadWip()` so the manuscript's own tab picks up the new run without a manual reload — reusing
  the `wip.refresh` cross-sync mechanism inc 402 built for statcheck, now generalized to a second tool.
- `10f_wip.jsx`: `WipDetails` now also fetches `/wip/manuscripts/{id}/funding-runs` (added to its
  existing `Promise.all`) and renders a new `WipFundingRuns` list inside the "Checks" tab, alongside
  `WipChecks` — a compact, read-only summary (title/counts/date) reusing the exact `.wip-checkpoint-*`
  CSS recipe `WipChecks`'s own "Content checkpoints" list already uses, so **zero new CSS**. Full
  results/reload live in Discover > Funding's own pre-existing "Recent runs" history (which already
  shows every run, WIP-sourced or not, since `funding_run_summaries` already returned `source_kind`/
  `title`) — this list is a scoped "what's been searched for this manuscript" view, not a duplicate UI.

## Key technical detail

The original plan (written before implementation) proposed reusing statcheck's `tool_runs`/
`wip_tool_runs` polymorphic tables for this too. Implementation surfaced a better fit: Funding Discovery
already has its own generic provenance columns (`source_kind`/`source_id`, already freeform strings)
that don't force a false coupling to file content — a manuscript with zero files can still get a
funding search from a typed description, which the `wip_tool_runs` schema (NOT NULL `file_id`/
`snapshot_id`) would have wrongly disallowed without a migration. Reusing the *right* existing
mechanism (a filter on an already-generic column) needed zero schema change at all, smaller than
planned. This is exactly the kind of implementation-time refinement the plan document flagged as
possible ("whichever proves cleaner during implementation").

## Manual verification script

1. Open a WIP manuscript with no primary file (an early-stage manuscript). Go to Discover > Funding —
   confirm it's already in "Describe research" mode with the description pre-filled from the
   manuscript's title, and a "Pre-filled from `<title>`" note.
2. Run "Discover funding" — confirm it completes normally (identical to a manual/paper-mode run).
3. Jump back to the manuscript's own tab (via the WIP cue) → Checks tab — confirm a new "Funding
   searches" entry appears with the correct title/counts/date, **without a manual page reload**.
4. Confirm a second manuscript's funding-runs list stays empty (correct scoping), and a Library-paper
   funding run doesn't show up in either manuscript's list.

Verified live end-to-end via Playwright with a real search (no provider stubbing) against the real
WIP-watched "DC Comment" manuscript — real OpenAlex/Crossref/Grants.gov results returned (25
opportunities, 20 prospects), correctly tagged `source_kind: "wip-manuscript"`, `source_id: "2"`,
`title: "DC Comment"`, and the WIP tab's Checks list updated automatically. Zero new console errors.

## Pytest

`pytest tests/test_wip_funding.py -q` — **5 passed** (new): a run tags and lists correctly for a
manuscript; `paper_id`+`manuscript_id` together 422s; a nonexistent `manuscript_id` 404s on both the run
and list endpoints; the list endpoint is correctly scoped across two manuscripts; the list route stays
loopback-only. `pytest tests/test_funding_discovery.py tests/test_wip_checks.py tests/test_wip_api.py
tests/test_health.py tests/test_frontend_assembly.py -q` — 106 passed (no regressions). Full suite
before merge: see `changes.md`.

## Files changed

- `app/backend/api/routers/funding.py` (`manuscript_id` field, validation, provenance tagging)
- `app/backend/api/routers/wip_checks.py` (new `GET .../funding-runs`)
- `app/backend/funding/run_report.py` (`funding_run_summaries` source filter kwargs)
- `app/frontend/js/08k_funding_discovery.jsx` (manuscript pre-fill + `manuscript_id` passthrough + cross-sync)
- `app/frontend/js/10f_wip.jsx` (`WipFundingRuns`, fetch + render in the Checks tab)
- `tests/test_wip_funding.py` (new)
- `tests/test_health.py` (route allowlist)
- `.claude/qa-routes/route_75_wip_workspace.md` (extended)
- `.claude/security-audits/2026-07-27_wip-funding-discovery.md` (new — PASS)
- `callosum-app.html` (rebuilt)
