# Security Audit — PubMed discovery provider (NCBI E-utilities), inc 186

**Date:** 2026-06-28
**Feature:** `app/backend/discovery/pubmed_provider.py` (`PubMedSearchProvider` + `_eutils_search` + `summary_to_item`)
registered into the discovery `SourceRegistry` (`build_default_registry`). Backlog #28 SP1a — a second Search source.

**Audit gate trigger:** a new external fetch/integration (NCBI E-utilities). **No new endpoint** (it rides the inc-183
`/discovery/search`), no new ingestion path (save is unchanged), no new dependency (httpx already present), no migration.

## Threat review

### SSRF / external calls
- Two GETs to **constant hosts** under `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` (`esearch.fcgi` then
  `esummary.fcgi`). The user's query rides as a bound `term` **parameter** (`httpx.get(..., params=...)`), never as
  the URL/host — it cannot redirect the fetch. The esummary `id` list is built only from PMIDs that passed
  `i.isdigit()` (so no arbitrary string reaches the second call's params). **No user-supplied URL is ever fetched.**
- httpx timeout (15s default) on both calls; any non-200 (or non-JSON esearch body) → `[]` (fail-closed). A provider
  that raises is swallowed by `SourceRegistry.search_all`, so a PubMed outage never sinks the Crossref results.

### Input validation (rule #4) — untrusted NCBI response
- `summary_to_item` is fully defensive: tolerates missing/odd fields; PMID coerced from `uid`; DOI taken from
  `articleids` (idtype=="doi") or parsed from `elocationid` via a strict DOI regex (`10.\d{4,9}/\S+`); year parsed
  with a leading-4-digit regex; authors filtered to dict entries with a `name`. An entry with **no title and no DOI is
  dropped**. The esearch idlist is filtered to digit-only PMIDs (capped at `retmax`).

### Injection (rule #3)
- The provider performs **no SQL** — it returns `Item`s. Persistence (dedup + `save_item`) is the inc-183 path,
  already audited (bound parameters). PubMed `Item`s dedup across providers by DOI→PMID→title (a PubMed copy carrying
  a DOI merges with the Crossref copy → one row, both source labels).

### Data egress (invariant #3)
- Transmits the user's **search terms** to NCBI (public bibliographic metadata) — the same class as the Crossref
  search / the gap-finder OpenAlex lookups, explicitly **NOT** the Gemini library-text gate. No library text leaves the
  machine; no Gemini/genai host is contacted. Returned data is public (PMIDs/titles/DOIs).

### Secret handling / supply-chain / resource caps
- `email` is the polite-pool contact (`resolved_mailto("CALLOSUM_CROSSREF_MAILTO")` — Settings → Metadata access /
  env), a non-secret already sent to Crossref/OpenAlex; sent as the NCBI `email` param. No NCBI **api_key** in v1 (so
  no secret-in-URL); the keyless rate limit is sufficient for interactive search. `tool=callosum` per NCBI policy.
- No new dependency (httpx). `retmax = min(max(limit,1), 50)` caps both calls; the esummary `id` list is bounded by it.

## Negative-path checks
- Non-200 esearch / esummary → `[]`; non-JSON esearch body → `[]` (`_eutils_search` guards). Blank query → no fetch
  (`test_provider_uses_injected_fetcher`). No-title-no-DOI record dropped; DOI parsed from articleids + elocationid
  (`test_summary_to_item_*`). Cross-provider dedup on DOI (`test_run_search_dedups_crossref_and_pubmed_on_doi`).
- **Live spot-check** (`crispr gene editing`, retmax 3) → 3 real records mapped (title/PMID/DOI/year/source) — the
  hermetic tests' schema assumptions hold against the live API.

## Principles (rule #9)
Non-triggering — a search *source*, not a claim/judgment. It only adds results to the **complete deduped list** the
search endpoint already returns (augment, never filter); the human still decides what to save. (Values: public-metadata
egress, no PDF fetch / no paywall circumvention.)

## Decision

**Security Audit: PASS.** A constant-host, query-as-parameter, fail-closed public-metadata fetch with defensive
response parsing, bounded results, no user-URL fetch, no new secret/dependency/endpoint/migration, and not the Gemini
gate. Pre-hosted-deploy re-review still applies to the whole API surface.
