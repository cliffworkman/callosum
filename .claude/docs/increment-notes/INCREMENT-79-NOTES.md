# Increment 79 — Count badge subtracts hidden uncertain papers

## Implemented
A direct follow-on to inc-77's **Settings → hide uncertain papers by default** (and inc-51's per-axis 👁
toggle): when an axis is showing only assigned/manual papers, its **count badge now shows the *visible* count**
(total − uncertain), not the full assignment count — so the number on the badge matches what the list actually
shows. The badge tracks the per-axis view state, so flipping 👁 (or the Settings default) updates it live.

- `app/backend/clustering/axis_assignments.py` — `axis_score_state(conn, axis_id, *, cutoff=None)` gained the
  optional `cutoff` kwarg and now returns **`uncertain_count`** in all three return dicts: the number of scored
  assignments below the cutoff (`confidence IS NOT NULL AND confidence < cutoff`, joined `cluster_node_papers`→
  `cluster_nodes` by axis_id). `cutoff=None` (the default) → `uncertain_count` 0, so existing callers are
  unaffected.
- `app/backend/api/routers/axes.py` — `AxisResponse.uncertain_count: int = 0`; `_axis_response` now calls
  `axis_score_state(conn, id, cutoff=_axis_cutoff(row))` and sets `uncertain_count=int(state["uncertain_count"])`.
- `app/frontend/js/15_axes.jsx` — `AxisItem` computes `badgeCount = hideUncertain ? max(0, total − uncertain) :
  total` (from the server-provided `axis.uncertain_count`, keyed on the per-axis `hideUncertain` view-state) and
  renders it; the tooltip explains "N assigned · M uncertain hidden" when hiding. The My Publications card passes
  `hideUncertainDefault={false}`, so it always shows its full member count.
- Rebuilt `callosum-app.html`.

## Key technical detail
The uncertain count is **server-computed**, because the frontend only knows a paper's tier when an axis card is
expanded (the per-paper confidences come from `/axes/{id}/clusters`, not the `/axes` list). `axis_score_state`
is the right home: it already owns the assignment-count join and imports the schema tables + `and_`/`func`. The
"uncertain" definition mirrors the read-time tiering in `routers/axes.py` exactly — **assigned = confidence ≥
cutoff**, so **uncertain = scored (confidence NOT NULL) but < cutoff**; manual (`confidence IS NULL`) is never
uncertain. The cutoff is the axis's own `_axis_cutoff(row)` (per-axis `scoring_gain`, default 0.35), so the
subtraction is consistent with how that axis tiers its papers.

## Manual verification script
1. Hard-refresh the app (Ctrl+Shift+R) to load the rebuilt frontend.
2. Pick an axis that has both assigned and uncertain papers (or score one). Note its count badge.
3. Toggle the axis's 👁 (or Settings → Axes → "Hide uncertain papers by default"): the badge drops to the
   assigned/manual-only count, and its tooltip reads "N assigned · M uncertain hidden …". Toggle back → full count.
   _(Visual check delegated to the user — no in-repo browser automation this session.)_

## Pytest
**361 passed, 1 skipped** — unchanged count; the new behavior is covered by assertions added to two existing
axis tests (`test_axis_score_produces_three_honest_tiers` now also asserts the listed axis's `uncertain_count ==
1`; `test_axes_and_clusters_return_sidebar_tree_data` pops the new field), not new test functions. `ruff` clean.
No migration, no new endpoint, no egress (an additive read-only field on the existing `/axes` response).

> Note: the recent **indeterminate progress bars** (`ProgressBar`, wired into the long async jobs), the **My
> Publications card move** (below the filter/sort controls) and the **inter-axis-card spacing** bump (2→5px) were
> committed earlier this session as small unnumbered UI chores; this is the next numbered increment.
