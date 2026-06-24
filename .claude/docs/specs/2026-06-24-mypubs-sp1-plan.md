# My Publications SP1 — Dashboard Restructure & Publication Cards — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the My Publications dashboard tab into author-priority order — Overview (collapsible metrics + flip-chart) → Research summary → Publications (library-style cards) → OpenAlex footer card — reusing existing components and adding no new endpoints.

**Architecture:** Backend adds two pre-cached OpenAlex fields (additive). Frontend extracts a shared `PaperCard` from the monolithic `PaperList`, builds a new axis-scoped publications list around it, restructures `31_mypubs_dashboard.jsx`, and moves the missing-works queue into a modal. Spec: `.claude/docs/specs/2026-06-24-mypubs-sp1-restructure-design.md`.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy Core (backend); React 18 JSX chunks under `app/frontend/js/`, esbuild-precompiled via `python tools/build_frontend.py` (frontend); pytest + ruff + headed Playwright (`.local/visual/`) for verification.

## Global Constraints
- 600-line hard cap on every file under `app/` and `integrations/`. Current: `10_pdf_layer.jsx` 492, `31_mypubs_dashboard.jsx` 281, `clustering/my_publications.py` 496, `routers/my_publications.py` 414.
- Parameterized SQL only; secrets in env; validate untrusted input at the boundary. No new egress, no new endpoint, no migration in SP1.
- Rule #8: read `.claude/DESIGN.md` before any CSS; conform to tokens/recipes (`--accent` indigo, `--verified` green, `--flag` amber, `--danger` red; `.btn-*`; `--radius-sm`). New "add" controls are green.
- OpenAlex figures are shown **verbatim + attributed**, never recomputed into a callosum composite (invariant from inc 81).
- After ANY `app/frontend/` edit: `python tools/build_frontend.py`, then verify in the headed browser against the live instance on **:8888**.
- `pytest` green + `ruff format` + `ruff check .` clean before each commit. Commit locally; do not push (end-of-session push is a separate, user-aware step).

---

## Task 1: Backend — OpenAlex `openalex_extra` (2-yr mean citedness + affiliation)

**Files:**
- Modify: `integrations/openalex/author.py` (`ResolvedAuthor` dataclass ~line 28; `_author_from_obj` ~line 212)
- Modify: `app/backend/clustering/my_publications.py` (`build_dashboard`)
- Modify: `app/backend/api/routers/my_publications.py` (`DashboardResponse` + the dashboard handler)
- Test: `tests/test_my_publications.py` (existing) + `tests/test_openalex_author.py` if present (else add cases to the my-pubs test)

**Interfaces:**
- Produces: `ResolvedAuthor.two_year_mean_citedness: float = 0.0`, `ResolvedAuthor.affiliation: str | None = None`; dashboard JSON gains `openalex_extra: {two_year_mean_citedness: float, affiliation: str | None, openalex_author_id: str | None} | null` and `starred_count: int` (for #8).

- [ ] **Step 1: Write the failing test** — parse the two fields from a cached author object.

```python
# tests/test_my_publications.py (add)
from integrations.openalex.author import _author_from_obj

def test_author_from_obj_parses_openalex_extra():
    obj = {
        "id": "https://openalex.org/A5023888391",
        "display_name": "Jane Smith",
        "works_count": 79,
        "cited_by_count": 1605,
        "summary_stats": {"h_index": 23, "i10_index": 32, "2yr_mean_citedness": 4.125},
        "last_known_institutions": [{"display_name": "University of Pennsylvania"}],
        "counts_by_year": [],
    }
    a = _author_from_obj(obj, matched_by="orcid")
    assert a.two_year_mean_citedness == 4.125
    assert a.affiliation == "University of Pennsylvania"
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_my_publications.py::test_author_from_obj_parses_openalex_extra -v`
Expected: FAIL (`AttributeError: 'ResolvedAuthor' object has no attribute 'two_year_mean_citedness'`).

- [ ] **Step 3: Add the fields to `ResolvedAuthor`** (after `counts_by_year`, line ~40):

```python
    two_year_mean_citedness: float = 0.0  # OpenAlex summary_stats["2yr_mean_citedness"], shown verbatim
    affiliation: str | None = None        # last-known institution display name
```

- [ ] **Step 4: Populate them in `_author_from_obj`** (in the `return ResolvedAuthor(...)`, line ~230):

```python
        two_year_mean_citedness=float(stats.get("2yr_mean_citedness") or 0.0),
        affiliation=(
            (obj.get("last_known_institutions") or [{}])[0].get("display_name")
            if obj.get("last_known_institutions") else None
        ),
```

- [ ] **Step 5: Run the test, verify it passes**

Run: `pytest tests/test_my_publications.py::test_author_from_obj_parses_openalex_extra -v`
Expected: PASS.

- [ ] **Step 6: Surface `openalex_extra` in the dashboard.** In `clustering/my_publications.py::build_dashboard`, where the cached author is read, add to the returned dict:

```python
        "openalex_extra": {
            "two_year_mean_citedness": round(author.two_year_mean_citedness, 3),
            "affiliation": author.affiliation,
            "openalex_author_id": author.author_id,
        },
        "starred_count": len(profile.get("starred_paper_ids") or []),  # #8: hide the "⭐ only" toggle when 0
```
In `routers/my_publications.py`, add the Pydantic model + fields:

```python
class OpenAlexExtra(BaseModel):
    two_year_mean_citedness: float = 0.0
    affiliation: str | None = None
    openalex_author_id: str | None = None

class DashboardResponse(BaseModel):
    # ...existing fields...
    openalex_extra: OpenAlexExtra | None = None
    starred_count: int = 0
```
Map it in the handler that builds `DashboardResponse` from `build_dashboard(...)` (pass through `result.get("openalex_extra")`).

- [ ] **Step 7: Add a dashboard-shape test** asserting `openalex_extra` is present when resolved (reuse the existing dashboard test's fake author client; assert `body["openalex_extra"]["affiliation"]`).

- [ ] **Step 8: Run the my-pubs suite + ruff**

Run: `pytest tests/test_my_publications.py -q && ruff check app integrations tests`
Expected: PASS, clean.

- [ ] **Step 9: Commit**

```bash
git add integrations/openalex/author.py app/backend/clustering/my_publications.py app/backend/api/routers/my_publications.py tests/test_my_publications.py
git commit -m "feat(my-pubs): openalex_extra (2yr mean citedness + affiliation) in dashboard response"
```

---

## Task 2: Frontend — extract a shared `PaperCard` from `PaperList`

**Why:** the publications list (#13) needs the library card aesthetic + parity without duplicating markup. `PaperList` is a 40-prop monolith that is the whole library pane; only its per-paper card (lines 435–480) is reusable.

**Files:**
- Modify: `app/frontend/js/10_pdf_layer.jsx` (extract the card map body into `function PaperCard(...)`; `PaperList` renders `<PaperCard .../>`).

**Interfaces:**
- Produces: `function PaperCard({ paper, selecting, isSelected, onSelect, onOpen, checked, onToggleCheck, footExtra })` — `paper` is a list item; `selecting` shows the copy button + checkbox; `onOpen(paper)` on double-click; `footExtra` is optional JSX appended in `.paper-foot` (the library passes its focus/trash buttons here). Returns the `.paper` card.

- [ ] **Step 1: Create `PaperCard`** in `10_pdf_layer.jsx` (above `PaperList`), moving the markup from lines 435–480 verbatim and parameterizing it:

```jsx
function PaperCard({ paper: p, selecting, isSelected, onSelect, onOpen, checked, onToggleCheck, footExtra }) {
  const unresolved = needsMetadata(p);
  return (
    <div
      key={p.id}
      className={"paper" + (isSelected ? " sel" : "")}
      onClick={() => onSelect && onSelect(p.id)}
      onDoubleClick={() => onOpen && onOpen(p)}
      title="Double-click to open the PDF"
    >
      {selecting && <PaperCopyButton paperId={p.id} />}
      {selecting &&
        <input type="checkbox" className="paper-select" checked={!!checked}
          title="Select" onClick={e => e.stopPropagation()} onChange={() => onToggleCheck(p.id)} />}
      <p className="paper-title">{p.title || <span className="placeholder">Untitled</span>}</p>
      <div className="paper-meta">
        {unresolved
          ? <span className="placeholder">metadata not yet resolved</span>
          : <>
              {p.authors && p.authors.length > 0 && <span className="paper-authors">{fmtAuthors(p.authors)}</span>}
              {p.year && <span>· {p.year}</span>}
              {p.venue && <span className="paper-venue">· {p.venue}</span>}
            </>}
      </div>
      <div className="paper-foot">
        <span className={"tier " + tierClass(p.processing_tier)}>{tierLabel(p.processing_tier)}</span>
        {p.attachment_count > 0 && <span className="chip">{p.attachment_count} file{p.attachment_count > 1 ? "s" : ""}</span>}
        {unresolved && <span className="needs-doi">needs DOI</span>}
        {footExtra}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Replace the map body in `PaperList`** (lines 430–482) to render `PaperCard`, moving the focus/trash buttons into `footExtra`:

```jsx
      {state.status === "ready" && state.papers.map(p => {
        const fStaged = focusAxis ? (focusPending || {})[p.id] : undefined;
        const fIn = fStaged ? fStaged === "add" : !!(focusAxis && focusMembers && focusMembers.has(p.id));
        const footExtra = <>
          {focusAxis &&
            <button className={"paper-axis-add" + (fIn ? " in" : "") + (fStaged ? " staged" : "")}
              title={fIn ? "On this axis — click to remove" : "Add to this axis"}
              onClick={e => { e.stopPropagation(); onToggleFocusPaper(p.id); }}>
              {fStaged === "add" ? "✓ staged" : fStaged === "remove" ? "− staged" : fIn ? "✓ in axis" : "+ add"}
            </button>}
          {trashView && <button className="paper-restore" title="Restore from Trash"
            onClick={e => { e.stopPropagation(); onRestore(p.id); }}>Restore</button>}
          {trashView && <button className="paper-restore danger" title="Permanently delete — cannot be undone"
            onClick={e => { e.stopPropagation(); onPurge(p.id); }}>Delete forever</button>}
        </>;
        return <PaperCard key={p.id} paper={p} selecting={selecting} isSelected={selected === p.id}
          onSelect={onSelect} onOpen={onOpenPdf} checked={selectedLibraryIds && selectedLibraryIds.has(p.id)}
          onToggleCheck={onToggleLibrarySelect} footExtra={footExtra} />;
      })}
```

- [ ] **Step 3: Rebuild + sanity-check the bundle**

Run: `python tools/build_frontend.py && node --check callosum-app.html` *(if node --check rejects HTML, instead grep the built file for `function PaperCard` to confirm inclusion)*
Expected: build writes `callosum-app.html`; `PaperCard` present.

- [ ] **Step 4: Library regression check (headed Playwright, :8888).** Reuse `.local/visual/drive.py` to screenshot `01-library` and confirm cards render identically (title/authors/year/venue/tier/chips), double-click still opens, checkbox select still works.

Run: `python .local/visual/drive.py`
Expected: library cards unchanged; 0 console errors.

- [ ] **Step 5: pytest (unchanged backend) + ruff**

Run: `pytest -q && ruff check .`
Expected: 428+ pass; clean. (No Python changed, but run to be safe.)

- [ ] **Step 6: Commit**

```bash
git add app/frontend/js/10_pdf_layer.jsx callosum-app.html
git commit -m "refactor(frontend): extract shared PaperCard from PaperList (no behavior change)"
```

---

## Task 3: Frontend — restructure the dashboard (Overview + summary + OpenAlex footer)

**Files:**
- Modify: `app/frontend/js/31_mypubs_dashboard.jsx` (re-order sections; collapsible Overview; single flip-chart; #8 star-filter fix; OpenAlex footer card with extra stats + 2nd Refresh + a "Review N →" button that calls a handler stubbed now and wired in Task 5)
- Modify: `app/frontend/styles.css` (new tokens-only classes: `.mypubs-overview`, `.mypubs-overview-cols`, `.mypubs-collapse`, `.mypubs-chart-flip`, `.openalex-card`; read DESIGN.md first)

**Interfaces:**
- Consumes: dashboard JSON `openalex_extra` (Task 1), `metrics`, `pubs_by_year`, `counts_by_year`, `indexed_works`/`in_library`/`gap`, `research_summary`, `starred` availability.
- Produces: a `reviewMissing()` callback placeholder (opens the modal added in Task 5) — for now it sets local state `missingOpen` (the modal renders in Task 5).

- [ ] **Step 1: Add Overview collapse state** (mirrors existing localStorage prefs):

```jsx
const [overviewOpen, setOverviewOpen] = useState(() => localStorage.getItem("callosum.mypubsOverviewCollapsed") !== "1");
useEffect(() => { localStorage.setItem("callosum.mypubsOverviewCollapsed", overviewOpen ? "0" : "1"); }, [overviewOpen]);
```

- [ ] **Step 2: Single flip-chart state + 10-year window + `'NN` labels.** Replace the two `<MyPubsBarChart>` instances with one + a flip toggle:

```jsx
const [chartMode, setChartMode] = useState("pubs");  // "pubs" | "cites"
const last10 = (rows) => rows.slice(-10).map(r => ({ ...r, label: "'" + String(r.year).slice(-2) }));
// chartMode === "pubs" → pubs_by_year (count); "cites" → counts_by_year (cited_by_count)
```
Render: a header with two pill buttons (Publications / Citations, the active one `.on`) and the single chart fed `last10(...)` with the `'NN` labels. Pass the label through `MyPubsBarChart` (it currently renders `.pubs-bar-year` from the year — change it to render the provided `label`).

- [ ] **Step 3: Lay out Overview as 2 columns** — left the 2×2 metric tiles (existing `MyPubsTile`s in a `.mypubs-overview-cols` grid), right the flip-chart. Wrap the whole block in a collapsible `<section className="mypubs-overview">` with a chevron toggle bound to `overviewOpen`.

- [ ] **Step 4: #8 — hide the "⭐ only" toggle when no starred pubs.** `starred_count` already comes from the dashboard (added in Task 1). Guard the render: `const hasStarred = (data.starred_count || 0) > 0;` then `{hasStarred && <label className="mypubs-starred-toggle">…</label>}`.

- [ ] **Step 5: OpenAlex footer card.** After the publications section placeholder (Task 4 fills the list), render:

```jsx
<section className="openalex-card">
  <div className="mypubs-summary-head">
    <span>OpenAlex</span>
    <span className="mypubs-source">as of {data.as_of || "—"}</span>
  </div>
  <div className="openalex-gap">
    {data.indexed_works} indexed · {data.in_library} in library · {data.gap} not imported
    {data.gap > 0 && <button className="btn btn-ghost" onClick={() => setMissingOpen(true)}>Review {data.gap} →</button>}
  </div>
  {data.openalex_extra &&
    <div className="mypubs-source">
      2-yr mean citedness {data.openalex_extra.two_year_mean_citedness}
      {data.openalex_extra.affiliation ? ` · ${data.openalex_extra.affiliation}` : ""}
      {data.openalex_extra.openalex_author_id &&
        <> · <a className="btn-link" href={`https://openalex.org/${data.openalex_extra.openalex_author_id}`} target="_blank" rel="noopener noreferrer">OpenAlex profile ↗</a></>}
    </div>}
  <button className="btn btn-ghost" onClick={refreshMyPubs}>↻ Refresh from OpenAlex</button>
</section>
```
`refreshMyPubs` = POST `/my-publications/refresh`, poll `/my-publications/refresh/{job_id}`, then re-fetch the dashboard (reuse the Settings refresh logic pattern from `35_settings.jsx`).

- [ ] **Step 6: Re-order the render** to: Overview → Research summary → `{/* Publications — Task 4 */}` → OpenAlex card. Remove the old top attribution line (`.mypubs-head` `source:` span) and the old inline missing/dismissed sections (they move to the Task 5 modal) and the old two-chart block.

- [ ] **Step 7: CSS.** Read `.claude/DESIGN.md`, then add tokens-only `.mypubs-overview`, `.mypubs-overview-cols` (2-col grid), `.mypubs-collapse` (chevron button via `.btn-icon`), `.mypubs-chart-flip` (pill group), `.openalex-card`, `.openalex-gap`. No raw hex; reuse `--panel`/`--line`/`--radius-sm`.

- [ ] **Step 8: Rebuild + headed verify (:8888).** Extend `.local/visual/drive_mypubs.py`: open the dashboard, screenshot, assert order (Overview, summary, OpenAlex last), toggle collapse, flip the chart (Publications⇄Citations), confirm `'NN` year labels, confirm OpenAlex card shows as-of/gap/2-yr-mean/affiliation/profile-link/refresh.

Run: `python tools/build_frontend.py && python .local/visual/drive_mypubs.py`
Expected: new order + flip + collapse render; 0 console errors. Read the screenshots to confirm.

- [ ] **Step 9: Commit**

```bash
git add app/frontend/js/31_mypubs_dashboard.jsx app/frontend/styles.css callosum-app.html .local/visual/drive_mypubs.py
git commit -m "feat(my-pubs): restructure dashboard — collapsible Overview + flip-chart + OpenAlex footer (#1,3,4,5,6,8,11)"
```

---

## Task 4: Frontend — `MyPubsPublications` axis-scoped list (full parity) + relocate Decompose

**Files:**
- Create: `app/frontend/js/33_mypubs_pubs.jsx` (the publications list component)
- Modify: `app/frontend/js/31_mypubs_dashboard.jsx` (render `<MyPubsPublications axisId={axisId} onSummarize={onSummarize} />` between summary and OpenAlex card; move the Decompose button into its controls row)
- Modify: `app/frontend/js/30_viewer.jsx` (LibraryFrame) + `app/frontend/js/40_app.jsx` — thread an `onSummarizePapers(ids)` callback to the dashboard so "summarize selected" drives the right-pane synthesis.

**Interfaces:**
- Consumes: `PaperCard` (Task 2); `GET /papers?axis_id=<axisId>` with `q`/`search_field`/`item_type`/`sort`; bulk endpoints `POST /papers/export`, `POST /citations/render`, `DELETE /papers/{id}`; `onSummarize(ids)` prop.
- Produces: `function MyPubsPublications({ axisId, onSummarize, onOpenPdf, decomposeSlot })` — self-contained list with its own search/sort/selection state.

- [ ] **Step 1: Thread the summarize callback.** In `40_app.jsx`, define and pass `onSummarizePapers`:

```jsx
const summarizePaperIds = useCallback((ids) => {
  if (!ids.length) return;
  setPendingSummarize(prev => ({ paper_ids: ids, count: ids.length, nonce: (prev ? prev.nonce : 0) + 1 }));
  setRightOpen(true);
}, []);
```
Pass it through `LibraryFrame` (`30_viewer.jsx`) to `<MyPubsDashboard onSummarize={summarizePaperIds} onOpenPdf={openPdf} />`.

- [ ] **Step 2: Build `MyPubsPublications`** in the new chunk `33_mypubs_pubs.jsx`:

```jsx
function MyPubsPublications({ axisId, onSummarize, onOpenPdf, decomposeSlot }) {
  const [state, setState] = useState({ status: "loading", papers: [] });
  const [q, setQ] = useState(""); const debounced = useDebounced(q, 250);
  const [sort, setSort] = useState("year_desc");
  const [sel, setSel] = useState(new Set());
  const [citeStyles, setCiteStyles] = useState([]);
  useEffect(() => { api("/citations/styles").then(r => { if (r.ok) setCiteStyles(r.data.styles || []); }); }, []);
  useEffect(() => {
    let live = true; setState(s => ({ ...s, status: "loading" }));
    const qs = new URLSearchParams({ axis_id: axisId, limit: 500 });
    if (debounced.trim()) qs.set("q", debounced.trim());
    if (sort !== "added") qs.set("sort", sort);
    api(`/papers?${qs.toString()}`).then(r => { if (!live) return;
      r.ok ? setState({ status: "ready", papers: r.data }) : setState({ status: "error", error: r.error, papers: [] }); });
    return () => { live = false; };
  }, [axisId, debounced, sort]);
  const toggle = (id) => setSel(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  // bulk handlers: export/bibliography/delete copy the 40_app.jsx patterns scoped to [...sel]; delete confirms + refetches; summarize → onSummarize([...sel]).
  // controls row: <input search/> + sort <select> (year_desc/year_asc/title/title_desc/added) + {decomposeSlot}
  // bulk bar (when sel.size): summarize · export… · bibliography… · delete · clear  (reuse .axis-bulk-bar markup)
  // list: state.papers.map(p => <PaperCard paper={p} selecting isSelected={false} onOpen={onOpenPdf} checked={sel.has(p.id)} onToggleCheck={toggle} />)
}
```
Fill in the bulk handlers verbatim from `40_app.jsx:258-296` (export) / `279-296` (bibliography) / `235-244` (delete) scoped to `[...sel]`; on delete success, refetch (bump a local `refresh` nonce). Header shows `Publications ({state.papers.length})`.

- [ ] **Step 3: Relocate Decompose (#10).** Move the "Break down by domain / Re-decompose" button out of `31`'s old domains section into `MyPubsPublications`' controls row via the `decomposeSlot` prop. `31` passes the existing decompose button (its job logic stays in `31`, the button renders in the list's controls row).

- [ ] **Step 4: Render it in `31`** between the research summary and the OpenAlex card:

```jsx
<MyPubsPublications axisId={axisId} onSummarize={onSummarize} onOpenPdf={onOpenPdf} decomposeSlot={decomposeButton} />
```

- [ ] **Step 5: CSS** (read DESIGN.md): reuse `.searchbar`, `.lib-sort`, `.axis-bulk-bar`, `.pane-list-body` styling; add a `.mypubs-pubs` wrapper only if needed. No new hex.

- [ ] **Step 6: Rebuild + headed verify (:8888).** In `drive_mypubs.py`: confirm the Publications section renders library-style cards scoped to the axis (count matches `in_library`), search narrows, sort reorders, selecting shows the bulk bar, copy/open work, the Decompose button sits in the controls row. Screenshot.

Run: `python tools/build_frontend.py && python .local/visual/drive_mypubs.py`
Expected: cards render with parity; 0 console errors.

- [ ] **Step 7: pytest + ruff** (frontend-only, but run): `pytest -q && ruff check .` → green/clean.

- [ ] **Step 8: Commit**

```bash
git add app/frontend/js/33_mypubs_pubs.jsx app/frontend/js/31_mypubs_dashboard.jsx app/frontend/js/30_viewer.jsx app/frontend/js/40_app.jsx app/frontend/styles.css callosum-app.html .local/visual/drive_mypubs.py
git commit -m "feat(my-pubs): publications as axis-scoped library cards w/ parity + relocate Decompose (#7,10,13)"
```

---

## Task 5: Frontend — missing-works modal (#12)

**Files:**
- Create: `app/frontend/js/32_mypubs_missing.jsx` (`MissingWorksModal`)
- Modify: `app/frontend/js/31_mypubs_dashboard.jsx` (render the modal when `missingOpen`; remove the old inline missing/dismissed sections)
- Modify: `app/frontend/styles.css` if a modal class is missing (reuse the existing modal recipe, e.g. `.modal-backdrop`/`.modal`)

**Interfaces:**
- Consumes: dashboard `missing_works[]` + `dismissed_works[]`; endpoints `POST /my-publications/works/import`, `/dismiss`, `/undismiss`; `open`/`onClose`/`onChanged` props.
- Produces: `function MissingWorksModal({ open, onClose, missing, dismissed, onChanged })`.

- [ ] **Step 1: Build the modal** reusing the existing missing/dismissed JSX (today in `31`), wrapped in the project's modal shell (match an existing modal, e.g. `19_duplicates.jsx`/`27_scan.jsx` structure: backdrop + `.modal` + a header with a ✕ close). Import (`btn btn-ghost`) / Dismiss / Restore call the existing endpoints and then `onChanged()` (re-fetch dashboard).

- [ ] **Step 2: Wire it in `31`.** `const [missingOpen, setMissingOpen] = useState(false);` Render `<MissingWorksModal open={missingOpen} onClose={() => setMissingOpen(false)} missing={data.missing_works} dismissed={data.dismissed_works} onChanged={reloadDashboard} />`. The OpenAlex card's "Review N →" (Task 3) sets `missingOpen`.

- [ ] **Step 3: Remove** the old inline `.mypubs-missing` collapsibles from `31` (now in the modal).

- [ ] **Step 4: Rebuild + headed verify (:8888).** In `drive_mypubs.py`: click "Review N →", confirm the modal opens with the missing list; verify Import/Dismiss/Restore still function (use a disposable work — the live library is test data) and the dashboard refreshes; close the modal.

Run: `python tools/build_frontend.py && python .local/visual/drive_mypubs.py`
Expected: modal opens/closes; actions work; 0 console errors.

- [ ] **Step 5: Confirm file sizes under 600.**

Run: `wc -l app/frontend/js/31_mypubs_dashboard.jsx app/frontend/js/32_mypubs_missing.jsx app/frontend/js/33_mypubs_pubs.jsx app/frontend/js/10_pdf_layer.jsx`
Expected: all < 600. (If `31` is still large, the chart could move to its own chunk — but it should be lean after missing/pubs extraction.)

- [ ] **Step 6: Commit**

```bash
git add app/frontend/js/32_mypubs_missing.jsx app/frontend/js/31_mypubs_dashboard.jsx app/frontend/styles.css callosum-app.html .local/visual/drive_mypubs.py
git commit -m "feat(my-pubs): move missing-works import/reject into a modal (#12)"
```

---

## Task 6: Full verification + docs + final commit

**Files:**
- Modify: `.claude/changes.md` (changelog entry), `.claude/docs/increment-notes/INCREMENT-<NN>-NOTES.md` (new), `RECOVERY-LOG.md` (one line), `.claude/CLAUDE.md` (footer + decision-log row + increment number), `app/backend/help/help_content.md` (My Publications section: new layout, flip-chart, missing-works modal) + the `HELP-DOCS-SYNCED` marker.

- [ ] **Step 1: Full suite + lint + format**

Run: `pytest -q && ruff format --check . && ruff check .`
Expected: all green/clean (CI parity).

- [ ] **Step 2: Full headed Playwright pass (:8888)** — re-run `drive_mypubs.py` end-to-end; read every screenshot; confirm the four-section order, collapse, flip, `'NN` labels, #8 star-filter hidden when no starred, axis-scoped cards with search/sort/bulk parity, OpenAlex footer card, and the missing-works modal.

- [ ] **Step 3: Update docs** — changelog + increment notes (Implemented / Key technical detail / Manual verification script / Pytest count) + CLAUDE.md footer & decision-log row & increment number; refresh the help corpus My Publications section + move `HELP-DOCS-SYNCED` forward.

- [ ] **Step 4: Append RECOVERY-LOG line** (`[ISO] increment <NN> (My-Pubs SP1) — commit <sha> — files: … — summary`).

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "docs(my-pubs): SP1 increment notes + changelog + help + CLAUDE.md"
```

---

## Self-review notes
- **Spec coverage:** #1/#6 → OpenAlex card (T3); #3 → collapsible Overview (T3); #4/#5 → 2×2 metrics + single flip-chart 10yr/`'NN` (T3); #7 → section order (T3+T4); #8 → star-filter guard (T3 step 4; `starred_count` supplied by T1); #10 → search/sort + relocated Decompose (T4); #11 → 2nd Refresh in OpenAlex card (T3); #12 → missing-works modal (T5); #13 + parity → `PaperCard` + `MyPubsPublications` (T2/T4). All covered.
- **Open risk resolved:** `PaperList` is too coupled to reuse wholesale → extract `PaperCard` (T2) is the chosen path (matches the spec's fallback).
- **Type consistency:** `PaperCard` props identical in T2 and T4; `onSummarize(ids)`/`summarizePaperIds(ids)` consistent; `openalex_extra` shape identical across T1/T3.
- **Gate:** no new endpoint/egress/migration → no audit gate; rule #8 applies (CSS). `starred_count` is supplied by T1 (folded in), so T3's #8 guard has no dangling dependency.
