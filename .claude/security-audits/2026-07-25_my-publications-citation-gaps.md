# Security audit — My Publications citation gaps

**Increment:** 386
**Status:** PASS

## Surface

- Explicit-refresh OpenAlex metadata reads for confirmed My Publications records.
- A bounded, local cache of candidate metadata and inspectable graph evidence.
- Existing metadata-only library import and reversible gap-dismiss actions.
- A new read-only dashboard surface; no LLM use and no manuscript/PDF text egress.

## Review checklist

- [x] Requests remain fixed to the existing OpenAlex adapter and validated `W\d+` identifiers.
- [x] Work/reference/candidate fan-out is bounded before network work and persistence.
- [x] Plain dashboard reads make no network request.
- [x] Cached JSON is bounded and treated as untrusted external metadata at render boundaries.
- [x] Imports require the existing DOI-validation/deduplication path.
- [x] Dismissal remains additive/reversible local preference state.
- [x] Errors fail closed without exposing secrets or mutating the prior cache.
- [x] Tests cover malformed identifiers, caps, failed fetches, filtering, and no-refresh reads.

## Threat review

- **Input validation / injection:** refresh accepts no caller-controlled identifier or URL. Work ids returned by
  the injected/existing adapter are revalidated as `W\d+`; strings are stripped and length-bounded before the
  local snapshot. SQL uses SQLAlchemy expressions/bound values. React escapes external titles/authors.
- **SSRF / redirect:** no new fetcher exists. All requests route through the existing `OpenAlexClient`, whose
  host is fixed to `https://api.openalex.org/works`; validated work ids become only filter/path components.
- **Data egress / privacy:** only DOI/OpenAlex public identifiers for confirmed own publications and public graph
  metadata leave the machine, and only after **Find/Refresh gaps**. No PDF/manuscript/chunk/abstract/note text,
  profile name, provider key, or LLM prompt is sent. `GET` reads the local snapshot only.
- **Resource exhaustion:** at most 75 DOI-backed publications are scanned; at most 20 shared anchors advance;
  the existing adapter caps citing results at 200 per anchor; 25 candidates persist; author count, titles, DOI,
  authors, and per-anchor evidence sources are bounded. The async job keeps network latency off the request path.
- **Cache/output handling:** the single-row JSON snapshot is atomically replaced only after computation. Response
  models, `W\d+` validation, safe positive paper-id coercion, and live-source filtering drop malformed/stale cache
  material rather than rendering it or returning a 500. A real empty snapshot stays distinguishable from
  uncomputed state.
- **Writes / authorization:** Add reuses the existing DOI-required, deduplicating, metadata-only `/gaps/add`
  path; it neither acquires a file nor adds the work to My Publications. Dismiss reuses the local gap-preference
  writer. Existing access-control/read-only middleware covers the new POST route; no auth/session logic changed.
- **Secrets / supply chain / files:** no secret is read or logged, no dependency was added, and no file path,
  upload, extraction, or arbitrary write surface was introduced.
- **Failure behavior:** candidate-level graph exceptions fail closed. A refresh-level failure records a bounded
  job error and leaves the preceding snapshot intact; UI errors remain explicit.

## Negative-path evidence

- Malformed OpenAlex candidate ids are excluded before persistence.
- Malformed cached candidate/coverage JSON returns a valid empty/local response, not a 500.
- Name-only unconfirmed My Publications members do not participate.
- Directly cited, own, existing-library, dismissed, imported, and source-deleted rows are filtered.
- Plain GETs perform zero fake-client calls; only explicit refresh populates the graph.
- Injected refresh failure returns `error` and preserves the byte-equivalent prior API snapshot.
- Empty snapshots render the silence-is-not-a-certificate warning.
- Focused backend/My-Publications/gap/migration/frontend suite: 114 passed.
- Full project suite: 1597 passed, 1 skipped.
- Chromium path: candidate/evidence/Add-Dismiss affordances mount without console/page errors; mobile overflow
  assertion passes at 375×812.

## Result

**Security Audit: PASS.** No unresolved finding or accepted risk.
