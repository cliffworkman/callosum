# Security audit — My Publications impact dashboard (Part 2, Layer 1) — increment 81

**Date:** 2026-06-20
**Feature:** an Overview dashboard tab for the pinned My Publications axis — headline OpenAlex metrics +
publications-by-year chart + indexed-vs-library gap, plus an editable, AI-generated research summary.
**Gate trigger:** 3 new API endpoints + a new data-egress path (the research summary) + a feature spanning
3+ files / ~300+ LOC + a migration.

## Surface added
- Migration **0010** (`profile.research_summary`, Text nullable — additive, idempotent, inspect-guarded).
- `GET /my-publications/dashboard` — sync, **cache-only** read of the resolved OpenAlex record + cached works
  + the local library. Returns a status summary.
- `POST /my-publications/summary/generate` — generates a DRAFT research summary from the user's own
  publication titles/abstracts via the egress-gated Gemini generator. Does not persist.
- `PUT /my-publications/summary {summary}` — persists the (edited) summary on the profile row.
- `integrations/openalex/author.py`: enriched `ResolvedAuthor` (stats parsed from the already-fetched author
  object) + cache-only `cached_author()`.
- `integrations/gemini/research_summary.py` + `EgressGatedResearchSummaryGenerator` (the inc-58 seam).
- Frontend: `31_mypubs_dashboard.jsx` (a frame tab) + a 📊 button on the My Pubs card.

## Threat review

**Input validation.** `PUT /my-publications/summary` caps the summary at `MAX_SUMMARY_LEN` (4000) → 422 over.
The generate endpoint takes no user-supplied free text (its input is the user's own library rows). All SQL is
SQLAlchemy bound-param (rule #3); no user/external string is interpolated into SQL. The model's generated
summary is whitespace-collapsed + length-capped (`_clean`) and rendered as plain text in a `<textarea>` (no
`dangerouslySetInnerHTML`), so untrusted model output cannot inject markup.

**Data egress (invariant #3).** The dashboard read (`GET /dashboard`) makes **no network call** — it reads
only the `external_api_cache` rows that a prior Settings → Refresh already wrote, gated on
`profile.openalex_author_id` being set (`cached_author` never fetches; if the cache is cold it returns None →
the endpoint reports `not-resolved`). The research-summary generate sends the user's **own** publication
titles/abstracts (library text) and is therefore gated by the **library** `CALLOSUM_ALLOW_DATA_EGRESS` flag at
the DI seam (`EgressGatedResearchSummaryGenerator`, mirroring inc-58): egress-off → `DataEgressDisabledError`
→ **503** *before any genai import or network call*. The provider keeps its own internal check as
defense-in-depth. No library text leaves the machine without explicit consent.

**SSRF / external calls.** No new fetcher is introduced. The OpenAlex author/works fetch (already audited in
inc 78) is unchanged; the dashboard only *reads its cache*. The Gemini call reuses the existing
`GeminiConfig`/`google-genai` path (httpx timeouts, fixed model). URLs are constructed from constants, never
from request data.

**Secret handling.** No new secret. `GOOGLE_API_KEY` is read from the environment via `GeminiConfig`
(unchanged); never logged or returned.

**Resource caps.** Generation input is capped (`MAX_DOCUMENTS` 60 publications, `MAX_ABSTRACT_CHARS` 600 each)
so the prompt can't grow unbounded with the library. The summary column + response are capped. The dashboard
read is O(works) over an already-bounded cached set (`_MAX_WORKS_PAGES` from inc 78).

**File-path safety.** No file paths are constructed or served.

**Supply chain.** No new third-party dependency (reuses `httpx`, `google-genai`, `sqlalchemy`, the in-repo
SVG rendering — no chart library added).

**Inspectability / no opaque scores (PRINCIPLES).** Headline metrics are OpenAlex's authoritative figures
shown verbatim + attributed ("source: OpenAlex · as of <date>"); there is no callosum-invented composite
"impact score." The indexed-vs-library gap is a fact + import nudge. The research summary is labeled an
"AI-generated draft — edit freely," is non-load-bearing, and the user owns the persisted text.

## Negative-path checks (recorded)
- **Egress off → generate:** `test_summary_generate_egress_off_returns_503` → **503** (no genai import, no
  network). ✓
- **Not resolved (no author id) → dashboard:** `build_dashboard` returns `{"status":"not-resolved"}` with no
  fetch; `cached_author` cold → None (`test_cached_author_reads_cache_without_fetching` asserts zero fetches). ✓
- **No identity → dashboard:** `{"status":"no-identity"}`. ✓
- **No members → generate:** 422 ("nothing to summarize"), never calls Gemini
  (`test_summary_generate_no_members_returns_422`). ✓
- **Oversize summary → PUT:** 422 at `MAX_SUMMARY_LEN`. ✓
- **Route surface:** the 3 new routes are in the `test_health.py` allowlist; the GET is read-only, the
  generate/PUT are explicit mutations. ✓

## Result
**Security Audit: PASS.** The dashboard is a cache-only, egress-free read; the only egress (the research
summary) is gated at the authoritative DI seam exactly like every other Gemini path, sends only the user's own
publication text, and degrades to 503 when consent is absent. No new fetcher, secret, dependency, or
file-write path; all SQL is bound-param; untrusted model output is capped + rendered as text.
