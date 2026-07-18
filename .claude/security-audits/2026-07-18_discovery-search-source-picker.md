# Security audit — Discovery Search source picker (inc 296)

**Date:** 2026-07-18
**Feature:** data-driven source picker for **Discover → Search**: new read-only `GET /discovery/sources` plus optional
`source` query parameter on `GET /discovery/search`.
**Branch:** `feature/discover-search-synthesize`.
**Triggers:** new API endpoint + request-contract change on an existing public-metadata search endpoint.

## What's new

- `GET /discovery/sources` returns `{"sources":[{"kind","label"}, ...]}` from the in-process discovery
  `SourceRegistry`.
- `GET /discovery/search?q=...&source=<kind>` restricts provider fan-out to one registered provider. Omitting
  `source` preserves the prior all-provider fan-out + cross-provider dedup.

## Threat review

- **Input validation:** `q` remains capped by FastAPI (`min_length=1`, `max_length=500`) and `limit` remains capped
  (`1..50`). The new `source` query value is optional and capped (`min_length=1`, `max_length=50`), normalized to
  lowercase, and must match a registered provider kind; unknown values return 422.
- **External calls / SSRF:** the new endpoint makes no external calls. The new `source` parameter never controls a
  URL, host, path, or arbitrary import; it only selects an already-registered provider object from the local registry.
  Provider implementations keep their fixed-host public-metadata behavior (Crossref / PubMed) and use query params.
- **Egress posture:** this remains the existing public-metadata Search channel. The user query is sent only to the
  selected public metadata provider(s). No PDF text or library text is sent, and the Gemini/library-text egress gate is
  untouched. Selecting **All sources** preserves the existing fan-out; selecting one source reduces egress.
- **Injection:** no SQL is introduced. Library identity checks remain in `run_search` through existing
  repository helpers using SQLAlchemy-bound operations.
- **Authorization:** no new auth/session behavior. Same local-only API posture as the existing Search endpoint.
- **Resource caps:** source metadata is a tiny in-memory list. Search still caps `limit` at 50 and each provider
  implementation has its own clamp/fail-closed behavior. A failing selected provider returns an empty item list rather
  than a 500.
- **Output encoding:** JSON via FastAPI. Provider `kind`/`label` come from local application provider objects, not
  user input.
- **Supply-chain:** no new dependency.

## Negative-path checks

- `GET /discovery/search?q=paper&source=missing` returns 422.
- `GET /discovery/search?q=paper&source=pubmed` queries only the PubMed fake provider in hermetic tests.
- `GET /discovery/search?q=paper` with no `source` still queries all fake providers and dedups shared DOI results.
- `GET /discovery/sources` returns only registry metadata.

## Verdict

The source picker narrows an existing fixed registry; it does not add a user-controlled network target, SQL path, file
path, dependency, secret, or library-text egress path. Unknown sources fail closed.

**Security Audit: PASS**
