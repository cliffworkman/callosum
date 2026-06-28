# Increment 183 — Literature discovery SP1: the SourceProvider registry + Crossref search + save

Backlog #28 (the Discover/Search track). SP0 (inc 182) was the prerequisite `LibraryFrame` split; **SP1 (this
increment) is the backend** — the registry, the normalized `Item` with cross-provider dedup, the Crossref search
provider, and the two endpoints. **The in-app Search tab is SP1's frontend half (inc 184).**

Design spec: `.claude/docs/specs/2026-06-28-discovery-search-design.md` (Search-tab-first; all sources [Crossref
leads SP1, PubMed/bioRxiv drop in later]; axis-relevance highlight is SP1b; bioRxiv lands in the Feed = SP2).

## Implemented

- **`app/backend/discovery/__init__.py`** (NEW) — package docstring (the AI-augments-never-filters + metadata-only +
  public-metadata-not-Gemini-gate posture).
- **`app/backend/discovery/providers.py`** (NEW) — the registry pattern (mirrors the acquisition-resolver registry +
  the pane registry):
  - `Item` (frozen dataclass): `title`, `sources` (provider names, unioned on dedup), `doi`, `pmid`, `abstract`,
    `authors` ("Family, Given"), `journal`, `year`, `url`, `in_library`. `dedup_key` = DOI → PMID → normalized-title
    precedence; `merged_with(other)` unions `sources` + fills blank fields; `to_dict()` (adds `dedup_key`).
  - `normalized_title` (lowercase, collapse non-alnum).
  - `SourceProvider` Protocol (`name` + `search(query, limit) -> list[Item]`).
  - `SourceRegistry` (`register` / `providers` / `search_all` — **a provider that raises is skipped**, never sinks the
    others).
  - `build_default_registry()` → registers `CrossrefSearchProvider` (PubMed/bioRxiv register here later).
- **`app/backend/discovery/crossref_provider.py`** (NEW) — `CrossrefSearchProvider` (`name="crossref"`, injectable
  `fetcher` for hermetic tests, polite-pool mailto from `resolved_mailto("CALLOSUM_CROSSREF_MAILTO")`); `_httpx_search`
  GETs the **constant** `https://api.crossref.org/works` with `query`/`rows`/`select` as bound params (returns `[]` on
  non-200); `message_to_item` maps one Crossref item → `Item` (JATS stripped via `abstract_plain_text`; **drops
  no-title + no-DOI**). Separate from the per-DOI `CrossrefClient` (which caches per DOI).
- **`app/backend/discovery/search.py`** (NEW) — `DISCOVERY_SOURCE = "discovery-import"`; `run_search(conn, registry,
  query, limit=25)` fans out → dedups via `merged_with` (order preserved) → marks `in_library` via
  `find_existing_paper_by_identity`; `save_item(conn, *, title, doi, abstract, authors, journal, year, url)` dedups →
  returns `{paper_id, created:False}` for an existing identity, else `create_paper(... imported_source=DISCOVERY_SOURCE)`
  → `{paper_id, created:True}`. **No PDF fetch** (the OA-acquire lane is untouched).
- **`app/backend/api/routers/discovery.py`** (NEW) — `GET /discovery/search?q=&limit=` → `{items:[item.to_dict()]}`
  (registry from `request.app.state.discovery_registry`); `POST /discovery/save` (`SaveRequest`, bounded) → `save_item`
  + `conn.commit()`.
- **`app/backend/api/app.py`** — wired: import the `discovery` router + `build_default_registry`/`SourceRegistry`; a
  keyword-only `create_app(discovery_registry=None)` param; `api.state.discovery_registry = discovery_registry or
  build_default_registry()`; `api.include_router(discovery.router)`.

## Key technical detail

- **Dedup precedence is `dedup_key`** (DOI → PMID → normalized title), so the same work returned by two providers
  collapses to one `Item` with both source labels (`merged_with` unions `sources` and fills the first non-blank field).
  `run_search` preserves first-occurrence order, then re-marks `in_library` against the live library.
- **`save_item` is dedup-aware + metadata-only.** `imported_source = "discovery-import"` is kept out of the
  crossref-update allowlist (like `user-edited`/`merged`), so a later batch enrich won't clobber it; saving the same
  identity twice returns the same `paper_id` with `created:False` (no duplicate row).
- **No SSRF:** the only outbound call is to the constant Crossref host with the query as a bound parameter; the `url`
  field is stored for display only, never dereferenced.

## Manual verification script

Backend-only this increment (the UI is inc 184). Hermetic, offline:

```
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m pytest tests/test_discovery.py -q   # 15 passed
```

To eyeball the endpoints, inject a fake registry (see `tests/test_discovery.py::_FakeProvider`) into
`create_app(discovery_registry=…)` and `GET /discovery/search?q=…` / `POST /discovery/save`.

## Gates

- **pytest:** +15 `tests/test_discovery.py` (Item dedup-key/merge, Crossref message→Item mapping + JATS strip +
  drop-no-title-no-doi, provider injected-fetcher + blank-query, registry skips a failing provider + default-registry,
  run_search dedup + in_library marking, save_item create + dedup, the two endpoints' shape + 422 + the
  save→search-in_library cycle, registry-accepts-a-new-provider). Full suite run offline (in progress).
- **ruff:** check + `format --check` clean.
- **QA (rule #10):** new `route_43_discovery.md` declares `api: /discovery/search, /discovery/save`; surface check →
  **123/123 API + 618/618 FE, 0 uncovered**.
- **Audit:** `.claude/security-audits/2026-06-28_discovery-search.md` **PASS** (bounded inputs; bound-param
  persistence; constant external host, query-as-parameter, no SSRF; no user-URL fetch / no PDF retrieval; public
  metadata egress not the Gemini gate; no new dependency).
- **Principles:** discovery search makes no claim/judgment about the literature — it returns a complete deduped list
  (AI augments, never filters → SP1b's axis-relevance highlight is a hint not a gate); save is metadata-only, the human
  decides. Non-triggering. (Values: public-metadata egress + no paywall circumvention — the OA lane is untouched.)
- **No migration, no new dependency, no frontend change** (no `build_frontend` needed).

## NEXT — SP1 frontend (inc 184)

The **Search tab** in `30c_frame.jsx`: a query box → `GET /discovery/search` → result rows (title/authors/year/journal,
source labels, an "in library" marker, a one-click **Save** → `POST /discovery/save`), keyboard triage; headed verify;
help-corpus + a `fe:` claim added to `route_43`. Then SP1a (PubMed provider) / SP1b (axis-relevance highlight) / SP2
(Feed).
