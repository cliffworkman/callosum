# callosum — Microsoft Word add-in (Office.js), SP1

Cite while you write in **desktop Microsoft Word** (Windows/Mac), backed by your local callosum library. Like the
LibreOffice adapter, this is a thin *field-placer* — it never formats citations itself; it searches your library
and inserts what callosum's citation engine renders. **Everything stays on your machine** (see *How it works*).

> **SP1 (this version)** ships the spine: **search your library → insert a formatted citation as static text** at
> the cursor. Live, updatable citations + whole-document renumbering/bibliography (the Zotero-style
> cite-while-you-write loop) land in SP2; Suggest / style switching / flatten in SP3.

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
author/title/year, and click a result — the formatted in-text citation is inserted at your cursor.
(callosum must be running in HTTPS mode for the task pane to reach it.)

## How it works (for the curious)
The task pane is served by callosum at `https://localhost:8443/integrations/word/taskpane.html` and its API calls
(`/papers?q=`, `/citations/render`) are **same-origin** — so they reach your local library directly, with **no
egress** and no CORS exception. The only external load is **office.js** from Microsoft's CDN: that is the Office
platform SDK every add-in must load (it cannot use Subresource Integrity because Microsoft updates it in place);
it is not callosum sending your data anywhere. Citation formatting happens in callosum's bundled citeproc engine,
so the output matches the in-app "Cite as…" and the LibreOffice adapter.

## Credit
The live-field / embedded-CSL-JSON cite design (coming in SP2) follows the **Zotero `CSL_CITATION` field
convention** (reused as a *pattern*, not code). callosum's rendering is built on **citeproc-js** + the **CSL**
project — see the project's `THIRD-PARTY-NOTICES.md`. **office.js** is Microsoft's Office Add-ins SDK.

## Limitations (SP1)
Inserts a single citation as **static text** (no live updating / renumbering / bibliography yet — that is SP2);
no Suggest / style-switch-whole-doc / flatten yet (SP3); **desktop Word only**; requires the HTTPS run-mode +
the trusted dev cert. Word-on-the-web + Google Docs ride a future authenticated relay.
