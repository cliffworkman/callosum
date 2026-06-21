# Security Audit — My Publications (the own-papers auto-axis, inc 78)

**Status: PASS (2026-06-20) — built; hermetic + invariant tests green (361 passed, 1 skipped).**

**Trigger:** new API endpoints (`/my-publications/*`), a **new external fetch** (OpenAlex authors + works), and
a new write/ingest path (the resolver + the enrichment import-hook write axis memberships). Three audit-gate
criteria fire.

## Scope
A profile (name/variants/ORCID), an OpenAlex author client, a resolver that builds a pinned
`kind="my_publications"` axis (ORCID/DOI-confirmed members + name-only candidates), a confirm/reject decisions
store, a cache-based import hook, and the frontend. Migration 0009. **LLM-free.**

## Threat review
- **Authorship claim is facts-vs-candidates (the core principle):** ORCID/DOI matches → confirmed members
  (high confidence); name-only matches → **candidates** rendered "uncertain", never auto-confirmed; the user
  confirms/rejects (persisted). No opaque score (reuses `cluster_node_papers.confidence`). Pinned by tests
  (confirmed=0.95, candidate=0.25, rejected excluded, confirmed→manual).
- **LLM-free / no tokens:** the resolver + client + import hook make **no model calls** — author
  disambiguation is structured-metadata work. (Distinct from the inc-49 metadata enrich + the Gemini summary
  path.)
- **External calls = metadata egress, NOT the Gemini gate:** OpenAlex author/works lookups send only public
  identifiers (name / ORCID / DOIs) — the same posture as the Crossref DOI lookup — so they are correctly
  **not** behind `CALLOSUM_ALLOW_DATA_EGRESS`. httpx timeouts; **fail-closed** (the client returns None / [] and
  never raises — test-pinned); responses cached in `external_api_cache`; polite-pool `CALLOSUM_OPENALEX_MAILTO`.
  No library text leaves the machine.
- **Input validation:** the profile fields are bound-param stored; a `decide` paper_id is validated to an
  existing paper (else 404); ORCID/name are used only as OpenAlex query params (URL-encoded by httpx) + the
  created axis label is a constant. All `profile_repo` / resolver SQL is bound-param (rule #3).
- **Additive / no existing path altered:** the import hook is a **lazy-imported, try/except-guarded no-op when
  the feature is unused** (no profile / no cached works / no axis) — it cannot break import or enrichment; the
  resolver only touches the my_publications axis + the decisions store; `AxisResponse` gained an additive
  `kind` field (default "standard"). No change to scoring, summary, verification, or other axis behavior.
- **Resource posture:** author-works fetch is cursor-paginated with a page cap (~1000 works); the import hook
  is a pure DB read of the cached works (no per-import egress); a transient total fetch failure is **not**
  cached (retryable).
- **Supply-chain:** no new dependency (httpx already present).

## Negative-path checks (covered by tests/test_my_publications.py + the invariants)
- `decide` on a non-existent paper → 404; rejected paper excluded from all future runs; confirmed → manual.
- No identity → `no-identity`; resolved-to-nothing → `no-match`; dismissed → skipped unless force-refreshed.
- Import hook: matching cached DOI → added; **no profile → no-op, no axis created, no error.**
- Author client: ORCID vs name resolution, works DOI normalization + caching, **fail-closed on a network
  exception.** Route-surface + migration-head asserts updated to `0009`.

## Verdict
**Security Audit: PASS.** My Publications resolves authorship deterministically (facts vs candidates, human
confirms low confidence), is **LLM-free**, treats OpenAlex as metadata egress (not the library-text gate,
fail-closed + cached), validates inputs + uses bound-param SQL, and is strictly additive (a guarded no-op when
unused) with **no new dependency**. **Deferred:** Part 2 — the impact dashboard tab.
