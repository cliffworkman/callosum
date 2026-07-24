# Increment 372 - Multiple live citations inside prose-bearing Writer notes

## Context

P1 roadmap item #10 already rendered multiple citation clusters with the same native note index and safely
refused placement conversion when one note held multiple clusters or user prose. Authoring was still blocked:
**Add citation...** at a caret inside an existing Writer note tried to create a nested footnote/endnote, which
Writer does not support.

## Implemented

- Note-style insertion now classifies the caret before mutation. A main-document caret creates a new configured
  footnote/endnote; a caret inside an existing configured note inserts an independent live ReferenceMark at that
  position.
- A caret in the other note placement or an unsupported Writer text container fails with a specific error before
  any field, note, or document preference changes.
- Existing refresh, edit, flatten, and deletion paths continue to address each live ReferenceMark independently.
  Deleting the last live cluster removes an otherwise-empty Callosum-created note, but retains a note containing
  user prose.
- Placement conversion remains deliberately fail-closed for prose-bearing and multi-cluster source notes. This
  increment does not invent lossy rules for moving or merging that prose.
- The packaged extension version is `0.17.0`.
- The full installed-Writer harness remains bounded, but its process ceiling is now 720 rather than 480 seconds
  so the expanded conversion and note lifecycle suite can finish without skipping any scenario.

## Gates

- **Principles / governance:** aligned and non-triggering. This is deterministic, user-invoked document editing;
  it creates no scholarly claim, recommendation, ranking, or hidden judgment.
- **Security:** `2026-07-24_prose-mixed-writer-notes.md` - **PASS**.
- **QA:** route 34 records the installed-Writer authoring, refresh, staged deletion, and refusal checks.
- **Experience:** writers can keep explanatory prose and several independently editable citations in one native
  footnote/endnote without changing the established composer or citation-field model.

## Verification

- LibreOffice adapter/OXT: **111 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** against installed OXT `0.17.0`, including both
  footnotes and endnotes through the real Writer view caret.
- Full project suite: **1556 passed, 1 skipped**.

## Result

The prose-mixed multi-cluster note slice of P1 item #10 is complete. Tracked-change placement conversion remains.
