# Increment 520 — Native Word footnote/endnote citation placement

**Date:** 2026-08-28
**Scope:** Word P1 parity: native note placement and note-aware document scanning. No backend change.

## User behavior

Selecting a CSL style whose catalog `citation_format` is `note` reveals a document-level **New note citations**
choice: **Footnotes** (default) or **Endnotes**. The choice persists in Word document settings.

- From the main document, Insert creates a native footnote/endnote at the selection end and places the same live
  Callosum Content Control inside the note.
- From an existing configured note, Insert places the citation at the cursor rather than nesting a new note.
- Editing uses the existing cursor/content-control flow unchanged.
- Deleting a citation-only Callosum-created note removes the native note marker too. If a note also contains prose
  or other controls, only the citation is removed.
- Existing notes are never converted when the preference changes.

The preference appears only for note styles; ordinary author-date/numeric styles retain the existing compact UI.

## Native note order and citeproc contract

WordApi 1.5 exposes ordered `Body.footnotes` and `Body.endnotes` collections, each `NoteItem.body`, and
`Range.insertFootnote`/`insertEndnote`. Callosum scans every note body and assigns the native collection position
plus one as `noteIndex`:

- ordinary non-Callosum notes create real gaps;
- two Callosum citation clusters in one note share the same index;
- indexes remain monotonic in native note order.

Those `{items, noteIndex}` clusters go through the unchanged `/citations/render-document` endpoint, whose existing
validation/citeproc bridge already supports equal positive indexes and first/subsequent/ibid position state.

Sources consulted:

- [Word.Range (`insertFootnote`, `insertEndnote`, `parentBody`)](https://learn.microsoft.com/en-us/javascript/api/word/word.range?view=word-js-preview)
- [Word.Body (`footnotes`, `endnotes`, `type`)](https://learn.microsoft.com/en-us/javascript/api/word/word.body?view=word-js-preview)
- [Word.NoteItem](https://learn.microsoft.com/en-us/javascript/api/word/word.noteitem?view=word-js-preview)
- [OfficeDev native notes sample](https://github.com/OfficeDev/office-js-snippets/blob/prod/samples/word/50-document/manage-footnotes.yaml)

## Fail-closed placement rules

Callosum does not have an honest cross-story ordering for a document mixing main-body and note-contained live
citations, nor can footnote and endnote index sequences be merged without inventing semantics. Before Refresh or
new insertion:

- in-text style + any note-contained Callosum citation: reject;
- note style + any main-body Callosum citation: reject;
- note style + both footnote and endnote citations: reject;
- note style + existing note type differing from the document preference: reject.

Document diagnostics surfaces the same placement issue. No automatic migration or conversion is attempted.

## All-document lifecycle coverage

The shared Word scan now includes main-body, footnote-body, and endnote-body controls for:

- Refresh/render;
- Document diagnostics;
- Citations in this document;
- click-to-navigate;
- XML-part reference counting on Delete;
- Flatten preflight, operation, and post-operation verification.

This prevents native-note citations from becoming invisible to an existing document operation.

## Compatibility and boundaries

- Native note behavior requires WordApi 1.5 and fails explicitly on older hosts.
- WordApi 1.4 Custom XML storage from inc 519 is unchanged.
- The production CSL prompt/rendering contract, citeproc engine, citation item payload, paper-ID stamping,
  bibliography storage, providers, scientific verification, and egress behavior are unchanged.
- No new endpoint, dependency, migration, permission, or network request exists.

## Automated verification

Final gates passed:

- Word pure logic: **40/40** (`node --test adapters/word/taskpane_core.test.js`).
- Focused Word/access/citation pytest: **82 passed** in 117.82s.
- Full repository suite: **2563 passed, 3 skipped** in 978.87s (16m18.87s; `pytest -n auto -q
  --tb=short`).
- JavaScript syntax checks passed for `taskpane.js` and `taskpane_core.js`.
- Ruff check/format, Bandit, Tach, line-budget, QA surface gate, and `git diff --check` passed.

The pure layer covers:

- `{items, noteIndex}` request construction;
- repeated indexes for multiple citations in one note;
- body-type classification;
- note/in-text placement acceptance and every fail-closed mismatch class.

## Experience pass

Local persona walkthrough (no subagent available under the active execution constraint): an academic choosing
Chicago notes sees one contextual Footnotes/Endnotes choice, then uses the same search/composer/Insert flow as
before. The UI does not expose `noteIndex`, WordApi, citeproc, or implementation detail. Existing citations are
never silently moved. The cheapest useful correction was making the preference contextual—hidden for non-note
styles—rather than adding a permanent advanced-settings block.

## Honest verification boundary

No available agent can drive real Word. Office.js note collection loading, note insertion, note-body Content
Controls, deletion of citation-only notes, and Word-on-the-web behavior are **not yet live-verified**. Automated
tests prove only the pure request/placement rules and existing backend contract. Do not describe native note
support as live-proven until the manual script below is completed.

## Manual Word verification owed

1. Select Chicago notes; verify the Footnotes/Endnotes control appears and persists per document.
2. Insert from main text in Footnotes mode; verify a native note marker and live citation appear.
3. Add a second citation inside that same note; Refresh and verify both use the same native note index.
4. Insert an ordinary note between two Callosum notes; verify subsequent/ibid behavior follows native numbering.
5. Repeat with Endnotes in a fresh document.
6. Verify Edit, Delete, panel navigation, diagnostics, and Flatten for note-contained citations.
7. Verify deleting a citation-only note removes its marker, while deleting one citation from a prose-bearing note
   preserves the note and prose.
8. Switch an inline-citation document to Chicago notes and verify fail-closed guidance, not silent conversion.
9. Create a controlled footnote/endnote mix and verify Refresh refuses it.
10. Repeat the core path in Word on the web.

## Next

After live verification, continue P1 with bibliography categories/chapter-section blocks. Do not add section
bibliographies to this increment.
