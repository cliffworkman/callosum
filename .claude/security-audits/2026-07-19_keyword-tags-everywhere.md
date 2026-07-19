# Security Audit — Keyword tags everywhere (inc 307)

**Date:** 2026-07-19
**Increment:** 307
**Trigger:** audit gate #1 (a request-schema change — `SaveRequest.pmid`) + #2 (a metadata fetch is now **triggered**
by the `/discovery/save` endpoint and by `/papers/{id}/re-resolve`, via the enrichment cascade).

## Change under review
Make every paper-ingest/refresh path populate the inc-306 keyword tags, via the enrichment machinery:
- **Refactor:** the inc-306 registry keyword loop → reusable `enrichment.import_registry_keyword_tags(conn,
  paper_id, *, ref, registry)`.
- **`/papers/{id}/re-resolve`** now calls it after the force-re-resolve (so 🔎 adds OpenAlex/PubMed keywords, not
  just Crossref subjects).
- **`/discovery/save`** (both Feed + Search) now, on a NEW paper, runs the multi-pass enrich in a **FastAPI
  BackgroundTask** so the saved paper arrives with tags + gap-fills; the save response returns immediately.
- `SaveRequest` gains `pmid` (stored in the CSL by `save_item`) to drive PubMed MeSH.

## Threat review
- **Egress posture (invariant #3).** All fetches are the **same public bibliographic-metadata** enrich cascade
  (Crossref / OpenAlex / EuropePMC / PubMed) — the inc-87/183/210 posture, **NOT** the Gemini library-text gate. No
  library text leaves the machine. The change is *when* it fires: the save endpoint now triggers it (background),
  and re-resolve adds the OpenAlex/PubMed keyword reads. Both were already user-initiated network actions in intent
  (the user saved / re-resolved a paper); the fetch is bounded to that one paper.
- **New request field (`pmid`).** Bounded `max_length=40`; `save_item` **digit-validates** it
  (`"".join(ch for ch in pmid if ch.isdigit())`) before it enters the CSL / any downstream PubMed `id=` param → no
  SSRF, no injection. A non-numeric/empty pmid is dropped (falsy → stripped from the CSL).
- **Background task safety.** `_enrich_saved_paper_bg` runs after the response in its own `run_write(engine, …)`
  transaction (per-paper commit, the inc-B concurrency posture); it is wrapped in a bare `except → pass` so a
  slow/failed source **never** blocks or fails the save, and never surfaces to the caller. It fires only when the
  save **created** a new paper AND a doi/pmid is present (no fetch for a dedup no-op or an identifier-less save).
- **Injection / SQL (rule #3).** Tags are written through the inc-306 `_apply_keyword_tags` → `add_tags_to_paper`
  (bound-param Core). MeSH/OpenAlex names are display strings, capped, never interpolated.
- **Facts vs candidates / no opaque score (principles 3, 7).** Unchanged from inc 306 — imported keywords are facts
  from a **named index**, source-labeled, deletable + inc-143-suppressible; OpenAlex scores filter noise
  server-side and are never surfaced.
- **Provenance.** The background enrich relabels a saved paper's `imported_source` `discovery-import → crossref`
  (the multi-enrich provenance rule). Deliberate + accepted — the paper is now genuinely Crossref-enriched; not a
  silent metadata **overwrite** (gap-fill only fills empty fields, never overwrites a value).
- **No new dependency; no new file-write/ingestion path; no secrets.**

## Negative-path checks (run)
- **Hermeticity / no-surprise-egress:** `/discovery/save` with an **empty** `app.state.enrich_registry` makes **no**
  network call from the background task (test `test_save_endpoint_creates_then_search_marks_in_library`, updated);
  with a keyword-capable **stub** registry it attaches the tags (`test_save_enriches_saved_paper_with_keyword_tags`).
- **Re-resolve** with a stub keyword registry + a fake Crossref client attaches `keyword:openalex` tags, no network
  (`test_reresolve_also_imports_registry_keyword_tags`).
- **`import_registry_keyword_tags`** with an empty registry is a no-op (no fetch, no write).
- **Read-only mode:** `/discovery/save` remains 403 under `CALLOSUM_READ_ONLY` (POST blocked before the handler →
  no save, no background task) — `test_mobile_ingress` unchanged.
- **Dedup save:** an existing-paper save (`created=False`) enqueues **no** background task.

## Verdict
**Security Audit: PASS.** Same public-metadata egress as inc 306, now triggered per-paper by save (background,
fail-closed) + re-resolve; `pmid` is digit-validated (no SSRF); tagging is hermetic-by-construction (registry-gated,
tests inject empty/stub registries); no opaque score, no library-text egress, no new dependency. Full suite green
recorded in `INCREMENT-307-NOTES.md`.
