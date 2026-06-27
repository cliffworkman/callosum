# Increment 154 — statcheck flagged-chip deep-link to the specific inconsistent test (#statcheck (d))

The remaining autonomous part of the statcheck experience-pass finding (inc 140). Frontend-only.

## Implemented (`app/frontend/js/06_methods_statcheck.jsx`)

When a per-paper statcheck run finishes, `StatcheckPaper` now **scrolls the first inconsistent row into view and
flashes it** — so the "⚠ N flagged" chip path (inc 141: filter → open Statistics check → auto-select the flagged
paper → auto-run) lands the deadline-citer on *the specific result that doesn't recompute*, not just the full list
of all tests.

- A `listRef` on the `.statcheck-list`; a `useEffect` on `state.status` finds the first
  `.statcheck-item.flagged-row` on `done`, `scrollIntoView({block:"nearest"})` + adds a transient `flash` class
  (~1.4s).
- Inconsistent rows are marked `flagged-row` (`r.consistency !== "consistent"`) — the deep-link target.
- CSS: a `@keyframes statcheckflash` (flag-amber → transparent) + `.statcheck-item.flash`, reusing the existing
  flash pattern (`helpflash`); tokens only (rule #8).

## Key technical detail

Fires on **any** completed check (manual or the chip auto-run) — for a manual check it's also helpful (jumps to
the first problem), for the chip path it completes the deep-link. Coordinate honesty unchanged: clicking a row
still opens the page at `precision:"region"` (page-open, no fake exact rect). **No Principles trigger** (a
navigation affordance over the existing signal — still a list-to-review, never a verdict). No backend/endpoint/
migration change.

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc154_statcheck_flash.py`): seeds a clean + a flagged paper (an
inconsistent `t(28)=2.10, p=.001`); click the flagged chip → Statistics check opens + auto-runs → the inconsistent
row is marked `.flagged-row` and receives the `flash` class. 0 console/page/genai.

## Pytest

**556** unchanged (frontend-only; the statcheck data path is covered by `test_statcheck`). `ruff` clean; build +
assembly green; QA surface **109/109 API + 561/561 FE, 0 uncovered** (route_33 covers statcheck; the flash is
cosmetic). No migration.

## Remaining statcheck finding (needs Cliff — [design])

(b) a "Check statistics" entry on the paper itself (inc-122 deliberately moved it out of Details — weigh
re-cluttering); (e) the "⚠ flagged" (signal) vs "📋 to review" (work-state) duality (inc-133 made them coexist).
Both are design calls, left above the line for your decision.
