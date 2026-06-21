# Increment 91 — Filter the library by type (+ prerequisite module splits)

Chore 1 of the "2 chores + 1 carrot" patter. Adding filter-by-type surfaced that two core files were at/over
the **600-line hard limit (rule #1)** — `repository.py` (625) and `papers.py` (600) — so per rule #1 they were
**modularized first**, then the feature landed. (The user chose "split, then feature.")

## Implemented

### Part 1 — modularization (behavior-preserving; rule #1)
- **`repository.py` 625 → 538.** Extracted the native-annotations data-access — `create_annotation` /
  `get_annotation` / `list_annotations_for_paper` / `delete_annotation` / `update_annotation` + the
  `NATIVE_ANNOTATION_SOURCES` / `ANNOTATION_COORDINATE_SYSTEM` constants + the `_UNSET` sentinel — verbatim into
  new **`app/backend/persistence/annotations_repo.py`** (cohesive table concern; precedent: `dedup_repo.py` inc 67,
  `tags_repo.py` inc 71). Removed the now-unused `annotations` schema import. Repointed importers:
  `routers/annotations.py` (split the import block; `get_paper` stays from `repository`) and
  `tests/test_persistence_core.py`.
- **`papers.py` 600 → 539.** Extracted the binary PDF file-serving — the `GET /papers/{paper_id}/pdf` route +
  its dedicated path helpers (`_select_primary_pdf_attachment` / `_is_pdf_attachment` / `_local_attachment_path`)
  — verbatim into new **`app/backend/api/routers/paper_files.py`** (route-extraction precedent: `duplicates.py`
  inc 64). Removed the now-unused `FileResponse` import and `Path` from the `pathlib` import (`_attachment_response`
  / `_path_filename` stay — they're shared with the JSON detail response). Registered `paper_files.router` in
  `app.py` right after `papers.router` (the `/pdf` path is a distinct segment, so include-order can't collide).

### Part 2 — feature: filter the library by item type
- **`repository.py`** — `list_papers(item_type=…)` adds `WHERE papers.item_type == :item_type` (a **bound** value,
  rule #3); composes with the existing q/deleted/axis/tag/needs-review/sort clauses. New `list_item_types(conn)`
  returns the distinct **live** item types + per-type counts, most-common first (NULL excluded).
- **`papers.py`** — an `item_type` query param on `GET /papers`, and a new **`GET /papers/item-types`** facet
  endpoint (defined before `/papers/{paper_id}` so the literal segment wins) returning `[{item_type, count}]`.
- **Frontend** — a **Type** dropdown in the library `.searchbar` (`10_pdf_layer.jsx`), shown only when types are
  present, options labeled by a `_typeLabel` map ("article-journal" → "Journal article (32)", unknown types
  prettified). `40_app.jsx` adds `libraryItemType` + `itemTypes` state, fetches `/papers/item-types` (refreshed on
  `libRefresh`), and threads `&item_type=`. `.searchbar` gained `flex-wrap: wrap` so the 4th control degrades
  gracefully on a narrow pane (stays one row when wide). Rebuilt `callosum-app.html`.

## Key technical detail
The PDF route **moved routers without changing its path** (`/papers/{paper_id}/pdf`), so the route-surface
allowlist (`test_health.py`) is unchanged except for the genuinely-new `/papers/item-types`. The Type facet is
**honest** — it only offers item types that actually exist in the live library (counts included), rather than a
hardcoded list that could show empty types. The filter value is bound, not interpolated (rule #3); no allowlist
is needed because it's an exact equality on a bound param, not a SQL identifier.

## Manual verification script
1. Hard-refresh. In the library header, a **Type** dropdown ("All types / Journal article (N) / …") sits with
   Search/Sort; pick a type → the list narrows; the count badges match.
2. Confirm types with zero live papers never appear; soft-delete the last paper of a type → it drops from the
   dropdown on the next library refresh.
   _(Visual check delegated to the user.)_

## Pytest
**385 passed, 1 skipped** (+1: `test_filter_by_item_type_and_item_types_endpoint` — exact-type filter, absent
type → empty, the facet list excludes NULL + orders by count, composes with soft-delete). The two splits are
behavior-preserving (annotations + PDF-serving tests unchanged). `ruff` clean. No migration, no egress.
