# callosum — LibreOffice citation adapter (v1)

Cite-while-you-write in **LibreOffice Writer**, backed by callosum's citation engine. The adapter is a thin
*field-placer*: it never formats citations itself — it places live fields, reads the full ordered citation set out
of your document, and writes back the in-text citations + bibliography that callosum renders (with correct numeric
renumbering and author-date disambiguation). Everything is **local** — the macro talks only to your callosum
server on `127.0.0.1`.

This is **v2** (inc 162): a one-click **extension** (`.oxt`) that adds a **Callosum** menu + toolbar to Writer, so
you never touch the macro dialog. It covers the core loop — **add citation** (search your library), **suggest-and-cite**
(from the sentence), refresh/restyle/renumber, bibliography, flatten, and a configurable server URL. (The raw Python
macro is still installable by hand — see *Manual install* — for development.)

## Prerequisites
- **LibreOffice** with its bundled Python (any recent 7.x/24.x/25.x).
- **callosum running** locally: from the project root, `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`.
  (Different port? Use the **Server URL…** menu item — no source edit needed.)

## Install (recommended)
**From callosum:** Settings → **LibreOffice plugin** → **Install plugin**. LibreOffice's Extension Manager opens —
click Install, then restart Writer. (Or **Download .oxt** and double-click it.) The `.oxt` is built by
`tools/build_libreoffice_oxt.py` (the Settings button builds + opens it for you).

A **Callosum** menu + toolbar then appear in Writer. (Run `python tools/build_libreoffice_oxt.py` to produce
`dist/callosum.oxt` yourself; `unopkg add dist/callosum.oxt` installs it from the command line.)

## Manual install (dev / no extension)
Copy `callosum_cite.py` into your LibreOffice user **Scripts/python** folder (create it if needed):

| OS | Folder |
|---|---|
| Windows | `%APPDATA%\LibreOffice\4\user\Scripts\python\` |
| macOS | `~/Library/Application Support/LibreOffice/4/user/Scripts/python/` |
| Linux | `~/.config/libreoffice/4/user/Scripts/python/` |

Restart LibreOffice. The macros then appear under **Tools → Macros → Organize Macros → Python → My Macros →
callosum_cite** (and can be bound to a toolbar via **Tools → Customize**). The extension above does this wiring for you.

## Use
Start callosum, open a document in Writer, and use the **Callosum** menu / toolbar:

1. **Add citation…** — the composer: **search your library live as you type** (author / title / year), **add one
   or more** results to the citation you're building, see a **real rendered preview** as you go, then click
   **Insert**. Building `(Smith, 2020; Jones, 2021)` from scratch is one composer session, not an insert-then-merge.
   Select an assembled item and click **Options…** to set a **locator** (page/chapter/section/… — the fixed CSL
   vocabulary), a **prefix**/**suffix** (e.g. "see …"), or **suppress the author**/show **author only** — each is
   per-occurrence (this citation only; your library record is never touched), and the preview updates live.
2. **Suggest citation** — **select (highlight)** the sentence you're writing (or place the cursor in it): callosum
   ranks **your library** by relevance to that sentence and shows a pick-list — each row gives the paper's **stance**
   (supports / contrasts / mentions the claim), a **match** score, and a **quote** preview (the evidence). Pick one
   and it inserts right after your sentence. Ranked by relevance, not citation count; nothing auto-inserts.
   *(The first run loads the local relevance + stance models, so it can take a few seconds.)* Check **"Also
   search beyond my library"** to also surface papers you don't have yet (via public metadata search + OpenAlex's
   citation graph) — each carries its own reason (e.g. "cited by a locally relevant paper: …"), never a bare
   score. This sends your sentence to public metadata providers (not an AI/Gemini call) — off by default, opt-in
   each time you check it. Picking a beyond-library result adds it to your library first, then cites it.
3. **Refresh / renumber + bibliography** — re-render every citation and rebuild the bibliography (run after edits, or
   after moving citations — numeric styles renumber by position). For a large document, **Refresh citations
   only** leaves the bibliography untouched, while **Refresh bibliography only** leaves citation text untouched
   and works even when automatic bibliography rebuilding is paused. **Refresh citation at cursor** updates just
   the live citation containing the caret. It still renders the full citation sequence for correct numbering,
   but leaves every other citation and the bibliography untouched. A document-wide pending-citations warning
   remains until you run a document-wide citation refresh. **Refresh current section** updates the nearest
   preceding heading and its nested subsections, stopping at the next heading of the same or higher rank. Text
   before the first heading is a preamble section; a document without headings is one section.
4. **Toggle automatic citation formatting** — switch to manual refresh mode for a large document. Citation
   inserts and edits remain structured live fields, but their visible text waits for **Refresh / renumber +
   bibliography** or **Refresh citations only**. New inserts visibly show `{citation}` while pending. Turning
   automatic formatting back on affects later changes; run one explicit refresh to resolve existing pending
   changes. Bibliography auto-rebuilding is controlled separately. Whenever a Callosum operation leaves citation
   formatting or the bibliography pending, Writer shows a non-dismissible **Callosum refresh pending** bar naming
   the stale surface(s); **Refresh pending** updates exactly those surfaces and removes the bar.
5. **Citation style…** — pick a CSL style id (`apa`, `ieee`, `nature`, `modern-language-association`,
   `chicago-author-date`, `chicago-notes-bibliography`, `harvard-cite-them-right`) and a locale (`en-US`/`en-GB`);
   the whole document re-renders. The choice is saved in the document.
6. **Prepare submission copy…** (recommended) — the safe way to hand off for submission: saves a **separate
   copy** with citations converted to static text; your open document is **never changed**. Names the copy
   `<your-document>-submission-copy.odt` by default (always ODF for now) and tells you exactly where it saved.
7. **Flatten to static text** — the advanced option: convert the live citation fields to plain text **in this
   document** directly. **One-way:** after flattening, the citations no longer update. Prefer **Prepare
   submission copy…** unless you specifically want to keep editing the flattened version yourself.
8. **Insert CRediT statement** — insert the **CRediT contribution statement** you built + staged in callosum
   (Theory → CRediT statement → **Send to LibreOffice**) at the cursor, as plain static text. A contributorship
   statement is prose the author asserts, not a live citation field, so it is inserted as literal text (no
   ReferenceMark, unaffected by refresh/flatten). If nothing is staged, the macro tells you to build one first.
9. **Server URL…** — point the plugin at callosum if you run it on a non-default port (stored in `~/.callosum/`).

**Acting on an existing citation** — place the cursor **inside** the citation first (all show an honest
message if it isn't):
10. **Edit citation…** — reopens the same live-search composer used for **Add citation…**, pre-populated with
   this citation's current sources and their locator/prefix/suffix/suppress-author options. Add or remove
   sources, reorder them (**Move ↑ / ↓**), change any source's **Options…**, then click **Update**. The
   citation's identity is preserved — this changes what it contains, not which citation it is.
11. **Delete citation** — removes the citation entirely, both the field and its rendered text.
12. **Merge with next / previous citation** — combines the citation at the cursor with the adjacent one into a
    single grouped citation, e.g. two separate `(Smith, 2020)` `(Jones, 2021)` become one
    `(Smith, 2020; Jones, 2021)`. Any text between the two originals (a comma, "and", …) is left in place — use
    **Edit citation…** afterward if you want to add locators/prefixes to the now-combined result.
13. **Split citation** — reverses a grouped citation back into that many separate single-work citations, joined
    by `"; "`.
14. **Open in callosum** — opens the cited work's paper page in your callosum web app (a browser tab). For a
    grouped citation, opens the **first** work only for now.

**Bibliography controls:**
15. **Insert bibliography here** — (re)builds the bibliography at the cursor instead of its current location —
    the "move" action: invoking it again elsewhere moves the block there.
16. **Toggle automatic bibliography rebuild** — pause the bibliography specifically (citations keep updating
    normally on refresh; the bibliography just stays as-is until you turn this back on) — useful for a long
    document where rebuilding the reference list on every edit is unwanted friction.
17. **Document diagnostics…** — a read-only health check: reports any malformed citation field, a citation
    written by a newer callosum schema this plugin doesn't understand, a citation-id collision, a citation whose
    source paper is no longer in your library, and whether the bibliography block is damaged or just not built
    yet. Never changes your document — it only tells you what it finds (and, for a damaged bibliography,
    that a plain Refresh safely rebuilds it).
18. **Citations in this document…** — an overview of every unique work you've cited: how many times, whether
    it's still in your library, and its retraction/correction status, with a live filter box and a **Go to**
    button that jumps you to its first occurrence. The same panel can **Toggle bibliography exclude** for a
    cited work or **Add uncited work(s)…** (for further reading). It is a snapshot at the moment you open it —
    reopen after editing to refresh.

The pending-refresh flags are saved inside the document. If you save and reopen while work is pending, the bar
returns the next time you use a Callosum command. Changes made entirely outside Callosum — for example manually
moving a citation through Writer's own cut/paste commands — are not yet observed automatically; run **Refresh /
renumber + bibliography** after those edits.

(The macro names behind these — `CallosumAddCitation`, `CallosumSuggestCitations`, `CallosumRefresh`,
`CallosumRefreshCitations`, `CallosumRefreshBibliography`,
`CallosumSetStyle`, `CallosumFlatten`, `CallosumPrepareSubmissionCopy`, `CallosumInsertStatement`,
`CallosumInsertCitation` (by id), `CallosumSetServerUrl`, `CallosumEditCitation`, `CallosumDeleteCitation`,
`CallosumMergeWithNext`, `CallosumMergeWithPrevious`, `CallosumSplitCitation`, `CallosumOpenInCallosum`,
`CallosumInsertBibliographyHere`, `CallosumToggleCiteAuto`, `CallosumToggleBibAuto`, `CallosumDiagnostics`,
`CallosumCitationsPanel` — are also runnable from the Python macro dialog if you installed by hand.)

The bibliography is a **bounded** managed block (a start/end bookmark pair) — a refresh only ever rebuilds
what's between those two bookmarks, so any of your own text placed after the bibliography is always preserved.
It still defaults to the document end on first use; move it anywhere with **Insert bibliography here**.

## How it works (for the curious)
Each citation is a Writer **ReferenceMark** whose name carries the cited work's CSL-JSON payload (base64-encoded);
the visible marked text is the rendered citation. On refresh the adapter scans every such mark **in document
order**, POSTs the ordered set to callosum's `POST /citations/render-document`, and writes the position-aware
result back. All formatting happens in callosum's bundled citeproc engine, so the output is identical to the in-app
"Cite as…" and to the future Word/Google-Docs adapters.

## Testing
Real UNO mutation logic (inserting/editing marks, the bibliography rebuild, flatten, …) isn't meaningfully
fakeable, so it's proven against a real headless LibreOffice + a real callosum server instead of pytest:
`python adapters/libreoffice/run_roundtrip.py` (seeds a temp library, starts both, runs `selftest_uno.py`, tears
down). This also runs in CI (`.github/workflows/libreoffice-adapter.yml`), scoped to changes under this
directory and deliberately non-blocking — a real headless-UNO session has observed transient startup flakiness
even in local runs, so it reports status visibly without gating merges.

## Credit
The live-field design — embedding the citation's CSL-JSON in the field and re-rendering the ordered set — follows
the **Zotero `CSL_CITATION` field convention** (reused as a *pattern*, not code). callosum's citation rendering is
built on **citeproc-js** and the **CSL** project; see the project's `THIRD-PARTY-NOTICES.md`.

## Limitations (v1)
Insert is by paper id, by relevance via **Suggest**, or by the live-search **Add citation…** composer, which
also handles **Edit citation…** (add/remove/reorder sources, per-item locator/prefix/suffix/suppress-author via
**Options…**, on an existing citation); Suggest covers papers **already in your library** (finding relevant
papers you don't yet have is a future stage) and shows a truncated quote per row (read the full evidence in
callosum's in-app **Cite** panel). There's no "suppress date" option — CSL/citeproc-js has no equivalent
mechanism. A CSL style that defines its own `<citation><sort>` (4 of the 7 bundled styles: apa, ieee, nature,
harvard-cite-them-right) will re-sort a grouped citation's items regardless of the order you arrange them in —
the composer's preview always shows the real result, so you'll see this rather than be surprised by it.
**Prepare submission copy…** always saves ODF (`.odt`) for now, regardless of your document's original format;
in-text styles only (footnote/note styles later); no Track-Changes-corruption handling. Word (Office.js) and
Google Docs are the next two adapters.
