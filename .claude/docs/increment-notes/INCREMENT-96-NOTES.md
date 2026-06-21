# Increment 96 — Sidebar Tags browser + Details "More → + add field"

The two **chores** of the patter (the carrot, statcheck-as-a-library-lens, follows in its own plan-mode
increment). Both are small, **frontend-only** wins reusing already-tested endpoints — no new backend, no new
test, no migration; pytest stays **405**.

## Implemented

### Chore 1 — sidebar Tags browser
Tags were only visible per-paper (the Details TagsRow); there was no way to see the whole tag vocabulary. New
**`TagsPanel`** (`app/frontend/js/10_pdf_layer.jsx`) renders below the Axes panel in the left sidebar: each tag
with its **paper count**, click to **filter the library** (reuses the inc-71 `filterToTag` / `libraryTagFilter`).
Collapsible; a quick filter when there are >8 tags; hidden entirely when there are no tags. Reuses
`GET /tags` (already returns `paper_count`). The sidebar scrolls as one column (`.pane{overflow-y:auto}`), so the
panel just stacks under `.axis-group`.
- **Live refresh:** a `tagRefresh` nonce (`40_app.jsx`) threaded to `Sidebar`→`TagsPanel`; the Details `TagsRow`
  calls a new `onTagsChanged` (threaded App→`RightPane`→`DetailContent`→`TagsRow`) after a successful add/remove,
  so a tag added/removed on a paper updates the sidebar browser immediately.

### Chore 2 — "More → + add field" in Details
The Details "More" section only surfaced extra fields a DOI happened to populate; you couldn't add a
bibliographic field by hand (the inc-49 deferral). The "More" section now **always renders** and includes a new
**`AddFieldRow`** (`25_detail.jsx`): a field-name input + value input + **+ add** → `saveField("csl", {key:
value})`, reusing the inc-49 validated generic `csl` patch (backend accepts letter-led `[A-Za-z0-9_-]` keys;
reserved/core keys are rejected with a 422 that surfaces as the pane's save note). On success the field appears
in "More" (the PATCH returns the updated paper → `extras` recomputes). Reference-manager parity (Zotero/Mendeley
let you add fields).

Rebuilt `callosum-app.html`. CSS for both is token-based (`.tags-panel-*`, `.detail-addfield-*`).

## Key technical detail
Neither chore touches Python — both ride existing, tested endpoints (`GET /tags` from inc 71; the `csl` patch
on `PATCH /papers/{id}` from inc 49, unit-tested in `test_paper_edits.py`). The only non-trivial wiring is the
`tagRefresh` nonce + `onTagsChanged` callback so the left-sidebar Tags browser stays in sync with per-paper tag
edits made in the right-pane Details (sibling panes under App).

## Manual verification script
1. Hard-refresh. With tags in your library, a **Tags** panel appears below Axes (each with a count); click one →
   the library filters to it (the "Filtered to tag…" banner shows; clear restores). Add a tag to a paper in
   Details → it appears/updates in the sidebar panel without a reload.
2. Open a paper → **More** → type a field name (e.g. `publisher-place`) + value → **+ add** → it appears in More;
   a reserved/core name (e.g. `title`) shows a save error. _(Visual check delegated to the user.)_

## Pytest
**405 passed, 1 skipped** — unchanged (frontend-only; both chores reuse already-tested endpoints). `ruff` clean.
No migration, no egress, no new endpoint.
