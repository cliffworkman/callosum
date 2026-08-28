# callosum — Microsoft Word add-in (Office.js)

Cite while you write in **desktop Microsoft Word** (Windows/Mac), backed by your local callosum library. Like the
LibreOffice adapter, this is a thin *field-placer* — it never formats citations itself; it searches your library
and inserts what callosum's citation engine renders. **Everything stays on your machine** (see *How it works*).

> **SP3** completed desktop Word parity: **search → insert a live citation**, **Suggest** citations from the
> sentence you're writing (relevance-from-the-sentence, with stance + a quote), **Refresh** (re-render + renumber
> every citation in document order + rebuild the bibliography), a **one-click whole-document style switch** (the
> style dropdown re-renders everything + is remembered per document), and **Flatten** (live → static text). Built
> on `/papers/export`, `/citations/render-document`, `/citations/suggest`, `/citations/styles` — all local.
> **SP4** adds **Word on the web** (see below) — the identical task pane, reached through the same relay tunnel
> the Google Docs add-on already uses, since Word-on-the-web can't reach your machine directly. **Inc 509** adds
> a real citation composer: **grouped citations** (combine several works into one), per-work **locator/label/
> prefix/suffix/suppress-author**, and **Edit/Delete citation at cursor** — closing the P0 gap named in
> callosum's LibreOffice-adapter parity roadmap.

## Why the setup is different from LibreOffice
A Word add-in is a **web page** that runs inside Word, and Office requires it to be served over **HTTPS** — it
**cannot reach `http://localhost`**. On **desktop**, callosum serves the add-in over HTTPS *on your machine*,
same-origin with its API: nothing leaves your computer, but you trust a local certificate once. **Word-on-the-web
runs in Microsoft's cloud and can't reach your machine at all** — that's what the relay in "Word on the web"
below is for (the same tunnel `adapters/googledocs/` already uses, just relaying more than one add-in's assets).

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
   - **Windows — corrected 2026-08-28 (live-verified; the Trust Center's "Catalog Url" field genuinely rejects a
     bare local path — confirmed against Microsoft's own current docs, not just this project's earlier
     assumption):** Word's Trusted Add-in Catalogs needs a **network share path**, not a plain `C:\...` folder
     path, even for a folder on your own machine:
     1. In File Explorer, right-click the `adapters/word` folder (containing `manifest.xml`) → **Properties** →
        **Sharing** tab → **Share…** button.
     2. In the *Network access* dialog, add yourself with **Read/Write** permission → **Share**. Note the exact
        network path shown (e.g. `\\YOUR-PC-NAME\word`) — this is the value Word needs, not the local path.
     3. In Word: **File → Options → Trust Center → Trust Center Settings → Trusted Add-in Catalogs**, paste that
        `\\...` network path into **Catalog Url**, click **Add catalog**, tick **Show in Menu**, OK, OK. Close and
        reopen Word.
     4. **Home → Add-ins → Advanced** (not "Shared Folder" directly — that tab lives *inside* this dialog) →
        choose the **SHARED FOLDER** tab at the top of the Office Add-ins dialog → select **Callosum Citations** →
        **Add**.
   - **Mac:** copy `manifest.xml` to `~/Library/Containers/com.microsoft.Word/Data/Documents/wef/` (create it if
     needed), restart Word, then **Home → Add-ins → Callosum Citations**.

## Use
Open Word → **Home → Callosum → Show Citations**. In the task pane (callosum must be running in HTTPS mode):

- **Add works to a citation** — pick a citation **style**, search (or click **Suggest from the sentence** — see
  below) and click a result: it's added to the **citation you're building**, not inserted immediately, so several
  works can be combined into one grouped citation (e.g. `(Smith, 2020; Jones, 2021)`). Each added work gets its
  own optional **Options…** (⋯): a **locator** (page, chapter, figure, …) + value, **prefix**/**suffix** text, and
  mutually-exclusive **suppress author**/**author only**. Reorder with ↑/↓, remove with ✕.
- **Insert citation** — once the assembly has at least one work, inserts it as a **live** citation (a Content
  Control carrying every work's CSL-JSON plus its own locator/prefix/suffix) at the cursor.
- **Suggest from the sentence** — place the cursor in (or select) the sentence you're writing, click **Suggest from
  the sentence** → Callosum ranks **your library** by relevance and shows candidates with **stance** (supports /
  contrasts / mentions) + a **quote** (the reason); pick one to add to the assembly. *(The first run loads the
  local relevance + stance models, so it can take a few seconds.)*
- **Edit citation at cursor** — place the cursor inside an existing Callosum citation and click this to reopen the
  composer pre-populated with its works/locators; **Insert citation** becomes **Update citation**.
- **Delete citation at cursor** — fully removes the citation at the cursor (unlike Flatten, this drops it — no
  static text is kept).
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
`.tag` carries **one or more** cited works' CSL-JSON, each with its own optional locator/label/prefix/suffix/
suppress-author/author-only (base64) — the Zotero/LibreOffice embedded-CSL-JSON pattern, extended (inc 509) the
same way LibreOffice's own composer already was. **Refresh**
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

## Word on the web (SP4)

Word-on-the-web runs in Microsoft's cloud and can never reach `https://localhost:8443` — the desktop setup above
doesn't apply. Instead, this same task pane rides the **same cloudflared relay the Google Docs add-on already
uses** (`adapters/googledocs/`), extended to also forward the task-pane's own static files (Office itself has to
fetch those from somewhere reachable, since Word-on-the-web can't load them from your machine).

**One-time setup** (skip if you've already done this for Google Docs — it's the same tunnel):
1. Follow `adapters/googledocs/README.md`'s tunnel setup (the Quick Tunnel mode works too, but the URL changes
   every restart — a **named tunnel** is worth it if you'll use this regularly). You already need this for the
   Google Docs add-on to work, so if that's set up, you're done with this step.
2. **callosum:** Settings → **Remote access** → turn it **ON**, copy the access token.
3. **Sideload the web manifest:** Settings → Microsoft Word add-in (web) → **Download web manifest**, then in
   Word on the web: the ribbon's **Add-ins** → **Upload My Add-in** → pick the downloaded
   `callosum-word-manifest-web.xml`.
4. **Connect:** open the task pane (**Home → Callosum → Show Citations**) — since it's now loading from the
   tunnel's own address, a small **Access token** field appears at the top. Paste your token → **Save token**.
   (Saved per-browser via `localStorage`, scoped to the tunnel's own origin — separate from anything you've
   entered for the main app or the Google Docs add-on.)

Everything else — search/insert, Suggest, Refresh (true document-order scanning, unchanged from desktop), style
switch, Flatten — works identically to desktop; every fetch just carries the Bearer token automatically once
saved. The task-pane files themselves (HTML/JS/CSS/icon) carry no library data, so relaying them through the
tunnel needs no token — only your `/papers`, `/citations/*` calls do, exactly like the Google Docs add-on.

## Limitations
The bibliography lives at the document end (no chapter/section-scoped bibliographies yet — see the LibreOffice
adapter for that, still Word/Docs-only work); no native footnote/endnote placement yet (every citation is
in-text); Suggest covers papers **already in your library** (beyond-library discovery is a separate track);
desktop requires the HTTPS run-mode + the trusted dev cert. Word-on-the-web needs the relay above; Google Docs
has its own adapter (`adapters/googledocs/`).

Existing **Mendeley Cite** and **EndNote Cite While You Write** fields are not converted. Their vendors document
the outer Word mechanism (content controls for Mendeley Cite; `ADDIN EN.CITE` fields for EndNote), but not a
complete, versioned payload contract that Callosum could safely rewrite without risking citation data. Keep those
live fields under their originating tool. Vendor-supported flatten/remove-field-code workflows create static text
on a document copy; they are not editable citation migration. The evidence boundary and requirements for revisiting
it are recorded in `.claude/docs/research/2026-08-21_word_citation_migration_formats.md`.

> **Verification note:** there is no headless Word, so the in-Word behavior of the Office.js parts
> (`taskpane.js`) is **not exercised by an automated test** (nor, currently, by the maintainer — it ships
> best-effort-correct per the Office.js docs). The **pure logic** (`taskpane_core.js`: tag encode/decode, the
> render-document request/response mapping) is unit-tested with `node --test`, and the `/citations/render-document`
> contract it calls is covered by the Python suite. Treat the in-Word flow as untested until you run it in Word.
