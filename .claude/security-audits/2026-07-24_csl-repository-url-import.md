# Security audit — CSL repository and URL import (2026-07-24)

## Scope

Increment 368 adds explicit public-catalog search/install and HTTPS URL import to the citation-style manager:
`GET /citations/styles/repository/search`, `POST /citations/styles/repository/install`, and
`POST /citations/styles/url/install`. It adds no dependency, database schema, background task, credential,
library/PDF/manuscript-text flow, or general-purpose proxy. Fetched CSL files enter the existing personal-style
validation and storage path.

## Egress and authority

- Repository search runs only on explicit submit. It downloads a bounded public metadata index from the fixed
  `https://www.zotero.org/styles-files/styles.json` endpoint and matches the user's query locally, so the query is
  not transmitted to Zotero. The index is cached in memory for six hours. Repository installs accept a
  grammar-constrained repository id and construct a fixed `https://www.zotero.org/styles/{id}` URL server-side;
  client-supplied repository URLs and catalog `href` values never gain fetch authority.
- URL import is a separate explicit user action. It accepts HTTPS only, standard port 443 only, and refuses
  credentials, fragments, missing hosts, or URLs above 2048 characters. It is intentionally independent of the
  AI egress toggle: no library text is involved, and the button press is consent to fetch that public style.
- Every arbitrary hostname is resolved before each request/redirect/dependency fetch. Any non-global answer is
  rejected. When httpcore exposes the connected peer, that address is checked independently and any private,
  loopback, link-local, reserved, multicast, or otherwise non-global peer is rejected, closing the DNS-rebinding
  route in the production transport.

## Fetch and validation bounds

- Redirects are followed manually, capped at four hops after the initial request, and every destination is
  revalidated before connection. Repository redirects must remain inside the exact fixed-host path grammar.
- The repository index is capped at 5,000,000 streamed bytes and 20,000 rows. Each CSL response is capped at
  1,000,000 streamed bytes, including a `Content-Length` precheck and a mid-stream counter, and must decode as
  UTF-8 text.
- Fetched files then pass the existing DTD/entity, 20,000-element, 100-level, namespace, version, metadata,
  canonical-id, citation-layout, and real citeproc validation. Response metadata renders only through React text.
- Dependent styles may name a parent. Repository parents must remain canonical Zotero style ids. URL-import
  parents are subjected to the same arbitrary-URL guard (known Zotero HTTP canonical ids are upgraded to the
  fixed HTTPS repository URL). Cycles are rejected and the chain is capped at eight files.
- The complete chain is fetched and preflighted before any write. An update anywhere in the chain returns 409
  before persistence unless the user confirms replacement. Browser preflight returns expected failures over 200
  (no console error) and holds the exact validated chain behind a random opaque token for at most five minutes;
  the cache is capped at eight chains. Install requires the same source/mode, consumes the token after success,
  and performs no second fetch, preventing content from changing between validation and persistence. Writes
  retain the existing atomic per-file replacement, immutable bundled-style rule, deterministic ids, and
  exact-canonical duplicate handling.

## Negative-path proof

- Tests reject HTTP, credentials, fragments, nonstandard ports, private IP literals, private DNS answers, a
  private connected peer after public DNS, and a redirect to loopback before its request.
- Streamed oversize responses fail at the byte boundary. Invalid index/UTF-8/CSL, unknown repository ids,
  dependency cycles/depth, missing parents, and bundled canonical replacement fail before the requested style is
  stored.
- Hermetic tests prove repository title/acronym/format/discipline matching and dependent parent installation.
  A live isolated check installed `Journal of Experimental Psychology: General` from Zotero and resolved its
  installed bundled APA parent without touching real settings.
- API tests replace all external functions; the test suite performs no accidental live network request.

## Result

**Security Audit: PASS**
