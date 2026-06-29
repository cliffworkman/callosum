# Increment 204 — carry "hide uncertain" through to the library-pane axis filter (backlog A10, close-out)

## Implemented

The second **close-out** of the wrap-up pass (after inc 203 / A9), fixing a straight *shown ≠ summarized* bug. The
axis card's count badge (inc 63) filters the Library to that axis's papers, and the card has a 👁 hide-uncertain
toggle (inc 51) that shows only **assigned** (confidence ≥ the axis cutoff) + **manual** (confidence NULL) papers,
hiding the uncertain ones. But clicking the badge while hide-uncertain was on still filtered to **every** axis member
(the inc-63 `?axis_id=` subquery returns all `cluster_node_papers` rows) — so the user could *select-all → summarize*
papers the card had hidden. Now the badge carries the card's hide state and the filter matches the card.

- **`app/backend/persistence/repository.py`:** `list_papers(..., axis_hide_uncertain=False)`. New module constant
  **`DEFAULT_AXIS_CUTOFF = 0.35`** (mirrors `routers/axes.py` + `discovery/relevance.py`). When `axis_id` is set and
  `axis_hide_uncertain`, the existing axis-member subquery gains
  `WHERE (confidence IS NULL OR confidence >= cutoff)`, where `cutoff = axes.scoring_gain` for that axis (queried
  inline) **else** `DEFAULT_AXIS_CUTOFF` — the **exact** tiering `routers/axes.py::_axis_cutoff` + the read-time
  `assigned_ids` computation use, so the SQL set == the card's "assigned + manual" set. `or_` + `axes` were already
  imported (rule #3 — bound params throughout).
- **`app/backend/api/routers/papers.py`:** `GET /papers` gains `axis_hide_uncertain: bool = Query(False)`, threaded to
  `list_papers`. (Default false → the inc-63 behavior is byte-for-byte unchanged.)
- **Frontend wiring (4 hops, all booleans):** `15_axes.jsx` — the badge `onClick` passes the card's current
  `hideUncertain` (`handlers.filterToAxis(axis, hideUncertain)`); `AxesPanel.filterToAxis(axis, hideUncertain)` folds
  it into the `onFilterToAxis({id, label, hideUncertain})` payload. `40_app.jsx` — `filterToAxis` stores
  `libraryAxisFilter.hideUncertain`; the `/papers` query-string builder adds `axis_hide_uncertain=true` when set.
  `10_pdf_layer.jsx` — the "Filtered to axis …" banner appends "· assigned only" when hidden.

## Key technical detail

The cutoff is **per-axis** and looked up server-side from `axes.scoring_gain` (NULL → `DEFAULT_AXIS_CUTOFF`), so the
client never plumbs a number — it just sends the boolean, and the backend reconstructs the same cutoff the card's
read-time tiering used. A paper counts as "in the filtered view" if it has **at least one** axis cluster-node
membership that is manual (NULL) or ≥ cutoff — the same per-paper aggregation the card does. With hide OFF (the
default, and every pre-existing caller) the param is absent and the filter is the unchanged inc-63 all-members query.

## Manual verification script

`HF_HUB_OFFLINE=1 python -m pytest tests/test_papers.py -k axis -q` → 3 passed, incl. the new
`test_papers_list_axis_hide_uncertain` (an axis with one assigned [0.6] / one uncertain [0.2] / one manual [NULL]:
`?axis_id=` returns all three; `?axis_id=&axis_hide_uncertain=true` returns only assigned + manual).
**Headed (no egress):** `.local/visual/drive_inc204_hide_uncertain.py` — seed that axis, expand the card, click 👁
(hide ON), click the count badge → the Library shows only "Assigned paper" + "Manual paper" (not "Uncertain paper")
and the banner reads "Filtered to axis A10 axis · assigned only"; 0 console/page/genai.

## Gates

- **pytest:** full suite green — **713 passed, 1 skipped** (+1 `tests/test_papers.py`).
- **ruff** check + format clean; frontend rebuilt (`callosum-app.html`).
- **QA surface unchanged** — 136/136 API + 661/661 FE, 0 uncovered (a new query param on the existing `GET /papers` +
  the existing axis badge/banner elements, not a new surface); `route_15_axes.md` gained an A10 (shown == summarized)
  step.
- **Audit:** no new endpoint/egress/migration/dependency → no audit-gate trigger. **Principles non-triggering** — a
  retrieval/filter-consistency fix (the inc-66 class); inspectability/provenance/egress posture unchanged, no new
  claim/signal. The aligned shape was pre-decided with the maintainer (benchmark-revisions §A10).
- **Help corpus** updated (the axis count-badge bullet now states the filter matches the assigned-only card view;
  `HELP-DOCS-SYNCED` → 204). Also swept 4 stray `app/frontend/js/*.tmp.*` atomic-write orphans (rule #5).

## NEXT (continuing the close-out pass)

**A8** (verify the synthesis scope label vs the inc-153 coverage readout — likely already-covered, a confirm pass),
then the low-cost build-now items: **A1** saved searches, **A5** color tags/ratings, **A6** drag-into-axes, **A3**
full-text PDF search. The deferred B-items (MCP server, citation-context classifier) + **A7 Curated Axis** are larger
design passes.
