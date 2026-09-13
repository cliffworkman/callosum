# Increment 599 — Discover Search: expose search-capable providers (GitHub #77)

Discover → Search's source filter was Crossref/PubMed only, even though Callosum integrates more scholarly
sources. #77 exposes the additional providers **that have a real free-text search API** — **arXiv**, **Europe
PMC**, **PsyArXiv** — so the Search surface matches the underlying support. **Backend-only.**

## Approach (add real SearchProviders; the dropdown was already data-driven)
- New `app/backend/discovery/preprint_search.py`: `ArxivSearchProvider` / `EuropePmcSearchProvider` /
  `PsyArxivSearchProvider`, each `search(query, limit) -> list[Item]`, registered in `build_default_registry`.
  They **reuse the existing Feed sources' HTTP + parse** and map the normalized `FeedEntry` into the canonical
  `Item` (`_feed_entry_to_item`):
  - **arXiv** — the Feed uses `search_query=cat:<category>` (a category feed, not search); search issues
    `search_query=all:<query>` (free-text, relevance-ordered) via a small dedicated fetcher, reusing arXiv's
    Atom parse (`_safe_parse` + `entry_to_feed`).
  - **Europe PMC / PsyArXiv** — their Feed fetchers ALREADY issue a keyword/title search, so `_europepmc_fetch`
    + `record_to_entry` and `_osf_fetch` + `record_to_entry` are reused directly.
- **No frontend change:** the Discover Search dropdown already derives from `/discovery/sources`
  (`30d_discover.jsx:41,169-171`), and `run_search` already fans out + dedups + marks `in_library`. Registering
  the providers auto-exposes them; query routing (`?source=`) and cross-provider dedup are generic.
- **bioRxiv/medRxiv deliberately NOT added:** their integration is a date-window category pull with no
  free-text search API; Crossref already indexes those preprints in Search. Documented, not silent (the issue's
  "don't present Feed-only sources as search providers").

## Identity / dedup
Unchanged `Item.dedup_key` policy (doi → pmid → normalized title). A DOI-bearing result from two providers merges
into one row with both source pills; a DOI-less preprint dedups by normalized title. Provider is never an
epistemic-quality signal. (A DOI-less arXiv/PsyArXiv preprint won't merge with a DOI-bearing Crossref twin —
that's the existing identity model's known limit, not new behavior.)

## Latency (rule #12 / LATENCY.md §11)
`SourceRegistry.search_all` fans out **serially**, so "All sources" now issues five sequential external calls.
Per §11 I did **not** casually parallelize — arXiv (~1 req/3s) and OSF rate limits plus result-ordering
determinism make concurrency a *measured future candidate*, not a current invariant (matching the documented
axis-cluster boundary). Instead each new provider uses a bounded **10s** interactive timeout so one slow source
can't dominate, and a single-source search stays fast. **Trade-off surfaced:** "All sources" is now slower than
the old Crossref+PubMed default; if that proves annoying, bounded-concurrent fan-out (or trimming All) is the
follow-up — flagged here and in the module docstring.

## Testing
- `tests/test_discovery_preprint_search.py` (8): default registry exposes all five search kinds with labels;
  each provider maps its source records → `Item` (hermetic, injected fetchers); empty query → []; `run_search`
  fans out across the new providers and **dedups a shared DOI into one row with both source labels** while
  keeping distinct DOIs distinct; `in_library` marking still works.
- Updated `test_discovery.py::test_build_default_registry_registers_the_search_capable_providers` (the intended
  registry change — was asserting exactly crossref+pubmed).
- One real-API smoke per provider is a documented dev/manual follow-up (non-gating); hermetic injected-fetcher
  tests are the release gate. `tach` + QA surface map green (no new API surface — endpoints unchanged).

## Scope / gates
Backend-only; no new endpoint (so no security-audit-gate trigger — same audited Discover-search egress posture,
public metadata, not the Gemini gate). Help corpus + route_43 updated. No `experiments/**` / `summarization/**`
change. Line budget: `preprint_search.py` 140, `providers.py` 151 (both ≤600). Frozen 0.6/0.7 Ask untouched.

**Next up:** #78 (inc 600, milestone) — Discover UX cleanup (inline search ×, merge Gaps/Overlooked, rename
Saved-for-later → Saved).
