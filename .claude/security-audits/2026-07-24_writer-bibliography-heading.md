# Writer bibliography heading security audit

**Date:** 2026-07-24  
**Increment:** 374  
**Surface:** LibreOffice Writer `Bibliography heading…`

## Threat review

- **Input validation:** the document heading is capped at 120 characters, trimmed, and limited to printable
  single-line text. Blank input has one explicit meaning: remove the custom property and restore `References`.
- **Output encoding / injection:** Writer receives the value only through `XText.insertString`; it is never
  interpreted as HTML, XML, a UNO service name, a URL, a path, or a format string.
- **Persistence:** the value is one removable ODT user-defined property. It cannot select another document range
  or escape the existing start/end bookmark pair.
- **Failure behavior:** formatting happens before Writer mutation. If refresh fails after the property changes,
  the prior property is restored; the established transactional bibliography writer rolls back partial text
  mutations.
- **SSRF / egress:** no endpoint or external integration is added. The command uses the existing loopback
  citation-render request required by explicit bibliography refresh.
- **Secrets / authorization:** none.
- **Resource caps:** 120-character input cap; no recursion, file expansion, or unbounded collection.
- **File paths / writes:** no new filesystem path. Persistence is inside the Writer document the user is editing.
- **Supply chain:** no dependency added.

## Negative-path evidence

- Pure tests cover blank/default normalization, surrounding whitespace, oversized input, multiline input,
  explicit refresh, and prior-property restoration after an injected refresh failure.
- The installed OXT `0.19.0` roundtrip returned **SELFTEST OK**, covering paused automatic rebuilding,
  invalid-input no-mutation, save/reopen persistence, and blank reset. The first launch stopped before the
  self-test because the isolated UNO port did not open; an exact clean retry passed.

## Result

**Security Audit: PASS**
