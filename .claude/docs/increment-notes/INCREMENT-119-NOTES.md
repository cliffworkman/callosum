# Increment 119 — My Publications overhaul, SP3: citing articles & citation counts

The final sub-project of the My Publications overhaul (TDL **#14**). Shows each own-paper's OpenAlex citation count
(verbatim + attributed), opens the list of papers that **cite** it, and **imports** selected citing papers
(metadata-only) into the general library. Spec/plan + Principles gate:
`.claude/docs/specs/2026-06-24-mypubs-sp3-{citing-design,plan}.md`; audit
`.claude/security-audits/2026-06-24_mypubs-citing.md` (PASS).

**The whole overhaul (SP1 inc 117 + SP2 inc 118 + SP3 inc 119) now completes TDL #1 + #3–18.**

## Implemented

- **Backend — capture the work id + per-paper citation info (T1):** `AuthorWork.openalex_work_id` (extracted in
  `_work_from_obj` — already in the OpenAlex `select`, previously discarded); `build_dashboard` adds
  `paper_citations: {paper_id: {cited_by_count, openalex_work_id}}` (author works matched to live library papers by
  DOI); `DashboardResponse.paper_citations`. The `fetch_author_works` cache-read now carries the work id.
- **Backend — cited-by fetch (T2):** `OpenAlexAuthorClient.fetch_citing_works(conn, work_id)` — `filter=cites:<work_id>`,
  `select=…,authorships`, validated `^W\d+$`, **cached** under `citing:<work_id>`, **capped at 100** (surfaces
  `capped`), fail-closed. `CitingWork{doi,title,year,cited_by_count,authors}`. `GET /my-publications/citing/{work_id}`
  → `{works:[…,in_library], total, capped}` (in_library via `find_existing_paper_by_identity`). On-demand only.
- **Backend — import a citing work (T3):** `import_citing_work` (no author guardrail, **not** added to My Pubs):
  dedup → `create_paper(imported_source="citing-import")` → Crossref enrich (`force=True`). `POST
  /my-publications/citing/import {doi, title?, openalex_work_id?}`. Metadata-only; the PDF stays the OA-acquire lane.
- **Backend — Refresh now re-fetches works (T4):** `resolve_my_publications` calls `fetch_author_works(refresh=True)`
  so the "Refresh from OpenAlex" button gives fresh citation counts **and** the work ids the citing feature needs
  (previously works were read from cache, so counts went stale + work ids never populated without a Re-decompose).
- **Frontend — cited-by chip + Most-cited sort (T4):** `PaperCard` gains an optional `citeInfo` chip ("N cited-by",
  clickable when the work id is known → the citing modal); the library omits it (no chip there). `MyPubsPublications`
  builds `citeInfo` per card from `paper_citations`, adds a **"Most cited"** sort (client-side by count, composed with
  starred-first).
- **Frontend — citing-articles modal (T5, `34_mypubs_citing.jsx`):** lists the citing candidates (title · authors ·
  year · cited-by · DOI), framed "per OpenAlex … not exhaustive" + the capped note; **Import** per row (→ flips to
  "✓ in library" via a refetch) + a confirm-gated **Import all (N)**.

## Key technical details / Principles

- **Aligned with the Principles gate (rule #9):** the count is OpenAlex's figure shown **verbatim + attributed**
  (never a callosum composite or a ranking verdict — declined #7/#2); the citing list is **candidates**, coverage
  stated (#3/#6); import is **metadata-only, human-selected** (#5) into the general library; the PDF stays the OA-only
  lane (no paywall circumvention — A-A veto held); egress is **public metadata, bounded/cached/on-demand** (#10), not
  the Gemini gate. "Import all" is **confirm-gated** so the bulk path is a deliberate human action, not auto-apply.
- **Work ids reach the dashboard only after a works re-fetch:** old caches lack the id; the T4 `resolve refresh=True`
  change means a **Refresh** now populates them (a Re-decompose also does, via its existing `refresh=True`). Until a
  refresh, the chip shows the count but isn't clickable.
- **"Most cited" is client-side** (OpenAlex counts aren't a `/papers` column) — the fetch uses a default backend sort,
  then the cards are sorted by `paper_citations[id].cited_by_count` (then starred-first).

## Manual verification script

1. Server at the resolved-profile DB; open the dashboard. (If the citing chips aren't clickable, click **Refresh from
   OpenAlex** once to re-fetch works with their ids.)
2. Each own-pub card shows an **"N cited-by"** chip; **Sort → Most cited** reorders.
3. Click a chip → the citing modal lists the citing papers (per OpenAlex, capped at 100); **Import** one → it flips to
   "✓ in library"; **Import all (N)** (confirm) sweeps the rest. Imported papers land in the general library
   (metadata-only), not My Publications.

Verified headed via Playwright against the live `:8097` data (`.local/visual/drive_sp3.py`): 71 chips, Most-cited
reorder, a real `cites:` fetch (9 candidates), import → in-library.

## Pytest

**436 passed, 1 skipped** (+5 over inc 118: work-id capture, `paper_citations`, citing fetch+cache+endpoint+in_library,
import-citing dedup/not-in-mypubs, route surface ×2). `ruff format`/`check` clean. Audit PASS.

## File-size watch

`app/backend/clustering/my_publications.py` is **587/600** — the next backend addition there must split first
(candidate: extract the citing/import helpers, or the dashboard builder, to a sibling module).

## Commits (on main)

`e695dd4` (T1) · `2cbbfc8` (T2) · `be41163` (T3 + audit) · `26c3ffa` (T4) · `d90dc2c` (T5) · this docs commit.

## Overhaul complete

SP1 (restructure & cards) + SP2 (domain organization) + SP3 (citing articles) close the My Publications overhaul.
Deferred (noted): citation/citing for arbitrary library papers (we only hold OpenAlex work ids for the user's own
works); a citation-graph view; ranking the whole library by citations (declined — verdict risk).
