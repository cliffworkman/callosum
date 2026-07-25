# Security audit - Writer heading-scoped bibliographies

**Date:** 2026-07-25
**Increment:** 380
**Result:** PASS

## Scope

- Multiple heading-scoped Writer bibliography blocks alongside the full bibliography.
- Bookmark identity/inventory, outline membership, filtered rendering, refresh/removal, diagnostics, flatten,
  and placement-conversion interaction.

## Findings

- **Ownership is strict and bounded.** A block requires one exact adapter prefix plus a 32-character lowercase
  hexadecimal identity and all three `SCOPE`/`START`/`END` names. Copy-suffixed, uppercase, malformed, foreign,
  or partial names are never treated as complete blocks. Inventory is capped at 50 identities.
- **Membership is document-derived.** The scope bookmark is mapped through Writer's semantic `OutlineLevel`
  hierarchy. Only recognized live citation items whose inline mark or native-note anchor lies inside that
  subtree become allowed `callosum-*` ids.
- **Filtering cannot reorder or invent output.** Section blocks project aligned entries/ids/link spans/categories
  from the same full-document citeproc response. Misaligned metadata produces an empty projection rather than
  guessed membership. Uncited full-bibliography additions cannot enter without a live section citation.
- **Output remains bounded plain text.** Existing bibliography heading/category bounds and validated HTTP(S)
  DOI/URL spans are reused. Section blocks do not create internal entry targets, preventing duplicate bookmark
  ownership or ambiguous citation destinations.
- **Mutation is recoverable.** Changed full and section blocks share the Writer UndoManager transaction.
  Rollback checks citation states plus the exact full/section managed signatures. Insert/remove use their own
  one-step contexts and verify failed insertion/removal recovery.
- **Damage fails closed.** Damaged triples are reported by diagnostics and prevent bibliography refresh or new
  block insertion. Duplicate insertion, note insertion, citation-free scopes, and the over-50 cap mutate nothing.
- **Conversion is explicitly gated.** Citation placement conversion rejects any complete or damaged section
  bibliography before style lookup/render/mutation until multi-range conversion Undo/Redo is proven.
- **No new egress, secret, dependency, endpoint, or filesystem access.** This is local ODT structure and a
  deterministic projection of the existing local render response.

## Verification

- Pure tests cover strict names, damage inventory, section projection alignment/order, and conversion refusal.
- Installed Writer focused spike proves two section blocks plus full bibliography, shared refresh repair,
  diagnostics, save/reopen, independent removal, and fail-closed conversion: **SELFTEST OK**.
- The complete installed Writer matrix finished **SELFTEST OK**; the full project suite passed
  **1582 tests with 1 skipped**. Ruff, line-budget, QA-surface, OXT-package, and diff-hygiene gates pass.
