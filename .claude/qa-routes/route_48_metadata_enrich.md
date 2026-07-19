<!-- qa-coverage
api: POST /library/enrich/refresh
api: GET /library/enrich/refresh/{job_id}
api: POST /papers/{paper_id}/fill-metadata
fe: 10b_libmenus.jsx
fe: 25_detail.jsx
-->

# ROUTE 48 - Multi-pass, gap-filling metadata enrichment (inc 217)

**Tier:** 1 local-stateful
**Goal:** Exercise the multi-pass enricher and its safety boundaries — gap-fill (never overwrite a typed value),
DOI recovery, the library-wide async batch, the per-paper "Fill missing fields" control, and the public-metadata
(not Gemini-gate) egress posture. The live Crossref/OpenAlex fetches are the maintainer's spot-check; this route
verifies what callosum enforces. The header **Enrich metadata ↻** button + the per-paper button live in
`10b_libmenus.jsx` / `25_detail.jsx`.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET.** The enricher talks only to public
bibliographic registries (Crossref/OpenAlex), never the Gemini library-text gate — so it runs with egress unset.
For a hermetic UI drive, inject fake clients (`app.state.crossref_client` / `app.state.openalex_client`) + a stub
`app.state.enrich_search_provider`; otherwise seed papers that already have DOIs so the title-search path is inert.
Register console/pageerror/request listeners on any opened page.

## Standing assertions

- **Gap-fill, never overwrite (the core promise).** A field that already has a value is **never** changed by
  enrichment — only EMPTY fields are filled. A populated abstract/venue/title being overwritten is **Critical**.
- **Provenance is never downgraded.** A `user-edited` / `merged` / `ai-agent` paper keeps its `imported_source`
  after enrichment (its blanks may be filled, its typed values + its protected status are untouched). A hand-edited
  record being re-stamped `crossref` is **High**.
- **DOI recovery is conservative.** A missing DOI is recovered from the PDF or a Crossref title-search **only** on a
  strong title match (normalized-equal or token-Jaccard ≥ 0.7) with a compatible year; a weak/year-mismatched
  candidate is **not** adopted (the paper stays without a DOI — honest, not a wrong DOI). Adopting a wrong DOI is
  **High**.
- **Duplicate DOI as merge signal.** A recovered DOI that already belongs to a *different* library paper may be
  written after conservative matching, so the raw-PDF record can be detected and merged with the metadata-only record.
- **Public-metadata egress, not the library gate.** The cascade sends DOIs/PMIDs/titles to public registries — the
  inc-87/183/210 posture — and makes **no** request to a `generativelanguage`/genai host. Any genai-host request is
  **Critical**.
- **Honest "still missing".** The batch summary reports `still_missing_doi` for papers that genuinely could not be
  resolved — silence is not "resolved".

## Steps

1. Seed a `pdf-scaffold` paper with a DOI but no abstract/venue + a hand-edited paper with a typed venue.
2. `POST /papers/{id}/fill-metadata` on the scaffold (fake Crossref returning abstract+venue) → `filled_fields`
   includes `abstract`/`venue`; the returned paper shows them; `imported_source` is now `crossref`.
3. `POST /papers/{id}/fill-metadata` on the hand-edited paper → its blank fields fill, its typed venue is unchanged,
   `imported_source` stays `user-edited`.
4. `POST /library/enrich/refresh` → poll `GET /library/enrich/refresh/{job_id}` to `done`; the summary reports
   `papers`, `dois_recovered`, `fields_filled`, `still_missing_doi`.
5. `GET /library/enrich/refresh/nope` → **404**.
6. (UI) The library header shows **Enrich metadata ↻**; clicking it runs the batch with progress, then the library
   reloads. The Details pane shows **Fill missing fields** (next to 🔎 re-resolve).
7. **Keyword tags populate via enrichment (inc 306/307).** Both **Fill metadata** AND **🔎 re-resolve** import the
   rich, **source-labeled** keyword tags (`keyword:openalex` topics + `keyword:pubmed` MeSH, alongside
   `keyword:crossref` subjects) — verify a re-resolved/filled paper gains muted keyword chips whose tooltip names the
   source, that **no numeric score** is shown on any chip (OpenAlex scores filter server-side only), and that
   deleting one then re-running does **not** re-add it (inc-143 suppression holds across both paths).

## Pass criteria

- Gap-fill never overwrites a populated field; provenance never downgraded; DOI recovery conservative + dedup-safe;
  the batch + per-paper endpoints behave; unknown job → 404.
- 0 console/page errors and 0 genai-host requests across any opened page.
