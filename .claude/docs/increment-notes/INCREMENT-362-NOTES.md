# Increment 362 — LibreOffice note citations in real Writer footnotes

## Context

P1 roadmap item #10 requires note-style citations to behave like notes, not like long inline parentheticals.
CSL note processing also depends on the note's position: citeproc must see a one-based note index across the
complete ordered document to distinguish first and subsequent citations correctly. Writer exposes footnotes as
their own text containers, so the existing assumption that every ReferenceMark lives in the main document text
had to be removed without weakening the live-field model.

## Implemented

- The additive document-render request field `noteIndex` defaults to `0` for every existing in-text client and
  accepts only strict integers from 0 through 5000.
- Citeproc receives the supplied index in each citation cluster instead of a hardcoded zero.
- The LibreOffice adapter reads style family from the server's style manifest. Bundled
  `chicago-notes-bibliography` creates a native Writer Footnote at the cursor and inserts the live ReferenceMark
  into that footnote's own text.
- Scanning classifies inline, footnote, endnote, and unsupported contexts. Footnote citations are ordered by
  Writer's footnote collection and carry one-based indexes into the render request.
- Cursor lookup, edit/update, delete, flatten, section-scoped refresh, and payload rewrap now operate on the
  mark's actual text container. Deleting the only content in a note removes that empty footnote.
- Style changes validate every existing citation placement before changing document preferences. Inline-to-note,
  note-to-inline, mixed placement, and endnote cases fail with a visible explanation; no automatic conversion is
  implied or attempted.
- Merge/split remains explicitly inline-only. A grouped note citation is built or changed through the existing
  composer/Edit citation flow as one live cluster.
- Extension version bumped 0.11.0 → 0.12.0.

## Verification

- Citation API/render tests: **23 passed**.
- LibreOffice adapter unit tests: **84 passed**.
- Combined citation/adapter/OXT/install suite: **119 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** with the installed OXT and real Writer.
  The fixture inserted three native footnotes using Chicago notes and bibliography, proved note indexes 1/2/3,
  and proved the repeated source rendered differently from its first note.
- The real fixture also resolved the live field from a caret inside the footnote, refused an APA switch without
  changing the saved Chicago preference, deleted the middle note and observed indexes renumber to 1/2, then
  flattened all live fields while preserving their static footnote text.
- Full project suite: `1486 passed, 1 skipped in 661.07s (0:11:01)`.

## Gates

- **Principles / governance:** aligned and non-triggering. Citation formatting is deterministic, local, and
  user-invoked; it produces no literature claim, signal, recommendation, or judgment. The easier misaligned
  implementation would render note output inline or silently convert an existing document. This increment uses
  native notes for new citations and fails closed on incompatible existing placement.
- **Security:** `2026-07-23_libreoffice-note-footnotes.md` is **PASS**.
- **QA:** route 34 now covers `noteIndex`, subsequent-note rendering, and strict negative validation. Writer
  text-container behavior is covered by focused pure tests and the installed-extension real-UNO fixture.

## Experience pass

A humanities writer starting a new Chicago-notes manuscript can select the style once, cite at the prose cursor,
and continue writing with a normal Writer footnote and live editable citation. The result is visibly and
structurally a note, and deleting or flattening it behaves predictably. The remaining boundary is equally visible:
an existing APA manuscript cannot yet be converted automatically, and an endnote workflow cannot yet be chosen.
Those limitations remain under roadmap item #10 rather than being hidden behind a superficially successful style
change. The project no-delegation instruction prevented the usual persona subagent, so this walkthrough was
performed locally against the documented deadline-citer workflow.

## Manual verification debt

Install 0.12.0 and create a short Chicago-notes document through the menu: cite one source twice, edit the second
note, save/reopen, and confirm Writer's visible footnote numbering and text. Also confirm that selecting APA in
that document gives the explicit non-conversion message without changing the notes.

## Next

Continue P1 item #10 with an explicit footnote/endnote placement choice and safe conversion design. Do not add
automatic conversion until mixed notes, user prose, tracked changes, and rollback semantics have a written and
real-Writer-tested contract.
