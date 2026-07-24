# Increment 363 — LibreOffice native endnotes and persistent note placement

## Context

Increment 362 established correct note-style rendering in native Writer footnotes. P1 item #10 also calls for
endnotes where the host supports them. LibreOffice exposes `com.sun.star.text.Endnote` through the same text
interfaces as footnotes and exposes an ordered endnote collection, so the existing live-field model can support
both without inventing a second citation format.

## Implemented

- A document-local `CallosumNotePlacement` property stores `footnote` or `endnote`; missing or malformed legacy
  values safely default to footnotes.
- The new **Callosum → Note placement…** command presents a bounded Footnotes/Endnotes dropdown rather than a
  free-text setting.
- Note-family citation insertion creates either `com.sun.star.text.Footnote` or
  `com.sun.star.text.Endnote`, then places the same live ReferenceMark payload inside that note's own XText.
- Endnote scans use Writer's ordered endnote collection and send one-based `noteIndex` values to the unchanged
  shared render contract.
- Refresh and style validation now compare existing note context with the saved placement. Changing placement
  with incompatible live notes fails before the property changes; in-text, footnote, and endnote content is
  never silently relocated.
- The macro action and packaged OXT menu dispatch are wired and guarded against dead action names.
- Extension version bumped 0.12.0 → 0.13.0.

## Conversion contract (not implemented)

A future explicit conversion command must first inventory every live field and refuse ambiguous documents:
mixed placements, multiple independent live clusters inside one note, user prose sharing a note, unsupported
text containers, or tracked-change states without proven semantics. For eligible documents it must:

1. Preview the source/target placement and citation count, with a separate-copy option.
2. Capture every main-text anchor, payload, visible value, and document preference before mutation.
3. Perform all relocations in one Writer UndoManager transaction, preserving citation IDs and main-text order.
4. Re-render once using the complete resulting sequence.
5. Verify field count, payload identity, target placement, bibliography bounds, and saved preferences.
6. Roll back and verify the original snapshot on any failure.

The placement selector in this increment deliberately does none of this automatically.

## Verification

- Focused adapter/OXT/install suite: **105 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: first run reached a documented transient local-server
  connection reset in a later legacy manual-refresh spike; the unchanged second run completed successfully.
- The installed 0.13.0 OXT's real-Writer fixture created three native endnotes, observed placement `endnote` and
  indexes 1/2/3, proved a repeated Chicago citation shortened, resolved the citation from a caret inside the
  endnote, refused an endnote→footnote preference change without mutation, and flattened all fields while
  preserving static endnote text.
- Full project suite: `1495 passed, 1 skipped in 661.80s (0:11:01)`.

## Gates

- **Principles / governance:** non-triggering. This is deterministic, local, user-invoked document formatting;
  it creates no claim, signal, ranking, recommendation, or judgment.
- **Security:** `2026-07-23_libreoffice-note-placement.md` is **PASS**.
- **QA:** no browser surface or server API changed. Menu/action packaging has pure OXT coverage; native Writer
  service creation, document persistence, ordered indexing, and refusal behavior have real-UNO coverage.

## Experience pass

A humanities writer can select Chicago notes, choose Endnotes once, and use the same Add/Edit citation workflow;
Writer displays native endnotes and Callosum retains live formatting. The setting is discoverable beside Citation
style and uses a two-option control. The important boundary is explicit: changing the dropdown does not quietly
move an existing manuscript's citations. The project no-delegation instruction prevented the usual persona
subagent, so this walkthrough was performed locally against the deadline-citer workflow.

## Manual verification debt

Install 0.13.0, open **Callosum → Note placement…**, choose Endnotes, and insert the same source twice under
Chicago notes and bibliography. Confirm Writer's endnote presentation and the shortened repeat. Then reopen the
selector and choose Footnotes; the existing endnotes must remain unchanged and the explicit conversion message
must appear.

## Next

The next #10 slice is the explicit conversion command described above. Start with the narrow safe subset
(one live cluster per source note, no user prose or tracked changes) and preserve a fail-closed path for every
ambiguous document.
