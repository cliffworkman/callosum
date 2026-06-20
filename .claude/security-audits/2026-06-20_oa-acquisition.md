# Security Audit — Literature acquisition (legally-clear OA lane, Increment A)

**Status: PASS (2026-06-20) — Increment A built; structural + negative-path tests green.**

**Trigger:** new external fetches (OpenAlex API + downloading a PDF over the network) **and** a new
file-ingestion path (a fetched PDF imported into the local library). Two audit-gate criteria fire.

## Scope
Increment A only: resolve a paper (DOI/PMID/title) → an OpenAlex-asserted authorized open-access PDF →
download → validate → import into the local library as a `managed` attachment, labeled with OA color /
version / source. The legally-ambiguous lane is **absent** (not built, not scaffolded).

## Threat review (to be completed during the build)
- **Input validation:** `PaperRef` validated at the API boundary; OpenAlex JSON response shape validated +
  fail-closed; fetched PDF validated (magic bytes `%PDF-` + PyMuPDF opens ≥1 page) BEFORE `ingest_pdf_scaffold`;
  size cap enforced mid-stream; the managed filename is sanitized (no path chars from metadata); the temp file
  name is a uuid/checksum, never derived from a title.
- **External-call handling:** httpx timeouts on the OpenAlex lookup and the PDF download; clients fail closed
  (never raise to the request path; the async job records `error`). **SSRF:** the download URL comes from an OA
  database (OpenAlex), not user input — but `OaLocation` still enforces https-only + rejects IP-literal/empty
  hosts, and the download disables non-https redirects.
- **Structural OA-only guarantee:** the resolver seam returns an `OaLocation` (required OA color; no "closed"
  member) and the downloader takes an `OaLocation`, never a bare URL — so there is no arbitrary/non-OA fetch
  path. Pinned by structural tests.
- **Supply-chain:** no new dependency (httpx + PyMuPDF already present).
- **Terms / polite-pool:** OpenAlex `mailto` polite-pool identifier from `CALLOSUM_OPENALEX_MAILTO`; responses
  cached in `external_api_cache` to avoid re-hammering.

## Negative-path checks (to record results)
- Non-PDF (HTML) response → rejected at ingest, no rows written, temp file removed.
- Oversized response → rejected mid-stream, temp removed.
- `OaLocation` cannot be constructed with a non-OA color or a non-https URL.
- No public function in `app/backend/acquisition/` fetches a bare URL string.

## Verdict
**Security Audit: PASS.** Increment A ships the legally-clear OA lane with the bright lines enforced
**structurally** (the `OaLocation` seam — required OA color, no "closed" member; the downloader takes an
`OaLocation`, never a bare URL) and verified by tests. **No new dependency** (httpx + PyMuPDF already present).
The negative paths above are covered by `tests/test_acquisition.py` + `tests/test_openalex_adapter.py`
(303 passed, 1 skipped): non-PDF + oversized responses rejected at ingest (no rows, temp removed);
`OaLocation` rejects a non-OA color / non-https URL / IP-literal host; `download_oa_pdf` takes `OaLocation`, not
a URL; the imported copy is a local `managed` attachment (nothing transits a server); OpenAlex clients fail
closed; the resolve path caches via `external_api_cache` (polite-pool `mailto`). The legally-ambiguous lane is
**absent** (not built or scaffolded). **Follow-up (Increment B):** CORE needs a free key + T&C
(`CALLOSUM_CORE_API_KEY`); pin + `pip-audit` any new dep introduced then.
