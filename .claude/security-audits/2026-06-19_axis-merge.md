# Security audit — Axis merge (`POST /axes/merge`) + bulk delete + sort (increment 43)

**Date:** 2026-06-19
**Feature:** Axis management — sortable list, checkbox multi-select, bulk delete, and a curated
**merge** that consolidates several axes into one surviving axis.
**Audit trigger:** a new API endpoint (`POST /axes/merge`); also exposes a new read-only field
(`created_at`) on `AxisResponse`.

## Surface added
- **`POST /axes/merge`** (`app/backend/api/routers/axes.py`) — body `MergeAxesRequest`
  `{keep_axis_id:int, merge_axis_ids:list[int], label:str, description:str|None}`. Composes
  `merge_axes()` (`app/backend/clustering/axis_operations.py`): unions the merged axes' **manual**
  (confidence-NULL) assignments into the survivor, sets the survivor's label/description, deletes the
  folded axes (FK cascade), and returns the survivor. Local-only.
- **`AxisResponse.created_at`** — read-only datetime, sourced from the existing `axes.created_at`
  column (already in the schema; **no migration**). Enables client-side sort-by-recency.
- **Bulk delete** adds **no endpoint** — the frontend loops the existing
  `DELETE /axes/{axis_id}`.

## Threat review
- **Input validation / boundary (rule #4):** All inputs are typed by Pydantic. `label` is
  `Field(min_length=1, max_length=200)` and re-`strip()`-ped (whitespace-only → **422**).
  `description` is `Field(max_length=4000)`. `merge_axis_ids` is `Field(min_length=1)` (empty →
  **422**), de-duped, and required to be **disjoint** from `keep_axis_id` (overlap → **422**). Every
  id (survivor + each source) is existence-checked via `get_axis` → **404** on any miss. No code path
  can reach `merge_axes` with an unvalidated or partially-valid set, and there is **no 500** path
  (validation precedes the DB work; the work is plain composition of already-tested helpers).
- **Injection / SQL (rule #3):** `merge_axes` uses SQLAlchemy Core bound parameters only
  (`update(axes).where(axes.c.id == ...).values(label=..., description=...)`); ids are ints, never
  interpolated. Table/column references are schema constants. No string-built SQL.
- **SSRF / external calls / egress (invariant #3):** **None.** Merge, bulk delete, sort, and the
  follow-up re-score are entirely local (local embedding model + sqlite-vec). No `google.genai`, no
  httpx, no network. The egress gate is untouched and uninvolved.
- **Secret handling:** No secrets read or logged. N/A.
- **Resource caps:** A merge is bounded by the number of selected axes (a human checkbox selection),
  each step a handful of indexed SQLite ops; bulk delete is N independent `DELETE`s over the same
  selection. No unbounded loops, recursion, or large allocations. The follow-up re-score reuses the
  existing async axis-score job (already bounded by library size).
- **File-path / ingestion safety:** No file paths, uploads, or filesystem writes. N/A.
- **Data integrity / honesty contract:** Merge preserves only **manual** (human-override)
  assignments as a union; scored assignments are recomputed by the mandatory re-score from the merged
  text — never silently carried over with stale confidences. The frontend composition carries each
  folded axis's label as a `Related:` term so the survivor's embedding keeps that vocabulary
  (preserving discoverability) — this only shapes the axis *text*, which is always user-visible and
  editable before Apply. No verification/citation surface is touched.
- **Supply chain:** No new third-party dependency. `axis_operations.py` imports only existing
  first-party helpers + SQLAlchemy.
- **Route surface:** `tests/test_health.py::test_api_exposes_only_read_only_get_routes` updated to
  include `("/axes/merge", {"POST"})`; the invariant still pins the full mutation set (no
  unintended write routes).

## Negative-path checks (run)
Covered by `tests/test_axes.py::test_merge_validation` and `::test_merge_into_survivor_unions_manual_and_deletes_sources`:
- empty / whitespace-only label → **422**; `merge_axis_ids: []` → **422**; survivor present in
  `merge_axis_ids` → **422**; unknown `keep_axis_id` → **404**; unknown source id → **404**.
- A **rejected** merge changes nothing (both axes still present afterward).
- A successful merge: folded source deleted, survivor's manual assignments = the **union**, the
  papers themselves untouched, and the survivor re-scores cleanly.
- Full suite green (**145 passed**); live browser E2E shows **0 console errors**.

## Verdict
**Security Audit: PASS** — local-only, parameterized, fully validated at the boundary with no 500
path, no new egress or dependency, no file/secret surface, and the route-surface invariant holds.
