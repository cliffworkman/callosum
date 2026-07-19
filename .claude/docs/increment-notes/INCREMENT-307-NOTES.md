# Increment 307 — keyword tags everywhere (Feed/Search-save + 🔎 re-resolve)

## Context
inc 306 put keyword-tag population **inside the enrichment process** (`enrich_paper_metadata_multi`). Two
paper-ingest/refresh paths didn't go through it, so they produced no rich tags: (1) **Feed/Search save**
(`/discovery/save` → bare metadata-only create), and (2) **🔎 re-resolve** (only imported Crossref subjects). This
increment makes every path populate the source-labeled keyword tags, via the same machinery. (It also explains the
user's "no tags" screenshot — that was a **stale server** running pre-inc-306 code; the extraction was verified
correct against live OpenAlex for the exact paper.)

## Implemented
- **Refactor (DRY):** the inc-306 registry keyword loop → reusable `import_registry_keyword_tags(conn, paper_id, *,
  ref, registry)` in `app/backend/metadata/enrichment.py` (exported from the package). `enrich_paper_metadata_multi`
  now calls it (behavior identical); the two new paths call the same function.
- **#3 — 🔎 re-resolve** (`app/backend/api/routers/paper_enrich.py::reresolve_paper`): after the force-re-resolve +
  retraction check, builds the app registry and calls `import_registry_keyword_tags` for the re-resolved paper. So
  re-resolve now imports OpenAlex topics + PubMed MeSH, matching Fill-metadata (not just Crossref subjects).
  Fail-closed — never turns a 200 into a 500.
- **#2 — Feed/Search save** (`app/backend/api/routers/discovery.py`): `discovery_save` gains a `Request` +
  `BackgroundTasks`; on a **created** paper with a doi/pmid it enqueues `_enrich_saved_paper_bg`, which runs
  `enrich_paper_metadata_multi` on the new paper in its own `run_write` **after the response is sent** — the save
  returns instantly and the paper arrives enriched + tagged. `SaveRequest` gains `pmid`; `save_item`
  (`app/backend/discovery/search.py`) digit-validates it into the CSL so the bg enrich can drive MeSH.
- **Frontend:** both `/discovery/save` payloads (`js/30d_discover.jsx`, `js/30e_feed.jsx`) send `pmid: it.pmid ||
  null`; `callosum-app.html` rebuilt. No other JSX change (the tags render through the existing pane).

## Key technical detail — hermetic by construction, no create_app change
Both new paths ride `app.state.enrich_registry or build_default_enrich_registry(...)` — the exact seam inc 306 and
`test_retraction` use. An **empty/stub** registry advertises no `keyword_source`, so it fetches nothing and writes
nothing; production's real registry lights it up. So the save-endpoint tests inject an empty registry (no network)
or a keyword-capable **stub** (asserts the tags) — no live OpenAlex/PubMed in the suite. FastAPI `BackgroundTasks`
run **within** the TestClient request, so a save test can assert the tags are attached by the time `client.post`
returns.

## Decisions / notes
- **Provenance:** the bg enrich relabels a saved paper's `imported_source` `discovery-import → crossref` (the
  multi-enrich rule). Accepted (the paper is now genuinely Crossref-enriched; gap-fill only fills EMPTY fields,
  never overwrites). QA route_43 updated to match.
- A dedup save (`created=False`) enqueues no enrich; a save with neither doi nor pmid enqueues none.

## Gates
- **Security audit (#1 request-schema `pmid` + #2 fetch-on-save/re-resolve):** `2026-07-19_keyword-tags-everywhere.md`
  — **PASS**. Same public-metadata enrich egress (NOT the Gemini gate), now per-paper + background + fail-closed;
  `pmid` digit-validated (no SSRF); hermetic negative-paths; read-only mode still 403s the save.
- **QA (#10):** route_43 (discovery-save now bg-enriches → tags) + route_48 (both enrich buttons populate the rich
  source-labeled tags, no score shown) updated; `build_surface_map.py check` → **248 API / 1157 FE, 0 uncovered**.
- **Principles (#9):** unchanged from inc 306 (facts from a named index; scores filter server-side, never surfaced).
- **Experience (#11):** corpus-builder — saved-from-Feed/Search papers now arrive tagged (background, non-blocking);
  🔎 and Fill-metadata both populate consistently. No surprise egress (public metadata only); the save stays instant.

## Manual verification script (RESTART the server first)
1. **Restart the dev server** (loads inc 306 + 307). The frontend was rebuilt; hard-refresh the browser.
2. **Search** a paper → **Save** → open it → within a moment, muted `keyword:openalex` (+ `keyword:pubmed` if
   biomedical) chips appear, each tooltip naming its source; no score shown.
3. **🔎 re-resolve** an existing paper → confirm OpenAlex topic tags appear (not just Crossref subjects).
4. Delete an imported keyword, re-run either path → it is **not** re-added (inc-143 suppression).

## Pytest
3 new tests (`test_save_enriches_saved_paper_with_keyword_tags`, `test_import_registry_keyword_tags…`,
`test_reresolve_also_imports_registry_keyword_tags`) + the updated hermeticity of the existing save-route test.
Expected total **1283 passed / 1 skipped**. Full `pytest -n auto` → **<PENDING — CI is the authoritative gate; the
local harness has been killing the ~13-min run>**. ruff check + format + line-budget clean.
