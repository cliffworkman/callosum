# Increment 121 — THEORY/METHODS accordion side-panes on a module registry (UI shell)

The first half of the THEORY/METHODS future-track (the designated "next major upgrade"): replace the two fixed
side-pane wrappers with **accordions** driven by an **extensible module registry**. Behavior-preserving for the
section functionality — only arrangement + selection change. Spec/plan:
`.claude/docs/specs/2026-06-25-theory-methods-accordion-{design,plan}.md`.

**Deferred (separate later tracks):** the findings/flag/review subsystem, statcheck-as-a-METHODS-module, the
FACT-vs-CANDIDATE machinery. This increment is the empty accordion shell + registry + DESIGN.md only.

## Implemented

- **Registry + accordion (`app/frontend/js/05_panes.jsx`, new):** `PANE_SECTIONS` + `registerPaneSection({id,
  label, paneId, order, render})` + `<PaneAccordion paneId ctx openId onOpen/>`. Sections **self-register at load**
  from their own chunks (load order 05<10<15<20<25 ⇒ the registry exists first); `order` makes display position
  data-driven; the accordion renders ALL of a pane's sections but shows only the open one (**mount-but-hide**:
  `.acc-section:not(.open) .acc-body { display:none }`), so an in-progress synthesis survives a section switch.
- **Left pane = THEORY accordion:** **AXES** (`15_axes.jsx`) · **SYNTHESIS** (`20_synthesis.jsx`) · **TAGS**
  (`10_pdf_layer.jsx`), one open at a time, AXES default. `Sidebar` is now brand/⚙/❓ header + `<PaneAccordion
  paneId="theory">`. AXES/TAGS lost their redundant internal section labels (the accordion header is the label).
- **Right pane = METHODS accordion:** **DETAILS** (`25_detail.jsx`), registered from `05_panes.jsx` (see size note).
  Shows a "Select a paper to see its details" hint when nothing is selected; the editable Details on select.
- **App wiring (`40_app.jsx`):** assembles one `paneCtx` prop-bundle and renders the two accordions; new
  `callosum.theoryOpen`/`callosum.methodsOpen` persisted state; summarize-from-library now opens the **SYNTHESIS**
  section (left) instead of the old right pane. The inc-57 `RightPane` + `detailH` + `.divider-h` drag-split are
  **retired**; the outer panel resize/collapse (`leftW/rightW/leftOpen/rightOpen`) + reading mode + center tabs are
  untouched.
- **TAGS empty-state (the one intentional behavior change):** `TagsPanel` no longer `return null`s when empty — it
  shows "No tags yet — add tags from a paper's Details pane," so the feature is discoverable (the user reported never
  seeing Tags because their library had none).
- **DESIGN.md §5** — the THEORY/METHODS placement rubric (place by cognitive task), the accordion/registry pattern,
  the AI-usage principle ("where did the judgment go?"), a FACT-vs-CANDIDATE forward-note, accessibility.
- **QA:** `route_00` recalibrated for the accordion (steps 4/5 + the `fe:` coverage tokens); surface map regenerated
  (88/88 API, gate green).

## Key technical details

- **esbuild DCE gotcha:** the build wraps all chunks in one IIFE and **dead-code-eliminates unreferenced top-level
  functions** — a registered-but-unused component is stripped from the bundle until something references it. So the
  Task-1 "is PaneAccordion in the bundle" check was wrong (it only appears once App uses it, Task 3); the correct
  gate is **raw-source inclusion + a successful esbuild build** (`test_frontend_assembly.py` checks the *raw*
  assembly precisely for this reason). Documented in DESIGN.md §5.
- **Hoisting + chunk order** make the registry work: `registerPaneSection`/`_loadLayout`/`DetailContent` are hoisted
  function declarations available across the concatenated IIFE; the `const PANE_SECTIONS` executes (chunk 05) before
  the register calls (chunks 10/15/20). The DETAILS render closure references `DetailContent` (chunk 25) but only at
  render time, so registering it from 05 is fine.
- **`node --check` doesn't accept `.html`** — the syntactic gate is the esbuild build itself (it transpiles + parses
  the JSX; a syntax error fails the build).

## File-size note (rule #1)

`25_detail.jsx` was **already 625 (>600) before inc 121** — a pre-existing violation. To avoid worsening it, the
DETAILS registration lives in `05_panes.jsx` (not 25); 25 is back to exactly 625. **Follow-up debt:** split
`25_detail.jsx` — the upcoming "statcheck → METHODS section" work (user-queued) will pull the statcheck section out
of it and should bring it under cap. All other touched files are under 600 (40_app 572, 10_pdf 515, 15_axes 500,
20_synthesis 349, 05_panes 46).

## Manual verification

Headed Playwright on the seeded `:8097` (`.local/visual/verify_accordion.py`): THEORY headers render in order
AXES/SYNTHESIS/TAGS (AXES open); clicking SYNTHESIS collapses AXES + shows the query box; TAGS shows its list/empty
hint; METHODS shows the DETAILS hint then the editable pane on select; the open section **persists across reload**;
the outer divider collapse works; **0 console/page errors**. **Additivity proof:** a throwaway section registered
from a brand-new chunk appeared as "DUMMY PROOF" with **zero edits to `PaneAccordion`**, then reverted.

## Pytest

**437 passed, 1 skipped** (frontend-only — unchanged from inc 120; the assembly + route-surface + health tests
exercise the new chunk/wiring). `ruff format`/`check` clean.

## Commits (on main)

`8b234d0` (T1 registry+accordion+css) · `9022849` (T2 register sections + TagsPanel empty-state) · `39508cb`
(T3 App switch + retire RightPane) · `0058ac0` (T4 DESIGN.md) · `ce35fb1` (T5 QA route) · this docs commit
(+ the T6 details-registration move to keep 25_detail.jsx ≤ 625).

## Next (user-queued)

1. **statcheck → METHODS accordion section** — relocate the Settings batch-run into a `registerPaneSection({paneId:
   "methods"})` section; the first real METHODS module (and it relieves the 25_detail.jsx size debt).
2. **Synthesis produces no text summary** — investigate: synthesis shows retrieved sections but no narrative.
   Leading hypothesis: egress off (no generation) on the user's instance; could also be a render bug. Needs a
   proper look.
3. Then the broader findings subsystem (FACT vs CANDIDATE) + the THEORY/METHODS vocabulary adoption once METHODS
   modules exist.
