<!-- qa-coverage
api: /citations*
fe: 25_detail.jsx, 35cb_citation_style_editor.jsx, 35d_citation_styles.jsx, 37_cite.jsx
-->

# ROUTE 34 - Citations engine

**Tier:** 1 local-stateful
**Goal:** Exhaust citation style listing, single citation rendering, and document bibliography rendering.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.
- **Style previews are fixed-example-only (inc 365).** `POST /citations/styles/preview` renders bundled fictional
  records through local citeproc. A preview request must never include or retrieve library text and must fire no
  external request.
- **Installed style XML is server-owned (inc 366).** Runtime style ids resolve only to bundled files or
  server-generated `custom-*` files under the local settings directory. A request-supplied id/path/URL must never
  select arbitrary XML. The Node sidecar receives validated XML from Python and performs no network request.
- **Personal-style lifecycle is local and guarded (inc 367).** Export returns only the selected validated
  `custom-*` CSL with a constrained portable id marker. Removal cannot accept a path, remove a bundled/default
  style, or orphan an installed dependent. Neither operation may make an external request.
- **Imported-style validation and copies are portable (inc 369).** Installed CSL satisfies the official local
  1.0.2 schema and macro rules. A duplicate receives a new canonical identity and resolves as independent even
  when its source was dependent; the source style remains unchanged.
- **Source edits preserve installed identity (inc 370).** Editing is limited to independent personal styles.
  Unsaved preview uses request-supplied validated XML without writing it. Save preserves both the local style id
  and canonical CSL id, uses an exact revision precondition, and atomically retains the prior file on failure.
- **Zotero citation resolution is local-only and bounded (inc 464).** `POST /citations/zotero/resolve` never
  fires an external request — it matches or creates a library paper purely from the citation's own embedded
  CSL-JSON. Empty or over-300-item input → 422. The real end-to-end caller is the LibreOffice adapter's
  "Convert Zotero citations…" command, verified via `python adapters/libreoffice/run_roundtrip.py`
  (`spike_zotero_citation_conversion`), not this browser-driven route — this wildcard (`/citations*`) already
  covers the endpoint for the QA surface-map gate; the assertions here are what a browser-only run can still check.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open "Cite as..." for a seeded paper. Confirm styles load (`GET /citations/styles`) with stable ids plus parsed
   CSL metadata, locales, favorite/recent state, and a valid application default. Search by full name, acronym,
   journal/discipline term, and no-match; query length above 120 → 422.
2. Switch styles and render (`POST /citations/render`). Confirm preview updates, copy succeeds, and missing CSL fields degrade cleanly.
3. Render a bibliography/document export (`POST /citations/render-document`) using multiple selected papers.
   Confirm ordering, escaping, and selected style are honored. With `chicago-notes-bibliography`, send ordered
   clusters with `noteIndex` 1, 2, and 3 (repeat the first source at 3); confirm the repeated note uses citeproc's
   subsequent-note form rather than repeating the first-note form. Install a schema-valid diagnostic note style
   with `near-note-distance="2"` and assert exact first, ibid, ibid-with-locator, near-note, and far-subsequent
   outputs for indexes `1,2,3,4,5,8`. Mixed zero/positive and descending indexes → 422; equal positive indexes
   remain valid for multiple clusters in one note.
4. Preview APA, IEEE, and Chicago notes (`POST /citations/styles/preview`) with en-US/en-GB. Confirm the response
   contains formatted citation/note/bibliography examples for the fixed fictional records, including first and
   subsequent note positions where applicable. Unknown style/locale → 422; unavailable engine → 503; rendering
   failure → 502.
5. Update (`PUT /citations/styles/preferences`) the application default, locale, favorite, and recent style.
   Reload and confirm bounded persistence, deduplicated recents, and that recording a document style does not
   implicitly replace the application default. Unknown style/locale → 422.
6. Install a valid local style (`POST /citations/styles/install`) and use its server-generated `custom-*` id with
   both `/citations/render` and `/citations/render-document`. Confirm output follows the custom layout and the
   style remains available after app restart. Validation preflight returns `already_installed` for an exact
   duplicate and `update_available` for changed content under the same canonical CSL id, without writing. A direct
   changed install without `replace:true` remains 409. A dependent style resolves only through an installed
   canonical parent. Bundled canonical ids cannot be replaced.
7. Export the personal style (`GET /citations/styles/{style_id}/export`): confirm a `.csl` attachment with the
   exact portable `callosum-style-id` marker, no private path, and no mutation. Reinstall it against a clean local
   settings directory and confirm the same id plus `already_installed` on an exact repeat. A malformed/misplaced
   marker fails validation. Bundled/unknown export → 409/404.
8. Remove the personal style (`DELETE /citations/styles/{style_id}`). Confirm application-default and
   installed-parent removal → 409 with no mutation; bundled/unknown removal → 409/404. After choosing another
   default and removing dependents first, deletion succeeds, cleans Favorites/Recent, and subsequent render by
   the removed id → 422.
9. Duplicate (`POST /citations/styles/{style_id}/duplicate`) a bundled style and a dependent personal style.
   Confirm each result has a distinct canonical id, is independent, renders through both citation endpoints, and
   leaves its source untouched. A missing source → 404; an empty/oversized title fails cleanly.
10. Read an independent personal style (`GET /citations/styles/{style_id}/source`) and retain its SHA-256
    revision. Validate edited XML (`POST .../source/validate`) and confirm the returned fictional preview reflects
    the unsaved layout without changing the installed file. Save (`PUT .../source`) with the exact revision and
    confirm the stable local/canonical ids, changed render output, edit provenance, and atomic persistence.
    Reuse the stale revision -> 409 and no overwrite. Bundled/dependent source access, changed canonical id,
    dependent conversion, invalid/oversized CSL, and citeproc failure all fail without mutation or egress.
11. Try an unknown style, no selected papers, malformed paper id state, and `noteIndex` values that are negative, above 5000, fractional, or boolean. Confirm validation messaging/422 responses and no crash.
12. Confirm no citation surface presents papers as good/bad or ranked by hidden score.
13. **Manual Writer adapter check:** select Chicago notes, insert one citation from the main document, type prose
    after it inside the native note, put the caret later in that same note, and use **Add citation…** again.
    Confirm one native note contains two independently editable live fields with the same one-based note index,
    separated by intact prose. Refresh, delete the first citation, then delete the second: prose and the note
    remain. Attempt placement conversion before deletion and confirm it refuses without changing the document.
14. **Manual Writer tracked-change conversion:** create tracked prose insertion and deletion outside live
    citations plus a tracked edit in an ordinary note. Convert inline citations to footnotes. Confirm every
    redline retains its identity/type/description/range text/context, Track Changes remains enabled, and Writer
    Undo/Redo preserves both. Add a tracked insertion inside a live citation and confirm conversion refuses
    before mutation. Repeat with an unreadable or managed-bibliography-overlapping redline → fail closed.
15. **Manual Writer bibliography heading:** pause automatic bibliography rebuilding, choose **Bibliography
    heading…**, enter `Works Cited`, and confirm only the bounded heading changes immediately while citations,
    entries, trailing prose, and the paused setting remain intact. Save/reopen and confirm the heading persists.
    Submit a blank heading and confirm **References** returns. Oversized or multiline/control-character input
    must fail without changing either the document property or managed bibliography.
16. **Manual Writer citation-to-bibliography links:** create two single-work citations plus one grouped citation,
    choose **Toggle citation-to-bibliography links**, and confirm each single-work citation has a document-local
    destination at its own rendered bibliography entry while the grouped citation stays plain. Exclude one cited
    work and confirm its link/target disappear without affecting the other. Save/reopen, refresh, and convert
    citation placement; links and targets must remain coherent. Toggle the feature off and confirm Callosum
    internal links are removed while an unrelated external hyperlink remains unchanged. With the caret in the
    grouped citation, choose **Go to bibliography entry…**, select its second source, and confirm Writer lands on
    that source's full-bibliography entry even while visible links are off. Exclude that source and confirm it is
    no longer offered; remove the full bibliography and confirm the command explains how to restore a destination.
    Save/reopen and repeat the second-source jump. Use **Open cited work in callosum…** on the same group, choose
    the second source, and confirm that paper—not the first—opens in Callosum.
17. **Manual Writer bibliography title/DOI links:** first use a style that renders DOI or URL text, choose
    **Toggle bibliography title/DOI links**, and confirm only that already-rendered identifier becomes an external
    hyperlink. Switch to a style such as Nature that omits the identifier and confirm the exact rendered title
    links to the source DOI without adding or changing text. Save/reopen, refresh, move the bibliography, and
    convert citation placement; the opt-in setting and links must remain coherent. Toggle off and confirm the
    bibliography text is byte-for-byte unchanged, managed web links are removed, and a hyperlink in ordinary
    prose remains untouched. Unsafe URLs, ambiguous/transformed/oversized titles, multi-source entries, and
    malformed, credentialed, non-HTTP(S), overlapping, or out-of-range metadata must remain plain.
18. **Manual Writer categorized bibliography:** create at least three visible bibliography entries, open
    **Citations in this document…**, and assign works to differently named categories. Ctrl/Shift-select a mixed
    batch, choose **Set category…**, confirm the picker defaults to the no-op placeholder, then reuse an existing
    category and verify every selected row updates after one refresh. Exercise **Create new category…** and
    **Remove category**; blank create input must not remove anything. Go to with multiple selections or one
    uncited row, and exclusion with multiple selections or one uncited row, must explain the constraint and keep
    the panel open. Confirm
    category headings sort alphabetically, the active CSL style's entry order remains stable within a category,
    and unassigned works remain under **Other references**. Verify include-uncited/exclude-cited behavior,
    internal citation targets, DOI/URL links, refresh, bibliography movement, placement conversion, save/reopen,
    and failure rollback remain coherent. Remove one assignment, then remove the final batch and confirm the
    exact ordinary uncategorized layout returns. Oversized, multiline/control, over-1,000-work batch,
    reserved **Other references**, excessive, corrupt, or nonnumeric-id metadata must fail without mutation.
19. **Manual Writer category order:** with at least three named bibliography categories, open **Category
    order…**, move the last group to the first position, and Save. Confirm category headings follow that order,
    citeproc order inside each group is unchanged, and **Other references** remains last. Save/reopen, refresh,
    move the bibliography, and convert citation placement; order, entry targets, and DOI/URL links must remain
    coherent. Create a new category and confirm it follows configured groups alphabetically until repositioned.
    Cancel must mutate nothing. Choose **Reset alphabetical**, then Save; confirm alphabetical order returns and
    the custom property is removed. With fewer than two categories, the action must explain the requirement.
    Oversized, duplicate, blank, control-character, reserved-label, non-list, or over-50-label metadata must
    degrade to alphabetical or fail before mutation; a refresh failure must restore the exact prior property.
20. **Manual Writer section bibliographies:** make two peer Heading 1 chapters with distinct citations and one
    nested Heading 2. Place the caret in each chapter and choose **Insert current-section bibliography here**.
    Confirm each local block contains only its heading subtree's works, the nested work belongs to its parent,
    and the full bibliography still contains all works. Add/remove/move a citation, run bibliography refresh,
    save/reopen, edit a section block manually, and refresh again; membership/text/category order/DOI links must
    repair without changing prose or another block. A second insert in the same subtree, insertion from a note,
    a citation-free section, over 50 blocks, or damaged/foreign/copy-suffixed bookmark names must not mutate.
    Diagnostics reports complete/damaged blocks. Removal targets only the caret's subtree; flatten removes all
    managed wrappers while preserving text. Convert between APA inline citations and Chicago footnotes; confirm
    the full bibliography and both non-empty section blocks update in one Writer Undo step, Undo/Redo restore exact
    snapshots, and save-as-converted-copy leaves the open document unchanged. Inject the second range write failure
    and confirm every citation/full/section surface returns to its exact prior signature. Damaged or empty section
    blocks must refuse before mutation. Open **Section bibliographies…** and confirm rows follow document order
    with owning heading and unique cited-work count. Jump to the second block; remove the first and confirm its
    peer/full bibliography/citations survive. Cancel **Remove all** with no mutation, then confirm it and verify
    every section block is removed in one Writer Undo step. Undo/Redo must restore/remove exact text, bookmarks,
    and managed DOI/title links. Inject failure on the second removal and confirm the runtime recovery restores
    both blocks exactly. A damaged triple must be reported, omitted from the list, and disable bulk removal.
20b. **Manual Word section bibliographies (inc 524):** with an in-text style, make two peer Heading 1 sections
    plus a nested Heading 2 and distinct Callosum citations. Insert a current-section bibliography in each peer;
    confirm subtree-only membership, nested-heading inclusion, full-bibliography coexistence, category/order
    preservation, independent removal, save/reopen identity, refresh repair, and Flatten retaining text. A second
    insert in one subtree, no preceding heading, a citation-free section, a note body/style, a damaged/duplicate
    pair, and a 51st block must fail before mutation. Diagnostics must distinguish complete and damaged pairs.
    Run in desktop Word and Word on the web; this remains a maintainer MANUAL route because no agent can drive Word.
20c. **Manual Word bibliography title/DOI links (inc 525):** use a style that prints DOI/URL text, enable **Link
    bibliography titles/DOIs to the web**, and confirm the identifier becomes clickable in the full bibliography
    plus every current-section block without changing visible text. Switch to a style that omits identifiers and
    confirm a uniquely rendered single-source title links to its DOI/URL. Exercise categories/order, Refresh,
    save/reopen, and section insertion while enabled. Disable and confirm only managed bibliography links vanish;
    an ordinary-prose hyperlink remains. Unsafe/credentialed/non-HTTP(S), out-of-range, overlapping, transformed,
    duplicate-anchor, multi-source, malformed-alignment, and astral-Unicode-before-anchor cases must remain plain
    or land on the exact intended text—never a neighboring range. Repeat the core path in desktop Word and Word
    on the web; this remains MANUAL because no available agent can drive Word.
20d. **Manual Word evidence-aware Suggest (inc 526):** select a draft sentence and run **Suggest from the
    sentence**. Confirm ranked order is unchanged and every in-library row has **Details…** with the full quote,
    page/range, complete support/mention/contrast breakdown, semantic-retrieval explanation, and the weak-evidence
    warning only when neither shared threshold clears. Edit/remove the auto page locator, add the work, insert,
    refresh, edit/update the citation, and save/reopen; confirm locator and compact evidence audit survive. In
    **Citations in this document…**, confirm the evidence badge and **View evidence…** show only the recorded page
    plus bounded snippet. **Open in PDF** must open the same paper/page at region precision, never fabricate an
    exact highlight, and remain disabled without a PDF attachment. Details alone must not mutate the document;
    ordinary search-added citations carry no evidence badge. Confirm the flow remains local with zero provider
    requests, then repeat in Word on the web. This remains MANUAL because no available agent can drive Word.
21. **Manual Writer journal abbreviations:** use a short-title CSL style such as Nature with one journal carrying
    library `container-title-short` metadata, one exact NLM/MEDLINE title or ISSN, and one unknown journal. In
    **Journal abbreviations…**, verify **Library abbreviations** uses embedded metadata, **MEDLINE first** prefers
    the NLM match and reports library fallbacks plus the unknown title, and **Full journal titles** restores the
    complete names. Confirm each change updates live citation text where applicable plus full and section
    bibliographies, survives save/reopen, and leaves the encoded citation metadata unchanged. Repeat with APA and
    confirm the dialog explains that its full-title request leaves visible text unchanged. Cancel must mutate
    nothing; an injected refresh failure must restore both the prior preference and rendered document.
22. **Manual Writer Zotero citation conversion:** hand-build (or use a real Zotero-cited document) a Writer file
    with a Zotero-shaped inline `ReferenceMark` matching an existing library paper by DOI, a second with no
    match, a malformed Zotero-named mark, a `ZOTERO_BREF_…` Bookmark-mode anchor, and a `ZOTERO_BIBL …`
    TextSection. Choose **Convert Zotero citations…** and confirm the pre-mutation dialog names exact counts
    (citations to convert, note-style/Bookmark-mode left unconverted, bibliography to be replaced). Confirm the
    matched citation keeps the existing paper's identity, the unmatched one creates a new metadata-only library
    paper from its embedded metadata, the malformed mark and Bookmark-mode anchor are left untouched and named
    in the summary, and Zotero's bibliography is replaced with a Callosum-managed one. Cancel the confirm dialog
    and verify nothing in the document changed.

## Pass criteria

- Style list, citation preview, copy, and document render complete.
- 0 console/page errors and 0 genai-host requests.
- Bad inputs fail cleanly; output is visibly tied to the selected style and note position.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_34_citations_engine.md` + `screenshots/` (see `_TEMPLATE.md`).
