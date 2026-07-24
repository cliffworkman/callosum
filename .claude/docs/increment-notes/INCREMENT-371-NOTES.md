# Increment 371 - Exact ibid and near-note context

## Context

P1 roadmap item #10 already placed note-style citations in native Writer footnotes/endnotes and passed their
one-based indexes to citeproc. The remaining position coverage asserted only that a repeated Chicago note differed
from its first note. That could not prove ibid, changed-locator ibid, near-note distance, far-subsequent behavior,
or the effect of ordinary user-authored notes on the native sequence.

## Implemented

- The shared document renderer rejects a mixture of zero and positive `noteIndex` values and rejects descending
  positive indexes before invoking citeproc. Equal positive indexes remain valid for multiple citation clusters
  inside one note.
- A schema-valid imported diagnostic note style labels the citeproc first, ibid, ibid-with-locator, near-note,
  and far-subsequent branches. The public install and render APIs assert each exact output.
- The real-UNO fixture installs the same class of note style and creates six live citation notes plus two
  ordinary Writer footnotes. Native indexes `1,2,3,4,5,8` prove that visible Writer numbering, including gaps
  from ordinary notes, drives near-note distance. The ordinary note text remains unchanged.

## Gates

- **Principles / governance:** aligned and non-triggering. Citation formatting is deterministic, local, and
  user-invoked; it creates no literature claim, signal, recommendation, or judgment. The avoided shortcut is a
  citation-only counter that would disagree with the manuscript's visible note numbering.
- **Security:** `2026-07-24_note-position-context.md` - **PASS**.
- **QA:** route 34 now requires exact imported-style position branches and malformed-sequence rejection.
- **Experience:** a humanities writer can mix explanatory footnotes with live citations and have style-defined
  ibid/near-note forms follow the note numbers they see. No new control or click-through is required.

## Verification

- Citation engine: **56 passed**.
- LibreOffice adapter/OXT: **110 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** against the installed OXT and real Writer,
  including exact position labels and unchanged ordinary notes.
- Full project suite: **1555 passed, 1 skipped**.

## Result

The broader ibid/subsequent/near-note style and context coverage under P1 item #10 is complete. The two remaining
#10 slices are multiple independent live clusters mixed with user prose inside one note, then tracked-change
placement conversion.
