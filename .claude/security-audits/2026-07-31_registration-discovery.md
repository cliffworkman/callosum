# Security and privacy audit — registration discovery

**Date:** 2026-07-31
**Increment:** 427
**Status:** PASS

## Surface

An explicit paper action queries public OSF and DataCite JSON APIs using paper DOI/title and detected registration
identifiers, then stores candidate metadata and user confirmation/rejection decisions. Direct non-OSF references are
surfaced locally. No registration artifact is downloaded in this increment.

## Threat review

- **Unexpected egress:** opening Methods, reading transparency evidence, loading stored candidates, saving manual
  references, and direct-reference candidate creation are local. A POST is rejected unless `metadata_consent=true`.
  The UI fetches a local preview and displays exact outbound vs local-only fields before the user starts discovery.
- **Document leakage:** provider requests contain no abstract, chunks, PDF text, registration text, notes, tags,
  annotations, synthesis, or embedding. Tests inspect the provider request object and pin the absence of an abstract or
  full-text field.
- **SSRF/open redirects:** user-pasted URLs never enter the HTTP fetcher. OSF/DataCite providers construct URLs from
  fixed `https://api.osf.io/v2` / `https://api.datacite.org` origins and validated/escaped identifiers. The bounded
  client sets `follow_redirects=False`; no redirect target is followed.
- **Resource exhaustion:** JSON bodies are capped at 5 MiB, each request has a 20-second timeout, OSF node and
  DataCite query results are capped at 10, and contributor reads are capped at 50.
- **Content handling:** responses must be HTTP 200, valid JSON, and a top-level object. Unexpected status/shape fails
  closed as a classified provider error. React renders returned metadata as text; external navigation uses a new
  no-opener browser context.
- **Provider isolation:** registry exceptions become per-provider error reports. Candidate writes occur only after all
  provider calls return and in a transaction; a provider failure cannot delete existing candidate/link rows.
- **Credentials/privacy:** no Callosum credential, browser cookie, auth token, or registry login is used. User-agent is
  generic. Discovery queries only public metadata endpoints and does not scrape search engines or authenticated pages.
- **Candidate confusion:** candidates remain unattached, confirmation is a separate local write, and status/evidence
  classes avoid “verified/correct/compliant.” Reject state persists; a fresh search is explicit.
- **Database input:** all persistence uses SQLAlchemy bound expressions. The table has controlled status/linkage checks
  and foreign keys; one registration may be represented on multiple paper rows without forced one-to-one identity.
- **Dependencies/supply chain:** no dependency or executable was added; existing `httpx` is reused.

## Negative-path evidence

- Consent false returns 422 before provider invocation.
- Preview and stored-candidate GETs invoke no provider.
- A broken provider does not suppress a local direct-reference candidate.
- OSF project results remain confirmation-required; withdrawn state is retained.
- DataCite typed relation values are retained rather than collapsed into a score.
- Candidate confirmation creates no attachment and downloads no content.
- Rejection suppresses ordinary repeat searches; only a requested fresh search resurfaces it.
- Hermetic tests perform no registry egress.

## Result

**PASS.** Metadata discovery is deliberate, bounded, fixed-origin, credential-free, provider-isolated, and
evidence-preserving. Increment 428 registration artifact acquisition requires its own URL/content/file/version audit.
