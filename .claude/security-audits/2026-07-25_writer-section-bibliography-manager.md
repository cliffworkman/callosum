# Security audit — Writer section-bibliography manager

**Date:** 2026-07-25
**Increment:** 384
**Scope:** document-ordered section-bibliography inventory/navigation, selected removal, confirmed remove-all,
and runtime Writer Undo/Redo recovery.

## Threat review

- **Input validation / ownership:** only exact adapter-owned lowercase-hex scope/start/end bookmark triples are
  listed or mutated. The existing 50-block cap remains. Unknown/copy-suffixed bookmarks are ignored; incomplete
  triples are reported and make bulk removal fail closed.
- **Document boundaries:** labels come from Writer outline headings and are bounded to 120 characters. Work counts
  are distinct embedded Callosum ids inside the recorded heading subtree. Jump targets only a validated managed
  start bookmark. Removal selects exactly between that block's start/end pair and separately removes its scope
  marker; it never selects heading prose, citations, another section, or the full bibliography.
- **Destructive action / confirmation:** selected removal is explicit. Remove-all requires a yes/no confirmation
  with No as the safe default and states the exact block count plus the surfaces that remain unchanged.
- **Rollback / Undo:** selected and bulk removal use one named Writer Undo context. Real Writer exposed a native
  empty-range restoration edge case during injected failure. A document-runtime listener now keys bounded
  recovery snapshots by strict block identity, repairs the current state under a locked Undo manager, and is
  cleared with the document/Undo history. Current local render plans restore text, categories, and managed
  DOI/title links; offline/stale fallback restores exact plain text and marks bibliography formatting pending.
- **Resource caps:** at most 50 rows and blocks are processed. Recovery snapshots are interned by block id and
  exact contents so successive removals share stored payloads instead of duplicating every surviving block per
  Undo state. State is runtime-only and discarded when Undo history or the document is cleared.
- **Output encoding / injection:** heading text and counts are plain UNO list-box labels, never markup, bookmark
  names, URLs, or dispatch commands.
- **Network / egress:** removal can optionally use the existing local Callosum render endpoint to preserve current
  managed link spans through Undo. Failure/offline operation remains available without that plan. No new endpoint,
  external host, provider, LLM path, or background request is introduced.
- **Secrets / files / supply chain:** no credential, file path, persisted setting, dependency, or package change.

## Negative-path checks

- Pure tests cover bounded manager-row count wording and strict/damaged bookmark inventory.
- Installed Writer verifies heading order/counts, second-block jump, selected removal, confirmed bulk core removal,
  one-step Undo/Redo, unchanged citations/full bibliography, exact managed-link restoration, and save/reopen.
- Installed Writer injects failure on the second block after the first is deleted and verifies both blocks and
  links return exactly before the original exception propagates.

## Result

**Security Audit: PASS**
