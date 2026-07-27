# Increment 401 — save GRIM/GRIMMER checks per paper

**Date:** 2026-07-27
**Status:** Implemented and verified live (Playwright); 5 new backend tests including a
server-side-recomputation proof; security audit PASS.

## Context

GRIM (`07_methods_grim.jsx`) was a pure manual-entry calculator that wasn't even paper-aware —
`registerPaneSection` passed it no `ctx` at all, unlike every sibling Methods section. The user asked
to save GRIM results, attached to the specific paper, and recalled whenever the Data section is open
for that paper — since a paper may have several reported means worth checking (different
experiments/tables), this is a small per-paper saved-checks log, not a single last-result cache (the
statcheck-cache shape from Increment 400 doesn't fit here).

## Implemented

**Backend** — a new table `paper_grim_checks` (`app/backend/persistence/schema_grim_checks.py`,
migration `0057`): append-only (a user may legitimately save the same mean/N twice under different
labels), `paper_id` FK CASCADE, `label` (optional, ≤120 chars), `mean`/`sd`/`n`/`items` (the raw
reported inputs), `result_json` (the server-recomputed `GrimComputeResponse`, frozen at save time),
`created_at`. New repo `grim_checks_repo.py` (list/add/delete, mirroring `paper_urls_repo.py`'s
shape). New sibling router `app/backend/api/routers/methods_grim_saved.py` (the existing
`POST /methods/grim` calculator in `methods.py` is untouched):
- `GET /papers/{paper_id}/grim-checks` — the saved list, newest-first.
- `POST /papers/{paper_id}/grim-checks` — **re-runs `grim_test`/`grimmer_test` server-side** on the
  submitted raw inputs and persists that result; never trusts a client-supplied verdict.
- `DELETE /papers/{paper_id}/grim-checks/{check_id}` — 204; scoped to the `(paper_id, check_id)` pair
  together, so a mismatched pair 404s rather than touching the wrong paper's row.

**Frontend** (`07_methods_grim.jsx`, `GrimSection`): now takes `{ ctx }` (the one-line fix that makes
GRIM paper-aware at all — `render: (ctx) => <GrimSection ctx={ctx} />`, matching every sibling
section). A `useEffect` on `paperId` fetches the saved list (the same self-fetch pattern
`StatcheckPaper` already uses). A "Save this check" link appears after a live Check result
(`paperId != null` only); a "Saved checks — this paper" list renders below the form
(label-or-computed-description / consistent-impossible pill / date / a `.btn-icon` × delete), gated on
`saved.checks.length > 0`.

## Principles-gate note (rule #9)

The easy/misaligned path would let the frontend POST its already-computed `grim`/`grimmer` verdict for
storage verbatim. The aligned design implemented here has the save endpoint take only the raw reported
inputs and re-derive the verdict server-side, identically to `POST /methods/grim` — a saved record can
never drift from what the deterministic function actually returns (the computation is pure arithmetic,
effectively free to redo). Verified directly: `test_save_recomputes_server_side_and_matches_calling_
grim_directly` calls `grim_test`/`grimmer_test` independently and asserts the saved record matches
exactly. See `.claude/security-audits/2026-07-27_grim-saved-checks.md`.

## Bug found and fixed during live verification: stale form/result across a paper switch

Live Playwright verification surfaced a real bug: `GrimSection`'s live-Check form (`f`) and result
(`state`) didn't reset when `paperId` changed. Concretely: a Check was run and saved against the
Hadza/Tsimane paper (paper 17) in the My Publications workspace — but the saved record landed against
paper 1 (a different, previously-selected paper, confirmed by inspecting the DB directly:
`paper_grim_checks` had `paper_id=1`, not 17). Switching away and back to paper 17 then showed a
**stale live-Check result** (the old mean/N/verdict still filled in and clickable via "Save this
check") with no saved-checks list for paper 17 — a UX trap where a user could believe "Save" would
attach to the newly-selected paper when it was actually left over from a previous one.

Root cause: no effect reset `f`/`state` on `paperId` change (`saved` already did). Fixed with:
```jsx
useEffect(() => {
  setF({ mean: "", sd: "", n: "", items: "1" });
  setState({ status: "idle" });
}, [paperId]);
```
Re-verified end-to-end after the fix: Check + Save against paper 17 now correctly persists to
`paper_id=17` (confirmed via `GET /papers/17/grim-checks`); switching to a different paper shows an
empty, freshly-reset form with no saved list; switching back to paper 17 shows the reset form (no
stale values) with the saved check correctly reappearing; Delete removes it and it stays gone after a
hard refresh. The one stray test record accidentally saved against paper 1 during the initial
(pre-fix) reproduction was removed via `DELETE /papers/1/grim-checks/1` before finishing verification.

## Manual verification script

1. Select a paper, open Methods → Data. Enter an impossible mean (3.48, N 20) → Check → confirm
   "impossible" + nearest-possible. Click "Save this check" → confirm it appears under "Saved checks —
   this paper" with the mean/N description, an "impossible" pill, and today's date.
2. Select a different paper → confirm the Data form is empty (no stale values) and no saved list shows.
3. Reselect the first paper → confirm the form is still empty/reset (not showing the old Check) and the
   saved check reappears.
4. Click × on the saved check → confirm it's removed; hard-refresh the page and confirm it stays gone.
5. Confirm zero console errors throughout (only a pre-existing, unrelated 404 on `/wip/browse-dirs`
   from earlier folder-browser testing was observed — not touched by this increment).

## Pytest

`pytest tests/test_grim_saved.py -q` — **5 passed**: empty list + 404 for a missing paper; a saved
record's `grim`/`grimmer` fields match calling `grim_test`/`grimmer_test` directly (the
server-side-recomputation proof); list is newest-first and strictly paper-scoped; delete is scoped to
`(paper_id, check_id)` (wrong pairing 404s, real row survives) and a second delete 404s; invalid inputs
(n=0, non-numeric mean, an oversized label) all 422. `pytest tests/test_health.py -q` — the exhaustive
route allowlist updated with the 3 new routes. `pytest tests/test_frontend_assembly.py -q` — 53 passed
(no test asserted `GrimSection`'s old no-`ctx` signature literally, so nothing needed updating besides
the rebuild). Full suite before merge: see `changes.md`.

## Files changed

- `app/backend/persistence/schema_grim_checks.py` (new)
- `app/backend/persistence/schema.py` (re-export)
- `app/backend/persistence/grim_checks_repo.py` (new)
- `app/backend/api/routers/methods_grim_saved.py` (new)
- `app/backend/api/app.py` (mount the new router)
- `alembic/versions/0057_paper_grim_checks.py` (new)
- `app/frontend/js/07_methods_grim.jsx` (paper-aware `ctx`, save/list/delete, the paperId-reset fix)
- `app/frontend/styles.css` (`.grim-saved-list`/`.grim-saved-item`/`.grim-saved-desc`/`.grim-saved-date`)
- `tests/test_grim_saved.py` (new)
- `tests/test_health.py` (route allowlist)
- `.claude/qa-routes/route_37_methods_grim.md` (extended)
- `.claude/security-audits/2026-07-27_grim-saved-checks.md` (new — PASS)
- `callosum-app.html` (rebuilt)
