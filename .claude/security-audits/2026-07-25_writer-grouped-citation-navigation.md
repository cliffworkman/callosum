# Security audit — Writer grouped-citation navigation

**Date:** 2026-07-25
**Increment:** 383
**Scope:** source selection for existing Writer citation fields, local Callosum deep links, and deterministic
full-bibliography bookmark navigation.

## Threat review

- **Input validation:** only embedded citation items with exact `callosum-<digits>` ids become choices. Foreign,
  malformed, empty, and duplicate ids fail closed. At most 50 source rows are inspected or displayed.
- **Document destinations:** bibliography jumps derive only `CALLOSUM_BIB_ENTRY_<digits>` names and require the
  bookmark to exist in Writer's current full-bibliography target collection. Section bibliographies deliberately
  create no duplicate targets. Excluded works therefore cannot resolve.
- **Network / egress:** the bibliography action performs no network request. Opening a cited work retains the
  pre-existing explicit browser action to the user's configured Callosum base and appends only a validated
  numeric paper id. Grouped selection does not add a provider, external host, background request, or LLM path.
- **Output encoding / injection:** source metadata is shown only as plain UNO list-box text through the existing
  bounded `Author Year — Title` formatter. It is not interpreted as markup, a dispatch URL, a bookmark name, or
  executable content.
- **Mutation safety:** choosing or cancelling a source does not rewrite document text, citation payloads,
  bibliography content, preferences, or hyperlinks. A successful bibliography action moves only Writer's view
  cursor. Missing targets return a clear message and leave the document unchanged.
- **Secrets / persistence / supply chain:** no secret, credential, new stored state, dependency, or package is
  introduced.

## Negative-path checks

- Pure tests cover malformed/foreign ids, duplicates, available-target restriction, and the 50-choice cap.
- Installed Writer coverage verifies an excluded target cannot resolve, explicit navigation works with visible
  links disabled, and the second grouped source remains navigable after ODT save/reopen.
- Installed Writer's browser-open spike replaces the chooser result with the second grouped source and confirms
  the exact numeric local deep link, without launching a browser.

## Result

**Security Audit: PASS**
