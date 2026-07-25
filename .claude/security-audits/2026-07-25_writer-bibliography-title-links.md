# Security audit — Writer bibliography title links

**Date:** 2026-07-25
**Increment:** 382
**Scope:** additive title-fallback spans in the existing `/citations/render-document` response and their
existing bounded LibreOffice hyperlink path.

## Threat review

- **Input validation:** a fallback requires exactly one citeproc bibliography entry id, an existing source item,
  a string title no longer than 2,000 characters, and one unique exact or ASCII-case-only match in the normalized
  rendered entry. Ambiguous, transformed, missing, oversized, and multi-source titles return no span.
- **Destinations:** DOI values are stripped only of recognized resolver/`doi:` prefixes, must begin `10.`, contain
  `/`, fit the 2,048-character cap, and contain no whitespace/control characters. Reserved path characters are
  percent-encoded before constructing an HTTPS `doi.org` URL. URL fallback uses the existing HTTP(S)-only
  validator: hostname required, credentials and whitespace/control characters rejected.
- **Output encoding / injection:** the response contains only integer offsets, lengths, and a validated URL.
  Bibliography HTML remains sanitized and unchanged. Writer inserts the citeproc plain text first and formats only
  the validated bounded span; source title text is never interpreted as UNO markup or a command.
- **SSRF / external calls / egress:** rendering remains local and makes no request to DOI or URL destinations.
  Writer follows a link only through the user's ordinary explicit hyperlink action. No LLM or new network path was
  added, and default-off egress posture is unchanged.
- **Resource caps:** existing 5,000-item/request, 20-links/entry, and 2,048-character URL caps remain. Title
  matching adds a 2,000-character title cap and performs bounded linear substring checks on an already-rendered
  entry.
- **Secrets:** no secret, credential, token, or new persistence is introduced. Credentialed URLs are rejected.
- **File/path safety:** no file path, ingestion, or write surface is added.
- **Supply chain:** no dependency or package change.

## Negative-path checks

- `tests/test_citations.py` verifies credentialed/unsafe URLs, ambiguous and transformed titles, multi-source
  entries, visible-identifier precedence, DOI prefix normalization/encoding, and a real Nature response whose DOI
  is omitted from text.
- `tests/test_libreoffice_adapter.py` retains malformed, oversized, overlapping, and out-of-range span rejection
  at the host boundary.
- The focused installed-Writer spike passed against OXT 0.27.0: real Nature title links applied inside the managed
  bibliography, visible DOI links remained primary under APA, toggle-off removed only managed links, an unrelated
  external hyperlink survived, and links persisted through save/reopen and placement conversion.

## Result

**Security Audit: PASS**
