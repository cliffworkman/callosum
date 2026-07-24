# Increment 373 - Tracked-change-aware Writer placement conversion

## Context

P1 note-style item #10 had one remaining limitation: placement conversion rejected every document containing a
Writer tracked change. That was safe but unnecessarily broad. Prose redlines outside Callosum-managed content do
not need to be accepted or rejected just to move live citations between inline text, footnotes, and endnotes.

## Implemented

- Conversion enumerates Writer redlines through `XEnumerationAccess` and reads their authoritative
  `RedlineStart`/`RedlineEnd` ranges. The redline object itself is not assumed to be a readable text range.
- Preflight compares those ranges against live citation anchors, complete source citation notes and their main
  anchors, the existing/planned conversion-state point, and the existing/planned managed bibliography range.
- An unrelated redline is allowed. A managed-range overlap or any redline whose endpoints Writer does not expose
  comparably is refused before rendering or mutation.
- The transaction snapshots stable redline identity, type, author/comment, description, selected range text, and
  main/footnote/endnote/other context. The same signature is required after conversion and automatic rollback.
- If Track Changes recording is enabled, Callosum pauses it only while applying its one verified Undo operation,
  then restores the original setting. Conversion does not create a forest of Callosum-authored redlines and does
  not accept or reject the user's changes.
- The packaged extension version is `0.18.0`.

## Gates

- **Principles / governance:** aligned and non-triggering. This is explicit deterministic document maintenance;
  no scholarly claim, recommendation, ranking, or judgment is created.
- **Security:** `2026-07-24_tracked-change-writer-conversion.md` - **PASS**.
- **QA:** route 34 records unrelated-redline preservation, recording-state restoration, Undo/Redo, and managed
  overlap/unreadable-range refusal.
- **Experience:** a collaborator can leave tracked prose edits pending while changing citation style/placement;
  only changes inside content Callosum must rewrite need resolution first.

## Verification

- LibreOffice adapter/OXT: **119 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** against installed OXT `0.18.0`, preserving
  tracked main-text insertion/deletion and ordinary-footnote edits through conversion and Undo/Redo, while
  refusing a tracked insertion inside a live citation.
- Full project suite: **1564 passed, 1 skipped**.

## Result

P1 roadmap item #10, proper note-style citation support, is complete.
