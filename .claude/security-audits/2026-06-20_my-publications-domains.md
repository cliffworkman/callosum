# Security audit — My Publications domain decomposition (Part 2, Layer 2) — increment 83

**Date:** 2026-06-20
**Feature:** cluster the user's confirmed My-Publications papers into research **domains** (impact-by-domain +
a dashboard chart re-filter). **Gate trigger:** 2 new API endpoints + a migration + a feature spanning 3+ files
/ ~300 LOC.

## Surface added
- Migration **0011** (`profile.research_domains` JSON, nullable — additive, idempotent, inspect-guarded).
- `POST /my-publications/domains` (async job) + `GET /my-publications/domains/{job_id}` (poll).
- `decompose_domains()` (local clustering) + `_dashboard_domains()` (enrich with citations) in
  `clustering/my_publications.py`; `profile_repo.set_research_domains`.
- `integrations/openalex/author.py`: `AuthorWork.cited_by_count` + a `fetch_author_works(refresh=…)` flag.
- Frontend: a Research-domains section in `31_mypubs_dashboard.jsx` (decompose button + impact bars +
  select-to-refilter).

## Threat review

**Input validation / injection.** The decompose endpoint takes **no request body** (it operates on the user's
own resolved corpus). `research_domains` is **app-derived** JSON (cluster labels from local c-TF-IDF + the
user's own paper ids), never free user text. All SQL is SQLAlchemy bound-param (rule #3) — the member query,
the `papers.id IN (...)` enrichment, and the JSON write. Domain labels/terms render as plain text in the
frontend (no `dangerouslySetInnerHTML`).

**Data egress (invariant #3).** Decomposition is **local** — it clusters the papers' embeddings with the
local sentence-transformers model + local c-TF-IDF labels; **no Gemini / LLM, zero library-text egress.** The
one network call is the OpenAlex works **refresh** inside decompose (`fetch_author_works(refresh=True)`) to
freshen per-paper citations — the **same OpenAlex metadata egress audited in inc 78** (public DOIs/citation
counts), explicitly **NOT** the Gemini library-text gate. The dashboard read stays cache-only/egress-free.

**SSRF / external calls.** No new fetcher; the OpenAlex works call is unchanged except for one added `select`
field (`cited_by_count`). URLs are built from constants.

**Secret handling.** No new secret.

**Resource caps.** Cluster count is √n-capped (`MAX_DOMAINS` 8); the works fetch is page-capped (inc 78
`_MAX_WORKS_PAGES`); the member set is the user's own (bounded) library. The decompose runs async so it can't
block the request thread.

**File-path safety / supply chain.** No file paths; no new dependency (numpy/sklearn already present, reused
via the inc-52 axis-suggestion helpers).

**Inspectability / no opaque scores (PRINCIPLES).** Domains are a **local, deterministic clustering** shown
with their member papers + the c-TF-IDF **terms** that named them (the user sees *why*). Impact-by-domain is an
honest **citation SUM** of OpenAlex per-paper counts (attributed), never a composite "domain score." The
decomposition is labeled "grouped by similarity" + re-runnable — a lens, not a taxonomy. **Unconfirmed
name-only candidates (0.25) are excluded** so domains describe confirmed work only.

## Negative-path checks (recorded)
- **Too few confirmed papers → decompose:** `{"status":"too-few"}`, no crash, no write
  (`test_decompose_too_few`). ✓
- **Not resolved (no author id) → decompose:** `{"status":"not-resolved"}`, no clustering. ✓
- **Candidate exclusion:** the 0.25 name-only candidate is not placed in any domain
  (`test_decompose_domains_clusters_confirmed_members`). ✓
- **Citations freshen:** `fetch_author_works(refresh=True)` re-fetches + re-caches; old caches (no
  `cited_by_count`) upgrade (`test_author_work_cited_by_count_and_refresh`). ✓
- **Route surface:** the GET poll is read-only; the POST is an explicit mutation — both in the `test_health.py`
  allowlist. ✓

## Result
**Security Audit: PASS.** Decomposition is local + LLM-free (no library-text egress); the only network call is
the already-audited OpenAlex metadata refresh. SQL is bound-param; the persisted artifact is app-derived JSON;
impact-by-domain is honest citation sums (no composite score); inputs are the user's own corpus, √n-capped, and
candidate papers are excluded. No new fetcher, secret, dependency, or file-write path.
