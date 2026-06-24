# Security audit — My Publications citing articles & import (inc 119, SP3)

**Date:** 2026-06-24
**Feature:** show each own-paper's OpenAlex citation count, fetch the **citing** papers (`GET /my-publications/citing/{work_id}`), and **import** a selected citing paper (`POST /my-publications/citing/import`).

**Triggers:** audit gate #2 (a new external fetch — OpenAlex `cites:`) and #3 (a new file/record-creation path — citing-work import); two new endpoints.

## Threat review

- **Input validation (boundary):**
  - `work_id` is validated `re.fullmatch(r"W\d+", work_id)` in `fetch_citing_works` (anything else → empty result, no fetch). It is interpolated only into the OpenAlex `filter=cites:<work_id>` **query param** (urlencoded by httpx), never into a URL path we build or into SQL.
  - Import body `CitingImportRequest{doi, title?, openalex_work_id?}` (Pydantic). `doi` is `.strip().lower()`-normalized; empty → 422. `title` is stored as a CSL/string value (React-escaped on render). `openalex_work_id` is stored as an opaque id column value.
- **SSRF / external calls:** the only outbound call is to the **fixed** `OPENALEX_ROOT/works` via the injectable `fetcher` (default httpx) with a bounded `timeout`; the work-id is a validated query param, so no attacker-controlled host/path. Fail-closed (any exception/non-200 → empty, cached as a non-200). On-demand only (the read endpoint fires when the user opens a paper's citing list).
- **Egress posture:** **public metadata only** (OpenAlex `cites:` + Crossref DOI enrich) — the same class as the existing author/works lookups; **NOT** the Gemini library-text gate. No library text leaves the machine.
- **Injection / SQL:** import uses `find_existing_paper_by_identity` (bound params) + `create_paper` (SQLAlchemy Core, bound) + `enrich_paper_metadata_from_crossref`. No string-built SQL.
- **Acquisition boundary (A-A veto):** import is **metadata-only** — a record from a DOI; **no PDF is fetched** here (the PDF stays the separate inc-74 OA-only lane → no paywall circumvention). No reaching into other tools' stores. Discovery, not accusation.
- **Resource caps:** citing list capped at **100** (`_MAX_CITING`, `capped` surfaced — coverage stated, not implied); each citing fetch is **cached** under `citing:<work_id>` (a 2nd open costs zero egress); import is **per-DOI** (the "Import all" bulk loop is a client-side, confirm-gated sequence of these single imports). Dedup (`find_existing_paper_by_identity`) prevents duplicate creation.
- **Secret handling / supply chain:** none / no new dependency (reuses the existing OpenAlex client + httpx).
- **AuthZ:** single-user, 127.0.0.1, GET-only CORS — same posture as the sibling My-Publications endpoints; re-review before any hosted deployment (standing note).

## Negative-path checks (tests)
- `fetch_citing_works` with a malformed work id → `([], False)`, **no fetch** (`test_fetch_citing_works_caches_and_endpoint`).
- 2nd citing fetch served from cache (no extra fetcher call) — same test.
- `import_citing_work` empty DOI → `invalid` (→ endpoint 422); re-import → `exists` (dedup); a citing paper is **not** added to My Publications (`test_import_citing_work`).
- Route-surface invariant updated for both new routes (`test_api_exposes_only_read_only_get_routes`).

## Principles gate
Recorded in the spec (`2026-06-24-mypubs-sp3-citing-design.md` §2) — **aligned**: count = OpenAlex verbatim+attributed (no composite/verdict); citing list = candidates (coverage stated); import = metadata-only, human-selected; PDFs stay the OA-only lane.

## Result
**Security Audit: PASS** — a validated, bounded, cached, fail-closed public-metadata fetch + a metadata-only, deduped, human-selected import; no SSRF/injection surface, no new egress class, no acquisition-boundary crossing, no new dependency.
