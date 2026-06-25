# Design spec — accordion side-panes on a module registry (THEORY/METHODS UI shell)

**Date:** 2026-06-25
**Status:** approved design → spec under review
**Scope:** the **UI-shell + DESIGN.md** half of the THEORY/METHODS future-track
(`.claude/docs/future-tracks/opus4.8_future-tracks_theorymethods.md`, STEPs 1–4). Designated "next major upgrade."
**Explicitly deferred:** the findings/flag/review subsystem, statcheck-as-a-module, retraction/OSF/any METHODS
check — those are the *separate* later track (`_theorymethodsextension.md`).

---

## 1. Problem & goal

Today the side panes are hard-coded: the **left** `Sidebar` (`10_pdf_layer.jsx`) stacks AXES (`15_axes.jsx`) +
TAGS (`TagsPanel`); the **right** `RightPane` (`20_synthesis.jsx`, inc-57) is a fixed vertical drag-split with
SYNTHESIS always on top and DETAILS (`25_detail.jsx`) below when a paper is selected. Adding a section means
editing those wrappers. The goal: replace both fixed layouts with an **accordion** driven by an **extensible
module registry**, so the panes become a *data-defined* list of sections (and future METHODS modules are additive)
— **behavior-preserving** for the actual axes/synthesis/tags/details functionality; only arrangement + selection
change.

This establishes the THEORY (knowing the literature) vs METHODS (evaluating how a paper was studied) cognitive-task
model as the app's organizing principle, **internally** — the visible THEORY/METHODS labels are deferred ("soft
labels") until the METHODS modules that earn the word exist.

## 2. Decisions (from brainstorming)

- **Accordion, one section open per pane** (the doc's plan). Left pane sections: **AXES, SYNTHESIS, TAGS**; right
  pane section: **DETAILS**. Synthesis relocates from the right pane into the left accordion (mutually exclusive
  with axes) — accepted trade: no more simultaneous axes+synthesis, but each section gets full pane height.
- **TAGS = its own accordion section** (a first-class organizing lens beside AXES), **always shown** with an
  empty-state hint when there are no tags (fixes today's vanish-when-empty discoverability gap — the one
  intentional behavior change beyond arrangement).
- **Soft labels:** no "THEORY"/"METHODS" umbrella pane headers yet — the section headers (AXES / SYNTHESIS / TAGS //
  DETAILS) are the only visible labels. Internally each section declares `paneId: "theory" | "methods"` so the
  architecture + the eventual rename are ready.

## 3. Architecture — the module registry + accordion

### 3.1 Registry (new chunk `app/frontend/js/05_panes.jsx`, loads before the section chunks)
- A module-level `PANE_SECTIONS = []` + `registerPaneSection({ id, label, paneId, render })`. Each section chunk
  calls `registerPaneSection(...)` at load — self-registering, so a new section is **one call in a new chunk, zero
  edits to the accordion** (the explicit additivity test). `render` is `(ctx) => <Component …/>`; `ctx` is the
  shared prop-bundle the App passes down (see 3.3).
- A **`<PaneAccordion paneId="theory" ctx={…} openId=… onOpen=… />`** component: filters `PANE_SECTIONS` by
  `paneId` (in registration order), renders each as a header (always visible) + a body. **One body open at a time**
  per pane; clicking a collapsed header opens it and collapses the rest.
- **Mount-but-hide:** all sections in a pane stay **mounted**, the inactive ones CSS-hidden (`display:none`), not
  unmounted — so an in-progress synthesis (polling, results, scroll) survives switching to AXES and back, and
  DETAILS keeps its state. Mirrors the center `LibraryFrame`'s hidden-but-mounted PDF tabs.

### 3.2 Section registrations (the four existing components, unchanged internally)
| id | label | paneId | render → component (chunk) |
|---|---|---|---|
| `axes` | AXES | theory | `AxesPanel` (`15_axes.jsx`) |
| `synthesis` | SYNTHESIS | theory | `SynthesisPane` (`20_synthesis.jsx`) |
| `tags` | TAGS | theory | `TagsPanel` (`10_pdf_layer.jsx`) — empty-state instead of `return null` |
| `details` | DETAILS | methods | `DetailContent` (`25_detail.jsx`) |

`Sidebar` (left wrapper) and `RightPane` (right wrapper, the inc-57 split) are **replaced** by two
`<PaneAccordion>`s. The left pane keeps its brand/⚙/❓ header above the accordion.

### 3.3 Prop threading
App assembles one `ctx` object with every prop any section needs today (e.g. `selectedPaper`, `onSelectPaper`,
`onOpenPaper`, `onOpenCitation`, `onSaveHighlight`, `onFilterToTag`, `onFilterToAxis`, `onEnterFocus`,
`onOpenMyPubsDashboard`, `onTagsChanged`, `pendingSummarize`, `axisRefresh`, `tagRefresh`,
`hideUncertainDefault`, `axisCutoffDefault`, `conn`) and passes it to both `<PaneAccordion>`s; each section's
`render(ctx)` picks what it needs. This centralizes the threading the wrappers do today.

## 4. State, persistence & behavior-preservation

- **New localStorage keys:** `callosum.theoryOpen` (`axes`|`synthesis`|`tags`, default `axes`) and
  `callosum.methodsOpen` (`details`, default `details`) — the open section per pane persists across reload.
- **Preserved untouched:** the outer `Divider`s + `callosum.leftW`/`rightW`/`leftOpen`/`rightOpen` (panel width
  resize + collapse-to-focus), reading mode, and the center `LibraryFrame` tab system.
- **Retired:** the inc-57 inner vertical split — `.divider-h`, the `detailH` state + `callosum.detailH` key, and the
  `RightPane` drag wiring. The accordion supersedes it. (The shared `_beginDrag`/`_clampW` helpers stay — the outer
  dividers still use them.)
- **Selecting a paper** opens/shows the DETAILS section in the right (methods) pane (preserves today's
  "select → see details"); with no paper selected, DETAILS shows its existing empty hint.
- Otherwise **behavior-preserving**: axes scoring/merge/suggest, synthesis generate/history/citations, tag
  filtering, and the editable Details all function exactly as today — only where they live + how they're selected
  changes. (Sole intentional behavior change: the TAGS empty-state, §2.)

## 5. DESIGN.md additions (rule #8)
Add a section encoding:
- **The THEORY/METHODS placement rubric:** THEORY = knowing the literature (axes, synthesis, tags); METHODS =
  evaluating how a paper was studied (details now; checks later). *Place a tool by the user's cognitive task, not by
  its implementation — "AI-powered" is orthogonal to the distinction.* (Documented even though the visible labels
  are soft, so future modules know which pane they belong in.)
- **The accordion + module-registry pattern** (sections are data; addable, someday user-supplied).
- **The AI-usage principle:** the AI's job is to make verification cheap, never to substitute for it — "where did
  the judgment go?" must land on a checkable computation or on the human.
- A **forward-reference** to the FACT-vs-CANDIDATE output contract (built in the later findings track, not here).
- **Accessibility:** differentiate sections by icon/label + color (never color alone); prefer a highlight over a
  blink; gate motion behind `prefers-reduced-motion`.

## 6. File plan (600-line cap)
- **New:** `app/frontend/js/05_panes.jsx` (registry + `PaneAccordion`); `styles.css` accordion classes (tokens
  only, rule #8).
- **Modified:** `40_app.jsx` (render two `<PaneAccordion>`s + assemble `ctx`; drop the `Sidebar`/`RightPane`
  wiring + `detailH`); `10_pdf_layer.jsx` (`Sidebar` → a thin brand/⚙/❓ header; `TagsPanel` empty-state; register
  `tags`); `15_axes.jsx` (register `axes`); `20_synthesis.jsx` (register `synthesis`; drop the `RightPane` split
  shell, keep `SynthesisPane`); `25_detail.jsx` (register `details`); `30_viewer.jsx` only if `LibraryFrame`
  references the removed wrappers. Re-measure each against 600; `40_app.jsx` (~552) should *shrink* as wrapper
  wiring moves into the registry.

## 7. Gate / verification
- **Principles gate (rule #9): non-triggering.** No new claim/signal/judgment, no egress change, no
  fact/candidate/provenance surface — purely arrangement + selection, behavior-preserving. (The findings/output
  contract that *would* trigger it is the deferred track.)
- **No backend, no migration, no new endpoint** — frontend-only.
- **Verify (headed Playwright on the seeded `:8097`):** the THEORY pane switches AXES⇄SYNTHESIS⇄TAGS (one open at a
  time) and the open section **persists across reload**; selecting a paper shows DETAILS; the outer panel
  resize/collapse + reading mode + center tabs are intact; an **in-progress synthesis survives** a section switch
  (mount-but-hide); a **throwaway dummy registered section** appears with no accordion-component edit (proves the
  registry), then is removed. pytest (frontend-only, but run it) green; `ruff` clean; rebuild `callosum-app.html`.

## 8. Out of scope
Findings/flag/review subsystem, the `paper_findings` schema, statcheck/retraction/OSF/transparency METHODS modules,
the FACT-vs-CANDIDATE machinery, the "N to review" badge — all the *separate* findings track. This increment is the
empty accordion shell + registry + DESIGN.md only; the METHODS pane legitimately holds just DETAILS until those land.
