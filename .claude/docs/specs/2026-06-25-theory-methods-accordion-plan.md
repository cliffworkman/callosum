# Accordion Side-Panes on a Module Registry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use `- [ ]` checkboxes.

**Goal:** Replace the two fixed side-pane wrappers (left `Sidebar`, right `RightPane`/inc-57 split) with an **accordion** driven by an **extensible module registry** — left pane = AXES · SYNTHESIS · TAGS, right pane = DETAILS, one section open per pane — behavior-preserving for the section functionality.

**Architecture:** A new early chunk `05_panes.jsx` holds `PANE_SECTIONS` + `registerPaneSection({id,label,paneId,render})` + a `<PaneAccordion paneId openId onOpen ctx/>` component. Each section chunk self-registers at load (chunk order 05<10<15<20<25 guarantees the registry exists first). App assembles one `ctx` prop-bundle, owns the open-section state per pane (persisted), and renders two `<PaneAccordion>`s. Sections stay mounted (CSS-hidden when collapsed) so in-progress synthesis survives a switch. Spec: `.claude/docs/specs/2026-06-25-theory-methods-accordion-design.md`.

**Tech Stack:** React 18 JSX chunks under `app/frontend/js/` (CDN React, esbuild-precompiled into `callosum-app.html` via `python tools/build_frontend.py`); no bundler/HMR — one concatenated IIFE, so top-level `function` declarations are hoisted across chunks and top-level `const`s execute in chunk order. Verification: `node --check` on the built file, `pytest tests/test_frontend_assembly.py`, headed Playwright against the seeded `:8097`.

## Global Constraints
- **Frontend-only.** No backend, no migration, no new endpoint, no egress change. Principles gate non-triggering (behavior-preserving arrangement, no claim/signal/fact-candidate surface).
- 600-line cap on `app/` files. Current: `40_app.jsx` ~552 (should *shrink*), `10_pdf_layer.jsx` ~520, `20_synthesis.jsx` ~365, `15_axes.jsx` ~500, `25_detail.jsx` ~630 (exempt? no — it's app/frontend; it's already over? re-measure: it's not in the modify-heavy set; only its registration is added). Re-`wc -l` each touched file before committing.
- Rule #8 (DESIGN.md) for CSS — tokens/recipes only; read DESIGN.md before adding classes.
- Rule #10 (QA): this changes an end-user surface → update `route_00` + the surface checklist in the same increment.
- After ANY `app/frontend/` edit: `python tools/build_frontend.py`, then `node --check callosum-app.html`. Behavior-preserving: only the **one** intentional change beyond arrangement is the TAGS empty-state (was `return null`).
- The shared helpers `_loadLayout`/`_saveLayout`/`_clampW`/`_beginDrag` + `Divider` (40_app.jsx:1-36) and `leftW/rightW/leftOpen/rightOpen` + reading mode stay. The inc-57 `detailH` + `.divider-h` are retired.

---

## Task 1: The registry + PaneAccordion component + CSS

**Files:**
- Create: `app/frontend/js/05_panes.jsx`
- Modify: `app/frontend/styles.css` (accordion classes)

**Interfaces:**
- Produces: `registerPaneSection({ id, label, paneId, render })` (paneId ∈ `"theory"|"methods"`; `render` is `(ctx) => JSX`); `PANE_SECTIONS` (module array); `function PaneAccordion({ paneId, ctx, openId, onOpen })`.

- [ ] **Step 1: Create `05_panes.jsx`** with the registry + accordion:

```jsx
// inc <NN>: THEORY/METHODS side panes as an accordion on an extensible module registry. Each section chunk
// self-registers at load (chunk order 05<10<15<20<25 ⇒ this array exists before the register calls run). The
// accordion renders all of its pane's sections but shows only the open one (mount-but-hide), so an in-progress
// synthesis survives a section switch. Pane labels are deliberately "soft" (section headers only) for now; the
// paneId ("theory"|"methods") is the internal architecture + the eventual rename. See DESIGN.md (placement rubric).
const PANE_SECTIONS = [];
function registerPaneSection(section) {
  if (!PANE_SECTIONS.some(s => s.id === section.id)) PANE_SECTIONS.push(section);  // idempotent by id
}
function paneSections(paneId) { return PANE_SECTIONS.filter(s => s.paneId === paneId); }

function PaneAccordion({ paneId, ctx, openId, onOpen }) {
  const sections = paneSections(paneId);
  if (sections.length === 0) return null;
  const active = sections.some(s => s.id === openId) ? openId : sections[0].id;
  return (
    <div className="pane-accordion">
      {sections.map(s => (
        <section key={s.id} className={"acc-section" + (s.id === active ? " open" : "")}>
          <button className="acc-header" aria-expanded={s.id === active}
            onClick={() => onOpen(s.id === active ? active : s.id)} title={s.label}>
            <span className="acc-chevron">{s.id === active ? "▾" : "▸"}</span>
            <span className="acc-label">{s.label}</span>
          </button>
          {/* mount-but-hide: every body stays mounted; inactive ones are display:none via .acc-section (not .open) */}
          <div className="acc-body">{s.render(ctx)}</div>
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Add CSS** (read DESIGN.md first; tokens only) after the existing `.pane-sidebar`/`.pane-detail` block in `styles.css`:

```css
  /* inc <NN>: accordion side panes (THEORY/METHODS shell). One section body visible per pane; headers stacked. */
  .pane-accordion { display: flex; flex-direction: column; min-height: 0; flex: 1; }
  .acc-section { display: flex; flex-direction: column; border-top: 1px solid var(--line); min-height: 0; }
  .acc-section:first-child { border-top: none; }
  .acc-header {
    display: flex; align-items: center; gap: 6px; width: 100%; text-align: left; cursor: pointer;
    background: none; border: none; font-family: var(--sans); font-size: 11px; font-weight: 600;
    letter-spacing: 0.04em; text-transform: uppercase; color: var(--ink-2); padding: 9px 4px;
  }
  .acc-header:hover { color: var(--accent); }
  .acc-chevron { color: var(--ink-3); }
  .acc-body { display: none; min-height: 0; overflow: auto; flex: 1; }
  .acc-section.open .acc-body { display: block; }
```

- [ ] **Step 3: Rebuild + syntactic gate.** `python tools/build_frontend.py && node --check callosum-app.html && grep -c "function PaneAccordion" callosum-app.html` → build writes the file; `node --check` exits 0; PaneAccordion present (1).
- [ ] **Step 4: Assembly test + ruff (no Python changed, but the new chunk must be included).** `pytest tests/test_frontend_assembly.py -q` → green (the new chunk is auto-globbed + the in-sync test matches the rebuild).
- [ ] **Step 5: Commit** `feat(panes): pane-section registry + PaneAccordion component + CSS (shell, not yet wired)`.

---

## Task 2: TagsPanel empty-state + register the four sections

**Files:** Modify `10_pdf_layer.jsx` (TagsPanel empty-state + register `tags`), `15_axes.jsx` (register `axes`), `20_synthesis.jsx` (register `synthesis`), `25_detail.jsx` (register `details`).

**Interfaces:**
- Consumes: `registerPaneSection` (Task 1); the existing components `AxesPanel`/`SynthesisPane`/`TagsPanel`/`DetailContent`.
- Produces: four registered sections — `axes`/`synthesis`/`tags` (paneId `theory`), `details` (paneId `methods`).

- [ ] **Step 1: TagsPanel empty-state.** In `10_pdf_layer.jsx`, replace `TagsPanel`'s `if (tags == null || tags.length === 0) return null;` (line ~159) so it renders an empty-state instead of vanishing (discoverability fix — the one intentional behavior change):

```jsx
  if (tags == null) return null;  // still loading → nothing
  // (removed: the `tags.length === 0 → return null` early-out; the empty list now shows a hint below)
```

and inside the list block, when `tags.length === 0`, render the hint (replace/guard the existing `.tags-panel-list` body):

```jsx
        <div className="tags-panel-list">
          {tags.length === 0
            ? <span className="tag-suggest-empty">No tags yet — add tags from a paper's Details pane.</span>
            : shown.map(t => (
                <button key={t.id} className={"tags-panel-item" + (tagIsImported(t.source) ? " tags-panel-item-imported" : "")}
                  title={tagSourceLabel(t.source) + " · filter the library to “" + t.name + "”"}
                  onClick={() => onFilterToTag && onFilterToTag({ id: t.id, name: t.name })}>
                  <span className="tags-panel-name">{t.name}</span>
                  <span className="tags-panel-count">{t.paper_count}</span>
                </button>))}
          {tags.length > 0 && shown.length === 0 && <span className="tag-suggest-empty">no matching tags</span>}
        </div>
```
(Keep the `tags.length > 8` filter input + the src-filter guarded on `tags.length > 0`.) Also drop the now-redundant outer `.axis-group`/chevron wrapper if the accordion header replaces it — **but** TagsPanel is rendered *inside* an accordion body now, so remove its own `.axis-group-head`/`tags-panel-toggle` collapse header (the accordion header is the collapse control). Net: TagsPanel returns just the filter + src-filter + list (no self-collapse).

- [ ] **Step 2: Register `tags`** at the top level of `10_pdf_layer.jsx` (after the TagsPanel definition):

```jsx
registerPaneSection({ id: "tags", label: "Tags", paneId: "theory",
  render: (ctx) => <TagsPanel onFilterToTag={ctx.onFilterToTag} tagRefresh={ctx.tagRefresh} /> });
```

- [ ] **Step 3: Register `axes`** at the top level of `15_axes.jsx` (after `AxesPanel`):

```jsx
registerPaneSection({ id: "axes", label: "Axes", paneId: "theory",
  render: (ctx) => <AxesPanel onSelectPaper={ctx.onSelectPaper} selectedPaper={ctx.selectedPaper}
    onOpenPaper={ctx.onOpenPaper} onEnterFocus={ctx.onEnterFocus} onFilterToAxis={ctx.onFilterToAxis}
    onOpenMyPubsDashboard={ctx.onOpenMyPubsDashboard} axisRefresh={ctx.axisRefresh}
    hideUncertainDefault={ctx.hideUncertainDefault} axisCutoffDefault={ctx.axisCutoffDefault} /> });
```

- [ ] **Step 4: Register `synthesis`** at the top level of `20_synthesis.jsx` (after `SynthesisPane`; leave `RightPane` in place for now — Task 3 removes it):

```jsx
registerPaneSection({ id: "synthesis", label: "Synthesis", paneId: "theory",
  render: (ctx) => <SynthesisPane onOpenCitation={ctx.onOpenCitation} onSaveHighlight={ctx.onSaveHighlight}
    pendingSummarize={ctx.pendingSummarize} /> });
```

- [ ] **Step 5: Register `details`** at the top level of `25_detail.jsx` (after `DetailContent`); the closure shows the no-selection hint so the always-mounted methods section is graceful:

```jsx
registerPaneSection({ id: "details", label: "Details", paneId: "methods",
  render: (ctx) => ctx.selectedPaper != null
    ? <DetailContent paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper}
        onFilterToTag={ctx.onFilterToTag} onTagsChanged={ctx.onTagsChanged} />
    : <div className="axis-hint">Select a paper to see its details.</div> });
```

- [ ] **Step 6: Rebuild + gate.** `python tools/build_frontend.py && node --check callosum-app.html && grep -c "registerPaneSection({ id:" callosum-app.html` → 0 errors; 4 registrations present. (Sections register but App doesn't render the accordion yet — the app still looks unchanged because Sidebar/RightPane are still wired. That's expected.)
- [ ] **Step 7: Commit** `feat(panes): register axes/synthesis/tags/details sections + TagsPanel empty-state`.

---

## Task 3: Wire App to the accordions (the switch); retire the wrappers + inc-57 split

**Files:** Modify `40_app.jsx` (state + ctx + render), `10_pdf_layer.jsx` (`Sidebar` → header + theory accordion), `20_synthesis.jsx` (remove `RightPane`).

**Interfaces:**
- Consumes: `PaneAccordion` (Task 1), the four registered sections (Task 2).
- Produces: App renders `<Sidebar .../>` (header + `<PaneAccordion paneId="theory"/>`) on the left and `<div className="pane pane-detail"><PaneAccordion paneId="methods"/></div>` on the right; `callosum.theoryOpen`/`callosum.methodsOpen` persisted.

- [ ] **Step 1: Add open-section state** in `40_app.jsx` near the layout state (after line 82):

```jsx
  const [theoryOpen, setTheoryOpen] = useState(() => _loadLayout("callosum.theoryOpen", "axes"));
  const [methodsOpen, setMethodsOpen] = useState(() => _loadLayout("callosum.methodsOpen", "details"));
  useEffect(() => { _saveLayout("callosum.theoryOpen", theoryOpen); }, [theoryOpen]);
  useEffect(() => { _saveLayout("callosum.methodsOpen", methodsOpen); }, [methodsOpen]);
```

- [ ] **Step 2: Summarize opens the SYNTHESIS section.** In `summarizePaperIds` and `bulkSummarizePapers` (40_app.jsx ~235-254), replace `setRightOpen(true)` with `setLeftOpen(true); setTheoryOpen("synthesis");` (synthesis now lives left). Verify both call sites.

- [ ] **Step 3: Assemble `ctx` + render the accordions.** In App's `return`, replace the `<Sidebar … />` call with the same `<Sidebar>` carrying the new props, and replace `<RightPane … />` with the methods accordion. First build `ctx` just before the `return` (after `cols`):

```jsx
  const paneCtx = {
    conn, selectedPaper: selected, onSelectPaper: setSelected, onOpenPaper: openPdf,
    onOpenCitation: openCitation, onSaveHighlight: saveCitationHighlight,
    onFilterToTag: filterToTag, onFilterToAxis: filterToAxis, onEnterFocus: enterFocus,
    onOpenMyPubsDashboard: openMyPubsDashboard, onTagsChanged: () => setTagRefresh(n => n + 1),
    pendingSummarize, axisRefresh, tagRefresh, hideUncertainDefault, axisCutoffDefault,
  };
```
Left (replace the existing `<Sidebar .../>`):
```jsx
        <Sidebar conn={conn} onOpenSettings={() => setSettingsOpen(true)} onOpenHelp={() => setHelpOpen(true)}
          ctx={paneCtx} theoryOpen={theoryOpen} onTheoryOpen={setTheoryOpen} />
```
Right (replace the `rightOpen ? <RightPane .../> : <div className="pane-collapsed" />`):
```jsx
      {rightOpen && !readingMode
        ? <div className="pane pane-detail"><PaneAccordion paneId="methods" ctx={paneCtx} openId={methodsOpen} onOpen={setMethodsOpen} /></div>
        : <div className="pane-collapsed" />}
```

- [ ] **Step 4: Rewrite `Sidebar`** (`10_pdf_layer.jsx`) to the brand/⚙/❓ header + the theory accordion (drop the direct `AxesPanel`/`TagsPanel` children):

```jsx
function Sidebar({ conn, onOpenSettings, onOpenHelp, ctx, theoryOpen, onTheoryOpen }) {
  return (
    <div className="pane pane-sidebar">
      <div className="pane-head">
        <button className="icon-help" title="Help & tips" onClick={onOpenHelp}>?</button>
        <button className="icon-gear" title="Settings" onClick={onOpenSettings}>⚙</button>
        <div className="brand">
          <div className={"brand-logo" + (conn.state === "ok" ? " connected" : "")} role="img" aria-label="Callosum"
            title={conn.state === "ok" ? ("Connected" + (conn.version ? " (" + conn.version + ")" : "")) : conn.state === "bad" ? "Disconnected" : "Connecting..."} />
          <h1>Callosum</h1>
        </div>
      </div>
      <PaneAccordion paneId="theory" ctx={ctx} openId={theoryOpen} onOpen={onTheoryOpen} />
    </div>
  );
}
```

- [ ] **Step 5: Remove `RightPane`** from `20_synthesis.jsx` (the whole `function RightPane({…}) {…}` block, 339-363) — it's superseded by the methods accordion. Keep `SynthesisPane` + the `synthesis` registration. (The `_beginDrag`/`_clampW` helpers stay in 40_app.jsx for the outer dividers.)

- [ ] **Step 6: Rebuild + gate.** `python tools/build_frontend.py && node --check callosum-app.html` → 0 errors. `grep -c "RightPane" callosum-app.html` → 0 (removed).
- [ ] **Step 7: Headed verify (seeded `:8097`).** Drive with `qa_server` + Playwright (free): confirm the left pane shows AXES/SYNTHESIS/TAGS headers, one body open; clicking SYNTHESIS collapses AXES and shows the query box; the right pane shows DETAILS (empty-state hint with nothing selected; the editable Details once a paper is selected); the outer panel resize/collapse + reading mode + center tabs still work; reload preserves the open sections. Screenshot. (Driver: `.local/visual/verify_accordion.py`.)
- [ ] **Step 8: pytest + ruff.** `pytest -q && ruff check .` → green/clean (frontend-only; the assembly + route-surface tests must still pass).
- [ ] **Step 9: Commit** `feat(panes): switch App to theory/methods accordions; retire Sidebar children + inc-57 RightPane split`.

---

## Task 4: DESIGN.md additions

**Files:** Modify `.claude/DESIGN.md`.

- [ ] **Step 1: Add a "Pane architecture (THEORY/METHODS)" section** documenting: the **placement rubric** (THEORY = knowing the literature: axes/synthesis/tags; METHODS = evaluating how a paper was studied: details now, checks later — *place a tool by the user's cognitive task, not its implementation; "AI-powered" is orthogonal*); the **accordion + module-registry** pattern (sections are data via `registerPaneSection`; additive; someday user-supplied); the **AI-usage principle** ("AI makes verification cheap, never substitutes for it — where did the judgment go? must land on a checkable computation or the human"); a **forward-reference** to the FACT-vs-CANDIDATE output contract (the later findings track); and **accessibility** (icon+label not color alone; highlight over blink; `prefers-reduced-motion`). Note the visible labels are "soft" for now (section headers only); `paneId` is the internal architecture.
- [ ] **Step 2: Commit** `docs(design): pane architecture — THEORY/METHODS placement rubric + accordion/registry + AI-usage principle`.

---

## Task 5: QA route + surface map (rule #10)

**Files:** Modify `.claude/qa-routes/route_00_smoke_readonly.md`; regenerate `tools/qa/surface-map.json` (gitignored).

- [ ] **Step 1: Update `route_00`** steps 2/3/4/5: the left pane is now an accordion (AXES/SYNTHESIS/TAGS — one open at a time, switching persists); SYNTHESIS moved from the right pane into the left accordion; the right pane is the DETAILS accordion (empty-state with nothing selected). Add an assertion that switching THEORY sections persists across reload, and that an in-progress synthesis survives a section switch. Keep the qa-coverage block's api/fe tokens valid (the FE chunks `05_panes.jsx`, `10_pdf_layer.jsx`, `20_synthesis.jsx`, `40_app.jsx` are covered; add `05_panes.jsx`).
- [ ] **Step 2: Regenerate + check the surface map.** `python tools/qa/build_surface_map.py extract && python tools/qa/build_surface_map.py check` → API still 88/88 (no API change); FE count changes (new accordion buttons) but FE is a checklist, not a gate → `check` still exits 0.
- [ ] **Step 3: Commit** `docs(qa): calibrate route_00 for the accordion panes + new 05_panes chunk`.

---

## Task 6: Verify + docs + finalize

**Files:** `.claude/docs/increment-notes/INCREMENT-<NN>-NOTES.md` (new), `.claude/changes.md`, `.claude/CLAUDE.md` (footer + decision-log row + number/test count), `RECOVERY-LOG.md`. Help corpus: check if any user-facing help text references the old pane layout (grep `help_content.md` for "Synthesis"/"right pane"/"sidebar"); update + move `HELP-DOCS-SYNCED` if so.

- [ ] **Step 1: Full gate.** `pytest -q && ruff format --check . && ruff check .` → all green/clean.
- [ ] **Step 2: Full headed Playwright pass** (`verify_accordion.py` on `:8097`): the additivity proof — temporarily `registerPaneSection({id:"_dummy",label:"Dummy",paneId:"theory",render:()=>…})` in a scratch spot, rebuild, confirm it appears in the THEORY accordion with **zero edits to PaneAccordion**, then remove it. Plus the full behavior pass (switch/persist/synthesis-survives/outer-resize/tabs/reading-mode).
- [ ] **Step 3: Docs** — increment notes (Implemented / key technical detail [the registry + mount-but-hide + hoist/chunk-order] / manual verification script / pytest count), changes.md entry, CLAUDE.md footer + decision-log row + increment number bump; help corpus if needed.
- [ ] **Step 4: RECOVERY-LOG line; final commit** `docs(panes): increment notes + changelog + CLAUDE.md (inc <NN>)`; push on the user's OK.

---

## Self-review
- **Spec coverage:** §2 accordion/sections → T1+T2+T3; TAGS own section + empty-state → T2; soft labels (paneId internal) → T1 (PaneAccordion has no umbrella header) + T3; registry/additivity → T1 + T6 dummy proof; mount-but-hide → T1 (`.acc-body` always rendered); persistence keys → T3; retire inc-57 split → T3 (RightPane removed, detailH dropped); preserve outer dividers/reading/tabs → untouched in T3; DESIGN.md → T4; QA route → T5; Principles non-trigger / frontend-only → Global Constraints. All covered.
- **Placeholder scan:** `<NN>` is the increment number (resolve at execution: current footer is inc 120 → this is **inc 121**). No other placeholders; code blocks are concrete.
- **Type consistency:** `registerPaneSection({id,label,paneId,render})` + `PaneAccordion({paneId,ctx,openId,onOpen})` + `paneCtx` keys are identical across T1/T2/T3; `theoryOpen`/`methodsOpen`/`callosum.theoryOpen`/`callosum.methodsOpen` consistent T3↔spec.
- **No JS unit-test harness exists** (the suite is Python/API) → verification is `node --check` + `test_frontend_assembly.py` + headed Playwright, not fabricated JSX pytest. Honest + matches the project's inc-101/104 frontend-refactor precedent.
