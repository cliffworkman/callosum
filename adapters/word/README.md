# callosum — Microsoft Word add-in (Office.js), SP1

Cite while you write in **desktop Microsoft Word** (Windows/Mac), backed by your local callosum library. Like the
LibreOffice adapter, this is a thin *field-placer* — it never formats citations itself; it searches your library
and inserts what callosum's citation engine renders. **Everything stays on your machine** (see *How it works*).

> **SP2 (this version)** ships cite-while-you-write: **search your library → insert a live citation**, and a
> **Refresh** that re-renders + renumbers every citation in document order and rebuilds the bibliography (via
> `/citations/render-document` — numeric styles renumber `[1][2][3]` by position; author-date disambiguates).
> Suggest (relevance-from-the-sentence) / one-click style switching / flatten-to-static land in SP3.

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
Open Word → **Home → Callosum → Show Citations**. In the task pane: pick a citation **style**, type an
author/title/year, and click a result — a **live** citation is inserted at your cursor (a Content Control carrying
the work's CSL-JSON). Click **Refresh / renumber + bibliography** after edits or moves to re-render every citation
in document order and rebuild the **References** block at the end of the document. (callosum must be running in
HTTPS mode for the task pane to reach it.)

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

## Limitations (SP2)
One work per citation (no grouped cites / page-locators yet); no Suggest (relevance-from-the-sentence) /
one-click style-switch / flatten-to-static yet (SP3); the bibliography lives at the document end; **desktop Word
only**; requires the HTTPS run-mode + the trusted dev cert. Word-on-the-web + Google Docs ride a future
authenticated relay.

> **Verification note:** there is no headless Word, so the in-Word behavior of the Office.js parts
> (`taskpane.js`) is **not exercised by an automated test** (nor, currently, by the maintainer — it ships
> best-effort-correct per the Office.js docs). The **pure logic** (`taskpane_core.js`: tag encode/decode, the
> render-document request/response mapping) is unit-tested with `node --test`, and the `/citations/render-document`
> contract it calls is covered by the Python suite. Treat the in-Word flow as untested until you run it in Word.
