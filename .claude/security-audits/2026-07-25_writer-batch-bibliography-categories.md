# Security audit - Writer batch bibliography categories

**Date:** 2026-07-25
**Increment:** 378
**Result:** PASS

## Scope

- Multi-selection and reusable category choices in the existing Writer document-citations panel.
- Transactional multi-paper category assignment/removal over the Increment 377 document property.
- Interaction with bibliography refresh, rollback, links, conversion, and save/reopen.

## Findings

- **The existing trust boundary is unchanged.** Category data remains local Writer user-property text. The
  panel adds no endpoint, egress, secret, dependency, filesystem path, subprocess, or new document surface.
- **Batch input is bounded before mutation.** Paper ids are string-normalized, deduplicated in stable order,
  limited to 1,000 unique works, and required to be numeric with at most 20 digits. The existing total-map,
  category-count, label-length/control-character, raw-property, and reserved-label caps still apply.
- **Picker sentinels cannot become document data.** Internal create/remove/choose values contain a newline,
  which the category validator rejects. The panel resolves them before calling the setter; mixed selection's
  choose sentinel and cancelled/blank create input are no-ops.
- **One atomic logical operation.** The adapter computes the complete updated map, validates/serializes it once,
  writes once, and performs one bibliography-only refresh. Render/UNO failure restores the complete previous
  map while the existing Writer UndoManager restores the managed bibliography.
- **Ambiguous actions fail closed.** Multiple or uncited selections cannot silently navigate or alter exclusion.
  The panel explains the constraint and remains open. Category operations may intentionally include cited and
  uncited works because both can be visible bibliography members.
- **Output and link safety are inherited.** Category labels remain plain Writer text inside the bounded managed
  bibliography. Batch grouping still uses the same category-aware entry bookmarks and validated DOI/URL spans.

## Verification

- Pure tests cover batch deduplication, one refresh, shared-label canonicalization, full-map rollback, the
  1,000-work bound, filtered multi-selection mapping, deterministic reusable choices, and mixed-selection no-op.
- Installed Writer focused spike batch-assigns/reassigns/clears categories and preserves layout, DOI links,
  placement conversion, and save/reopen behavior: **SELFTEST OK**.
- Installed Writer full matrix: **SELFTEST OK**.
- Full project suite: **1578 passed, 1 skipped**.
- Ruff check/format, line budget, QA surface map, OXT packaging, and diff hygiene: **PASS**.
