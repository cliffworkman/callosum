# Security audit - Writer citation-to-bibliography links

**Date:** 2026-07-24
**Increment:** 375
**Result:** PASS

## Scope

- Additive `bibliography_entry_ids` output from the local citeproc sidecar and Python render contract.
- Stable Writer bibliography-entry bookmarks and document-local citation hyperlinks.
- Document preference, refresh/placement-conversion persistence, menu packaging, and installed-Writer proof.

## Findings

- **No new egress or dependency.** The feature uses the existing local render endpoint, bundled citeproc-js,
  Writer bookmarks, and `HyperLinkURL`; it introduces no network destination, subprocess argument, or package.
- **Destinations are constrained.** Only adapter-owned ids matching `callosum-<digits>` become
  `CALLOSUM_BIB_ENTRY_<digits>` bookmarks. User/request text cannot become a URL, path, bookmark name, or markup.
- **Ambiguity fails plain.** A citation links only when it contains exactly one work that has a rendered
  bibliography entry. Grouped citations and excluded works receive no Callosum link.
- **Unrelated links are preserved.** Disable/refresh removes only `#CALLOSUM_BIB_ENTRY_*` destinations; an
  external or manually authored hyperlink is retained.
- **Mutation remains transactional.** Citation text/link changes and bibliography target rebuilds share the
  established Writer UndoManager transaction. The rollback oracle now verifies both visible text and managed URL.
- **Bounded bibliography invariant remains.** Entry targets are inserted inside the existing start/end bookmark
  pair; rebuild removes only the reserved target prefix and never selects through document end.
- **Backward compatibility is additive.** Existing `bibliography_text` and `bibliography_html` fields are
  unchanged. Missing/misaligned sidecar metadata degrades to entries without targets rather than guessing.

## Verification required

- Pure tests for ordered ids, excluded/uncited membership, stable names, ambiguity, rollback preference, menu.
- Installed Writer toggle-on/off and save/reopen proof with single/grouped citations.
- Full project, lint, dependency-lock, line-budget, surface-map, and OXT packaging gates.
