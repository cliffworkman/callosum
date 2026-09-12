# Increment 591 — Trashing an open paper no longer logs a benign 422 (#60)

Trashing a paper whose reading-pane tab is open produced a `POST /citations/render` **422** ("No existing
(non-trashed) papers to render") + a browser console error. Nothing broke, but it was noise. Fixed at **two**
boundaries — the stale UI state (root cause) AND the endpoint's inconsistent empty-set semantics — **without**
matching the human error string (the OA-state lesson: prose must never become reconstructed machine state).

## Root cause (frontend): the open tab kept the paper "selected"
`trashPapers` (`03_library.jsx`) already cleared the Detail-pane `selected`, but the tab→selected derivation in
`40_app.jsx` (`activeTab` → `setSelected(tab.paperId)`) **re-set** `selected` to the still-open trashed tab,
so its Detail-pane `CiteRow` re-fired `/citations/render` with the now-trashed id.
- **`40_app.jsx`** — `trashPapers` now also **closes the trashed paper's reading-pane tab**, reusing the
  existing `closeTab` primitive (tab key is canonically `"pdf:"+id`; `openPdf` is the only creator) via the
  established forward-ref pattern (`closeTabRef`, alongside `cancelFocusRef`). Once no tab holds the id,
  `selected` (and everything derived from it — `contextPaperId`, the Detail pane) clears for good.
- **`03_library.jsx`** — `trashPapers` calls the new `closePapers(targets)` from opts before clearing
  `selected`.

## Residual race (backend boundary): empty-live-set was inconsistently a 422
The tab-close removes the persistent re-fire, but a single in-flight render can still land **after** the DELETE
(a genuine timing race) — and the browser logs `Failed to load resource: 422` **itself**, un-suppressible from
JS, so "zero console errors" can only be met by not producing a 4xx for this benign case. The fix is a **small,
honest boundary correction**, not a broadening:
- `get_papers_for_export` **already silently drops trashed ids and renders the live subset** (1 live + 1
  trashed → 200 with 1 item). Only the *all*-trashed case (0 live) was a 422 — an inconsistency, not a
  validation guard. **`routers/citations.py`** now renders an **empty bibliography (200)** for the all-absent
  case (no citeproc call, no usage event), consistent with the partial case.
- **Genuine bad input stays observable:** unknown style/label, too-many-papers, and engine errors all still
  422/502/503. This does **not** broaden all 422s into benign.

## Tests
`tests/test_citations.py`: kept the invalid-style → 422 assertion (bad input stays observable); replaced the
"nonexistent paper → 422" assertion with `test_render_all_absent_papers_is_empty_not_error` (→ 200, empty
items/bibliography). 63 citations tests pass (real citeproc sidecar).

## Live verification (Playwright, seeded DB)
Open paper 1 (reading-pane tab + Detail-pane render active) → switch to Library → Delete paper 1: the
post-trash render is now **`RENDER 200`** with **0 console errors/warnings** from the race (previously a
`RENDER 422` + console error + warning); paper trashed to Trash as before. Unrelated render failures (bad
style) remain 422s.

## Note (line budget)
`40_app.jsx` is now at the **600-line cap** exactly (this fix landed as +3 net lines by reusing `closeTab`
rather than adding a new function). The **next** addition there must extract a chunk first — the reader-tab
cluster (`openPdf`/`closeTab`/`activatePaperTab`/`reorderPdfTabs` + the two tab effects) is the natural
`useReaderTabs` extraction when that time comes (not done here — minimal-diff bug fix).
