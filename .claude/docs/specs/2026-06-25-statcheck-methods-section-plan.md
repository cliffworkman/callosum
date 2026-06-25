# Statistics-check METHODS section (inc 122) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate statcheck out of Settings and the Details pane into a dedicated **METHODS accordion section**
("Statistics check"), the first real METHODS module on the inc-121 pane registry.

**Architecture:** A new frontend chunk `06_methods_statcheck.jsx` self-registers a METHODS-pane section
(`order: 20`, after DETAILS) holding both statcheck surfaces — the library-wide batch (moved verbatim from
`StatcheckSettings`) and the per-paper check (moved from `StatcheckRow`). The section reads the inc-121
`paneCtx`; the App gains two ctx callbacks (`onShowStatcheckFlagged`, `onStatcheckRan`) and its header-chip
refresh moves from "on Settings close" to "on mount + on batch completion." Statcheck is deleted from both old
homes. No backend change, no migration, no new endpoint.

**Tech Stack:** React (JSX chunks via global `React`/`useState`/`useEffect`), esbuild build
(`python tools/build_frontend.py`), pytest, ruff.

## Global Constraints

- **Frontend-only.** No backend file, no endpoint, no migration changes. Every statcheck endpoint already exists
  (`GET /papers/{id}/statcheck`, `POST /methods/statcheck/run`, `GET /methods/statcheck/run/{job_id}`,
  `GET /methods/statcheck/summary`).
- **600-line cap (rule #1).** `25_detail.jsx` is currently **>600** (a pre-existing violation); removing
  `StatcheckRow` must bring it **under 600**. Re-measure with `wc -l` and confirm.
- **Read `.claude/DESIGN.md` before any CSS change (rule #8).** Reuse existing element classes (`.eyebrow`,
  `.settings-sub`, `.settings-actions`, `.settings-note`, `.detail-statcheck`, `.statcheck-*`, `.btn`,
  `.btn-primary`, `.btn-link`, `.tag-suggest-empty`, `.cite-status verified|flagged`); add a new rule only if the
  visual check shows cramping, and only with existing tokens (no raw hex).
- **Honesty posture preserved verbatim (rule #9, non-triggering).** All statcheck caveat/counts copy moves
  **unchanged**: counts never a composite score; "a prompt to look, not a verdict"; non-accusatory; inline-APA
  caveat ("a clean result isn't a clean bill"). Coordinate honesty: per-test rows route to the page at
  `precision: "region"` (page-open, never a fake exact highlight).
- **Egress (invariant #3).** Statcheck is local/no-LLM — no `CALLOSUM_ALLOW_DATA_EGRESS` involvement; the section
  must make **no** genai-host request.
- **Rebuild after every `app/frontend/` edit:** `python tools/build_frontend.py` (a `callosum-app.html`-in-sync
  pytest assertion fails otherwise).
- **Verification reality:** the repo has **no JS unit-test runner**. Per task, the gate is: esbuild build
  succeeds (it parses+transpiles the JSX), `pytest -q` green (assembly + html-in-sync + route-surface), `ruff`
  clean (Python tasks only). A **headed Playwright** manual check is the final UI gate (Task 6).
- This is **increment 122**. Commit after each task; push only at session end on the user's OK.

---

### Task 1: Create the METHODS "Statistics check" section chunk + App wiring

Land the new section fully functional in one task (its two ctx callbacks must exist for it to work end-to-end),
so the moment it renders, the batch→chip-refresh loop and the show-flagged jump both work. The old Settings/
Details statcheck still exist after this task (removed in Tasks 2–3) — a brief, harmless duplicate.

**Files:**
- Create: `app/frontend/js/06_methods_statcheck.jsx`
- Modify: `app/frontend/js/40_app.jsx` (paneCtx + the chip-refresh effect)

**Interfaces:**
- Consumes from `05_panes.jsx`: `registerPaneSection({id,label,paneId,order,render})`; the `paneCtx` shape from
  `40_app.jsx` (`selectedPaper`, `onOpenPaper`, plus the two new callbacks below). Globals: `useState`,
  `useEffect` (React), `api`/`apiPost` (`00_lib.jsx`), `ProgressBar` (`10_pdf_layer.jsx`, a hoisted top-level
  `function` → resolvable from a render-time closure in an earlier chunk).
- Produces: a registered METHODS section `id: "statcheck"`. Requires `paneCtx.onShowStatcheckFlagged: () => void`
  and `paneCtx.onStatcheckRan: () => void`.

- [ ] **Step 1: Create `06_methods_statcheck.jsx`** with the library-wide batch (verbatim from
  `StatcheckSettings`), the per-paper check (a self-fetching adaptation of `StatcheckRow`), the section wrapper,
  and the registration:

```jsx
// inc 122: the "Statistics check" METHODS section — the first real module on the inc-121 pane registry.
// Consolidates statcheck's two surfaces, moved out of Settings (StatcheckSettings) and the Details pane
// (StatcheckRow): a library-wide batch run + a per-paper check. Local, deterministic, NO AI (no egress).
// Counts are a list to review, never a rank or verdict (Principles #2/#7 + the no-accusation A-A boundary).

// Library-wide batch (moved verbatim from StatcheckSettings, inc 97). On completion it calls ctx.onStatcheckRan()
// so the App refreshes the header "N flagged" chip; ctx.onShowStatcheckFlagged jumps to the library filter.
function StatcheckLibrary({ onShowFlagged, onRan }) {
  const [run, setRun] = useState({ status: "idle" });  // idle | running | done | error
  const start = async () => {
    setRun({ status: "running" });
    const poll = (jobId) => api(`/methods/statcheck/run/${jobId}`).then(r => {
      if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setRun({ status: "done", summary: d.summary }); if (onRan) onRan(); }
      else if (d.status === "error") setRun({ status: "error", error: d.detail || "Check failed." });
      else setTimeout(() => poll(jobId), 1500);
    });
    const r = await apiPost("/methods/statcheck/run", {});
    if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  const s = run.summary;
  return (
    <div className="statcheck-lib">
      <div className="settings-sub">Recompute reported APA-style p-values across your whole library (statcheck) — local, no AI. It flags where a reported and recomputed p disagree; usually innocent (typos, rounding, one-tailed tests) — a list to review, not a verdict.</div>
      <div className="settings-actions">
        <button className="btn btn-primary" disabled={run.status === "running"} onClick={start}>
          {run.status === "running" ? "Checking…" : "Check all papers"}
        </button>
      </div>
      {run.status === "running" && <ProgressBar label="Recomputing statistics…" />}
      {run.status === "error" && <div className="settings-note settings-note-err">Check failed: {run.error}</div>}
      {run.status === "done" && s &&
        <div className="settings-note">
          {s.checked} paper{s.checked === 1 ? "" : "s"} with statistics checked · <b>{s.flagged}</b> with inconsistencies.
          {s.flagged > 0 && onShowFlagged && <> <button className="btn-link" onClick={onShowFlagged}>Show flagged papers</button></>}
        </div>}
    </div>
  );
}

// Per-paper check (moved from StatcheckRow in 25_detail.jsx, inc 95). The section gets only the paper id via ctx,
// so it self-fetches the paper's title + chunk_count (statcheck needs extracted text). Each row routes to its
// page at region precision (page-open, never a fake exact highlight — coordinate-honesty contract).
function StatcheckPaper({ paperId, onOpenPaper }) {
  const [meta, setMeta] = useState(null);          // { title, hasText } | null
  const [state, setState] = useState({ status: "idle" });  // idle | running | done | error
  useEffect(() => {
    setState({ status: "idle" }); setMeta(null);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => {
      if (!live || !r.ok) return;
      setMeta({ title: r.data.title, hasText: (r.data.chunk_count || 0) > 0 });
    });
    return () => { live = false; };
  }, [paperId]);
  const run = async () => {
    setState({ status: "running" });
    const r = await api(`/papers/${paperId}/statcheck`);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  const open = (page) => { if (onOpenPaper && page != null) onOpenPaper({ id: paperId, title: meta ? meta.title : "" }, { page, precision: "region" }); };
  const label = (c) => c === "consistent" ? "consistent" : c === "decision-error" ? "decision error" : "inconsistent";
  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to check its statistical reporting.</div>;
  const hasText = meta ? meta.hasText : false;
  const d = state.data;
  return (
    <div className="detail-statcheck">
      <span className="detail-cite-label">{meta ? meta.title : "This paper"}</span>
      {!meta
        ? <span className="tag-suggest-empty">loading…</span>
        : !hasText
          ? <span className="tag-suggest-empty">Process a PDF first — statcheck reads the paper's extracted text.</span>
          : state.status === "idle"
            ? <button className="btn-link" title="Recompute reported p-values from this paper's text — local, no AI" onClick={run}>Check statistics</button>
            : null}
      {state.status === "running" && <span className="tag-suggest-empty">checking…</span>}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d && (d.checked === 0
        ? <div className="tag-suggest-empty">No APA-format statistics found in the extracted text.</div>
        : <div className="statcheck-result">
            <div className="statcheck-summary">{d.checked} checked · {d.inconsistent} inconsistent · {d.decision_errors} decision error{d.decision_errors === 1 ? "" : "s"}</div>
            <div className="statcheck-list">
              {d.results.map((r, i) => (
                <button key={i} className="statcheck-item" title={r.page != null ? "Open page " + r.page : ""} onClick={() => open(r.page)}>
                  <span className="statcheck-raw">{r.raw}</span>
                  <span className="statcheck-computed">computed p = {r.computed_p}</span>
                  <span className={"cite-status " + (r.consistency === "consistent" ? "verified" : "flagged")}>{label(r.consistency)}</span>
                </button>
              ))}
            </div>
            <div className="statcheck-caveat">
              statcheck reads only inline APA-style tests and recomputes each p — it can't see tables, Bayesian stats, or CIs, so a clean result isn't a clean bill. Inconsistencies are common and usually innocent (typos, rounding, one-tailed tests) — a prompt to look, not a verdict.
            </div>
          </div>)}
    </div>
  );
}

function StatcheckSection({ ctx }) {
  return (
    <div className="statcheck-section">
      <p className="eyebrow">Whole library</p>
      <StatcheckLibrary onShowFlagged={ctx.onShowStatcheckFlagged} onRan={ctx.onStatcheckRan} />
      <p className="eyebrow">This paper</p>
      <StatcheckPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} />
    </div>
  );
}

registerPaneSection({
  id: "statcheck", label: "Statistics check", paneId: "methods", order: 20,
  render: (ctx) => <StatcheckSection ctx={ctx} />,
});
```

- [ ] **Step 2: Add the chip-refresh callback + the two ctx props in `40_app.jsx`.** First add a `useCallback`
  near the existing statcheck handlers (after `clearSignalFilter`, ~line 395):

```jsx
  // inc-122: refresh the header "N flagged" chip from the persisted statcheck summary (cache-only count). Called
  // on mount and by the METHODS "Statistics check" section after a batch run (ctx.onStatcheckRan).
  const refreshStatcheckChip = useCallback(() => {
    api("/methods/statcheck/summary").then(r => { if (r.ok) setStatcheckFlagged(r.data.flagged || 0); });
  }, []);
```

  Then add both callbacks to `paneCtx` (the object at ~line 480) — append to the last property line:

```jsx
    pendingSummarize, axisRefresh, tagRefresh, hideUncertainDefault, axisCutoffDefault,
    onShowStatcheckFlagged: showStatcheckFlagged, onStatcheckRan: refreshStatcheckChip,
```

- [ ] **Step 3: Rewire the chip-refresh effect in `40_app.jsx`** (lines 457–462) from Settings-close-keyed to
  mount-only (the batch left Settings):

```jsx
  // inc-100/122: the statcheck "N flagged" header chip — fetched on mount; refreshed after a batch run via the
  // METHODS "Statistics check" section's ctx.onStatcheckRan (the batch no longer lives in Settings).
  useEffect(() => { refreshStatcheckChip(); }, [refreshStatcheckChip]);
```

- [ ] **Step 4: Rebuild the frontend.**

Run: `python tools/build_frontend.py`
Expected: completes without error (esbuild parses+transpiles the new chunk); `callosum-app.html` rewritten.

- [ ] **Step 5: Run the tests.**

Run: `pytest -q`
Expected: PASS — including `tests/test_frontend_assembly.py` (the new `06_methods_statcheck.jsx` is auto-globbed
into `assemble_jsx()`, and `callosum-app.html` is in sync because Step 4 rebuilt it).

- [ ] **Step 6: Commit.**

```bash
git add app/frontend/js/06_methods_statcheck.jsx app/frontend/js/40_app.jsx callosum-app.html
git commit -m "feat(methods): add Statistics check METHODS section (inc 122 t1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Remove statcheck from Settings

**Files:**
- Modify: `app/frontend/js/35_settings.jsx` (delete `StatcheckSettings`; drop the `onShowStatcheckFlagged` prop +
  its render in `SettingsModal`)
- Modify: `app/frontend/js/40_app.jsx` (drop `onShowStatcheckFlagged={showStatcheckFlagged}` from the
  `<SettingsModal …>` call site)

**Interfaces:**
- Consumes: nothing new. `showStatcheckFlagged` (App) stays defined — it's still used via `paneCtx` (Task 1).
- Produces: a `SettingsModal` with no statcheck surface and no `onShowStatcheckFlagged` prop.

- [ ] **Step 1: Delete `StatcheckSettings`** — the whole block in `35_settings.jsx` lines 84–120 (the
  `// Statistics check (inc 97) …` comment through the closing `}` of `function StatcheckSettings`).

- [ ] **Step 2: Drop the prop + render in `SettingsModal`.** In the `function SettingsModal({ … })` signature
  remove `onShowStatcheckFlagged,`; and delete the render line:

```jsx
        <StatcheckSettings onShowFlagged={onShowStatcheckFlagged} />
```

  (Leave `<MyPubsSettings … />` and the `axis-modal-note` immediately around it intact.)

- [ ] **Step 3: Drop the prop at the call site in `40_app.jsx`** (the `{settingsOpen && <SettingsModal … />}`
  line, ~544): remove `onShowStatcheckFlagged={showStatcheckFlagged}` from the attribute list. Leave every other
  prop unchanged.

- [ ] **Step 4: Rebuild + test.**

Run: `python tools/build_frontend.py && pytest -q`
Expected: build OK; pytest PASS (no `StatcheckSettings` reference remains → esbuild resolves cleanly).

- [ ] **Step 5: Commit.**

```bash
git add app/frontend/js/35_settings.jsx app/frontend/js/40_app.jsx callosum-app.html
git commit -m "refactor(settings): remove statcheck from Settings (moved to METHODS) (inc 122 t2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Remove statcheck from the Details pane (relieves the 600-line cap)

**Files:**
- Modify: `app/frontend/js/25_detail.jsx` (delete `StatcheckRow`; delete its render in `DetailContent`)

**Interfaces:**
- Consumes: nothing. `StatcheckRow` has no other caller (verify with grep before deleting).
- Produces: `25_detail.jsx` under 600 lines; `DetailContent` with no statcheck row.

- [ ] **Step 1: Confirm `StatcheckRow` has exactly one render site.**

Run: `grep -rn "StatcheckRow" app/frontend/js/`
Expected: only the definition (`25_detail.jsx:393`) and the render (`25_detail.jsx:612`). (The new section uses
`StatcheckPaper`, a different name — no collision.)

- [ ] **Step 2: Delete the `StatcheckRow` function** — `25_detail.jsx` lines 390–432 (the
  `// statcheck (inc 95): …` comment through the closing `}` of `function StatcheckRow`).

- [ ] **Step 3: Delete its render in `DetailContent`** — line 612:

```jsx
      <StatcheckRow paperId={p.id} paperTitle={p.title} hasText={(p.chunk_count || 0) > 0} onOpenPaper={onOpenPaper} />
```

  (Leave `<CiteRow paperId={p.id} />` immediately below it intact.)

- [ ] **Step 4: Re-measure the file — must be under 600 (rule #1).**

Run: `wc -l app/frontend/js/25_detail.jsx`
Expected: a count **< 600** (≈ 580). If still ≥ 600, STOP and report (an additional split is then needed — out
of this plan's scope).

- [ ] **Step 5: Rebuild + test.**

Run: `python tools/build_frontend.py && pytest -q`
Expected: build OK; pytest PASS.

- [ ] **Step 6: Commit.**

```bash
git add app/frontend/js/25_detail.jsx callosum-app.html
git commit -m "refactor(detail): remove statcheck row (moved to METHODS); 25_detail.jsx < 600 (inc 122 t3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Recalibrate the QA routes + regenerate the surface map (rule #10)

**Files:**
- Modify: `.claude/qa-routes/route_33_methods_statcheck.md` (point `fe:` at the new chunk; steps reach statcheck
  via the METHODS accordion)
- Modify: `.claude/qa-routes/route_30_detail_pane.md` (statcheck left the Detail pane)
- Verify (modify only if it asserts statcheck): `.claude/qa-routes/route_32_viewer_annotations.md`

**Interfaces:**
- Consumes: the `qa-coverage` block contract (`<!-- qa-coverage api: … fe: … -->`) from `_TEMPLATE.md`.
- Produces: a coverage set where `GET /papers/{paper_id}/statcheck` + `/methods/statcheck*` remain declared
  exactly once (in route_33) → the API hard-gate stays green.

- [ ] **Step 1: Update `route_33_methods_statcheck.md`.** Change the `fe:` line in the coverage block from
  `fe: 25_detail.jsx` to `fe: 06_methods_statcheck.jsx`. In **Steps**, change step 1 from "Open a paper detail
  pane and run per-paper statcheck" to navigate via the **METHODS pane → "Statistics check" section** (the
  per-paper check appears there once a paper is selected; the library batch is in the same section). Keep the
  `api:` line (both endpoint families still live here) and all honesty assertions.

- [ ] **Step 2: Update `route_30_detail_pane.md`.** In the coverage block's `api:` line, **remove**
  `GET /papers/{paper_id}/statcheck` (now covered solely by route_33). Remove **Step 8 (Statcheck)** and the
  statcheck mentions in the route title (line 6), Goal (line 11), the egress/signal assertions (lines 21, 23),
  and Pass criteria (lines 59–60). Renumber any steps after the deleted one.

- [ ] **Step 3: Check `route_32_viewer_annotations.md` for a real statcheck reference.**

Run: `grep -ni "statcheck\|statistics check\|statistical reporting" .claude/qa-routes/route_32_viewer_annotations.md`
Expected: if it's an incidental/false-positive match, leave the file unchanged; if it asserts a statcheck step in
the Detail/viewer surface, remove it (statcheck is no longer there). Note the finding either way.

- [ ] **Step 4: Regenerate the surface map + run the coverage check (report-only).**

Run: `python tools/qa/build_surface_map.py extract && python tools/qa/build_surface_map.py check`
Expected: `extract` rewrites the gitignored `tools/qa/surface-map.json`; `check` reports **0 uncovered API**
surfaces (the statcheck endpoints are still declared in route_33). The FE checklist may list the new
`06_methods_statcheck.jsx` elements — note them; FE is a checklist, not a hard gate. If an **API** surface is
newly uncovered, STOP and fix the route coverage line.

- [ ] **Step 5: Commit.**

```bash
git add .claude/qa-routes/route_33_methods_statcheck.md .claude/qa-routes/route_30_detail_pane.md
git commit -m "test(qa): recalibrate statcheck routes for the METHODS section (inc 122 t4)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Docs — help corpus, DESIGN.md, changes.md, increment notes, RECOVERY-LOG, CLAUDE.md footer

**Files:**
- Modify: `app/backend/help/help_content.md` (statcheck section → new location wording)
- Modify: `.claude/DESIGN.md` (§5 — note statcheck as the first METHODS module)
- Modify: `.claude/changes.md` (new top entry; move the `HELP-DOCS-SYNCED` marker to it)
- Create: `.claude/docs/increment-notes/INCREMENT-122-NOTES.md`
- Modify: `RECOVERY-LOG.md` (one-line entry)
- Modify: `.claude/CLAUDE.md` (footer increment note → inc 122; bump "currently at increment 122")

**Interfaces:**
- Consumes: the `HELP-DOCS-SYNCED` marker convention (Change tracking) + the increment-notes shape
  (Implemented / Key technical detail / Manual verification script / Pytest).
- Produces: docs that name the new statcheck location.

- [ ] **Step 1: Help corpus.** In `app/backend/help/help_content.md`, find the "Checking statistics (statcheck)"
  section (and the library-wide note added inc 97/100). Update the wording so it directs the user to the
  **METHODS pane → "Statistics check"** section for both the per-paper check and the "Check all papers" batch
  (previously "the Details pane" / "Settings → Statistics check"). Keep the honesty caveat text.

- [ ] **Step 2: DESIGN.md §5.** Add a short note under the THEORY/METHODS §5 that **statcheck is the first real
  METHODS module** (`06_methods_statcheck.jsx`, section `order: 20`, after DETAILS), reusing the `.settings-*` /
  `.detail-statcheck` / `.statcheck-*` recipes; no new tokens introduced.

- [ ] **Step 3: changes.md entry** at the top (newest-first), with the `HELP-DOCS-SYNCED` marker moved here:

```markdown
<!-- HELP-DOCS-SYNCED: inc 122 (statcheck → METHODS "Statistics check" section) -->
## 2026-06-25 — inc 122: statcheck relocated to a METHODS "Statistics check" section
- **Files:** `app/frontend/js/06_methods_statcheck.jsx` (new), `40_app.jsx`, `35_settings.jsx`, `25_detail.jsx`,
  QA routes 33/30, help corpus, DESIGN.md
- **What:** Moved both statcheck surfaces (library-wide batch from Settings + per-paper check from Details) into a
  dedicated METHODS accordion section; rewired the header "N flagged" chip refresh to mount + `ctx.onStatcheckRan`.
- **Why:** First real METHODS module on the inc-121 registry; co-locates the per-paper + library statcheck;
  relieves the `25_detail.jsx` >600 rule-#1 violation.
- **Revert:** restore the prior `StatcheckSettings`/`StatcheckRow` blocks + the Settings-close-keyed chip effect.
```

- [ ] **Step 4: Increment notes.** Create `.claude/docs/increment-notes/INCREMENT-122-NOTES.md` with:
  **Implemented** (the new chunk + section; removals from Settings/Details; chip rewire; QA recalibration),
  **Key technical detail** (the section self-fetches the selected paper's title+chunk_count because `paneCtx`
  carries only the id; the chip refresh moved from `settingsOpen` to mount + `onStatcheckRan`; honesty posture
  preserved verbatim → Principles non-triggering), **Manual verification script** (the Task 6 steps),
  **Pytest** (the green count from Task 6).

- [ ] **Step 5: RECOVERY-LOG.md** — prepend one line:
  `- inc 122 — statcheck → METHODS "Statistics check" section (per-paper + library-wide); removed from Settings & Details; chip refresh rewired; 25_detail.jsx back under 600. Frontend-only.`

- [ ] **Step 6: CLAUDE.md footer.** Add an inc-122 block at the top of the footer narrative (above inc 121) and
  update the header line "currently at **Increment 12x**" → 122. Keep it concise (the pattern of the recent
  footer entries).

- [ ] **Step 7: Commit.**

```bash
git add app/backend/help/help_content.md .claude/DESIGN.md .claude/changes.md \
  .claude/docs/increment-notes/INCREMENT-122-NOTES.md RECOVERY-LOG.md .claude/CLAUDE.md
git commit -m "docs(methods): statcheck relocation — help/DESIGN/changes/notes/CLAUDE (inc 122 t5)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Final verification (headed Playwright) + ruff

**Files:** none (verification only).

- [ ] **Step 1: `ruff` clean** (the only Python touched is none, but run it to be safe):

Run: `ruff check . && ruff format --check .`
Expected: PASS (no Python changed; this guards against accidental edits).

- [ ] **Step 2: Full pytest.**

Run: `pytest -q`
Expected: PASS. Record the count for the increment notes (Task 5 Step 4).

- [ ] **Step 3: Headed Playwright manual script** against the running app (`:8097`, the validation DB):
  1. Open the app → the **METHODS** pane (right) accordion shows **DETAILS** and **STATISTICS CHECK**.
  2. Open **Statistics check** → "Whole library": click **Check all papers** → it polls, then shows
     "N papers … · **M** with inconsistencies"; if M>0, **Show flagged papers** narrows the library to the
     statcheck-inconsistent filter (banner shows). The library header **"⚠ N flagged" chip** reflects M.
  3. Select a paper → the section's "This paper" sub-section shows the paper title; **Check statistics** →
     per-test rows (verbatim stat + `computed p =` + green/amber pill) + the non-accusatory caveat; clicking a
     row with a page **opens the page** (region precision, no fake exact rect).
  4. Open **Settings** → there is **no** "Statistics check" block.
  5. Open a paper's **Details** (DETAILS section) → there is **no** statcheck row (bibliographic only).
  6. DevTools network: **zero** requests to any `generativelanguage`/genai host throughout; **0** console/page
     errors.

  Capture screenshots; if any step fails, fix (return to the relevant task) before declaring done.

- [ ] **Step 4: Update the increment notes' Pytest line** with the count from Step 2 and amend the docs commit if
  needed:

```bash
git add .claude/docs/increment-notes/INCREMENT-122-NOTES.md && git commit -m "docs: inc 122 notes — pytest count + verification

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage** (against `2026-06-25-statcheck-methods-section-design.md`):
- §2 new section chunk + both surfaces → Task 1. §3 removals (Settings, Details) → Tasks 2, 3. §4 App wiring
  (paneCtx callbacks + chip rewire) → Task 1 Steps 2–3. §5 backend none + Principles non-trigger + rule-#10 route
  recalibration → Task 4. §6 files (incl. help, DESIGN) → Tasks 1–5. §7 verification (pytest, ruff, rebuild,
  headed Playwright) → Tasks 1–6. §8 out-of-scope honored (no compute change, no other modules). ✔ All covered.

**Placeholder scan:** every code step shows complete code; commands have expected output; no TBD/TODO. ✔

**Type/name consistency:** `StatcheckLibrary`/`StatcheckPaper`/`StatcheckSection` (new, Task 1) vs the deleted
`StatcheckSettings`/`StatcheckRow` (Tasks 2/3) — no name collision (verified by Task 3 Step 1 grep). `paneCtx`
adds `onShowStatcheckFlagged` + `onStatcheckRan`, consumed by `StatcheckSection` with the same names.
`refreshStatcheckChip` defined once (Task 1 Step 2), used in the effect (Task 1 Step 3) and `paneCtx`. ✔
