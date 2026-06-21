# callosum — LibreOffice citation adapter (v1)

Cite-while-you-write in **LibreOffice Writer**, backed by callosum's citation engine. The adapter is a thin
*field-placer*: it never formats citations itself — it places live fields, reads the full ordered citation set out
of your document, and writes back the in-text citations + bibliography that callosum renders (with correct numeric
renumbering and author-date disambiguation). Everything is **local** — the macro talks only to your callosum
server on `127.0.0.1`.

This is **v1**: a drop-in Python macro (the `.oxt` extension with a toolbar comes later). It covers the core loop —
insert, refresh/restyle/renumber, bibliography, and flatten.

## Prerequisites
- **LibreOffice** with its bundled Python (any recent 7.x/24.x/25.x).
- **callosum running** locally: from the project root, `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`.
  (If you run callosum on a different port, edit `DEFAULT_BASE` near the top of `callosum_cite.py`.)

## Install
Copy `callosum_cite.py` into your LibreOffice user **Scripts/python** folder, creating it if needed:

| OS | Folder |
|---|---|
| Windows | `%APPDATA%\LibreOffice\4\user\Scripts\python\` |
| macOS | `~/Library/Application Support/LibreOffice/4/user/Scripts/python/` |
| Linux | `~/.config/libreoffice/4/user/Scripts/python/` |

Restart LibreOffice (or just reopen the macro dialog). The four macros then appear under
**Tools → Macros → Organize Macros → Python → My Macros → callosum_cite**. For one-click use, bind them to toolbar
buttons via **Tools → Customize → Toolbars**.

## Use
1. Start callosum and open (or create) a document in Writer.
2. **CallosumInsertCitation** — enter a callosum **paper id** (the number in the library); a live citation field is
   inserted at the cursor and rendered immediately.
3. **CallosumRefresh** — re-render every citation in the document and rebuild the bibliography (run after edits, or
   after moving citations around — numeric styles renumber by position).
4. **CallosumSetStyle** — pick a CSL style id (`apa`, `ieee`, `nature`, `modern-language-association`,
   `chicago-author-date`, `chicago-notes-bibliography`, `harvard-cite-them-right`) and a locale (`en-US`/`en-GB`);
   the whole document re-renders in the new style. The choice is saved in the document.
5. **CallosumFlatten** — convert the live citation fields to plain static text for hand-off (e.g. journal
   submission). **One-way:** after flattening, the citations no longer update.

The bibliography is a managed block at the **end** of the document (under a "References" heading); it is rebuilt on
every refresh. Keep your citations above it.

## How it works (for the curious)
Each citation is a Writer **ReferenceMark** whose name carries the cited work's CSL-JSON payload (base64-encoded);
the visible marked text is the rendered citation. On refresh the adapter scans every such mark **in document
order**, POSTs the ordered set to callosum's `POST /citations/render-document`, and writes the position-aware
result back. All formatting happens in callosum's bundled citeproc engine, so the output is identical to the in-app
"Cite as…" and to the future Word/Google-Docs adapters.

## Credit
The live-field design — embedding the citation's CSL-JSON in the field and re-rendering the ordered set — follows
the **Zotero `CSL_CITATION` field convention** (reused as a *pattern*, not code). callosum's citation rendering is
built on **citeproc-js** and the **CSL** project; see the project's `THIRD-PARTY-NOTICES.md`.

## Limitations (v1)
Insert is by paper id (a library-search picker comes later); single work per citation (no grouped cites or
page-locators yet); the bibliography lives at the document end; in-text styles only (footnote/note styles later);
no Track-Changes-corruption handling. Word (Office.js) and Google Docs are the next two adapters.
