# Security Audit — Literature acquisition (legally-clear OA lane, Increment B: resolver cascade)

**Status: PASS (2026-06-20) — Increment B built; per-source + structural + negative-path tests green (334 passed, 1 skipped).**

**Trigger:** six new external fetches (DOAJ, Europe PMC, CORE, arXiv, bioRxiv/medRxiv, OSF) + a Crossref-OA
read, **and** a new secret (`CALLOSUM_CORE_API_KEY`). The external-fetch + secret-handling audit-gate criteria fire.

## Scope
Increment B fans the resolver cascade out behind the Increment-A `OaLocation` seam. No new endpoint, no new
DB migration, **no new dependency** (arXiv is read with a targeted regex, not an XML parser). The download +
import path (`fetch.py`) and the bright-line seam are unchanged. The legally-ambiguous lane remains absent.

## Threat review
- **OA-assertion delegation (the core bright line):** every adapter returns an `OaLocation` **only** when the
  *source's own data* asserts an authorized OA copy with a real https PDF — DOAJ: a direct-PDF fulltext link;
  Europe PMC: `isOpenAccess=Y` + a PMCID; Crossref-OA: a registered **license** + a PDF `link` (no license →
  None, we never guess); CORE: a CORE-hosted `downloadUrl`; arXiv/bioRxiv/OSF: the preprint server's own
  record. callosum never decides OA-ness. Verified by per-source "non-OA → None" tests.
- **Structural guarantee (unchanged):** resolvers return `OaLocation | None`; the downloader takes an
  `OaLocation`, never a bare URL. A non-OA color cannot construct an `OaLocation`
  (`test_oalocation_rejects_non_oa_color`). No adapter exposes a fetch-arbitrary-URL surface.
- **Input validation / untrusted responses:** each adapter validates response shape and fails closed (never
  raises to the caller — `test_*_fail_closed`); only https PDF URLs are accepted (`OaLocation` re-enforces
  https + non-IP host); landing-page/HTML/non-https links are rejected (DOAJ HTML-only, OSF non-https tests).
  **arXiv XML is parsed with a targeted regex, NOT a stdlib XML parser** — the Atom feed is untrusted, and
  stdlib XML is exposed to XXE / entity-expansion; we read only the one `/abs/` id field (rule #4).
- **SSRF:** all download URLs come from OA-database responses, not user input; `_require_safe_https` (https +
  non-IP host) is enforced on every `OaLocation` and re-checked on every redirect hop in `fetch.py`'s manual
  redirect loop (unchanged from Increment A). Metadata lookups go only to the fixed, hard-coded source base
  URLs.
- **Secret handling (`CALLOSUM_CORE_API_KEY`):** read from `os.environ` only; sent as a Bearer **header**
  (never in a URL/query, so it cannot leak into the `external_api_cache.request_json`, which stores only the
  query string). Never logged, echoed, or written to any file/doc/test/git. `.env` / `.env.*` / `*.key` are
  gitignored. **No key → the CORE resolver is a silent no-op** (`test_core_without_key_is_noop`), so the cascade
  works for users without a CORE account. (Key was pasted in chat → user to rotate after testing.)
- **Resource / rate limits / terms:** responses cached in `external_api_cache` (per-provider) to avoid
  re-hammering; httpx timeouts on every fetch; polite User-Agent on each source; CORE limited to `limit=1`,
  Europe PMC `pageSize=1`. The download size cap (80 MiB, mid-stream) + `%PDF-`/PyMuPDF validation from
  Increment A still gate every fetched file. **Terms:** OpenAlex/Crossref polite-pool identifiers; CORE T&C
  accepted by the user (free key); arXiv/bioRxiv/OSF/Europe PMC public APIs used within etiquette (single-item
  queries, cached).
- **Supply-chain:** no new dependency (httpx + stdlib only). Nothing to pin/pip-audit beyond the existing set.

## Negative-path checks (covered by tests/test_acquisition_sources.py)
- Non-OA / not-found responses → None for every source (DOAJ empty, EPMC `isOpenAccess=N`, EPMC no PMCID,
  Crossref no-license, bioRxiv not-found, OSF no-data).
- Non-PDF / landing-only / non-https links → None (DOAJ HTML, OSF http).
- CORE with no key → no fetch, None.
- Network exception → None + cached (no re-hammer): `test_doaj_fail_closed_and_caches`.
- A non-OA color cannot construct an `OaLocation`.
- The cascade stops at the first authorized copy; a new resolver registers without editing `resolve()`.

## Verdict
**Security Audit: PASS.** Increment B adds six OA sources + a Crossref-OA read behind the unchanged
`OaLocation` seam, with OA-ness delegated to each database, https-only + SSRF-guarded fetches, the CORE key
confined to an env var + Bearer header (never persisted/logged; absent → no-op), fail-closed adapters, cached
responses, and **no new dependency** (arXiv parsed by regex, not XML). The legally-ambiguous lane remains
absent. **Follow-up:** the user rotates `CALLOSUM_CORE_API_KEY` after testing (pasted in chat history).
