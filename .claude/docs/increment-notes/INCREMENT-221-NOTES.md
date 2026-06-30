# Increment 221 — the 40_app.jsx split (useLibrary) + the read/priority filter facet

## Implemented

The maintainer's chosen "proper split first" (over the compaction can-kick), then the deferred inc-220 filter facet.

### The 40_app.jsx split → `useLibrary` (03_library.jsx)

`40_app.jsx` had been pinned at the 600-line cap for 10+ increments ("split before the next addition there"); the
inc-220 filter facet needed headroom there. Extracted the **library-list subsystem** into a new `useLibrary(opts)`
hook (`app/frontend/js/03_library.jsx`, loads before App): the filter/query/list-fetch state, pagination, the bulk
+ trash + view-filter actions, saved searches, the statcheck/retraction "N flagged" chips + the findings overview,
the watched-folder rescan, and the p-curve/merge modal state (the bulk actions that open them + `onMerged` live in
the hook). **40_app.jsx 599 → 212.**

App keeps the shell + cross-cutting state: `conn`, settings/help, `useUiPrefs`, `selected`, tabs/activeTab,
annoRefresh/queueRefresh/tagRefresh, the open-modal flags (duplicates/wanted/gaps/scan/import), `openPdf` etc.,
`useFocusMode`, the health/Esc effects, `paneCtx`, and the render. The hook returns `libraryBits` (the LibraryFrame
prop bundle, **minus** the focus + `selected` props App still owns + spreads in) plus the handful App's paneCtx /
modals need (`pendingSummarize`, `filterToTag`/`filterToAxis`, the `show*` navigators, the chip refreshers,
`setFindingsRefresh`, `pcurvePapers`/`mergeIds`/`onMerged`, `showNeedsReview`, `setLibRefresh`).

### Key technical detail — breaking the focus↔library cycle

The hard part: a **circular dependency**. `useFocusMode`'s `onEnterClearFilters` must clear the library view
filters (focus-enter replaces any filter), and the library's filter/merge actions call `cancelFocus` +
`setAxisRefresh` — but `useFocusMode` is declared *after* `useLibrary` (cancelFocus must exist). Broken with two
refs: App declares `cancelFocusRef` + `setAxisRefreshRef`, passes the library `cancelFocus: () =>
cancelFocusRef.current()` + `setAxisRefresh: (fn) => setAxisRefreshRef.current(fn)`, then after `useFocusMode`
sets `cancelFocusRef.current = cancelFocus` + `setAxisRefreshRef.current = setAxisRefresh`, and wires
`useFocusMode({ onEnterClearFilters: lib.clearViewFilters })`. (`axisRefresh` stays owned by `useFocusMode` —
`saveFocus` bumps it internally — so a ref, not a move, keeps 39_focus.jsx untouched.)

### The read/priority filter facet (the deferred inc-220 piece)

With headroom freed, the library header gained a **Read** filter (all / unread / read) + a **Priority** filter
(all / high / normal / low) — `libraryReading` state in `useLibrary` → the `read_status`/`priority` query params
(already on `GET /papers` since inc 220). Live-library only (guarded `!trashView`). User facets, never a score.

## Manual verification script — behavior-preservation, the discipline

Frontend behavior isn't covered by pytest, so I used a **baseline regression driver** (`.local/visual/drive_inc221_library.py`):
run it GREEN on the **pre-refactor** code (the safety net), then GREEN after the extraction + the facet. Covers:
load (6 seeded), search (q) + clear, sort (Title A–Z), item-type filter + clear, the Trash toggle (+ back),
saved-search save → (menu closes) → re-open → delete (verified via `GET /saved-searches`), bulk-select, and the new
read/priority facet (filter Unread → 5 of 6; filter High → 1; clear → 6). **14/14 GREEN, deterministic 3/3, 0
console/page/genai.** Harness: own free port + own seeded DB (with WAL-sidecar cleanup) + an empty
`CALLOSUM_LIBRARY_DIR` (so the on-load auto-rescan doesn't scan the real library) + `window.prompt` stubbed for the
saved-search name. The build (esbuild) + `test_frontend_assembly` catch scope/sync errors.

## Pytest

**785 unchanged** (frontend-only — no Python touched; `test_frontend_assembly` confirms `callosum-app.html` is in
sync). QA surface **161/161 API + 719/719 FE, 0 uncovered** (the 2 new filter dropdowns are claimed via
`10_pdf_layer.jsx`; `route_50_reading_markers.md` gained a filter-facet step).

## Rule #1

`40_app.jsx` **599 → 212**; `03_library.jsx` **351**; `10_pdf_layer.jsx` **581** (+ the 2 filter dropdowns). All
comfortably under 600. **Standing watch:** `15_axes.jsx` is **614 (>600)** (pre-existing from inc 211/212) — a
separate behavior-preserving split, untouched here.

## NEXT

- **This completes Bella's reading-workflow thread** (reading queue inc 219 + read/priority markers inc 220 + the
  filter facet inc 221).
- **Standing rule-#1 follow-up:** the `15_axes.jsx` (614) split.
- The remaining backlog is the design-gated **B-items** (B2 collaboration, B3 OCR, B4 citation-context classifier,
  B5 mobile) — each its own brainstorm + the maintainer's pick.
