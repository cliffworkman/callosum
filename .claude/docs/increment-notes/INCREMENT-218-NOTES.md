# Increment 218 — metadata enrichment SP2: Europe PMC + PubMed sources

SP2 of the multi-pass gap-fill enricher (SP1 = inc 217). Two more sources join the cascade — each is one
`register()` + a response mapper on an **already-existing client** (the registry's promise: no endpoint/UI/migration/
dependency change). They mainly add **abstract** coverage (biomedical) when Crossref/OpenAlex leave it blank.

## Implemented

- **Europe PMC source** — `integrations/europepmc/adapter.py`: `EuropePmcClient.lookup_metadata(conn, ref)` (DOI/PMID)
  reuses the **same cached `resultType=core` fetch** the OA resolver already uses, mapped by a new `_csl_from_record`
  (title / author[`{family,given}` or `{literal}`] / container-title[journalInfo.journal.title] / issued[pubYear] /
  abstract[abstractText] / DOI / PMID). `EuropePmcEnrichSource` in `enrich_sources.py` (DOI/PMID-gated).
- **PubMed source** — `PubMedEnrichSource` in `enrich_sources.py` reuses `pubmed_provider`'s `_eutils_search` /
  `fetch_abstracts` / `summary_to_item`: **PMID known → efetch abstract only** (`{"abstract": …}` — the others
  usually supplied the rest); **else title-search → the matched record's** journal/year/DOI/PMID + efetch abstract,
  adopted only on a conservative `_title_overlap` (normalized-equal or token-Jaccard ≥ 0.7 — no wrong-paper
  enrichment). pubmed helpers are lazy-imported (no import-time cycle).
- **Registry** — `build_default_enrich_registry` now registers `crossref → openalex → europepmc → pubmed`.
- **Injection seam** — `api.state.enrich_registry` (NEW, default None → built from the clients) so the
  batch worker (`routers/library.py`) + per-paper endpoint (`routers/papers.py`) can take a fully-stubbed registry
  in tests (keeps the endpoint tests hermetic now that the default cascade includes live Europe PMC/PubMed clients).

## Key technical detail

- **Purely additive to the cascade.** SP2 sources only contribute more CSL fragments; the orchestrator's gap-merge
  (fill-empty-only), the provenance/DOI/duplicate guards, and the egress posture (public bibliographic metadata, not
  the Gemini gate) are all SP1's — unchanged. So the non-destructiveness + honesty properties hold identically.
- **Europe PMC reuses the OA resolver's cache** — `lookup_metadata` and `lookup_oa` read the *same* cached core
  record (one fetch serves both), so adding metadata enrichment costs no extra Europe PMC request for a paper whose
  OA was already checked.
- **The `enrich_registry` seam was the SP2 hermeticity fix** — once the default cascade gained real Europe PMC +
  PubMed clients, the SP1 endpoint tests (which injected only fake Crossref/OpenAlex) would have hit the live
  Europe PMC/NCBI hosts. Injecting a stub registry on `app.state.enrich_registry` keeps them offline + deterministic.

## Manual verification script

Same as inc 217 (the controls are unchanged); the difference is coverage. To see a SP2 source fill a gap:
1. A paper with a DOI but no abstract where Crossref has no abstract but Europe PMC/PubMed does → **Fill missing
   fields** populates the abstract from the later source.
2. The library-wide **Enrich metadata ↻** batch is unchanged; its "fields filled" should rise on a biomedical
   library now that abstracts come from Europe PMC/PubMed too.

The live Crossref/OpenAlex/Europe PMC/NCBI run over the real library is the maintainer's spot-check.

## Pytest

Full suite green. `tests/test_metadata_multi_enrich.py` +3 (14 total): the Europe PMC `core`→CSL mapper; the PubMed
source (PMID→abstract / title-match-adopt / title-mismatch-reject); the default registry is exactly
`[crossref, openalex, europepmc, pubmed]`. The two endpoint tests were repointed to an injected stub `enrich_registry`
(hermetic). No new QA surface (sources behind the existing `/library/enrich/*` + `/papers/{id}/fill-metadata`);
`route_48` unchanged (155/155 API + 697/697 FE, 0 uncovered). Audit addendum in `2026-06-30_metadata-enrich.md` PASS.
