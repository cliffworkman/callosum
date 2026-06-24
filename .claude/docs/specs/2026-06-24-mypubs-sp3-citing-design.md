# Design spec — My Publications overhaul, SP3: citing articles & citation counts

**Date:** 2026-06-24
**Status:** approved design (Principles gate run) → spec under review
**Scope:** SP3 (final sub-project). Covers TDL **#14**.
**Builds on:** SP1 (inc 117) + SP2 (inc 118). The OpenAlex work-id is already fetched but discarded today.

---

## 1. Goal

Show each of the user's own papers' **citation count** (OpenAlex's figure, verbatim + attributed), let them open the
list of **papers that cite it**, and **import** selected citing papers into the library (metadata-only). A discovery
surface over the user's own corpus.

## 2. Principles gate (rule #9) — recorded
- **Touches:** #3 facts-vs-candidates, #5 human-is-the-filter, #7 no-opaque-scores, #10 bounded/cached/on-demand egress.
  Closest example: **Example 3 (effect sizes)** + the extant **missing-works import (#85)**.
- **Misaligned easy path (declined):** a callosum "impact score" / ranking the library as a quality verdict (#7/#2);
  auto-importing all citing papers (#5/#3); presenting OpenAlex's citing list as complete/authoritative (#6).
- **Aligned (this design):** citation count = OpenAlex `cited_by_count` shown **verbatim + attributed**, never a
  composite/verdict; citing list = **candidates** ("per OpenAlex, as of <date>" — coverage stated); import is
  **metadata-only, human-selected** into the general library; PDFs stay the separate OA-only lane; egress is **public
  metadata, bounded/cached/on-demand** (only on click), not the Gemini gate.
- **Values (A-A):** *extends* the discovery/acquisition lane to citing works; veto boundaries hold (no paywall
  circumvention — metadata + OA-only PDFs; OpenAlex public API only; discovery not accusation).
- **Decisions (brainstorm):** show the count **and** a "Most cited" sort for the *own* corpus (a legitimate personal
  view, not a verdict on others); **per-row Import + "Import all"** — the latter behind a confirm (deliberate, not auto).

## 3. Backend (additive; new external fetch + 2 new endpoints → security audit)

### 3.1 Capture the OpenAlex work id
- `AuthorWork` gains **`openalex_work_id: str | None`**; `_work_from_obj` extracts `work.get("id")` (already in the
  `select`, currently discarded). No new request cost.

### 3.2 Per-paper citation info on the dashboard
- `DashboardResponse` gains **`paper_citations: dict[str, {cited_by_count, openalex_work_id}]`** keyed by **paper_id**
  (string keys for JSON), built by matching author works (by DOI) to live library papers. Lets the cards show the count
  + know the work id to request citing works. (Only the user's own in-library papers get an entry.)

### 3.3 Fetch citing works (the new external call)
- `OpenAlexAuthorClient.fetch_citing_works(conn, openalex_work_id) -> list[CitingWork]` — mirrors `_fetch_all_works`
  with `filter=cites:<work_id>`, `select=id,doi,title,publication_year,cited_by_count,authorships`, **cached** under
  provider `openalex_works` key `citing:<work_id>`, fail-closed. **Capped** at the top **100** citing works
  (`per-page`/cursor bounded) — an honest "showing N of M" when capped (no silent truncation). `CitingWork` =
  `{doi, title, year, cited_by_count, authors: list[str]}`.
- **`GET /my-publications/citing/{work_id}`** → `{works: [{doi,title,year,cited_by_count,authors,in_library}], total, capped}`.
  `in_library` via `find_existing_paper_by_identity` (DOI / openalex id). On-demand (only when the user opens the modal).

### 3.4 Import a citing work
- `import_citing_work(conn, *, doi, openalex_work_id=None, crossref_client=None) -> {status, paper_id}` — **no**
  author-work guardrail, **no** My-Pubs add: dedup (`find_existing_paper_by_identity`) → `create_paper`
  (`imported_source="citing-import"`, carrying `openalex_work_id`) → `enrich_paper_metadata_from_crossref(force=True)`.
  Status `imported|exists|invalid`.
- **`POST /my-publications/citing/import`** `{doi, openalex_work_id?}` → `WorkImportResponse`. "Import all" = the
  frontend loops this per shown citing paper (behind a confirm) — no bulk endpoint, no auto-apply.

## 4. Frontend

### 4.1 Citation-count chip on the My-Pubs cards (#14)
- `PaperCard` gains an **optional** `citeInfo` prop (`{count, workId, onOpenCiting}`); when present, renders an
  **"N cited-by"** chip in the card foot that opens the citing modal. The library passes nothing → no chip (no library
  impact). `MyPubsPublications` passes `citeInfo` per card from `data.paper_citations`.

### 4.2 "Most cited" sort (own corpus)
- `MyPubsPublications` adds a **"Most cited"** sort option; because the counts are OpenAlex (not a `/papers` column),
  this sort is applied **client-side** using `paper_citations` (after the backend fetch), composed with starred-first.

### 4.3 The citing-articles modal (new chunk `34_mypubs_citing.jsx`)
- `CitingModal({ workId, paperTitle, onClose, onChanged })` — fetches `GET /my-publications/citing/{workId}`, shows the
  candidate list ("papers OpenAlex records as citing «title», as of …" + the capped note), each row title/authors/year
  + its own cited-by + **Import** (or "in library" if `in_library`), plus an **Import all** button (confirm →
  loops the import endpoint over not-yet-in-library rows). On change → `onChanged` (refresh in-library markers).

## 5. Gate / audit
- **Security audit** (`.claude/security-audits/2026-06-24_mypubs-citing.md`): a new external fetch (OpenAlex `cites:`)
  + two new endpoints. Review: input validation (work_id charset; doi normalize), the fetch is the injectable
  fetcher + cache + fail-closed (no SSRF — fixed OpenAlex root, work_id validated), import is metadata-only + deduped,
  egress is public metadata (not the Gemini gate), resource caps (100 citing works; per-row import), no new dependency.
- **Principles gate:** recorded in §2 (PASS — aligned design).

## 6. Verification plan
- **pytest:** `_work_from_obj` captures the work id; `fetch_citing_works` builds the `cites:` request + caches (fake
  fetcher); the citing endpoint returns `in_library` flags; `import_citing_work` creates+dedups (no My-Pubs add);
  dashboard exposes `paper_citations`. Route-surface updated.
- **Headed Playwright (:8097 live data):** a My-Pubs card shows its cited-by chip; clicking opens the modal with citing
  candidates; Import adds one (dedup marks it in-library); "Most cited" reorders; "Import all" (confirm) sweeps the set.

## 7. Out of scope
- Citation counts / citing for **arbitrary** library papers (we only have OpenAlex work ids for the user's own works).
- Ranking the **whole** library by citations (declined — verdict risk); a citation-graph visualization; auto-import.
- This is the **final** My-Publications sub-project; the overhaul (SP1+SP2+SP3) completes #1 + #3–18 of the TDL.
