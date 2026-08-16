# Security audit — static online demo

**Date:** 2026-08-10  
**Status:** PASS  
**Feature:** a backend-free public build of the shared frontend over a curated immutable anomalous-is-bad
snapshot.  
**Audit triggers:** new public deployment shape; public corpus export; document redistribution; network and
credential trust boundary; more than six files.

## Threat review

- **Accidental working-library disclosure:** the exporter requires an explicit database path plus a public-source
  acknowledgement, opens it read-only, uses whitelisted SQL columns and curated IDs, strips attachment paths,
  embeds strict live response models, rejects extra fields, and scans for private keys, credentials, private field
  names, and Windows/Unix machine paths. It never discovers or defaults to a normal Callosum database.
- **Unexpected API or AI egress:** the artifact has no backend. `callosumFetch` delegates to an injected static
  provider; mutations and unknown reads fail in memory. A browser fetch guard rejects any origin/path outside the
  static deployment base, and CSP `connect-src 'self'` is defense in depth. The browser test captures requests.
- **Demo conditional as a security boundary:** it is not. There are no server/computation endpoints in the
  artifact. The runtime's disabled controls explain capability differences, while absence of deployed authority
  supplies the boundary.
- **Snapshot/schema drift:** Pydantic validation reuses live paper and synthesis response models, forbids demo-only
  extras, checks schema compatibility and internal IDs, and fails the build. Unknown nested live fields are also
  rejected before publication rather than silently ignored.
- **Static routing and framing:** a base tag plus direct-route copies support non-root reloads. Generated headers
  apply CSP, `frame-ancestors 'none'`, no-referrer, nosniff, and frame denial. Hosts that ignore `_headers` must
  reproduce those headers in their own configuration.
- **Document integrity/licensing:** only declared PDFs with an explicit redistribution license are copied. The
  exporter and builder verify SHA-256 plus PDF signatures. Attribution, license, canonical source, basis, notices,
  and verification date remain inspectable in the snapshot/about page. The CC BY-NC work constrains this artifact
  to a noncommercial deployment.
- **PDF parser supply chain:** the first implementation reused PDF.js 3.11.174 and `npm audit` correctly reported
  GHSA-wgrm-67xf-hhpq. The demo now pins PDF.js 4.10.38, loads its local ES module only in demo mode, and `npm audit`
  reports zero vulnerabilities. Normal Callosum behavior remains otherwise unchanged; upgrading its existing CDN
  pin is separate follow-up work.
- **Analytics/telemetry:** none added. External canonical/license links are ordinary user-initiated navigation,
  not background requests.
- **Build/deploy separation:** ordinary builds never create or publish public files. A manual workflow validates
  and uploads an artifact; its Pages deployment job runs only when the boolean `deploy` input is explicit.

## Negative-path checks

- Unknown nested snapshot field rejected.
- Unsupported snapshot schema version rejected with regeneration guidance.
- Credential-like marker, forbidden private field, Windows path, and Unix home path rejected.
- Existing external output directory refused before cleanup.
- Asset checksum/signature mismatch rejected.
- Non-GET provider calls return 405 locally.
- Direct synthesis route and reload exercised without Uvicorn.
- Final static artifact scanned for CDN/loopback/private-path/credential markers.
- The pinned PDF.js worker's synthetic `/home/web_user` browser-shim fallback is normalized to `/` at build time;
  vendored `.mjs` files are included in the final path/credential scan.
- Browser request capture constrained to the configured same-origin base path, with no live API request.
- Encoded and literal `..` traversal in deployment base paths rejected; document assets constrained to one
  `documents/<filename>` segment with a PDF media type and matching SHA-256.
- `npm audit` reports zero JavaScript dependency vulnerabilities after the PDF.js upgrade.
- Bandit and the strict runtime-requirements audit pass. The report-only development audit retains the repository's
  already documented `pytest 8.4.2` finding (PYSEC-2026-1845; fixed in 9.0.3); it is not shipped in the artifact.

## Result

The versioned whitelist contract, local-only provider, artifact scanning, browser request capture, CSP, licensed
asset verification, and explicit deploy gate establish the intended static trust boundary. The artifact contains
no authority that a bypassed disabled control could invoke.

**Security Audit: PASS.**
