# Security audit - Writer categorized bibliographies

**Date:** 2026-07-25
**Increment:** 377
**Result:** PASS

## Scope

- Document-local paper-id/category metadata stored in Writer user properties.
- Category assignment/removal from the existing Citations in this document panel.
- Reordering and category-heading insertion inside the bounded managed bibliography.
- Interaction with uncited/excluded membership, internal targets, DOI/URL links, refresh, conversion, and reopen.

## Findings

- **Identifiers and labels are constrained.** Assignment keys must be numeric Callosum paper ids. Labels are
  trimmed, at most 80 characters, and printable single-line text; the generated **Other references** label is
  reserved so user data cannot create an ambiguous duplicate group.
- **Document metadata is bounded.** The raw property is capped at 128 KiB before JSON parsing; paper ids at 20
  digits; and the decoded map at 1,000 assignments and 50 case-insensitive categories. Case variants reuse one
  canonical label. Corrupt JSON, a non-object value, or an over-cap stored map degrades to an ordinary
  uncategorized bibliography instead of partially trusting adversarial document metadata.
- **Output is plain text.** Category labels are inserted through Writer's plain-string API inside the established
  bibliography bookmark pair. They are never interpreted as HTML, a field name, bookmark name, URL, file path,
  or subprocess argument.
- **Ambiguous entries fail uncategorized.** A citeproc entry is grouped only when every represented paper id has
  the same category. Missing, mixed, malformed, or unknown ids remain visible under **Other references**.
- **Mutation remains bounded and recoverable.** The category map is changed before an explicit bibliography-only
  refresh; a render or Writer failure rolls back the managed bibliography through the existing UndoManager
  transaction and restores the complete prior map. Prose and content outside the bookmark pair are untouched.
- **Links stay aligned.** Entry bookmarks move with their reordered entries, while DOI/URL offsets are recomputed
  from the exact category-aware layout. Real Writer proves both internal targets and external links survive
  grouping, save/reopen, and citation placement conversion.
- **No new egress, secret, dependency, or file access.** Categories are local ODT metadata and deterministic
  Writer formatting. No endpoint, network request, token, filesystem path, package, or subprocess was added.

## Verification

- Pure tests cover deterministic grouping, style-order preservation, mixed-entry fallback, exact offsets,
  case canonicalization, reserved/oversized/control labels, panel projection, and failure rollback.
- Focused citation/LibreOffice/OXT/install/help suite: **210 passed**.
- Installed Writer focused spike and full matrix: **SELFTEST OK**, including links, conversion, save/reopen,
  invalid-input no-op, partial removal, and final ordinary-layout restoration.
- Full project suite: **1577 passed, 1 skipped**.
- Ruff check/format, line budget, QA surface map, OXT packaging, and diff hygiene: **PASS**.
