# Increment 509 — Word grouped-citation composer (backlog #33/#34, Word/Docs parity P0)

## Implemented

Following inc 508's live verification of the Word add-in (both desktop and Word-on-the-web), Cliff asked to
work toward genuine **parity** with the LibreOffice adapter — approximating what it does, for Word, to the
extent Office.js allows. Research (direct reads + two Explore agents) confirmed the full scope was far larger
than one increment (LibreOffice's own P0/P1/P2 build-out took ~360 increments), so the work was split:

1. **Research confirmed the shared backend already fully supports grouped citations + per-item locators** —
   `app/backend/citations/render.py::render_document` copies every key on an input citation item through
   unchanged (`item = dict(it)`), and `citeproc_runner.js::buildCitationItem` explicitly forwards
   `locator`/`label`/`prefix`/`suffix`/`suppress-author`/`author-only` onto citeproc's real `citationItems`.
   **Zero backend changes were needed** — this closes a purely adapter-side (UI) gap.
2. **This increment** builds the Word-side UI to use that already-existing backend capability: a real
   citation composer mirroring `adapters/libreoffice/composer.py`'s own assembly model (search/suggest → add
   to an ordered list → per-item Options → Insert as one grouped cluster), plus **Edit citation at cursor**
   and **Delete citation at cursor**.
3. The rest of the LibreOffice-vs-Word gap (note-style/footnote placement, bibliography categories/sections,
   a persistent citations panel, evidence-aware Suggest, citation-coverage/preflight audits, Insert-Evidence,
   open-science statements, Zotero-field conversion) is now an explicit phased backlog entry
   (`INCREMENT-BACKLOG.md` #33/#34) rather than an unscoped "parity" bullet — see that entry for the full
   P0/P1/P2 sequencing, pointing at
   `.claude/docs/future-tracks/chatgpt5.6_future-tracks_wordprocessorpluginsroadmap.md` (the same generic
   roadmap doc LibreOffice's own build followed) rather than re-narrating all 22 items.

### Files

- `adapters/word/taskpane_core.js` — new pure-logic exports: `LOCATOR_LABELS` (the 19-value CSL vocabulary,
  mirroring `CSL_LOCATOR_LABELS` in `callosum_cite.py`), `itemOverrides` (mirrors `_item_overrides`),
  `buildClusterItems`, `cslRecordRow` (a CSL-JSON-native version of `formatSearchRows`' author-label logic —
  CSL authors are `{family, given}` objects, not "Last, First" strings), `formatAssemblyRow` (mirrors
  `_format_assembly_row`), `assemblyRowFromDecodedItem` (mirrors `_assembly_item_from_decoded`, the Edit
  Citation round-trip). `encodeCitationTag`/`decodeCitationTag`/`buildDocumentRequest` needed **no changes** —
  already general enough to carry arbitrary per-item keys.
- `adapters/word/taskpane_core.test.js` — 7 new tests (19 total, was 13 pre-508/12 pre-509) covering the above
  in isolation, including a full round-trip test (`assemblyRowFromDecodedItem` → `buildClusterItems` reproduces
  the original decoded item exactly).
- `adapters/word/taskpane.html` — search/suggest results no longer insert immediately; a new `#assemblySection`
  (hidden until non-empty) lists the citation being built, with an **Insert citation**/**Cancel** action row,
  plus new **Edit citation at cursor**/**Delete citation at cursor** buttons.
- `adapters/word/taskpane.css` — styling for the assembly list, its per-row Options panel, and small icon
  buttons (move/options/remove).
- `adapters/word/taskpane.js` — `onPick` now adds to the in-memory `assembly` array instead of inserting;
  `renderAssembly`/`renderOptionsPanel`/`onAssemblyClick`/`onAssemblyChange` drive the new UI;
  `insertOrUpdateCitation` replaces the old single-item `insertCitation`; `editCitationAtCursor`/
  `deleteCitationAtCursor` are new. `refreshDocument` needed **no changes** — it already decodes each
  citation's full items array from its tag regardless of item count.
- `adapters/word/README.md` — the "Use" section documents the composer; the old "One work per citation (no
  grouped cites / page-locators yet)" limitation is removed (closed).
- `.claude/docs/INCREMENT-BACKLOG.md` — the Word/Docs P1 parity bullet restructured into an explicit phased
  checklist (P0 remainder / P1 / P2), pointing at the roadmap doc.

## Key technical detail

**The correlated-objects pattern for Edit Citation.** Office.js proxy objects (like a `Word.ContentControl`)
are normally scoped to the `RequestContext` of the `Word.run()` call that created them and become unusable once
that call returns. `editCitationAtCursor()` needs to hold a reference to the content control the cursor was in
at click-time, then use it again later inside `insertOrUpdateCitation()` (potentially several UI interactions
later, after the user has added/removed/reordered assembly rows). The documented mechanism for this is
`.track()`/`.untrack()` (shorthand for `context.trackedObjects.add/remove`) plus the `Word.run(object,
callback)` overload, which accepts a previously-tracked object and rebinds it into a **fresh** context
automatically. `insertOrUpdateCitation()`'s update branch calls `Word.run(editingCC, async function (ctx) {...})`
rather than the zero-arg `Word.run(async function (ctx) {...})` used everywhere else in this file — that one
argument is what makes the retagging work at all.

**Why `refreshDocument()` needed no changes.** It already scans every citation Content Control, decodes its
full tag (`CallosumCore.decodeCitationTag`, which was always an array of items, never assumed to be length 1),
and passes that array straight through to `/citations/render-document`. Grouped citations "just worked" once
the composer could build a multi-item tag — the render path was already correct, just never exercised.

## Manual verification script

No headless Word exists (project policy, confirmed again this session), so `node --test
adapters/word/taskpane_core.test.js` covers the new pure logic exhaustively (19/19 passing), and the Office.js
glue needs a real-Word check: search for 2+ works and add each to the assembly; open one's Options and set a
locator + label (e.g. "page" / "5"); reorder with ↑/↓; click **Insert citation**; confirm the rendered in-text
groups them with the locator applied (e.g. "(Smith, 2020, p. 5; Jones, 2021)" in an author-date style). Click
into that citation and **Edit citation at cursor**; confirm the composer reopens pre-populated with both works
and the locator; remove one, change the other's prefix, click **Update citation**; confirm the re-render
reflects the change. Click into a (different) citation and **Delete citation at cursor**; confirm it's gone
and Refresh/bibliography still work. Not yet run live — this is the next step, per this session's established
pattern of fixing anything the live run surfaces before calling the increment done.

## Pytest / tests

`node --test adapters/word/taskpane_core.test.js` → 19/19 passed. No Python test changes — confirmed by direct
read that `render.py`/`citeproc_runner.js` needed zero changes; the existing Python suite already covers
`render_document`'s multi-item/override-forwarding behavior (it was already exercised by other callers, just
never by the Word adapter specifically).
