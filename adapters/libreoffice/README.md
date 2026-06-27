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

1. **Add citation…** — **search your library** (author / title / year), pick a paper from the list, and it's
   inserted at the cursor as a live, formatted citation. The everyday cite action — no paper ids to remember.
2. **Suggest citation** — **select (highlight)** the sentence you're writing (or place the cursor in it): callosum
   ranks **your library** by relevance to that sentence and shows a pick-list — each row gives the paper's **stance**
   (supports / contrasts / mentions the claim), a **match** score, and a **quote** preview (the evidence). Pick one
   and it inserts right after your sentence. Ranked by relevance, not citation count; nothing auto-inserts.
   *(The first run loads the local relevance + stance models, so it can take a few seconds.)*
3. **Refresh / renumber + bibliography** — re-render every citation and rebuild the bibliography (run after edits, or
   after moving citations — numeric styles renumber by position).
4. **Citation style…** — pick a CSL style id (`apa`, `ieee`, `nature`, `modern-language-association`,
   `chicago-author-date`, `chicago-notes-bibliography`, `harvard-cite-them-right`) and a locale (`en-US`/`en-GB`);
   the whole document re-renders. The choice is saved in the document.
5. **Flatten to static text** — convert the live citation fields to plain text for hand-off (e.g. journal
   submission). **One-way:** after flattening, the citations no longer update.
6. **Server URL…** — point the plugin at callosum if you run it on a non-default port (stored in `~/.callosum/`).

(The macro names behind these — `CallosumAddCitation`, `CallosumSuggestCitations`, `CallosumRefresh`,
`CallosumSetStyle`, `CallosumFlatten`, `CallosumInsertCitation` (by id), `CallosumSetServerUrl` — are also runnable
from the Python macro dialog if you installed by hand.)

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
Insert is by paper id, or by relevance via **Suggest** (a name/title search picker comes later); Suggest covers
papers **already in your library** (finding relevant papers you don't yet have is the next stage), shows a
truncated quote per row (read the full evidence in callosum's in-app **Cite** panel), and inserts a single work;
single work per citation (no grouped cites or page-locators yet); the bibliography lives at the document end;
in-text styles only (footnote/note styles later); no Track-Changes-corruption handling. Word (Office.js) and
Google Docs are the next two adapters.
