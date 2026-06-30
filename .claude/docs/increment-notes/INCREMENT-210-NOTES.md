# Increment 210 — A2: library-wide per-paper citation counts

## Implemented

The eighth close-out of the cheapest-first wrap-up pass (A2): generalize the My-Publications cited-by display
(inc 119, SP3) so **every** library card can show its OpenAlex `cited_by_count` — verbatim + attributed
("cited by N · OpenAlex, as of <date>"), with an explicit (opt-in) **Most cited** sort. A displayed fact, never
a composite or a silent rank.

**Backend**
- **Migration `0027_paper_citation_counts`** — a dedicated per-paper store (PK `paper_id` FK CASCADE,
  `cited_by_count`, `source`, `retrieved_at`), kept OUT of the canonical `papers` row (consistent with
  open_science_signals / gap_candidates — every derived datum lives in its own table). `retrieved_at` IS the
  "as of <date>". Additive + guarded + no-op downgrade (the 0021/0022 pattern; `metadata.create_all` builds it on
  fresh DBs). Registered on the shared metadata via `schema_findings.py`, re-exported from `schema.py`.
- **`OpenAlexClient.fetch_cited_by_count(conn, ref)`** (`integrations/openalex/adapter.py`) — public, over the
  already-audited, **cached** DOI→work fetch (`_fetch_work`); returns the verbatim count (a real 0 is kept; a
  missing work/field → None). Fail-closed.
- **`repository.py`** — `list_papers` gains two correlated scalar subqueries (`cited_by_count` + `cited_by_as_of`
  labels — no JOIN, so no row duplication); a `citations_desc` key in `_paper_sort_order` (explicit Most-cited,
  NULL counts last); `upsert_citation_count` (OR-REPLACE on the PK → idempotent) + `list_live_papers_with_doi`
  (the bounded fetch set — DOI only, the reliable identifier).
- **`PaperListItem`** (`routers/papers.py`) += `cited_by_count` / `cited_by_as_of` (ISO via `_iso_or_none`).
- **`routers/citation_counts.py`** (new) — async batch `POST /papers/citation-counts/refresh` + `GET …/{job_id}`
  (mirrors the statcheck/retraction batch: JobStore + `mark_progress`); the worker fetches each live-with-DOI
  paper's count via `app.state.openalex_client` and upserts. Registered in `app.py` **before** `papers.router`
  (so `/papers/citation-counts/*` isn't captured by `/papers/{paper_id}` — the duplicates.py/fulltext.py
  precedent). `app.state.citation_count_jobs = JobStore()`.

**Frontend**
- The existing **static `paper-cite` chip** (inc 119) now renders on library cards: `PaperList` passes
  `citeInfo={count, asOf}` (no `workId` → the static span, no click target in the library); the tooltip carries
  "per OpenAlex · as of <date>".
- A **"Most cited"** option in the Sort dropdown (`citations_desc`) — opt-in, never the default.
- A **"Citations ↻"** header control (`CitationCountsButton` in `js/10b_libmenus.jsx`) — a self-contained
  POST→poll that, on completion, bumps the library refresh (`onCitationsRefreshed`) so the chips appear; it then
  reads **"Citations · <date>"** (the source + freshness, visible — the freshest `cited_by_as_of` across the list).

## Key technical detail

A2 is the canonical "a per-paper number" case (PRINCIPLES Example 3). The aligned shape is inc-119's, generalized:
the count is stored + shown **raw** (never a composite — #7), the citation sort is **explicit + user-invoked**
(never the default/silent — #2), a no-DOI / no-record paper shows **no chip** (honest "—", never a fabricated 0 —
#6; a genuine 0 shows "0 cited-by"), and the source + date are **visible** on the control + each chip's tooltip
(#8). Egress is the paper's **DOI → OpenAlex** (public metadata, bounded/cached/on-demand — #10), **NOT** the
Gemini library-text gate. The count lives in its own table (not `papers`), surfaced via scalar subqueries so the
list query stays one round-trip with no row duplication.

## Manual verification script

`HF_HUB_OFFLINE=1 python -m pytest tests/test_citation_counts.py -q` → 5 passed: `fetch_cited_by_count`
(verbatim, 0 kept, missing→None); upsert + list projection + Most-cited sort (counted desc, uncounted last) +
idempotent re-fetch; `list_live_papers_with_doi` (DOI-only); the refresh endpoint stores counts + shows them on
`GET /papers` (a 404'd DOI → None, never a fabricated 0; a real 0 shown); unknown job → 404.
**Headed (no Gemini egress):** `.local/visual/drive_inc210_citations.py` — a FAKE OpenAlex fetcher (offline):
unknown job → 404; click **Citations ↻** → 0 chips → **2 chips** + the control reads "Citations · 2026-06-29";
**Most cited** sort → "99 cited-by" first. 0 console/page/genai.

## Gates

- **pytest:** full suite green — **724 passed, 1 skipped** (+5 `tests/test_citation_counts.py`).
- **ruff** check + format clean; frontend rebuilt; migration head **0027** via `alembic_head()`.
- **QA surface** — **144/144 API** (+2: `/papers/citation-counts/refresh` POST + GET) **+ 679/679 FE, 0
  uncovered**; new `route_23_citation_counts.md`.
- **Security audit `2026-06-29_citation-counts.md` PASS** (no SSRF — constant host + DB-DOI path-quoted;
  bounded/cached/on-demand; public-metadata egress NOT the Gemini gate; bound-param upsert; no new dependency;
  additive guarded migration; honest-"—" / no-silent-rank).
- **Principles (Example 3) — aligned** (verbatim raw count, explicit opt-in sort, honest "—", visible
  attribution; declined the composite "evidence strength" / default-citations-rank). **No new CSS** (reuses
  `.paper-cite` + `.trash-toggle`) → no DESIGN change. **Help corpus** gained a "Citation counts" paragraph
  (`HELP-DOCS-SYNCED` → 210). **No new dependency.**
- **Rule-#1:** `js/40_app.jsx` stays at **599/600** (the new prop folded onto an existing line — the chronic
  watch item; a split is its own refactor). `js/10_pdf_layer.jsx` 562; `js/10b_libmenus.jsx` 93.

## NEXT

The cheapest-first A-items are now A9/A10/A8/A6/A5/A1/A3/**A2** — done. The remaining A-item is **A7 Curated
Axis** (the largest; its own design pass). The deferred **B-items** (MCP server, citation-context classifier) are
larger, own design passes.
