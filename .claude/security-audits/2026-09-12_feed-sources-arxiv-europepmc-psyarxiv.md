# Security audit — three new Feed sources (arXiv, Europe PMC, PsyArXiv/OSF) — inc 592 / #40

**Date:** 2026-09-12
**Scope:** three new `FeedSource` adapters that each make one external HTTP GET per poll —
`app/backend/discovery/arxiv_source.py` (arXiv Atom API), `europepmc_source.py` (Europe PMC REST),
`psyarxiv_source.py` (OSF preprints JSON:API) — plus their registration in `feed.py`.

**Trigger:** a new external fetch/integration (three new metadata/discovery services).

## Threat review

- **SSRF / URL control.** Each adapter targets a **constant host literal** (`export.arxiv.org`,
  `www.ebi.ac.uk`, `api.osf.io`). User input enters only as **query-string values** (an arXiv category token, a
  keyword, a PsyArXiv title keyword) or fixed filter/paging params — never interpolated into the host or path.
  A follower cannot redirect a fetch at an internal address. arXiv's adapter passes `follow_redirects=True`
  (arXiv's http→https 301) but the initial host is fixed and https-preferred.
- **Response-size / resource exhaustion.** Every fetch goes through **`bounded_get`** (`integrations/http_bounds`,
  backlog #56) with an explicit `max_bytes` cap (4 MB arXiv, 8 MB the two JSON APIs), so a pathological/oversized
  response is rejected before it is fully buffered. Each source also caps items to the caller's `limit` and its
  own `max_results`/`page_size`.
- **Untrusted-input parsing.** arXiv returns XML → parsed with `xml.etree.ElementTree` **behind a
  DOCTYPE/ENTITY + NUL guard** (`_safe_parse`), the same XXE/billion-laughs defense the GROBID TEI parser uses
  (ElementTree already blocks external entities; the guard blocks internal-entity expansion and the UTF-16
  NUL-interleaved `<!DOCTYPE` bypass by checking the decoded text and rejecting NUL). Europe PMC and OSF return
  JSON, parsed defensively (every field access tolerates a missing/oddly-typed node — e.g. the OSF
  contributor-embed parser skips a malformed contributor rather than raising; a "not-a-list" embed is handled by
  a regression test).
- **Failure behavior.** A non-200 (arXiv 429 rate-limit, Europe PMC 503, an OSF error) or a malformed body
  returns **`[]`**, and `refresh_subscriptions` already isolates one raising source from the rest of a poll — one
  throttled/broken source never aborts a Feed refresh (verified live: arXiv 429 → `[]`, Europe PMC 503 → `[]`).
- **Egress posture.** These are **public-metadata** GETs (like the existing bioRxiv/PubMed/Crossref feeds), NOT
  the Gemini library-text egress gate — no library text or user content leaves the machine; the request carries
  only a category/keyword and paging. No auth token or credential is sent to any of the three.
- **No new write path / no PDF ingest.** The adapters only read metadata into the existing `FeedEntry`/feed
  upsert path; they create no files and open no new persistence surface.
- **Rate-limit / politeness.** arXiv asks ~1 req/3s and 429s on bursts; a Feed poll issues one request per
  subscription per refresh (no background polling — the existing pull-first design), and `max_results` is kept
  modest (25) to stay fast and light. Europe PMC/OSF have no documented limit for this light use.
- **Supply chain.** No new dependency — reuses `httpx` (via `bounded_get`) and stdlib `xml.etree`.

## Negative-path checks (performed)
- arXiv `_safe_parse` rejects `<!DOCTYPE …[<!ENTITY…]>` and a NUL-bearing body → `None` → `[]` (unit test).
- Malformed / non-XML arXiv body → `[]`; Europe PMC 503 and arXiv 429 (observed live) → `[]`.
- OSF record with a `"not-a-list"` contributors embed and empty attributes → no raise, `authors=()` (unit test).
- Each source with a blank/empty value → `[]` (no fetch).
- Live contract probes returned only public metadata; no field is written unsanitized (the feed's existing
  `FeedEntry` mapping is the boundary).

**Security Audit: PASS**
