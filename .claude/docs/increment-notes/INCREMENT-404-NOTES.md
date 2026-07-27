# Increment 404 — wire Discover > Journals to WIP manuscripts

**Date:** 2026-07-27
**Status:** Implemented and verified live (Playwright, a real end-to-end journal search against a WIP
manuscript with real OpenAlex/DOAJ results); 5 new backend tests; security audit PASS.

## Context

Third of three "quick win" increments from the larger WIP-integration request. Unlike Funding (inc 403),
Discover > Journals has **no persistence at all today, even for Library papers** — `publishers.py`'s own
docstring states "Ephemeral job result; no table/migration" as a deliberate design choice (recomputing is
cheap, so the full ranked profile list is never stored). Making a manuscript's search history "visible from
the WIP's open tab" therefore genuinely required building new persistence for the first time — but a small,
purpose-scoped one, not a reversal of the original ephemeral design.

## Implemented

**Backend** — new table `wip_journal_runs` (migration `0058`, `app/backend/persistence/
schema_wip_journal_runs.py`, re-exported via `schema_wip.py`'s existing hub pattern): `manuscript_id` (FK
CASCADE), `topic_id`, `weighting`, `considered`, `shown`, `created_at`. **Deliberately a receipt only — never
the ranked profile list itself** — so this doesn't reverse `publishers.py`'s "ephemeral job result" design for
the paper/abstract paths; only a manuscript-tagged run ever writes a row, and only a compact summary.
- `PublishersRequest` gains an optional `manuscript_id`, paired with the existing `abstract`+`subject` mode
  (not a third exclusive input — mutually exclusive with `paper_id`, 422/404 validated the same way as `paper_id`
  and as inc 403's Funding `manuscript_id`).
- `_run_publishers_job`: after computing the report, if `manuscript_id` is set, `record_journal_run(conn,
  manuscript_id, topic_id=..., weighting=..., considered=..., shown=...)` — a small additive write, the
  existing paper/abstract paths are completely unaffected (no persistence call at all unless tagged).
- New `GET /wip/manuscripts/{manuscript_id}/journal-runs` (`wip_checks.py`) — 404s if missing, else
  `list_journal_runs(...)`.

**Frontend**:
- `08e_methods_publishers.jsx`: same manuscript pre-fill (`abstract` seeded from title/notes, never
  clobbering user edits) + "Pre-filled from `<title>`" note + `manuscript_id` passthrough + the
  `ctx.onReloadWip()` cross-sync call on completion, mirroring inc 403's Funding wiring exactly.
- `10f_wip.jsx`: `WipDetails` fetches `/wip/manuscripts/{id}/journal-runs` (added to its `Promise.all`) and
  renders a new `WipJournalRuns` list in the Checks tab, alongside `WipChecks`/`WipFundingRuns` — same
  `.wip-checkpoint-*` CSS reuse, zero new CSS.

**Bug found and fixed during live verification (affects both Journals and Funding):** `PublishersPanel`'s
input-mode effect only *initialized* `mode` once (`if (mode == null && status) setMode(...)`) — it never
*corrected* a stale `"paper"` mode left over from an earlier Library-paper selection once that paper was no
longer selected (e.g. because a WIP manuscript became active instead). Since workspace tabs mount-but-hide
(never remount on a context switch), a user who had selected a paper before ever opening a WIP manuscript
would land on a dead-end "Select a paper in the library, or paste an abstract instead" message in Discover >
Journals, even though the whole point of this increment is that abstract mode should take over automatically.
Reproduced live: selected a Library paper → Discover > Journals correctly showed "paper" mode → opened a WIP
manuscript → revisited Discover > Journals → **still stuck in stale "paper" mode**. Fixed by also correcting
the mode whenever it's `"paper"` but `ctx.selectedPaper` is now null:
```jsx
if (status && (mode == null || (mode === "paper" && ctx.selectedPaper == null))) {
  setMode(ctx.selectedPaper != null ? "paper" : "abstract");
}
```
`08k_funding_discovery.jsx` had the identical latent bug (mode was only ever set once via a `useState`
initializer, never re-derived) — fixed there too with an equivalent effect, even though it hadn't yet been
observed to fail in inc 403's testing (that session happened not to hit the paper-then-manuscript sequence).
Re-verified live: select paper → Journals shows "paper" mode → open WIP manuscript → Journals now correctly
self-corrects to "Paste an abstract", pre-filled from the manuscript.

## Manual verification script

1. Select a Library paper, confirm Discover > Journals shows "Selected paper" mode.
2. Open a WIP manuscript, revisit Discover > Journals — confirm it now shows "Paste an abstract" mode,
   pre-filled from the manuscript's title, with a "Pre-filled from `<title>`" note (proves the stale-mode fix).
3. Add a subject, run "Find journals" — confirm it completes normally.
4. Jump to the manuscript's own tab (WIP cue) → Checks tab — confirm a new "Journal searches" entry appears
   with the correct topic/weighting/counts/date, without a manual reload.
5. Confirm a second manuscript's journal-runs list stays empty; a Library-paper-mode run never writes a
   receipt for any manuscript.

Verified live end-to-end via Playwright with a real search (no provider stubbing in the browser) against the
real WIP-watched "DC Comment" manuscript — real OpenAlex/DOAJ results (56 considered, 25 shown), correctly
persisted and displayed in the Checks tab automatically. Zero new console errors.

## Pytest

`pytest tests/test_publishers.py -q` — **18 passed** (13 existing + 5 new): a manuscript-tagged run persists
a receipt matching the computed report exactly and lists correctly; `paper_id`+`manuscript_id` together 422s;
a nonexistent `manuscript_id` 404s on both the run and list endpoints; the list endpoint is correctly scoped
across two manuscripts; the list route stays loopback-only. `pytest tests/test_funding_discovery.py
tests/test_wip_funding.py tests/test_wip_checks.py tests/test_wip_api.py tests/test_health.py
tests/test_frontend_assembly.py -q` — no regressions (includes re-verifying inc 403's Funding tests still
pass after its shared mode-effect fix). Full suite before merge: see `changes.md`.

## Files changed

- `app/backend/persistence/schema_wip_journal_runs.py` (new)
- `app/backend/persistence/schema_wip.py`, `schema.py` (re-exports)
- `app/backend/persistence/wip_checks_repo.py` (`record_journal_run`/`list_journal_runs`)
- `app/backend/api/routers/publishers.py` (`manuscript_id`, validation, receipt persist)
- `app/backend/api/routers/wip_checks.py` (new `GET .../journal-runs`)
- `alembic/versions/0058_wip_journal_runs.py` (new)
- `app/frontend/js/08e_methods_publishers.jsx` (manuscript pre-fill + `manuscript_id` + stale-mode fix)
- `app/frontend/js/08k_funding_discovery.jsx` (the same stale-mode fix, found while fixing Journals)
- `app/frontend/js/10f_wip.jsx` (`WipJournalRuns`, fetch + render in the Checks tab)
- `tests/test_publishers.py` (5 new tests)
- `tests/test_health.py` (route allowlist)
- `.claude/qa-routes/route_75_wip_workspace.md` (extended)
- `.claude/security-audits/2026-07-27_wip-journal-discovery.md` (new — PASS)
- `callosum-app.html` (rebuilt)
