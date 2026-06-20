# Security Audit — Wanted list + OA re-check + coverage (acquisition Increment C, inc 76)

**Status: PASS (2026-06-20) — built; structural + negative-path tests green (347 passed, 1 skipped).**

**Trigger:** new API endpoints (`/wanted*`), a new DB write/ingest path (the re-check creates papers + imports
PDFs), and bulk external fetching (the re-check runs the cascade over the whole list). Three audit-gate
criteria fire.

## Scope
A persistent `wanted_items` table (migration 0008), CRUD + sync + coverage endpoints, and a manual async
re-check that runs the resolver cascade over open wants and auto-acquires hits. Builds on the inc-A/B
acquisition lane; no new dependency.

## Threat review
- **OA-only is structural (the core bright line):** the re-check (`acquisition/wanted.py::run_recheck`) resolves
  **only** through the `ResolverRegistry`, which can return only an `OaLocation` (database-asserted OA, https) —
  there is no path here to fetch a non-OA / arbitrary URL. Pinned by `test_recheck_fulfills_library_want`
  (the only download is the registry-produced `OaLocation`) + the inc-A/B structural guarantees. The download
  (80 MiB cap + `%PDF-`/PyMuPDF validation) and managed import are reused verbatim from inc A.
- **Input validation:** `POST /wanted` requires a `paper_id` or ≥1 of doi/pmid/title (else 422); a supplied
  `paper_id` is validated to an existing paper (else 404) before the FK insert. doi/pmid/title are stored as
  bound parameters and only ever used as resolver inputs / a created paper's metadata; the created paper's
  managed filename is sanitized by the existing inc-A filename path.
- **No fuzzy-match record creation:** an **external** want is fulfilled only if it has a doi or pmid — a
  title-only external want is skipped (`needs-id`), so the re-check never mints a paper (or downloads a PDF)
  from a fuzzy title match (`test_recheck_skips_title_only_external`). Library wants resolve on the existing
  paper's identifiers (title allowed, same as per-paper acquire).
- **Resource / politeness (bulk):** the re-check is sequential; each lookup is cached (`external_api_cache`)
  and each download is capped + validated; a per-run cap (`MAX_RECHECK_PER_RUN = 200`) bounds a run and is
  **logged, never silent**, if it truncates. One item's failure is caught per-item and never aborts the run.
- **Egress:** only the OA databases (the cascade) + the downloads they point at — NOT the Gemini egress gate,
  and never library text to an LLM. Soft-deleted papers are excluded from sync, coverage, and re-check.
- **SQL:** all `wanted_repo` access is SQLAlchemy bound-param (rule #3). **Supply-chain:** no new dependency.
- **Concurrency:** the re-check runs as a background job (sequential short transactions); SQLite-safe (no
  second mid-transaction connection).

## Negative-path checks (covered by tests/test_wanted.py)
- `POST /wanted {}` → 422; a bad `paper_id` → 404 (FK never violated).
- Title-only external want → skipped (`needs-id`), no paper created, registry never consulted.
- A re-check miss → `last_result="none"`, still wanted (not fulfilled).
- A per-item download error → counted, the run continues and still fulfills the healthy item.
- `sync_from_library` adds only live PDF-less papers and is idempotent; coverage excludes trashed papers.
- The only network fetch in a fulfillment is the registry's `OaLocation` (structural).

## Verdict
**Security Audit: PASS.** Increment C adds the wanted list + an auto-acquiring re-check whose OA-only posture
is structural (registry-only), with validated inputs, no fuzzy-match record creation, bulk-fetch politeness
(cache + caps + per-item isolation), bound-param SQL, and **no new dependency**. Egress is limited to the OA
databases. The legally-ambiguous lane remains absent.
