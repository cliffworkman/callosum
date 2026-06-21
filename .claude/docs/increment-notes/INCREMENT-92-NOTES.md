# Increment 92 — Un-dismiss for My-Publications missing works

Chore 2 of the patter. Completes inc-85's missing-works review queue with an **undo** for Dismiss — the exact
gap inc-67 closed for duplicate-dismissals. A mistakenly-dismissed own-paper can be restored to the queue.

## Implemented
- **`persistence/profile_repo.py`** — `undismiss_work(conn, doi)`: removes a normalized DOI from
  `profile.dismissed_work_dois` (mirror of inc-85's `dismiss_work`); no-op if the profile is unset, the DOI is
  blank, or it wasn't dismissed. Empty list → stored as NULL (matches `set_starred`).
- **`clustering/my_publications.py`** — `build_dashboard` now also returns **`dismissed_works`** (a new
  `_dashboard_dismissed_works(works, dismissed)`: the author's cached works whose DOI ∈ `dismissed_work_dois`,
  with title/year/citations, sorted by citations). The dismissed-DOI set is computed once and shared with
  `_dashboard_missing_works`. Cache-only, no network call (like the rest of the dashboard).
- **`routers/my_publications.py`** — `DashboardResponse.dismissed_works: list[MissingWork]` (reuses the existing
  model — same `{doi, title, year, cited_by_count}` shape), and a new **`POST /my-publications/works/undismiss`**
  endpoint (calls `undismiss_work`; local, idempotent, 204 — mirror of the dismiss endpoint).
- **Frontend** (`31_mypubs_dashboard.jsx`) — a collapsible **"Previously dismissed (N)"** section below the
  missing-works review list; each row has a **Restore** link that POSTs `/works/undismiss` then refetches the
  dashboard (so the work moves back up into the review list). Reuses the existing `actOnWork` helper +
  `.mypubs-missing` / `.missing-row` styles (no new CSS). Rebuilt `callosum-app.html`.

## Key technical detail
The dismissed list is **derived from the cached OpenAlex works** (titles come from there), not from the bare DOI
list — so a dismissed DOI that's no longer in the author's current works simply isn't shown (edge case;
acceptable, mirrors how `missing_works` only considers current works). Un-dismiss + dismiss are pure
`profile.dismissed_work_dois` JSON edits — no new table, no migration. Facts-vs-candidates is preserved: the
human dismisses/restores; nothing auto-acts.

## Manual verification script
1. Open the My Publications 📊 dashboard. In the missing-works review list, **Dismiss** a work → it leaves the
   list and a **"Previously dismissed (1)"** section appears.
2. Expand it → **Restore** the work → it moves back into the review list; the dismissed section disappears when
   empty.
   _(Visual check delegated to the user.)_

## Pytest
**386 passed, 1 skipped** (+1: `test_undismiss_returns_work_to_missing_queue` — dismiss → in `dismissed_works`,
not `missing_works`; undismiss → back in `missing_works`; case-insensitive; endpoint 204). `ruff` clean. No
migration, no egress (OpenAlex stays cache-only; this is pure local profile-JSON editing).
