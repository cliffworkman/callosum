# Increment 364 — LibreOffice explicit citation placement conversion

## Context

Increments 362–363 added real Writer footnotes/endnotes and deliberately refused silent relocation. P1 item #10
still required an explicit conversion workflow that could move an existing eligible manuscript between inline,
footnote, and endnote placement without guessing about ambiguous note content.

## Implemented

- **Callosum → Convert citation placement…** presents bounded target-style and footnote/endnote choices, then
  previews source placement, target placement, and live-citation count.
- The user chooses either **This document (one Undo step)** or **A separate .odt copy**.
- Conversion inventories the full document and refuses no fields, same placement, mixed/unsupported placement,
  tracked changes, malformed/newer fields, duplicate citation IDs, damaged bibliography bounds, multiple live
  clusters per source note, non-Callosum marks sharing a note, or any source note containing user prose.
- The complete target sequence, bibliography, uncited additions, and bibliography exclusions render before the
  first Writer mutation.
- Eligible fields relocate in reverse document order while preserving each encoded mark name/citation ID and
  their final document order. Native Writer footnote/endnote indexes are verified against `1..n`.
- A zero-width `CALLOSUM_CONVERSION_STATE` ReferenceMark carries the target style, locale, note placement, and
  dirty flags. It participates in Writer's native Undo context, unlike user-defined document properties.
- A document-local `XUndoManagerListener` reacts only to the named conversion action and re-wraps Writer's
  already-restored bibliography text with the recorded managed bookmark pair. This works around Writer restoring
  bibliography text but not the destroy/recreate bookmark pair byte-for-byte.
- Post-mutation verification checks field identity/order/count, placement, note indexes, visible renders,
  preferences, and bibliography. Any exception closes and undoes the transaction, then compares the complete
  pre-conversion snapshot.
- Separate-copy mode converts, stores an ODF copy, undoes the open document, clears Redo, and verifies the open
  document's exact snapshot before reporting success.
- Extension version bumped 0.13.0 → 0.14.0. The native harness timeout rose from 300s to 480s because the new
  Undo/Redo/rollback/copy fixture adds several full Writer render/save cycles.

## Empirical findings

1. A Python `XUndoAction` passed through the external UNO test bridge fails with
   `SystemError: can't import __main__ module`; packaging the class in a top-level module does not change that
   cross-process limitation.
2. Writer natively undoes the zero-width conversion state mark with the field relocations, so no custom undo
   action is needed for preferences.
3. The existing bibliography rebuild restores text under Undo but not the recreated same-name bookmark pair.
   An `XUndoManagerListener` is bridge-safe (the adapter already uses UNO listeners) and can repair only those
   zero-width boundaries without touching restored text.
4. One native run reached the old 300-second harness limit while continuing through later fixtures; 480 seconds
   provides headroom. A later run hit the already-documented transient UNO startup miss; the unchanged retry
   completed.

## Verification

- Focused adapter/OXT/install suite: **111 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** with the installed 0.14.0 OXT.
- Real Writer proves inline→footnote, Undo, Redo, footnote→endnote, endnote→inline, exact citation identities,
  note indexes, target preferences, bibliography state, user-prose refusal without mutation, injected failure
  rollback, and separate-copy isolation/reopen.
- Full project suite: **1501 passed, 1 skipped**.

## Gates

- **Principles / governance:** non-triggering. This is deterministic, local, user-invoked document formatting;
  it creates no claim, signal, ranking, recommendation, or judgment.
- **Security:** `2026-07-23_libreoffice-placement-conversion.md` is **PASS**.
- **QA:** no browser route or server API changed. Menu/action packaging has pure OXT coverage; mutation, refusal,
  Undo/Redo, rollback, persistence, and copy isolation have real installed-Writer coverage.

## Experience pass

A deadline humanities writer can take an APA inline manuscript, choose Chicago notes and Footnotes, review the
count, and convert it in one explicit action. They can immediately Ctrl+Z back to the exact APA document or choose
a separate copy instead. A note containing explanatory prose is not moved or partially rewritten; Callosum names
the refusal and leaves the document unchanged. The project no-delegation instruction prevented the usual persona
subagent, so this walkthrough was performed locally against the deadline-citer workflow.

## Manual verification debt

Install 0.14.0, open a saved inline APA document with a managed bibliography, and run **Callosum → Convert citation
placement… → Chicago notes and bibliography → Footnotes → This document**. Confirm native notes and bibliography,
then Ctrl+Z/Ctrl+Y and inspect both document text and bibliography. Repeat with **A separate .odt copy** and confirm
the open document remains unchanged.

## Next

Continue P1 item #10 only for ambiguity that can be modeled without guessing: multiple clusters/prose in one
note, tracked-change semantics, and broader ibid/near-note style/context coverage.
