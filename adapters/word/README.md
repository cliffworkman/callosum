# callosum — Microsoft Word add-in (Office.js), SP1

Cite while you write in **desktop Microsoft Word** (Windows/Mac), backed by your local callosum library. Like the
LibreOffice adapter, this is a thin *field-placer* — it never formats citations itself; it searches your library
and inserts what callosum's citation engine renders. **Everything stays on your machine** (see *How it works*).

> **SP3 (this version)** completes Word parity: **search → insert a live citation**, **Suggest** citations from the
> sentence you're writing (relevance-from-the-sentence, with stance + a quote), **Refresh** (re-render + renumber
> every citation in document order + rebuild the bibliography), a **one-click whole-document style switch** (the
> style dropdown re-renders everything + is remembered per document), and **Flatten** (live → static text). Built
> on `/papers/export`, `/citations/render-document`, `/citations/suggest`, `/citations/styles` — all local.

## Why the setup is different from LibreOffice
A Word add-in is a **web page** that runs inside Word, and Office requires it to be served over **HTTPS** — it
**cannot reach `http://localhost`**. So callosum serves the add-in over HTTPS *on your machine*, same-origin with
its API: nothing leaves your computer, but you trust a local certificate once. **Desktop Word only** —
Word-on-the-web runs in a cloud sandbox that can't reach your local library (that needs the future relay).

## One-time setup
1. **Trust a local certificate** (so Word accepts `https://localhost`):
   ```
   npx office-addin-dev-certs install
   ```
   (Run from anywhere; installs a local CA into your OS trust store. Run via `npx` — it is not a committed
   dependency.)
2. **Run callosum over HTTPS** on port 8443:
   ```
   python tools/run_https.py
   ```
   Then open the app at **https://localhost:8443** (the same trusted cert → no browser warning). HTTP on :8080
   still works for normal use; HTTPS is only needed while using the Word add-in.
3. **Sideload the manifest** into Word:
   - In callosum: **Settings → Microsoft Word add-in → Download manifest** (saves `manifest.xml`), or grab it from
     `adapters/word/manifest.xml` (Settings → **Open add-in folder**).
   - **Windows:** put `manifest.xml` in a folder, then in Word: **File → Options → Trust Center → Trust Center
     Settings → Trusted Add-in Catalogs**, add that folder's path, tick *Show in Menu*, restart Word. Then
     **Home → Add-ins → (Shared Folder) → Callosum Citations**.
   - **Mac:** copy `manifest.xml` to `~/Library/Containers/com.microsoft.Word/Data/Documents/wef/` (create it if
     needed), restart Word, then **Home → Add-ins → Callosum Citations**.

## Use
Open Word → **Home → Callosum → Show Citations**. In the task pane (callosum must be running in HTTPS mode):

- **Insert by search** — pick a citation **style**, type an author/title/year, click a result → a **live** citation
  is inserted at the cursor (a Content Control carrying the work's CSL-JSON).
- **Suggest from the sentence** — place the cursor in (or select) the sentence you're writing, click **Suggest from
  the sentence** → Callosum ranks **your library** by relevance and shows candidates with **stance** (supports /
  contrasts / mentions) + a **quote** (the reason); pick one to insert *after* the sentence. *(The first run loads
  the local relevance + stance models, so it can take a few seconds.)*
- **Refresh / renumber + bibliography** — re-render every citation in document order + rebuild the **References**
  block at the document end (run after edits/moves; numeric styles renumber by position).
- **Citation style** — changing the dropdown re-renders the whole document in the new style (the choice is
  remembered per document).
- **Flatten to static text** — convert the live citation + bibliography fields to plain text for hand-off
  (two-click confirm; **one-way**).

## How it works (for the curious)
The task pane is served by callosum at `https://localhost:8443/integrations/word/taskpane.html` and its API calls
(`/papers?q=`, `/papers/export`, `/citations/render-document`) are **same-origin** — so they reach your local
library directly, with **no egress** and no CORS exception. Each citation is a Word **Content Control** whose
`.tag` carries the cited work's CSL-JSON (base64) — the Zotero/LibreOffice embedded-CSL-JSON pattern. **Refresh**
scans those controls **in document order**, POSTs them to `/citations/render-document`, and writes back the
position-aware in-text + a managed **References** Content Control (tagged `CALLOSUM_BIBLIOGRAPHY`) at the document
end. The only external load is **office.js** from Microsoft's CDN: that is the Office platform SDK every add-in
must load (it cannot use Subresource Integrity because Microsoft updates it in place); it is not callosum sending
your data anywhere. All formatting happens in callosum's bundled citeproc engine, so the output matches the in-app
"Cite as…" and the LibreOffice adapter.

## Credit
The live-field / embedded-CSL-JSON cite design follows the **Zotero `CSL_CITATION` field convention** (reused as a
*pattern*, not code). callosum's rendering is built on **citeproc-js** + the **CSL** project — see the project's
`THIRD-PARTY-NOTICES.md`. **office.js** is Microsoft's Office Add-ins SDK.

## Limitations (SP3)
One work per citation (no grouped cites / page-locators yet); the bibliography lives at the document end; Suggest
covers papers **already in your library** (beyond-library discovery is a separate track); **desktop Word only**;
requires the HTTPS run-mode + the trusted dev cert. Word-on-the-web + Google Docs ride a future authenticated relay.

> **Verification note:** there is no headless Word, so the in-Word behavior of the Office.js parts
> (`taskpane.js`) is **not exercised by an automated test** (nor, currently, by the maintainer — it ships
> best-effort-correct per the Office.js docs). The **pure logic** (`taskpane_core.js`: tag encode/decode, the
> render-document request/response mapping) is unit-tested with `node --test`, and the `/citations/render-document`
> contract it calls is covered by the Python suite. Treat the in-Word flow as untested until you run it in Word.
