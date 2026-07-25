# Security audit - Writer section-bibliography placement conversion

**Date:** 2026-07-25
**Increment:** 381
**Status:** PASS

## Scope

- Extend explicit Writer citation-placement conversion across existing full-document and heading-scoped
  bibliography ranges.
- Preserve one-step Undo/Redo, rollback, tracked-change refusal, and converted-copy isolation.

## Threat review

- **Untrusted bookmark names:** only strict random lowercase-hex section scope/start/end triples are inventoried;
  foreign and copy-suffixed names are ignored. Damaged triples and the existing 50-block cap fail closed.
- **Range integrity:** section membership remains derived from live citation anchors inside the stored Writer
  outline subtree. Conversion targets only exact managed pairs from that inventory.
- **Native process safety:** conversion does not remove/recreate section boundary objects or mutate them from an
  Undo callback. Only the interior between two unchanged boundary characters is replaced.
- **State collision:** the hidden conversion-state ReferenceMark scans a bounded set of main-text positions and
  rejects occupied citation, bookmark, note-anchor, or foreign-reference points instead of assuming document start.
- **Transactional failure:** all target citation and bibliography text is rendered before mutation. A failure on
  the second managed range triggers Writer Undo and exact snapshot verification.
- **Copy isolation:** save-as-converted-copy verifies the open source snapshot after Undo; the reopened copy owns
  the converted placement and both section blocks.
- **Network scope:** no new endpoint, credential, filesystem traversal, or egress path was added. Existing
  loopback-only style/render requests remain unchanged.

## Evidence

- Pure adapter/OXT suite: **135 passed**.
- Installed Writer focused scenario: **SELFTEST OK** with exact multi-range Undo/Redo, injected rollback,
  converted-copy isolation, save/reopen, diagnostics, and independent removal.
- Damaged section inventory refuses before style lookup/HTTP; empty/degenerate section blocks refuse before the
  Undo transaction begins.

## Residual risk

LibreOffice bookmark gravity is implementation-specific. The adapter therefore checks old/new stable boundary
characters before entering the transaction and verifies every section render afterward. Unsupported empty blocks
are rejected rather than repaired heuristically.
