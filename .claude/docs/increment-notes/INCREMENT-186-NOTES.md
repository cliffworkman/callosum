# Increment 186 — Literature discovery SP1a: the PubMed source

Backlog #28 SP1a. A second Search source — **PubMed** (NCBI E-utilities) — that drops into the discovery
`SourceRegistry` with **no endpoint/UI change** (the registry's promise: adding a source = one `register()`). The
user said "keep going" after SP1b.

## Implemented

- **`app/backend/discovery/pubmed_provider.py`** (NEW) — `PubMedSearchProvider` (`name="pubmed"`, injectable
  `fetcher` for hermetic tests, polite-pool `email` from `resolved_mailto`, `search(query, limit)` capped at 50):
  - `_eutils_search` = **esearch** (`term` → PMIDs) then **esummary** (PMIDs → records), both GET to the **constant**
    `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` host with the query as a bound *param*; fail-closed (non-200 / no
    ids → `[]`).
  - `summary_to_item` maps an esummary record → a normalized `Item`: title (trailing "." stripped), `pmid` from `uid`,
    `doi` from `articleids` (idtype=="doi") or `elocationid` (strict DOI regex), authors, journal
    (`fulljournalname`/`source`), year (leading-4-digit), `url` = the pubmed.ncbi.nlm.nih.gov PMID page. Drops
    no-title-and-no-DOI. **v1 has no abstract** (esummary doesn't carry it; efetch deferred).
- **`app/backend/discovery/providers.py`** — `build_default_registry()` now registers Crossref **+** PubMed.
- (No `routers/`/`app.py`/frontend change — PubMed fans out behind the existing `/discovery/search`; the Search tab
  shows its results + a `pubmed` source pill, and a Crossref+PubMed overlap (same DOI) collapses to one row with both
  pills.)

## Key technical detail

- **Registry promise proven:** the only code change to *use* PubMed is one `register()` call — the endpoint, the
  frontend, the dedup, the relevance highlight all work unchanged (the inc-183 `SourceRegistry.search_all` fans out to
  every provider + skips one that raises). The updated `test_build_default_registry_registers_crossref_and_pubmed`
  pins this.
- **Cross-provider dedup on DOI:** PubMed extracts the DOI from `articleids`, so a paper indexed by both Crossref and
  PubMed merges on `doi:` → one `Item`, `sources=("crossref","pubmed")`, with the `pmid` filled from the PubMed copy.

## Manual verification script

Hermetic (injected fetcher): `pytest tests/test_pubmed_provider.py`. **Live schema spot-check** (public metadata):

```
python -c "from app.backend.discovery.pubmed_provider import PubMedSearchProvider; \
print(PubMedSearchProvider(email='<contact>').search('crispr gene editing', 3))"
```

→ confirmed 3 real records map (title / PMID / DOI from articleids / year / `pubmed` source) against the live
esearch→esummary schema the hermetic tests assume.

## Gates

- **pytest 643** (+4 `tests/test_pubmed_provider.py`: summary→Item mapping, DOI-from-elocationid + drop-empty,
  injected-fetcher + blank-query, cross-provider DOI dedup; the inc-183 registry test renamed/updated to expect
  crossref+pubmed). `ruff` check + `format --check` clean.
- **Audit:** `.claude/security-audits/2026-06-28_pubmed-provider.md` **PASS** (constant host + query-as-param → no
  SSRF; defensive response parsing; fail-closed; public-metadata egress, not the Gemini gate; no new dependency).
- **QA (rule #10):** no new API/FE surface (a provider behind the existing `/discovery/search`) → surface map
  unchanged (**124/124 API + 631/631 FE, 0 uncovered**); `route_43_discovery.md` notes PubMed as a registered source.
- **Principles:** non-triggering (a search source; the complete deduped list is still returned — augment, never
  filter). help corpus's Discover section now says "Crossref + PubMed."
- **No migration, no new dependency, no new endpoint, no frontend rebuild needed** (backend provider only; the
  served frontend is unchanged).

## NEXT (remaining #28)

- **SP2:** the Feed tab — subscriptions (journals by ISSN / PubMed keyword / **bioRxiv by category**) + polling on a
  cadence + a read/unread/starred store (needs a migration). The larger, design-led one.
- (Optional later: PubMed abstracts via efetch; an NCBI api_key for higher rate limits.)
