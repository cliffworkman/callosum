# Increment 39 Notes — Axis scoring calibration: natural-break relative tiering

## Problem (found on real data)
Increment 38 scored supervised axes with **absolute** thresholds (assigned ≥0.7 / uncertain ≥0.5).
On the real library it assigned **nothing**. Diagnosing the live DB
(`.local/validation-summarize/validation.sqlite`, read-only) showed the *ranking is correct* — for the
"anomalous-is-bad" axis the top matches are exactly the facial-difference papers (0.372, 0.346, 0.268,
0.267), then a clean drop to ~0.18 for off-topic papers — but `all-MiniLM-L6-v2` cosine similarity
between a short axis phrase and paper title/abstract metadata **maxes at 0.37 (median 0.02)**. Absolute
0.5/0.7 cutoffs are simply unreachable for this model+text-pair (they fit the orthogonal fake test
vectors / longer chunk text, not axis-vs-paper-metadata), so every paper fell below the floor.

## Fix — natural-break (relative) tiering
Assignment is now **relative to each axis's own ranking**, not an absolute cosine value:
- New `assignment_mode="natural_break"` in `app/backend/clustering/axis_scoring.py` (other modes
  untouched). `SUPERVISED_AXIS_CONFIG` (in `axes.py`, single source of truth):
  `uncertainty_threshold=0.2` (noise floor), `assignment_threshold=0.2`, `minimum_gap=0.03`.
- **assigned** = the cluster above the largest gap in the descending ranking, among papers at/above
  the floor (`natural_break_assigned_ids`, reuses `_largest_gap_cutoff_count`). **uncertain** = the
  rest of the eligible papers. **Never-empty**: if nothing clears the floor, the top-3 positive matches
  are shown as `uncertain` candidates. Below the floor → not stored.
- The 0.2 floor is a **documented MiniLM-calibrated constant**, not a learned value; flagged to revisit
  if the embedding model changes.

## No migration — tiers recomputed on read
`cluster_node_papers` still stores only `confidence` (float = scored, NULL = manual). The
assigned/uncertain split is **recomputed from the stored confidences on read** (`axis_clusters` calls
`natural_break_assigned_ids` over the node's scored confidences with the same `SUPERVISED_AXIS_CONFIG`).
Because the stored set *is* the eligible set and the gap function is identical, read-time tiers exactly
reproduce score-time tiers — consistent without persisting a tier column.

## Files
- `app/backend/clustering/axis_scoring.py` (+`natural_break` mode, `natural_break_assigned_ids`,
  `_natural_break_statuses`; 595 lines, under 600).
- `app/backend/api/routers/axes.py` (`SUPERVISED_AXIS_CONFIG`; job uses it; read tier via
  `natural_break_assigned_ids` over stored confidences instead of an absolute threshold).
- `app/frontend/js/15_axes.jsx` + `styles.css` (a small "tiers are relative to this axis" caption);
  rebuilt `callosum-app.html`.
- `tests/test_axes.py` (unit test for the gap split + sub-floor; API test for the never-empty fallback).

## Verification
- **pytest: 138 passed** (136 + 2 new). Existing fake-vector axes tests still hold under natural_break
  (high 1.0 ≥floor + above gap → assigned; borderline 0.6 → uncertain; far 0.0 <floor → absent; counts
  1/1). New: `natural_break_assigned_ids` splits a realistic compressed ranking at the gap and returns ∅
  when all sub-floor; never-empty API test surfaces the closest few as `uncertain` with 0 assigned.
- **Real-data check (read-only):** `natural_break_assigned_ids` over the 77 stored sims →
  `{Morality…, Evidence-against-anomalous-is-bad}` assigned (the off-topic papers excluded) — matches
  the intended result.
- **Live browser E2E** (`.local/axes_e2e/run.py`): create → score → tiers populate (assigned/uncertain),
  manual-add → 0 console errors.

## Action for the user
Existing axes scored under the old absolute logic have 0 stored assignments — **re-score** them (the
sidebar's Re-score button) to populate tiers under the new calibration.

## Rough edges
- The 0.2 floor is MiniLM-specific; a different embedding model would need recalibration (or a future
  per-model/auto floor).
- Re-score still re-evaluates from scratch (a manually-removed scored paper can reappear — inc-38 note).
