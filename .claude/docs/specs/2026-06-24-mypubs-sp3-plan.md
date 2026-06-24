# My Publications SP3 — Citing Articles & Citation Counts — Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use `- [ ]` checkboxes.

**Goal:** Show each own-paper's OpenAlex citation count (verbatim + attributed), open the list of citing papers, and import selected citing papers (metadata-only) into the library. Spec: `.claude/docs/specs/2026-06-24-mypubs-sp3-citing-design.md`.

**Architecture:** Capture the OpenAlex work-id (already fetched, discarded); expose per-paper citation info on the dashboard; a new cached `cites:` fetch + a read endpoint; a metadata-only import endpoint; frontend card chip + "Most cited" sort + a citing modal.

## Global Constraints
- 600-line cap. Now: `integrations/openalex/author.py` ~285, `clustering/my_publications.py` ~538, `routers/my_publications.py` ~444, `10_pdf_layer.jsx` ~520, `33_mypubs_pubs.jsx` ~190. Watch the clustering + router files.
- Parameterized SQL; new external call behind the injectable OpenAlex fetcher + cache + fail-closed. Import is metadata-only; PDFs stay the OA-only lane. **No migration.** Public-metadata egress only (NOT the Gemini gate).
- Rule #8 (DESIGN.md) for CSS. Rule #9 gate recorded in the spec §2 (PASS). New external fetch + 2 endpoints → security audit (T2/T3).
- After `app/frontend/` edits: `python tools/build_frontend.py`; verify headed on **:8097**. `pytest` + `ruff format` + `ruff check` green before each commit. Commit locally; push at session end.

---

## Task 1: Backend — capture work-id + `paper_citations` on the dashboard

**Files:** `integrations/openalex/author.py` (`AuthorWork`, `_work_from_obj`), `clustering/my_publications.py` (`build_dashboard`), `routers/my_publications.py` (`DashboardResponse`), `tests/test_my_publications.py`.

- [ ] **Step 1 — failing test:** `_work_from_obj({"id":"https://openalex.org/W1",...})` → `.openalex_work_id == "W1"`; `build_dashboard` returns `paper_citations[str(pid)] == {"cited_by_count": N, "openalex_work_id": "W1"}` for a library paper whose DOI matches an author work.
- [ ] **Step 2 — run, verify fail.**
- [ ] **Step 3 — implement:** add `openalex_work_id: str | None = None` to `AuthorWork`; in `_work_from_obj` set `openalex_work_id=(str(work.get("id")).rsplit("/",1)[-1] if work.get("id") else None)`. In `build_dashboard`, build `paper_citations`: map author works by DOI → for each live library paper (reuse the `_live_papers_by_doi` join, but return id+doi), `{str(pid): {"cited_by_count": w.cited_by_count, "openalex_work_id": w.openalex_work_id}}`. Add `paper_citations: dict[str, PaperCitation]` to `DashboardResponse` (model `PaperCitation{cited_by_count:int=0, openalex_work_id:str|None=None}`).
- [ ] **Step 4 — run pass; full `pytest -q` + `ruff`.**
- [ ] **Step 5 — commit** `feat(my-pubs): capture openalex_work_id + paper_citations on dashboard (SP3 T1)`.

---

## Task 2: Backend — fetch citing works + read endpoint (+ audit)

**Files:** `integrations/openalex/author.py` (`CitingWork`, `fetch_citing_works`), `routers/my_publications.py` (endpoint + models), `tests/test_my_publications.py`, `tests/test_health.py` (route surface), `.claude/security-audits/2026-06-24_mypubs-citing.md`.

- [ ] **Step 1 — open the audit stub.**
- [ ] **Step 2 — failing tests** (fake fetcher): `fetch_citing_works(conn, "W1")` issues a `filter=cites:W1` request, parses `CitingWork`s, caches under `citing:W1` (2nd call: no new fetch); `GET /my-publications/citing/W1` returns `{works:[...with in_library...], total, capped}`.
- [ ] **Step 3 — run, verify fail.**
- [ ] **Step 4 — implement** `CitingWork{doi,title,year,cited_by_count,authors:list[str]}` + `fetch_citing_works` (mirror `_fetch_all_works`: `filter=f"cites:{work_id}"`, `select="id,doi,title,publication_year,cited_by_count,authorships"`, cache key `f"citing:{work_id}"`, cap at 100 + return a `capped` bool; authors from `authorships[].author.display_name`). Validate `work_id` matches `^W\d+$` (else empty). Endpoint `GET /my-publications/citing/{work_id}` → resolve in_library per work via `find_existing_paper_by_identity(doi=…)`; same fail-closed status contract.
- [ ] **Step 5 — run pass; route-surface + full `pytest` + `ruff`.**
- [ ] **Step 6 — commit** `feat(my-pubs): OpenAlex cited-by fetch + GET /citing/{work_id} (SP3 T2)`.

---

## Task 3: Backend — import a citing work

**Files:** `clustering/my_publications.py` (`import_citing_work`), `routers/my_publications.py` (endpoint), `tests/test_my_publications.py`, `tests/test_health.py`, finish the audit.

- [ ] **Step 1 — failing tests:** `import_citing_work(conn, doi="10.x/new", crossref_client=_NoCrossref())` → creates a paper (`imported_source="citing-import"`), NOT added to My-Pubs; a 2nd call → `exists` (dedup); empty doi → `invalid`. Endpoint `POST /my-publications/citing/import {doi}` → 200 + `WorkImportResponse`.
- [ ] **Step 2 — run, verify fail.**
- [ ] **Step 3 — implement** `import_citing_work` (dedup via `find_existing_paper_by_identity` → `create_paper` + `enrich_paper_metadata_from_crossref(force=True)`; no `_add_confirmed_member`); endpoint reuses `WorkImportResponse`, `crossref_client` from `request.app.state` (mirror `import_missing_work`'s wiring).
- [ ] **Step 4 — run pass; route-surface + full `pytest` + `ruff`.**
- [ ] **Step 5 — finish the audit (PASS).**
- [ ] **Step 6 — commit** `feat(my-pubs): import a citing work (metadata-only, deduped) (SP3 T3)`.

---

## Task 4: Frontend — citation-count chip + "Most cited" sort

**Files:** `10_pdf_layer.jsx` (`PaperCard` optional `citeInfo`), `33_mypubs_pubs.jsx` (pass citeInfo, Most-cited client sort), `31_mypubs_dashboard.jsx` (pass `paper_citations`), `styles.css`.

- [ ] **Step 1** — `PaperCard` gains optional `citeInfo` (`{count, workId, onOpenCiting}`); when set, render a `.paper-cite` chip in `.paper-foot`: `"{count} cited-by"` with `onClick={e=>{e.stopPropagation(); onOpenCiting(workId, paper)}}` + a `title` attributing OpenAlex. Library callers omit it (no chip).
- [ ] **Step 2** — `MyPubsDashboard` passes `paperCitations={data.paper_citations}` + an `onOpenCiting` handler (opens the modal, T5) to `MyPubsPublications`.
- [ ] **Step 3** — `MyPubsPublications`: build `citeInfo` per card from `paperCitations[String(p.id)]` (only when present); add a **"Most cited"** sort option that, when selected, sorts client-side by `paperCitations[id].cited_by_count` desc (composed with starred-first). Render `<PaperCard citeInfo={…} onOpenCiting={…} … />`.
- [ ] **Step 4 — CSS** `.paper-cite` (a small ghost chip; tokens only — reuse `.chip`-like styling, `--ink-3`/`--accent` on hover).
- [ ] **Step 5 — rebuild; headed verify (:8097):** cards show "N cited-by"; "Most cited" reorders. Screenshot.
- [ ] **Step 6 — `pytest`/`ruff`; commit** `feat(my-pubs): cited-by chip on cards + Most-cited sort (SP3 T4)`.

---

## Task 5: Frontend — citing-articles modal + import

**Files:** Create `app/frontend/js/34_mypubs_citing.jsx` (`CitingModal`); `31_mypubs_dashboard.jsx` (state + render); `styles.css`.

- [ ] **Step 1** — `CitingModal({ workId, paperTitle, onClose, onChanged })`: on open, `GET /my-publications/citing/{workId}`; render the candidate list (title · authors · year · "N cited-by" + an attribution/"as of"/capped note), each row **Import** (or "✓ in library" when `in_library`); a header **Import all** (confirm → loop `POST /my-publications/citing/import` over not-in-library rows, then refetch the list). Reuse the `.axis-modal` shell.
- [ ] **Step 2** — `MyPubsDashboard`: `const [citing, setCiting] = useState(null)` (`{workId, title}`); `onOpenCiting(workId, paper)` sets it; render `<CitingModal … onChanged={() => {}} />` when set. Thread `onOpenCiting` to `MyPubsPublications` (T4).
- [ ] **Step 3 — CSS** reuse `.axis-modal*` + `.missing-row` recipes; add only what's missing. Tokens only.
- [ ] **Step 4 — rebuild; headed verify (:8097):** open a card's cited-by chip → modal lists citing candidates; Import one → it flips to "in library" (dedup); "Import all" (confirm) sweeps the rest. Screenshot. (Disposable test data.)
- [ ] **Step 5 — `pytest`/`ruff`; commit** `feat(my-pubs): citing-articles modal + import (per-row + import-all) (SP3 T5)`.

---

## Task 6: Verification + docs

- [ ] **Step 1** — full `pytest -q` + `ruff format --check` + `ruff check` green.
- [ ] **Step 2** — full headed Playwright pass on `:8097` (chip → modal → import → dedup → Most-cited → import-all).
- [ ] **Step 3** — docs: `INCREMENT-119-NOTES.md`; `changes.md` entry; `CLAUDE.md` footer + decision-log row + number→119; help corpus My-Pubs section (citing articles + counts) + `HELP-DOCS-SYNCED`→119. Note the overhaul (SP1+SP2+SP3) completes TDL #1 + #3–18.
- [ ] **Step 4** — RECOVERY-LOG line; commit `docs(my-pubs): SP3 increment notes + changelog + CLAUDE.md + help (inc 119)`; push.

## Self-review
- **Coverage:** #14 → counts (T1+T4), citing list (T2+T5), import (T3+T5). ✓
- **Gate:** new external fetch + 2 endpoints → audit (T2/T3); Principles recorded in spec §2; metadata-only import + OA-only PDFs (no boundary crossed).
- **Types:** `openalex_work_id`/`paper_citations`/`CitingWork`/`citeInfo` consistent across tasks.
- **600-cap watch:** `import_citing_work` (~20 lines) + endpoints push `clustering/my_publications.py` (~538) and the router (~444) up — re-measure; split if either nears 600 (the OpenAlex client has ample room for the fetch).
