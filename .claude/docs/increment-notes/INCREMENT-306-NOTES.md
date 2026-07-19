# Increment 306 — richer keyword tags: OpenAlex topics + PubMed MeSH → `keyword:*` tags

## Implemented
A paper's only auto-imported keyword tags were Crossref subjects (`keyword:crossref`, inc 73). The multi-pass
metadata enrich now also imports **OpenAlex curated topics** (`keyword:openalex`) and **PubMed MeSH descriptors**
(`keyword:pubmed`) — richer, browsable library facets. **Backend-only:** the frontend was already scaffolded
(`00_lib.jsx::tagSourceLabel` renders both provenances; `tagIsImported` is generic), so no JSX change / rebuild.

- **`integrations/openalex/work_keywords.py` (NEW leaf):** `keywords_from_work(work, *, max_terms=5,
  min_score=0.3)` — a pure function. Prefers the curated `topics` list (score-filtered), falls back to legacy
  `concepts` (score+level-filtered, level-0 disciplines dropped) for works cached before OpenAlex added topics.
  Deduped case-insensitively, capped. No egress.
- **`integrations/openalex/adapter.py`:** thin `fetch_work_keywords(conn, ref)` = `keywords_from_work(
  self._fetch_work(conn, ref) or {})` — reuses the **cached** work the cascade already fetched → zero extra egress.
- **`app/backend/discovery/pubmed_provider.py`:** `_parse_mesh(xml)` (targeted regex over the `<MeshHeadingList>`
  block — NOT an XML parser, XXE-safe, the `_parse_abstracts` pattern) + `fetch_mesh_terms(pmids, …)` (one batched
  efetch; digit-validated PMIDs → no SSRF; non-200 → `{}`). **Prefers the indexer's *major* headings** (descriptor
  or qualifier `MajorTopicYN="Y"`), falling back to all only when none are marked major — so generic **check-tags**
  ("Humans", "Male", "Adult") don't become facet noise (the experience-pass finding below).
- **`app/backend/metadata/enrich_sources.py`:** the two real sources gained a **keyword capability** —
  `OpenAlexEnrichSource` / `PubMedEnrichSource` each carry a `keyword_source` (`keyword:openalex` /
  `keyword:pubmed`) + a `keywords(conn, ref)` method. OpenAlex reuses the cached work; PubMed does one MeSH efetch
  when a PMID is known.
- **`app/backend/metadata/enrichment.py`:** after `apply_crossref_subject_tags`, `enrich_paper_metadata_multi`
  iterates `registry.sources` and, for any source advertising `keyword_source` + `keywords()`, writes the terms via
  `_apply_keyword_tags` (drop blanks + inc-143 suppressed → `add_tags_to_paper(import_source=…)`). Additive,
  idempotent, fail-closed.

The existing library **"Enrich metadata"** action (multi-enrich over every paper) now backfills the whole library
with the new sources — **no new endpoint, no new tool, no router change.**

## Key technical detail — why the tagging rides the registry (hermetic by construction)
The obvious design (pass an `openalex_client` + `mesh_fetcher` into `enrich_paper_metadata_multi`) can't be gated
cleanly: production `create_app()` leaves `app.state.openalex_client = None` (the cascade lazily builds a real
client **inside** its source), so there is no "is this production" flag to key off — and `test_retraction` avoids
network by injecting an **empty registry**, which a separate post-cascade client call would bypass and turn into a
real fetch. So the keyword import is driven **off the same registry** the CSL cascade already uses: a source that
advertises `keyword_source` + `keywords()` contributes tags. An empty / stub registry (every hermetic test) emits
no keywords and makes no call — **hermetic by construction**, and production's real `build_default_enrich_registry`
lights it up with zero extra wiring. OpenAlex = zero extra egress (cached work); PubMed = one bounded efetch.

## Gates
- **Principles (#9):** extends the aligned `keyword:crossref` pattern — facts from a **named index** (principle 3),
  source-labeled (1/8), additive/deletable/suppressible; OpenAlex scores filter noise server-side but are **never
  surfaced** (principle 7, no opaque score). Credit-the-lineage: the source is named in the `keyword:<source>`
  provenance + tooltip.
- **Security audit (#3/#5):** `2026-07-19_richer-keyword-tags.md` — **PASS** (XXE-safe MeSH parse, digit-validated
  no-SSRF fetch, public-metadata egress not the Gemini gate, hermetic negative-paths).
- **QA (#10):** `route_20_tags.md` extended (provenance-honesty + no-score assertions for all three `keyword:*`
  sources); `build_surface_map.py check` → **248 API / 1157 FE, 0 uncovered** (no new surface).
- **Experience (#11):** corpus-builder persona (inline pass) — after "Enrich metadata", richer source-labeled
  keyword facets feed the existing library tag filter; no dead-end. **Finding fixed in-increment:** raw MeSH would
  import generic check-tags ("Humans", "Male", "Adult") — real facet noise, parallel to the OpenAlex level-0
  concepts already dropped. Resolved by preferring **major** MeSH headings (with a fallback), consistent with the
  topics-only choice. OpenAlex topics are already curated + score-filtered + capped, so no spam there.

## Known follow-ups (non-blocking)
- **`adapter.py` is at 599/600** after the thin method — it must be split (the module-level work-mapping helpers →
  a `work_mapping.py` leaf, inc-137 pattern) **before its next edit**. Self-flagged by `check_line_budget.py --list`.
- Fold the MeSH efetch into the abstract efetch (one PubMed call instead of two) — an egress optimization.
- `tools/backfill_keyword_tags.py` stays Crossref-only; the "Enrich metadata" action covers the new sources.

## Manual verification script
1. Point at the real library DB; run the library **"Enrich metadata"** action.
2. Open a biomedical paper's detail pane → confirm new muted `keyword:openalex` + `keyword:pubmed` chips render,
   each tooltip naming its source; confirm **no score** is shown on any chip.
3. Delete one imported keyword, re-run "Enrich metadata" → confirm it is **not** re-added (inc-143 suppression).

## Pytest
15 new tests (6 `test_openalex_work_keywords` + 6 MeSH in `test_pubmed_provider` + 3 integration in
`test_metadata_multi_enrich`). Expected total **1280 passed / 1 skipped**. A full `pytest -n auto` run went
**1279 green** on this branch *before* the final experience-pass MeSH refinement; that refinement is isolated to
`_parse_mesh` (a leaf used only by `fetch_mesh_terms`, with no other dependents) and its 6 `test_pubmed_provider`
MeSH tests pass in isolation (16 passed with `test_openalex_work_keywords`). The local harness killed the
consolidated post-refinement `-n auto` run three times (resource pressure, not a failure — the machine had ~5 GB
free; a killed xdist worker reports a spurious node-down, 0 real failures), so the authoritative full-suite gate on
the exact committed state is **CI** (`pytest -n auto` on GitHub, which ran clean for inc 305). ruff check + format +
line-budget clean; QA surface map 248/1157, 0 uncovered.
