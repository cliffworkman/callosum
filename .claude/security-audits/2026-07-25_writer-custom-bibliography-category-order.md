# Security audit - Writer custom bibliography category order

**Date:** 2026-07-25
**Increment:** 379
**Result:** PASS

## Scope

- Document-local category-order metadata and deterministic grouping precedence.
- Writer category reorder/reset dialog.
- Refresh, failure rollback, links, conversion, and save/reopen interactions.

## Findings

- **Metadata is independently bounded.** The raw property is capped at 8 KiB before JSON parsing and must be a
  list of at most 50 unique text labels. Existing category validation enforces printable, nonblank,
  single-line labels of at most 80 characters and reserves **Other references**.
- **Corrupt input fails alphabetical.** Non-list, oversized, duplicate, blank, non-text, control-character, or
  reserved-label stored data returns no custom order. It cannot partially influence grouping.
- **Stale metadata is harmless.** Only active category labels participate in rendering. Stored inactive labels
  affect neither output nor links; active labels missing from the saved order follow configured groups
  alphabetically.
- **Output remains plain text.** Order values only rank already-validated active category labels. They are never
  interpreted as HTML, URLs, bookmarks, file paths, properties, commands, or subprocess arguments.
- **Mutation is recoverable.** Save validates and writes one property, then performs one bibliography-only
  refresh. Render/UNO failure restores the exact previous raw property while the existing Writer transaction
  restores the managed block. Cancel writes nothing; reset removes the property.
- **Links remain aligned.** Ordering reuses the Increment 377 category-aware layout, entry-bookmark movement,
  and validated DOI/URL span offsets. **Other references** is generated and always placed last.
- **No new egress, secret, dependency, endpoint, or filesystem access.** The feature is local ODT metadata and
  deterministic Writer formatting.

## Verification

- Pure tests cover explicit precedence, unranked alphabetical fallback, metadata bounds/corruption, one-refresh
  save/reset, and exact raw-property rollback.
- Installed Writer focused spike proves custom order, reopen, placement conversion, DOI links, and alphabetical
  reset: **SELFTEST OK**.
- Installed Writer full matrix: **SELFTEST OK**.
- Full project suite: **1579 passed, 1 skipped**.
- Ruff, line-budget, QA-surface, OXT-package, and diff-hygiene repository gates pass.
