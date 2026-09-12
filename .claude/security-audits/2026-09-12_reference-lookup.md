# Security audit — Reader "Find referenced paper…" reference lookup (inc 595)

**Date:** 2026-09-12
**Scope:** `POST /references/resolve` (`app/backend/api/routers/reference_lookup.py`), the read-only resolver
(`app/backend/metadata/reference_resolver.py`), and the new Crossref `query.bibliographic` fetcher
(`app/backend/discovery/crossref_provider.py::bibliographic_search`). Frontend: `30h_reference_finder.jsx`,
`SelectionPicker` in `30g_pdf_selection.jsx`.
**Trigger:** audit gate #1 (new API endpoint) + #2 (a new external-call *shape* — a raw citation string sent to
Crossref's search endpoint; the Crossref *host* is already an audited dependency).

## What the feature does
A user selects a reference in the PDF reader and clicks **🔎 find paper**. The selected text is sent to
`POST /references/resolve`, which (a) extracts a DOI if present and resolves it via the existing cached
`CrossrefClient.resolve_doi`, or (b) queries Crossref `query.bibliographic`, gates results by inspectable
title/author/year agreement, and marks each candidate `in_library`. It **creates nothing**. On explicit
confirmation the browser calls the existing, already-audited `POST /discovery/save` then
`POST /papers/{id}/acquire-oa`.

## Threat review

- **Input validation.** `text` is a Pydantic field `min_length=1, max_length=2000`; the resolver additionally
  NFKC-normalizes, collapses whitespace, and hard-bounds to `MAX_REFERENCE_LEN` (2000) before use. Empty →
  `none`; oversized → 422 at the boundary. No other request fields.
- **Injection.** No SQL is built from request data — the only DB access is `find_existing_paper_by_identity`
  (SQLAlchemy Core bound parameters) and `CrossrefClient`'s own parameterized cache. The DOI is extracted by a
  fixed regex (`metadata.doi.DOI_PATTERN`) and normalized; it is passed to Crossref via `httpx` `params=` (URL-
  encoded), never string-concatenated into a URL.
- **SSRF / external calls.** The only outbound host is Crossref, a fixed constant (`CROSSREF_SEARCH_URL` /
  `CROSSREF_BASE_URL`). The user controls the *query text*, never the URL/host/scheme. No user-supplied URL is
  ever fetched. No redirects are followed to attacker-chosen hosts (httpx default; Crossref is HTTPS-fixed).
- **Data egress / consent.** The request carries a bibliographic reference string to Crossref — the SAME
  posture as the existing Discover → Search (`/discovery/search`), which is explicitly *not* the Gemini
  library-text egress gate. It is user-initiated per action (the explicit click), never automatic: selecting or
  highlighting text sends nothing. No library full text, no PDF content, no chunks, no secrets leave the
  machine. Confirmed: with `CALLOSUM_ALLOW_DATA_EGRESS` unset, the flow makes **no** `generativelanguage`/Gemini
  request (it never routes through `llm/providers.py`).
- **Resource caps.** `bibliographic_search` uses `bounded_get(max_bytes=METADATA_RESPONSE_CAP)` (10 MB stream
  cap, `ResponseTooLargeError` before over-buffering) and caps `rows` to ≤20; the resolver returns ≤`BIB_LIMIT`
  (5) candidates. The DOI path reuses `CrossrefClient`'s already-bounded, cached fetch.
- **File-path safety.** None — the resolver touches no filesystem path; it never builds a path from input.
- **Output encoding.** The response is a typed Pydantic model (`classification` is a closed `Literal`;
  candidates carry only title/authors/year/venue/doi/url/in_library/existing_paper_id). No abstract or raw
  provider blob is echoed. The frontend renders values as React text nodes (no `dangerouslySetInnerHTML`).
- **Secret handling.** No secrets are read, logged, or returned. The polite-pool `mailto` (non-secret) is the
  only header material, reusing the existing `resolved_mailto` seam.
- **Write safety.** The resolve endpoint is strictly read-only (no `create_paper`, no commit). The add + OA
  steps are the pre-existing, separately-audited `/discovery/save` (deduped write inside `run_write`) and
  `/papers/{id}/acquire-oa` (per-paper-deduped job). A failed OA fetch cannot undo the metadata add (they are
  separate transactions/jobs — the inc-587/#58 decoupling).
- **Supply chain.** No new dependency. Reuses `httpx` (via `bounded_get`), the existing Crossref client, and
  stdlib (`re`, `unicodedata`).

## Negative-path checks (concrete results)
- Empty `text` (`""`) → **422** (`test_endpoint_rejects_empty_and_oversized_input`).
- Oversized `text` (2001 chars) → **422** (same test).
- Crossref transport failure (fetcher raises) → resolver returns `classification="none"`, `error` set to a
  human-readable message, and **zero** papers created — verified before/after row count
  (`test_crossref_failure_returns_error_and_creates_nothing`).
- Ordinary non-reference prose → the agreement gate suppresses the unrelated hit → `none`
  (`test_ordinary_prose_is_gated_out_to_none`).
- Ambiguous input → `multiple_candidates`, all surfaced, none auto-selected
  (`test_ambiguous_reference_returns_multiple_and_never_auto_picks`).
- Already-in-library DOI → `in_library:true` + `existing_paper_id`, surfaced not duplicated
  (`test_already_in_library_is_marked_with_existing_id`).
- Egress: no genai host is contacted (the resolver never imports/calls `llm/providers.py`); asserted by the
  QA route's standing egress assertion (route 94).

## Result

**Security Audit: PASS.** The endpoint is read-only, input-bounded, host-fixed (no SSRF), response-size-capped,
and sends only public bibliographic metadata (not gated library text) on an explicit per-action click. The add
and OA steps reuse existing audited paths with their existing dedup and OA/metadata decoupling.
