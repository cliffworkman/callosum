# Increment 63 Notes — Filter the library by axis (+ select-all)

Axes are an AI-scored lens over the library, but you could only see an axis's papers *inline* in the
sidebar. This wires **click an axis's count badge → the main Library narrows to that axis's papers**, with a
clearable "Filtered to axis …" banner. It completes the axes-as-navigation vision (the inc-44 click-to-open
pair) and pays off the inc-62 work: **filter to an axis → select all → summarize** = a verified synthesis of
an entire topic cluster in a few clicks. Backlog "open proposal: filter the library by axis."

## Implemented
- **Backend — an `axis_id` filter on the existing `GET /papers`** (no new endpoint, no migration):
  `repository.py::list_papers` gains `axis_id: int | None`; when set it adds a **bound-param `IN` subquery**
  (`papers.id IN (select paper_id from cluster_node_papers join cluster_nodes … where axis_id = :axis_id)`)
  that unions papers across all the axis's cluster nodes. Composes with the existing `deleted_at IS NULL` +
  `q` + pagination clauses (trashed papers stay excluded; search still works). `routers/papers.py::papers_index`
  threads an `axis_id` `Query` param through.
- **Frontend:**
  - `40_app.jsx`: `libraryAxisFilter` (`{id, label}`) state; the `/papers` fetch adds `&axis_id` (+ dep);
    `filterToAxis(axis)` (set filter, Library tab, page 0, clear selection, **exit trash/focus**),
    `clearAxisFilter`, `selectAllLibrary(ids)`. Reciprocally, `toggleTrash`/`enterFocus` clear the filter.
    Threaded `onFilterToAxis` App → `Sidebar` → `AxesPanel`; `libraryAxisFilter`/`onClearAxisFilter`/
    `onSelectAll` into `libraryProps`.
  - `15_axes.jsx`: the **count badge is now a clickable button** → "Show these N papers in the library"
    (`stop()`-wrapped so it doesn't toggle expand); keeps its scoring-status color (the tooltip carries both
    the filter hint and the status). A `filterToAxis` handler added to the AxesPanel `handlers`.
  - `10_pdf_layer.jsx`: a **"Filtered to axis {label} · clear"** banner (reuses the inc-50 `.focus-card`)
    above the search bar; a **"select all"** link in the library header (shown in `selecting` mode) →
    selects the current page. `selecting = !focusAxis && !trashView` is **unchanged**, so the filter keeps
    checkbox-select + summarize on (the synergy).
  - `styles.css`: clickable `.axis-count-badge` (border-reset + cursor + accent-soft hover ring);
    `.lib-select-all` link. Token-based per DESIGN.md. Rebuilt `callosum-app.html`.

## Security note (no separate audit doc)
Read-only feature. The `axis_id` filter is a **SQLAlchemy bound-param `IN` subquery** — no string
interpolation (rule #3). **No new endpoint, egress, ingestion, or migration**; the route path+method are
unchanged (route-surface invariant unaffected). Trashed papers remain excluded by the existing filter. An
unknown/empty axis → an empty list (graceful), with the banner still offering **clear**.

## Verification
- **pytest: 227** (+1, `tests/test_papers.py::test_papers_list_axis_filter`): `GET /papers?axis_id=N`
  returns only that axis's papers; the unassigned paper is excluded; `q` composes; an unknown axis → `[]`;
  a soft-deleted assigned paper drops out.
- **Live E2E** (`.local/library_axis_filter_e2e/`, seeded axis + injected fake generator): library shows 2
  papers → click the axis count badge → **"Filtered to axis Summary Axis"** banner + the library narrows to
  **1** paper → **select all → summarize** → a **verified** synthesis → **clear** → 2 papers restored; **0
  console errors**; screenshot. (The summarize uses `_seed_summarization_library`, whose attachments have no
  on-disk paths — `_seed_library`'s fake `C:\papers\…` paths break the coordinate step; a harness detail,
  not a feature bug.)

## Backlog
**"Filter the library by axis" (open proposal) — DONE (inc 63).** Deferred (noted): cross-page "select all
in the entire filtered set" (today covers the current 50-paper page); filter by axis **tier**
(assigned-only vs all); persisting the filter across reloads.
