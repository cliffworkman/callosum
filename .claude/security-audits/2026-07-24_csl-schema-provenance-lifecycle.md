# Security audit — CSL schema, provenance, updates, and duplication (2026-07-24)

## Scope

Increment 369 adds official local schema validation, a local provenance sidecar, explicit remote update checks,
and independent style duplication. It adds two localhost API routes, one file-write path, and one declared runtime
dependency (`lxml`). Remote checks reuse increment 368's guarded downloader and exact-byte preflight cache.

## Threat review

- **Input/XML:** local, repository, URL, and generated copies remain capped at 1,000,000 bytes, 20,000 elements,
  and 100 levels; DTD/entity declarations are rejected. `lxml` parses with DTD loading, entities, network access,
  recovery, and huge trees disabled. The official tagged CSL 1.0.2 RELAX NG schema then validates structure and
  the official Schematron validates macro existence/uniqueness before citeproc executes the style.
- **Files/paths:** style ids remain server-generated/constrained. Provenance is one fixed `provenance.json` beside
  personal styles, written through an atomic same-directory replacement with owner-only permissions where
  supported. Client filenames are reduced to a basename and cannot select a path. Malformed/unreadable metadata
  fails soft; removal cleans only the selected constrained record. Duplication reads only server-owned installed
  style paths and writes through the existing custom-style allocator.
- **Identity/injection/output:** a duplicate receives a random UUID-backed Callosum canonical URL and removes any
  `independent-parent` link, then revalidates the resulting standalone XML. Source ids/URLs/timestamps are bounded;
  React renders them as text, and source links come only from previously guarded HTTPS imports or fixed repository
  URLs. API style ids remain grammar-constrained by the store lookup.
- **SSRF/egress:** update checks are available only for styles with persisted repository/URL provenance and run
  only on `POST .../check-update`. They call the same fixed-repository or HTTPS/private-DNS/connected-peer guarded
  path audited in increment 368. Installed custom parents are checked; bundled parents are never replaced.
  Applying an update consumes the exact cached preflight token and performs no second fetch. No background timer,
  library/PDF/manuscript content, credential, or LLM egress is added.
- **Resources/concurrency:** provenance records and fields are bounded, JSON writes are locked in-process, prepared
  chains retain the existing five-minute/eight-entry bounds, dependency depth remains eight, and validator use is
  serialized around cached compiled schemas.
- **Supply chain:** `lxml>=5,<7` is declared in both runtime dependency sources and lockfile; it is BSD-3-Clause and
  already present in the development environment. The two official validation assets are generated from the CSL
  schema repository's immutable `v1.0.2` tag and ship with that repository's complete MIT license. The lock is
  SHA256-pinned and passes offline consistency verification. A live `pip-audit` attempt did not return within two
  minutes in this environment, so that external advisory lookup is recorded as unavailable rather than inferred.

## Negative-path proof

- Focused tests reject an otherwise parseable unsupported CSL attribute and a missing macro; existing malformed,
  DTD/entity, oversize, deep, missing-title/id/layout, invalid-class, bundled-replacement, and dependency failures
  remain clean 422 responses.
- Tests prove a dependent style omits the schema-forbidden root `class`; a dependent copy becomes independent,
  receives a new canonical id, previews through citeproc, and leaves its source installed.
- Tests prove repository/local/URL/copy provenance, parent provenance, removal cleanup, no update call before the
  explicit check, preserved exact-byte token, and detection/application of an updated installed custom parent.
- Increment 368's redirect, private DNS/peer, URL grammar, byte, cycle, and depth tests continue to cover the reused
  remote boundary.

## Result

**Security Audit: PASS**
