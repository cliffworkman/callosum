# Increment 217 — multi-pass, gap-filling metadata enrichment (SP1)

Beta feedback (Eileen): hand-editing records "to ensure DOIs are present and fields are consistently included" is the
chore. The fix: a **multi-source, gap-filling** enricher — recover a missing DOI, then fill *only the empty fields*
from a source cascade, **never overwriting a value the user typed** — runnable per-paper and across the whole library.
SP1 = the engine + registry + Crossref/OpenAlex sources + the batch + both controls. SP2 (inc 218) adds Europe PMC +
PubMed sources (each one `register()`).

## Implemented

- **Pluggable source registry** — `app/backend/metadata/enrich_sources.py` (NEW): `EnrichRef` (doi/pmid/title/year),
  an `EnrichmentSource` Protocol (`fetch(conn, ref) -> CSL-fragment | None`, fail-closed), `EnrichmentRegistry`
  (`fetch_all` skips a source that raises — mirrors the discovery `SourceRegistry`), `CrossrefEnrichSource`
  (by DOI → `resolve_doi().csl_json`), `OpenAlexEnrichSource` (by DOI/PMID/title → `fetch_work_csl`), and
  `build_default_enrich_registry(crossref_client=, openalex_client=)`.
- **OpenAlex CSL mapper** — `integrations/openalex/adapter.py`: `fetch_work_csl(conn, ref)` (reuses the cached
  `_fetch_work`) + `_csl_from_work` (title/author[`{literal}`]/issued/container-title[`primary_location.source`]/
  type[`_OA_TYPE_TO_CSL`]/abstract[`_reconstruct_abstract` from the inverted index]/DOI/PMID). Additive — existing
  callers of `_meta_from_work` are untouched.
- **The orchestrator** — `enrichment.py::enrich_paper_metadata_multi(conn, paper_id, *, registry, search_provider)`
  (the existing wholesale `enrich_paper_metadata_from_crossref` is left unchanged for the re-resolve/scan/OA-acquire/
  my-pubs callers). + `gap_merge` (fill-empty-only dict merge, DOI excluded) + `_gap_fill_columns` (project merged CSL
  → only the empty scalar columns) + `_titles_match`/`_years_compatible`/`_pmid_from_csl` + `MultiEnrichResult`.
- **Library batch** — `routers/library.py`: `POST /library/enrich/refresh` (202) + `GET …/{job_id}` + worker
  `_run_metadata_enrich_job` (builds the registry from `app.state.crossref_client`/`openalex_client`; iterates
  `list_live_paper_ids`; `mark_progress`; summary = papers/dois_recovered/fields_filled/still_missing_doi). New
  `api.state.metadata_enrich_jobs` + `api.state.enrich_search_provider` (test seam) in `create_app`.
- **Per-paper** — `routers/papers.py`: `POST /papers/{paper_id}/fill-metadata` → `FillMetadataResponse`
  (filled_fields/doi/still_missing_doi/paper).
- **Frontend** — `10b_libmenus.jsx::EnrichMetadataButton` (clone of `CitationCountsButton`; POST→poll, inline
  progress, summary tooltip, `onRefreshed`→`setLibRefresh`) wired into `10_pdf_layer.jsx` `lib-head-actions`
  (`onEnriched` from `40_app.jsx`); `25_detail.jsx` **Fill missing fields** button + `fillMetadata` callback;
  `.detail-fill` CSS (layout only). `callosum-app.html` rebuilt.

## Key technical detail

- **Gap-fill = the safety property.** `gap_merge` fills a CSL key only when the existing is empty (`_is_empty`);
  `_gap_fill_columns` emits a column update only when the paper's column is empty. A typed value is therefore never
  overwritten — and because of that, the batch can safely run over **all** live papers (not just the
  `_can_update_from_crossref` allowlist). **Provenance is never downgraded:** a `user-edited`/`merged`/`ai-agent`
  paper keeps its `imported_source` (it stays protected from the wholesale path); a `pdf-scaffold`/`null` paper that
  got enriched becomes `crossref`, else `crossref-unresolved`.
- **DOI is special** (UNIQUE column + dedup): the effective DOI is the existing one, else recovered (PDF →
  Crossref title-search) on a strong title match + compatible year, and **only adopted if it doesn't already belong
  to a different paper** (`find_existing_paper_by_identity`). A fragment's own DOI never sets the column —
  `merged["DOI"]` is forced to the guarded effective DOI.
- **`PaperRef` needs ≥1 of doi/pmid/title** — the paper's title always satisfies it, so OpenAlex-by-title can still
  gap-fill abstract/venue even when no DOI is recoverable.

## Manual verification script

1. `uvicorn app.backend.api.app:app --port 8888` → open `http://127.0.0.1:8888/`.
2. A paper with a DOI but no abstract → Detail → **Fill missing fields** → the abstract/venue populate; the note
   lists the filled fields. A hand-edited paper → its typed venue is untouched, blanks fill.
3. Library header → **Enrich metadata ↻** → a progress count → on done the cards reload + the tooltip reports
   "Filled N · recovered M DOIs · K still missing a DOI".
4. Live spot-check (set Settings → Metadata access contact email): run the batch over the real library; DOIs +
   abstracts populate; the "still missing a DOI" count drops.

Headed driver (no Gemini egress): `.local/visual/drive_inc217_enrich.py`.

## Pytest

Full suite green. New `tests/test_metadata_multi_enrich.py` (11): gap_merge fill-empty-only; cascade fills abstract
from a later source; never-overwrite; DOI recovery (strong adopts / weak + year-mismatch reject); duplicate-DOI
skipped; provenance preserved on user-edited; scaffold → crossref-unresolved; `_csl_from_work` mapper; the per-paper +
batch endpoints; unknown job → 404. Hermetic (stub sources + injected fake clients; offline). QA surface 155/155 API +
697/697 FE, 0 uncovered (`route_48_metadata_enrich.md`). Audit `2026-06-30_metadata-enrich.md` PASS.
