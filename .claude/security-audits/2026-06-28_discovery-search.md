# Security Audit — Literature discovery (Search tab backend), inc 183

**Date:** 2026-06-28
**Feature:** `app/backend/discovery/` (SourceProvider registry + normalized `Item` + dedup), the Crossref search
provider, `app/backend/discovery/search.py` (`run_search` / `save_item`), and `routers/discovery.py`
(`GET /discovery/search`, `POST /discovery/save`). Backend SP1 of backlog #28 (the Search tab); the in-app UI is inc 184.

**Audit gate triggers:** new API endpoints (2); a new external fetch (Crossref `/works?query=`); a new ingestion path
(`save_item` → `create_paper`); a net-new feature spanning 3+ files.

## Threat review

### Input validation (rule #4)
- `GET /discovery/search`: `q` is `Query(min_length=1, max_length=500)` → blank/oversized → **422**; `limit` is
  `Query(ge=1, le=50)` → out of range → 422. The handler `q.strip()`s before fanning out.
- `POST /discovery/save`: `SaveRequest` (pydantic) bounds every field — `title` 1..2000 (required), `doi` ≤300,
  `abstract` ≤20000, `authors` list ≤500, `journal` ≤600, `year` 1000..2100, `url` ≤2000. Over-bounds → 422.
- **Crossref response (untrusted):** `crossref_provider._httpx_search` returns `[]` on any non-200; `message_to_item`
  is fully defensive — `_first`/`_author_name`/`_year` tolerate missing/odd shapes, JATS abstracts are stripped via
  the existing `abstract_plain_text`, and an entry with **no title AND no DOI is dropped** (returns `None`). A
  provider that raises is swallowed by `SourceRegistry.search_all` (one bad source never sinks the search).

### Injection (rule #3)
- All persistence goes through `create_paper` / `find_existing_paper_by_identity` (SQLAlchemy Core bound parameters).
  No SQL text is built from request or Crossref data. `imported_source` is the constant `DISCOVERY_SOURCE`
  (`"discovery-import"`), never request-derived.
- `csl_json` is assembled from the validated fields (a dict, JSON-encoded by SQLAlchemy) — not interpolated.

### SSRF / external calls
- The only outbound call is `httpx.get(CROSSREF_SEARCH_URL, params=…, timeout=15)` — a **constant host**
  (`https://api.crossref.org/works`); the user's `q` rides as a bound query *parameter*, never as the URL/host, so it
  cannot redirect the fetch elsewhere. The polite-pool `mailto` comes from `resolved_mailto("CALLOSUM_CROSSREF_MAILTO")`
  (Settings → Metadata access / env), same posture as the existing Crossref/OpenAlex clients. **No user-supplied URL
  is ever fetched.**
- **`save_item` fetches nothing** — it stores the metadata the client already holds. The `url` field is stored in
  `csl_json["URL"]` only (display/citation), never dereferenced → no fetch-on-save, no PDF retrieval (the OA-acquire
  lane is untouched → **no paywall circumvention**, the A-A veto holds).

### Data egress (invariant #3)
- Discovery search transmits the user's **query string** to Crossref (public bibliographic metadata) — the same class
  as the existing DOI re-resolve / OpenAlex author lookup, explicitly **NOT** the Gemini library-text egress gate. No
  library text leaves the machine; no Gemini/genai host is contacted. The QA route asserts **0 genai-host requests**.

### Secret handling
- None introduced. The `mailto` is a polite-pool contact (already file-stored, non-secret); no API key (Crossref's
  search endpoint is keyless).

### Resource caps
- `limit` ≤ 50 (endpoint) and the provider re-caps `rows = min(max(limit,1), 50)`; `run_search` slices the merged set
  to `limit`. httpx timeout 15s. `SaveRequest` bounds each field (caps `authors` at 500, abstract at 20000 chars).

### File-path safety
- No filesystem path is built from request or Crossref data (no file write/read in this feature; `save_item` creates a
  metadata-only row with no attachment).

### Supply-chain
- **No new dependency.** `httpx` is already a project dep; the parsers are hand-rolled (project ethos).

## Negative-path checks
- Blank `q` → 422 (`test_search_endpoint_rejects_blank_query`).
- A provider that raises is skipped, others still return (`test_registry_search_all_skips_a_failing_provider`).
- Crossref entry with no title and no DOI → dropped (`test_message_to_item_drops_entries_with_no_title_and_no_doi`).
- Save twice with the same identity → one row, `created:false` (`test_save_item_dedups_against_an_existing_paper` +
  `test_save_endpoint_creates_then_search_marks_in_library`).
- DOI lowercased + deduped across providers; `in_library` reflects the live library
  (`test_run_search_*`). No genai host contacted (QA route_43 standing assertion).

## Decision

**Security Audit: PASS.** Local-first metadata search: bounded inputs, bound-param persistence, a constant external
host with the query as a parameter (no SSRF), no user-URL fetch, no PDF retrieval (OA lane untouched), public-metadata
egress only (not the Gemini gate), and no new dependency. The server-side reachability concerns of the scan routes do
not apply (no filesystem read); standard pre-hosted-deploy re-review still applies to the whole API surface.
