# Increment 600 — Discover UX cleanup (GitHub #78) 🎉 milestone

The 600th increment: a bounded Discover-navigation cleanup — inline search clear, one merged **Gaps & overlooked**
destination, and **Saved for later → Saved**. **Frontend-only.**

## 1. Inline search clear (×)
The standalone **Clear ×** button is removed; the search input (`30d_discover.jsx`) is wrapped so a right-aligned
**×** (`.discover-search-clear`, `aria-label="Clear search"`) appears **only when the field has text** and calls
the existing `clearActiveSearch` (identical semantics — cancels an in-flight search, clears query/results/cursor/
relevance without touching saved papers). No added toolbar width; keyboard-accessible.

## 2. Merge Gaps + Overlooked into one destination
Trace found the two are **cognitively adjacent, not different jobs**: both surface *relevant works you don't have
yet* — Gaps by citation edges (works you cite / that cite you), Overlooked by axis relevance vs. same-year
citations — and they **already share** the `/gaps/add` + `/gaps/dismiss` state (a dismissal is about the work, not
which lens surfaced it). So I merged **navigation, not ontology** (per the steering): the two toolbar buttons
become one **Gaps & overlooked** button opening a modal whose header carries a shared **Gaps | Overlooked** facet
toggle (`GapsOverlookedFacets`, hoisted from `36_gaps.jsx`). Switching swaps which modal mounts; **each facet
keeps its own typed state, endpoints, copy, and honesty framing** (`36_gaps.jsx` / `36b_overlooked.jsx` unchanged
but for the header toggle + `facet`/`onSwitchFacet` props). No data/state lost; no second taxonomy.
- `40_app.jsx`: two booleans (`gapsOpen`/`overlookedOpen`) → one tri-state `gapsOverlooked` (null|gaps|overlooked);
  one `onOpenGapsOverlooked` ctx callback; `nav.modal` deep-links (`gaps`/`overlooked`) open the right facet.
  (Net line change ≈ 0; `40_app.jsx` stays at the 600 cap.)

## 3. Rename "Saved for later" → "Saved"
The Discover toolbar button + the modal header (`36c_beyond_library_saved.jsx`) become **Saved**; persistence/state
unchanged. The **Save for later** *action* verb (Cite / LibreOffice) is kept — only the destination label changed.

## Testing
- **Playwright e2e** (`tests/e2e/test_smoke.py::test_discover_toolbar_inline_clear_and_merged_gaps_overlooked`,
  **passes headless**): the inline × is hidden when empty, appears with text, and clears the field (no standalone
  Clear button); one **Gaps & overlooked** button opens the modal; the header facet toggle switches to the
  Overlooked facet (its distinctive copy renders); the **Saved** button is present and "Saved for Later" is gone;
  zero console errors. Runs in CI's `e2e-smoke`.
- `tests/test_frontend_assembly.py` (87) — updated the three assertions that pinned the old separate
  buttons/labels (`onOpenGaps`/`onOpenOverlooked`, "Clear ×", the Overlooked-button title) to the merged
  structure (`onOpenGapsOverlooked`, the inline ×, "Gaps & overlooked"/"Saved", `GapsOverlookedFacets`).
- `styles.css`: `.discover-search-input` wrapper + `.discover-search-clear` (theme-aware, uses `--ink-3`/`--ink`).
- Light/dark + narrow-width polish of the wrapped input + facet toggle: manual (the toggle reuses the theme-aware
  `tags-srcfilter` primitive; the × uses tokens).

## Gates / scope
Frontend-only; **zero backend change** (no new endpoint — Gaps/Overlooked/Saved were already app-level modals
opened from the Search toolbar). No new API surface (QA map green); route_41 + route_43 prose updated; help
corpus updated (menu-bar list, Gaps/Overlooked/Saved sections, Clear reference, destination refs). Line budget:
all ≤600 (`40_app.jsx` 600, `30d_discover.jsx` 246). No `experiments/**` / `summarization/**` change; frozen
0.6/0.7 Ask untouched.

## Milestone
This completes the **inc 598 → 599 → 600** push (reader acquire-OA + Critique #79; Discover Search providers #77;
Discover UX cleanup #78). **Next: cut Desktop 0.5.14** (a separate task) bundling incs 595–600.
