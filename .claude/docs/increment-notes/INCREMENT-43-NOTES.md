# Increment 43 Notes — Axis management: sort + multi-select + bulk delete + curated merge

The flat Axes panel becomes manageable: order axes, act on several at once, and consolidate
near-duplicate lenses ("resting-state" / "rsfmri" / "functional connectivity") into one. No nesting —
true axis hierarchy stays deferred. (Confirmed with the user: enhanced flat list, and merge into a
surviving axis whose content is *composed from all sources via a comparison view*, not inherited
wholesale from one "primary".)

## Implemented

**Backend**
- **`app/backend/clustering/axis_operations.py`** (new, 48 lines — kept out of `axis_scoring.py`,
  which is at 598/600). `merge_axes(conn, *, keep_axis_id, merge_axis_ids, label, description)`
  composes existing helpers: unions every folded axis's **manual** (confidence-NULL) assignments into
  the survivor (`manual_assignment_paper_ids` → `add_manual_assignment`), sets the survivor's
  label/description via a parameterized `UPDATE` (so an empty description becomes NULL — unlike
  `update_axis`, whose `None` means "unchanged"), then `delete_axis` on each source (cluster_nodes +
  assignments cascade). Scored assignments are **not** carried over — the caller re-scores.
- **`app/backend/api/routers/axes.py`** (404 → 441):
  - `POST /axes/merge` (`MergeAxesRequest`) — validates label (non-empty after strip, ≤200),
    `merge_axis_ids` (non-empty, de-duped, disjoint from the survivor → 422), and existence of every
    id (404); calls `merge_axes`, commits, returns the merged survivor (`AxisResponse`). No 500 path.
  - `AxisResponse.created_at` — exposes the existing `axes.created_at` column (read-only, additive,
    **no migration**) for client-side sort-by-recency.

**Frontend** (`app/frontend/js/15_axes.jsx` 375 → 448; new `16_axes_merge.jsx` 127; `styles.css`;
rebuilt `callosum-app.html`)
- **Sort**: a `<select>` in the panel head → `name` (A–Z) / `count` (most papers) / `recent` (newest);
  the list is sorted on render (selection/merge act on real ids, not display order).
- **Multi-select**: a checkbox per axis row (`stopPropagation` so it doesn't toggle expand). When ≥1
  selected, a **bulk-action bar** shows "N selected", **merge** (enabled at ≥2), **delete**, **clear**.
  Bulk delete loops the existing `DELETE /axes/{id}` (confirm first; reports partial failures).
- **`MergeAxesModal`** (`16_axes_merge.jsx`) — a **comparison/curation view** (mirrors the inc-41
  modal): shows every selected axis's label + description + paper count; a radio picks which axis's
  identity survives; an editable merged label; carried-over **Related: term chips** (toggle/add); an
  editable resulting-description preview. **Apply** → `POST /axes/merge` → parent clears the selection,
  reloads, and auto-re-scores the survivor via the existing score-job poller.

## Key technical detail — discoverability across a merge (the user's requirement)

> "after merging, the independent scored results present in both independent axes should still be
> discoverable in the now primary, merged axis."

Merging two lenses must not create a "gap in the terms contributing to scoring." So the comparison
view, **by default, seeds each folded (secondary) axis's *label* as a checked `Related:` chip** (plus
that axis's own existing Related terms). The survivor's composed description is therefore
`[<survivor base prose>, "Related: " + <checked terms>].filter(Boolean).join("\n\n")` (inc-41
convention), and its re-score embeds text spanning **all** sources' vocabulary — so papers each
independent axis used to surface stay discoverable under the merged axis. Discoverability is served
three ways: (1) broadened embedding text, (2) **unioned manual assignments** (hard-preserved), and
(3) the **uncertain tier** still showing near-break papers. The composition is frontend-side and fully
user-editable before Apply; the backend just persists the approved text. Verified live: after merging
"Anomalous bias" into "Anomalous appearance", the survivor's description became
`anomalous faces\n\nRelated: Anomalous bias`.

## Manual verification script
1. `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`; open `http://127.0.0.1:8080/` and
   **hard-reload** (frontend-only rebuild; no restart needed if already running) — Ctrl+Shift+R.
2. Create ≥3 axes. In the Axes panel head, switch the **sort** dropdown between A–Z / most papers /
   newest — order updates, no errors.
3. Tick the checkbox on two axes → the **bulk bar** shows "2 selected"; **merge** enabled.
4. Click **merge** → the comparison modal lists both axes; pick the survivor radio; confirm the folded
   axis's label appears as a default-on `Related:` chip and in the editable preview; **Merge axes**.
5. Confirm: the folded axis disappears, the survivor remains and re-scores; open it and confirm its
   papers include the union of both axes' manual additions, and its description carries the folded
   label as a `Related:` term.
6. Select one axis → **delete** (confirm) → it's removed.

## Verification
- **pytest: 145** (added `test_merge_into_survivor_unions_manual_and_deletes_sources`,
  `test_merge_validation`; updated the `/axes` exact-shape test for `created_at`; route-surface
  invariant adds `/axes/merge`).
- **Live browser E2E** (`.local/axes_manage_e2e/`, fake embedding model + in-memory store): 3 axes →
  sort exercised → select 2 → bulk bar → merge comparison view (2 sources, 1 survivor tagged, preview
  contains "Related:") → merge → 2 axes, modal closed → bulk delete → 1 axis. **0 console errors**.
- **Security audit:** `.claude/security-audits/2026-06-19_axis-merge.md` — **PASS**.
- Line caps respected: `axes.py` 441, `axis_scoring.py` 598 (untouched), `axis_operations.py` 48,
  `15_axes.jsx` 448, `16_axes_merge.jsx` 127 — all < 600. **No migration, no egress.**
