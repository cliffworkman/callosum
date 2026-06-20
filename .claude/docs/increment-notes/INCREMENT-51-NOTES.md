# Increment 51 Notes — B′: eyeball toggle to hide/show UNCERTAIN papers

A small follow-on to inc-50's axes UX: an **eye toggle** that collapses an axis's list to an
assigned/manual-only view, hiding the UNCERTAIN candidates. Frontend-only.

## Implemented (`app/frontend/js/15_axes.jsx` + `styles.css`)
- `AxisItem` gains a per-axis `hideUncertain` state. An **👁 button** appears at the right of the
  Re-score row **only when the axis has ≥1 uncertain paper** (`uncertainCount`), dimmed (`.off`) when
  hiding. Clicking it filters `status === "uncertain"` rows out of the displayed list.
- When hiding, a subtle **"N uncertain hidden — show"** restore hint (`.axis-eye-hint`) renders under
  the visible papers so the hidden set is never silently lost. The genuinely-empty-axis hint is
  unchanged (the filter only hides; it doesn't change the "no papers at all" state).
- State is local to `AxisItem` (persists across expand/collapse + `axisRefresh`, like the cutoff
  flipper); resets per session. CSS is token-only; the eye reuses `.axis-icon-btn`.

## Key technical detail
The toggle is purely a *display* filter over `detail.papers` — it never touches assignments or the
backend. Assigned + manual papers always show; only scored-uncertain rows are hidden. Pairs with the
inc-45 cutoff flipper (which changes *which* papers are uncertain) and inc-50's ✓-confirm (which
*promotes* an uncertain paper out of that tier).

## Manual verification script
1. Rebuild (`python tools/build_frontend.py`), restart uvicorn, hard-reload.
2. Score an axis that yields ≥1 uncertain paper → expand it: an **👁** sits at the right of the
   Re-score row. Click it → the uncertain rows vanish (assigned/manual only) and a "N uncertain
   hidden — show" hint appears; the eye dims. Click the hint (or the eye) → they return.

## Verification
- **pytest: 174** (unchanged — frontend-only).
- **Live E2E** (`.local/eye_e2e/`, deterministic fake model): eye present with an uncertain paper;
  hiding removes the uncertain row + shows the restore hint; restore brings it back; **0 console
  errors**. Screenshot captured. No audit gate (no new endpoint/surface).
- `15_axes.jsx` 332→344 (< 600).

## Backlog
Done: **B′**. Next queued: suggest-optimal-axes; library multi-select + bulk delete (D, destructive →
needs a soft-delete/undo decision + plan); dedup (E); synthesis split (F); library merge (last);
favicon dark-swap; DESIGN.md `.btn-*` DRY; HELP viewer; SRI.
