# Increment 167 — split 40_app.jsx (clear the carried 600-line violation)

**What this is:** a behavior-preserving refactor clearing the rule-#1 violation flagged as "the immediate next chore"
across the last six increment footers — `app/frontend/js/40_app.jsx` had crept to **630/600** (the App god-component
accreted modal/bulk/chip wiring since the inc-128 split). Done autonomously ("follow your heart") because it's the
one remaining roadmap item I can fully verify myself (the main app is headed-verifiable; no Word/egress needed),
whereas Google Docs + beyond-library discovery genuinely need the user's steering (server/auth/egress/Principles forks).

## Implemented (frontend-only)

Two cohesive lifts out of App (the inc-128 precedent: extract a hook + helpers into earlier-loading chunks):

- **`app/frontend/js/39_focus.jsx`** (new, 59) — `useFocusMode({ setActiveTab, onEnterClearFilters })`, the axis
  "focus-mode" subsystem (inc-50 C: stage add/remove of papers to an axis from the library, commit on Save) lifted
  **verbatim** from App. Owns `focusAxis`/`focusMembers`/`focusPending`/`axisRefresh` + `enterFocus`/`cancelFocus`/
  `toggleFocusPaper`/`saveFocus`; returns them (+ `setAxisRefresh`, also bumped by App after a merge). Narrow
  interface: App passes `setActiveTab` + an `onEnterClearFilters` callback (clears the axis/tag/signal view filters).
- **`app/frontend/js/00_lib.jsx`** (+~40) — the two big client-download helpers moved here (the utils home):
  `downloadCitationExport(ids, format)` (inc-70) + `downloadBibliography(ids, style)` (inc-106) + a shared
  `_downloadBlob`. App's `bulkExportPapers`/`bulkBibliography` became 1-line wrappers.
- **`app/frontend/js/40_app.jsx`** (**630 → 551**, 49-line margin): removed the focus state + its 4 callbacks (now
  the hook) and the two ~18-line download bodies (now in 00_lib); calls `useFocusMode(...)` after the library
  state declarations (so the filter setters it closes over exist) and destructures the focus bundle. Everything
  App still references (cancelFocus in the filter callbacks, enterFocus/axisRefresh in paneCtx, focus* in the
  render) resolves from the destructure — no call-site changes needed.

## Key technical detail
- **Chunk ordering** makes this safe with no bundler: `00_lib.jsx` (00) loads first (download helpers + React-hook
  destructure), `39_focus.jsx` (39) before `40_app.jsx` (40) — so `useFocusMode` is defined before App uses it.
  esbuild DCE keeps all three (App references them).
- **Hook-call placement:** `useFocusMode` must be called *after* the `useState`s for `activeTab` + the
  axis/tag/signal filters (its `onEnterClearFilters` + `setActiveTab` close over those setters) — placed right
  after the modal-state declarations.
- Behavior-preserving: the focus logic + download logic are byte-identical to the inc-166 versions, just relocated.

## Manual verification
**Headed, no egress** (`.local/visual/drive_inc167_app_split.py` — seeds a real library + axis via
`tests.api_helpers._seed_library`): the library renders (3 cards); **bulk export** downloads
`callosum-citations.bib` (exercises the moved `downloadCitationExport`); **focus-mode** enters via the axis ＋ and
cancels (exercises `useFocusMode`); the **axis filter** applies (exercises `filterToAxis`, which uses the hook's
`cancelFocus`); **0 console/page/genai**. A broken hook/helper wire would throw on those clicks → a pageerror.

## Gates
- **No new surface / endpoint / migration / egress / dependency** → no audit gate, Principles non-triggering (pure
  refactor; no claim/signal/provenance change). Help corpus unchanged (no user-facing change).
- **Rule #1 satisfied:** 40_app.jsx 551/600. **New closest watch:** `30_viewer.jsx` at **595/600** — split before
  the next addition there.

## Pytest
**611** unchanged (frontend-only; `test_frontend_assembly.py` confirms `39_focus.jsx` is in the build + the build is
in sync). `node --test "adapters/word/*.test.js"` 11/11 unchanged; surface **120/120 API + 599/599 FE, 0 uncovered**;
`ruff` clean.

## Next
The roadmap's remaining items are both design-led + need the user: **Google Docs** via the authenticated
clffwrkmn.net relay (tunnel + auth + rate-limiting + opt-in egress) and **beyond-library discovery** (#30 SP2, trips
the audit + Principles gates). New rule-#1 watch: `30_viewer.jsx` (595/600).
