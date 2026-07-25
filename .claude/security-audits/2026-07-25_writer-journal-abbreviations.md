# Security audit — Writer journal-abbreviation controls

**Date:** 2026-07-25
**Increment:** 385
**Scope:** document render request/response, bundled MEDLINE lookup data, maintainer refresh tool, Writer
preference/dialog, and citation/bibliography refresh.

## Threat review

- **Runtime network / egress:** normal rendering only opens the committed gzip resource. Writer sends the same
  embedded CSL records to the existing loopback Callosum endpoint; no title, ISSN, citation, or manuscript data
  goes to NLM. The sole new network path is the maintainer-invoked refresh script with a fixed official HTTPS URL.
- **Download bounds / provenance:** the refresh tool pins the final response to the exact official URL (redirects
  fail), caps NLM source bytes at 15 MB, requires at least 30,000 parsed records before replacement, records source
  URL/Last-Modified/SHA-256, writes deterministic compressed JSON atomically, and credits NLM plus the snapshot
  date and terms in `THIRD-PARTY-NOTICES.md`.
- **Bundled-data parsing:** runtime rejects a missing or over-2-MB compressed file, reads at most 8 MB + 1 byte
  from the gzip stream before rejecting oversized JSON, parses no XML/entities, and validates the two required
  mapping objects. The committed snapshot is 1.14 MB
  compressed and 3.87 MB decompressed.
- **Matching / false attribution:** MEDLINE matches canonicalized ISSN first, then exact normalized full title.
  There is no fuzzy match. Generator collisions with different abbreviations are removed as ambiguous. Missing
  matches use bounded library metadata or remain full and produce an explicit unknown warning.
- **Input validation:** the API accepts only `library`, `medline`, or `full`. Journal titles and abbreviations are
  printable, whitespace-normalized strings capped at 500/300 characters. Response warnings expose at most 20
  unknown titles.
- **Data ownership / mutation:** every transformation operates on shallow copies of embedded CSL items immediately
  before citeproc. Neither Writer ReferenceMark payloads nor library rows are rewritten. Full mode removes short
  hints only from render copies.
- **Document safety:** the preference is a removable Writer user property. Applying it uses the existing
  pre-render-before-mutation and transactional citation/bibliography refresh. If rendering or mutation fails, the
  prior preference is restored; existing refresh rollback protects all managed Writer surfaces.
- **Compatibility:** absent preference/request fields retain the historical library-short-title behavior. Styles
  that do not request a short journal title render unchanged and report that fact instead of implying success.
- **Secrets / dependencies:** no credential, token, executable dependency, schema migration, or arbitrary path is
  introduced.

## Negative-path checks

- API tests cover all three render modes, NLM precedence, library fallback, unknown-title reporting, invalid-mode
  rejection, style detection, and caller-item immutability.
- Pure adapter tests cover request normalization and style-aware feedback copy.
- Installed Writer covers library/MEDLINE/full output, bounded unknown reporting, unchanged encoded metadata,
  injected refresh failure with preference/text rollback, and save/reopen persistence.

## Result

**Security Audit: PASS**
